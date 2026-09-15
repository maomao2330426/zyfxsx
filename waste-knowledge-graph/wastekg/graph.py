"""保留教学目录与外部标签的来源差异；支持离线查询及 Neo4j 导入。"""
import argparse
import os
import unicodedata
from collections import Counter
from .common import *


def build_graph(catalog):
    nodes, edges = {}, {}
    def node(kind,name):
        key=identity(kind,name)
        nodes[key]={'id':key,'name':name,'kind':kind}
        return key
    for row in catalog:
        source=node('ITEM',row['name'])
        for kind,relation,target in [('CATEGORY','BELONGS_TO',row['category']),('METHOD','DISPOSE_WITH',row['method'])]:
            if not target:
                continue
            dest=node(kind,target)
            key=identity('edge',source+relation+dest)
            metadata=row.get('method_provenance',row) if kind=='METHOD' else row
            edges[key]={'id':key,'source':source,'target':dest,'relation':relation,'label':REL_NAMES[relation],
                        'source_url':metadata['source_url'],'evidence':row['evidence'] if kind=='CATEGORY' else metadata.get('method_evidence',f"{row['name']}的示例投放要求：{row['method']}。"),
                        'region':row['region'],'provenance':metadata['provenance'],'review_status':metadata['review_status']}
    return {'nodes':list(nodes.values()),'edges':list(edges.values()),'region':'上海四分类名称映射',
            'data_note':'教学目录与外部来源标签分别标记；外部数据地区未核验，不自动构造投放方法。'}


def load_catalog(include_external=True):
    rows=read_json(DATA/'catalog.json')
    if not include_external:
        return [row for row in rows if row.get('provenance')!='external_dataset']
    path=DATA/'imported'/'catalog.json'
    if include_external and path.exists():
        existing={row['name'] for row in rows}
        rows=rows+[row for row in read_json(path) if row['name'] not in existing]
    return rows


class KnowledgeBase:
    def __init__(self,rows=None):
        self.rows=load_catalog() if rows is None else rows
        self.aliases=read_json(DATA/'aliases.json')
        self.graph=build_graph(self.rows)

    def search(self,query='',category='',limit=30,offset=0,scope='all'):
        if limit<1 or offset<0 or scope not in ('all','teaching','external'):
            raise ValueError('分页或来源筛选参数不合法')
        category=self.aliases.get(category,category)
        if category and category not in CATEGORIES:
            raise ValueError('未知分类')
        q=clean_text(unicodedata.normalize('NFKC',query))[:100]
        q=self.aliases.get(q,q)
        rows=[r for r in self.rows if (not category or r['category']==category)
              and (scope=='all' or (r.get('provenance')=='external_dataset')==(scope=='external'))
              and (not q or q in r['name'] or r['name'] in q or q==r['category'])]
        rows.sort(key=lambda r:(r['name']!=q,r.get('provenance')=='external_dataset',len(r['name']),r['name']))
        limit=min(limit,150)
        return {'query':query,'normalized_query':q,'total':len(rows),'items':rows[offset:offset+limit],
                'offset':offset,'next_offset':offset+limit if offset+limit<len(rows) else None,'scope':scope,
                'notice':'外部标签未经逐条审核；未命中时不猜测类别，请补充材质、清洁程度和物品状态。'}

    def subgraph(self,query='',category='',limit=24,scope='all',offset=None):
        if limit<1:
            raise ValueError('图谱节点数量必须为正数')
        limit=min(limit,80)
        # query 和 category 任一筛选时保留目录事实及其投放要求。
        page=self.search(query,category,limit,offset=offset or 0,scope=scope)
        if query or category or offset is not None:
            selected={identity('ITEM',r['name']) for r in page['items']}
        else:
            # 四个类别均衡展示，避免首页只出现可回收物。
            selected=set()
            groups=[self.search('',kind,limit,scope=scope)['items'] for kind in CATEGORIES]
            for position in range(limit):
                for group in groups:
                    if position<len(group) and len(selected)<limit:
                        selected.add(identity('ITEM',group[position]['name']))
        edges=[e for e in self.graph['edges'] if e['source'] in selected]
        ids={i for e in edges for i in (e['source'],e['target'])}
        return {'nodes':[n for n in self.graph['nodes'] if n['id'] in ids],'edges':edges,
                'total_items':page['total'],'item_offset':page['offset'],'next_offset':page['next_offset'],
                'total_nodes':len(self.graph['nodes']),'total_edges':len(self.graph['edges'])}


def import_neo4j(graph,uri,user,password,database='neo4j'):
    from neo4j import GraphDatabase
    if not password:
        raise ValueError('请设置 NEO4J_PASSWORD')
    with GraphDatabase.driver(uri,auth=(user,password)) as driver:
        driver.verify_connectivity()
        driver.execute_query('CREATE CONSTRAINT waste_entity_id IF NOT EXISTS FOR (n:WasteKGEntity) REQUIRE n.id IS UNIQUE', database_=database)
        nodes=graph['nodes'];edges=graph['edges']
        driver.execute_query('UNWIND $rows AS row MERGE (n:WasteKGEntity {id:row.id}) SET n.name=row.name, n.kind=row.kind, n.project=$project',
                             rows=nodes,project='wastekg_course',database_=database)
        # 关系名称来自固定白名单，不拼接输入数据中的标识符。
        for relation in ('BELONGS_TO','DISPOSE_WITH'):
            subset=[e for e in edges if e['relation']==relation]
            driver.execute_query(f'''UNWIND $rows AS row
                MATCH (a:WasteKGEntity {{id:row.source}}),(b:WasteKGEntity {{id:row.target}})
                MERGE (a)-[r:{relation}]->(b)
                SET r.id=row.id,r.source_url=row.source_url,r.evidence=row.evidence,
                    r.region=row.region,r.provenance=row.provenance,r.review_status=row.review_status''',rows=subset,database_=database)
        records,_,_=driver.execute_query('MATCH (n:WasteKGEntity {project:$project}) RETURN count(n) AS nodes',project='wastekg_course',database_=database)
        edge_records,_,_=driver.execute_query('MATCH (a:WasteKGEntity {project:$project})-[r]->(b:WasteKGEntity {project:$project}) RETURN count(r) AS edges',project='wastekg_course',database_=database)
        return {'nodes':records[0]['nodes'],'edges':edge_records[0]['edges'],'uri':uri,'database':database}


def main():
    p=argparse.ArgumentParser();p.add_argument('--neo4j',action='store_true')
    p.add_argument('--teaching-only',action='store_true');args=p.parse_args()
    graph=build_graph(load_catalog(include_external=not args.teaching_only))
    write_json(DATA/'graph.json',graph)
    if args.neo4j:
        result=import_neo4j(graph,os.getenv('NEO4J_URI','bolt://localhost:7687'),os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD',''),os.getenv('NEO4J_DATABASE','neo4j'))
        write_json(ROOT/'reports'/'neo4j_import.json',result);print(result)
    else:print(f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges")


if __name__=='__main__':main()
