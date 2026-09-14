"""从显式审核的数据构图；支持本地离线查询和参数化 Neo4j 导入。"""
import argparse
import os
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
            dest=node(kind,target)
            key=identity('edge',source+relation+dest)
            metadata=row.get('method_provenance',row) if kind=='METHOD' else row
            edges[key]={'id':key,'source':source,'target':dest,'relation':relation,'label':REL_NAMES[relation],
                        'source_url':metadata['source_url'],'evidence':row['evidence'] if kind=='CATEGORY' else metadata.get('method_evidence',f"{row['name']}的示例投放要求：{row['method']}。"),
                        'region':row['region'],'provenance':metadata['provenance'],'review_status':metadata['review_status']}
    return {'nodes':list(nodes.values()),'edges':list(edges.values()),'region':'上海',
            'data_note':'人工编制的教学目录；不是网页模型抽取准确率的证明。'}


class KnowledgeBase:
    def __init__(self):
        self.rows=read_json(DATA/'catalog.json')
        self.aliases=read_json(DATA/'aliases.json')
        self.graph=build_graph(self.rows)

    def search(self,query='',category='',limit=30):
        category=self.aliases.get(category,category)
        if category and category not in CATEGORIES:
            raise ValueError('未知分类')
        q=clean_text(query)[:100]
        q=self.aliases.get(q,q)
        rows=[r for r in self.rows if (not category or r['category']==category)
              and (not q or q in r['name'] or r['name'] in q or q==r['category'])]
        rows.sort(key=lambda r:(r['name']!=q,len(r['name']),r['name']))
        return {'query':query,'normalized_query':q,'total':len(rows),'items':rows[:min(max(limit,1),150)],
                'notice':'按上海分类口径展示典型物态。未命中时不猜测类别，请补充材质、清洁程度和物品状态。'}

    def subgraph(self,query='',category='',limit=24):
        # query 和 category 任一筛选时保留目录事实及其投放要求。
        if query or category:
            selected={identity('ITEM',r['name']) for r in self.search(query,category,limit)['items']}
        else:
            # 四个类别均衡展示，避免首页只出现可回收物。
            selected=set()
            for c in CATEGORIES:
                selected.update(identity('ITEM',r['name']) for r in self.search('',c,max(1,limit//4))['items'])
        edges=[e for e in self.graph['edges'] if e['source'] in selected]
        ids={i for e in edges for i in (e['source'],e['target'])}
        return {'nodes':[n for n in self.graph['nodes'] if n['id'] in ids],'edges':edges,
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
    p=argparse.ArgumentParser();p.add_argument('--neo4j',action='store_true');args=p.parse_args()
    graph=build_graph(read_json(DATA/'catalog.json'))
    write_json(DATA/'graph.json',graph)
    if args.neo4j:
        result=import_neo4j(graph,os.getenv('NEO4J_URI','bolt://localhost:7687'),os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD',''),os.getenv('NEO4J_DATABASE','neo4j'))
        write_json(ROOT/'reports'/'neo4j_import.json',result);print(result)
    else:print(f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges")


if __name__=='__main__':main()
