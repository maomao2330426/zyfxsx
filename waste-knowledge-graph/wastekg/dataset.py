"""接入外部分类表，保留来源、隔离冲突并构建弱监督实验数据。"""
import argparse
import csv
import hashlib
import json
import os
import random
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse
from .common import DATA, CATEGORIES, MAX_LEN, read_json, write_json, write_jsonl, clean_text, validate_sample


def normalize(value):
    if not isinstance(value,str):
        raise ValueError('字段必须是文本')
    return clean_text(unicodedata.normalize('NFKC',value))


def read_records(path):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as handle:
            return list(csv.DictReader(handle))
    if path.suffix.lower()=='.jsonl':
        return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    raise ValueError('仅支持 CSV 或 JSONL')


def audit(records,existing,aliases):
    grouped=defaultdict(list)
    rejected=[]
    mapping={**{kind:kind for kind in CATEGORIES},**aliases}
    for number,record in enumerate(records,1):
        try:
            if not isinstance(record,dict):
                raise ValueError('记录必须是对象')
            name=normalize(record.get('name',''))
            category=normalize(record.get('category',''))
            canonical=aliases.get(name,name)
            category=mapping.get(category,category)
            source_url=normalize(record.get('url',''))
            parsed=urlparse(source_url)
            if not name or len(name)>60 or category not in CATEGORIES:
                raise ValueError('名称为空、过长或类别不在四分类范围')
            if parsed.scheme not in ('http','https') or not parsed.netloc:
                raise ValueError('缺少可追溯的 HTTP 来源')
            grouped[canonical].append({'name':canonical,'original_name':name,'category':category,
                'original_category':record['category'],'source_url':source_url,
                'source':normalize(record.get('source','外部数据集')),'source_record':number,
                'method':normalize(record.get('method',''))})
        except (ValueError,TypeError) as error:
            rejected.append({'record':number,'reason':str(error),'raw':record})
    old={normalize(row['name']):row for row in existing}
    accepted=[];conflicts=[];overlaps=[]
    for name,group in sorted(grouped.items()):
        categories={row['category'] for row in group}
        if len(categories)>1 or (name in old and old[name]['category'] not in categories):
            conflicts.append({'name':name,'existing_category':old.get(name,{}).get('category'),
                              'incoming':group,'reason':'同名物品分类冲突，未覆盖目录，未进入训练集'})
            continue
        if name in old:
            overlaps.append({'name':name,'records':group})
            continue
        row=group[0]
        accepted.append({**row,'method':row.get('method') or None,
            'note':'外部数据集的分类标签与投放方法，未逐条人工核验；未提供地区与原始描述。',
            'region':'来源地区未核验','provenance':'external_dataset','review_status':'source_labeled',
            'confidence':None,'evidence':f"来源数据第{row['source_record']}条：{row['original_name']} → {row['original_category']}。类别名称映射不代表地区规则已核验。",
            'source_records':[entry['source_record'] for entry in group]})
    summary={'raw_records':len(records),'accepted_items':len(accepted),'existing_matches':len(overlaps),
        'conflict_items':len(conflicts),'rejected_records':len(rejected),
        'duplicate_records':sum(len(group)-1 for group in grouped.values()),
        'categories':dict(Counter(row['category'] for row in accepted)),
        'raw_categories':dict(Counter(str(row.get('category')) for row in records if isinstance(row,dict))),
        'description_records':sum(bool(row.get('description')) for row in records if isinstance(row,dict)),
        'policy':'source_labeled reference data; not human-reviewed facts or natural NER annotations',
        'category_mapping':{key:value for key,value in mapping.items() if key!=value and value in CATEGORIES},
        'sources':sorted({row['source_url'] for row in accepted})}
    return accepted,{'summary':summary,'conflicts':conflicts,'rejected':rejected,'existing_matches':overlaps}


def training_data(rows,output,seed=42):
    rng=random.Random(seed)
    datasets={split:[] for split in ('train','val','test')}
    templates=[('{i}属于{t}。','BELONGS_TO'),('{i}应归入{t}。','BELONGS_TO'),
               ('分类表将{i}标为{t}。','BELONGS_TO'),('{i}不是{t}。','NO_RELATION'),
               ('{i}是否属于{t}？','NO_RELATION'),('假如{i}属于{t}，需要核对。','NO_RELATION')]
    skipped=0
    for category in CATEGORIES:
        group=sorted([row for row in rows if row['category']==category],key=lambda row:row['name'])
        if len(group)<3:
            raise ValueError('每个类别至少需要3个物品才能划分训练、验证与测试集')
        rng.shuffle(group)
        train_count=min(len(group)-2,max(1,int(len(group)*.7)))
        val_count=min(len(group)-train_count-1,max(1,int(len(group)*.15)))
        for position,row in enumerate(group):
            split='train' if position<train_count else 'val' if position<train_count+val_count else 'test'
            samples=[]
            for index,(template,relation) in enumerate(templates):
                target=rng.choice([kind for kind in CATEGORIES if kind!=category]) if index==3 else category
                samples.append((template.format(i=row['name'],t=target),target,'CATEGORY',relation,index))
            if row.get('method'):
                samples.append((f"投放{row['name']}时，需要{row['method']}。",row['method'],'METHOD','DISPOSE_WITH',6))
                samples.append((f"{row['name']}的投放要求是{row['method']}。",row['method'],'METHOD','DISPOSE_WITH',7))
            for text,target,kind,relation,index in samples:
                if len(text)>MAX_LEN:
                    skipped+=1
                    continue
                start=text.index(row['name']);target_start=text.rindex(target)
                sample={'text':text,'group':row['name'],'template':index,'head':0,'tail':1,'relation':relation,
                        'entities':[{'start':start,'end':start+len(row['name']),'text':row['name'],'type':'ITEM'},
                                    {'start':target_start,'end':target_start+len(target),'text':target,'type':kind}]}
                validate_sample(sample)
                sample.update({'provenance':'weak_template','source_url':row['source_url'],
                               'label_review_status':row['review_status']})
                datasets[split].append(sample)
    for split,samples in datasets.items():
        rng.shuffle(samples)
        write_jsonl(output/f'{split}.jsonl',samples)
    chars=sorted(set(''.join(sample['text'] for sample in datasets['train'])))
    write_json(output/'vocab.json',{'<PAD>':0,'<UNK>':1,**{char:index+2 for index,char in enumerate(chars)}})
    manifest={'seed':seed,'scope':'external labels plus teaching seeds; weak template benchmark, not natural text',
        'split_policy':'category-stratified, canonical item-disjoint; shared templates across splits',
        'skipped_long_sentences':skipped,'catalog_items':len(rows),
        'splits':{split:{'sentences':len(samples),'items':sorted({sample['group'] for sample in samples}),
                         'relations':dict(Counter(sample['relation'] for sample in samples))} for split,samples in datasets.items()}}
    write_json(output/'manifest.json',manifest)
    return manifest


def merge_main_catalog(additions,path=None):
    path=Path(path or DATA/'old'/'catalog.json')
    original=path.read_bytes()
    rows=json.loads(original.decode('utf-8-sig'))
    aliases=read_json(DATA/'aliases.json')
    combined={}
    for row in rows+additions:
        name=aliases.get(normalize(row['name']),normalize(row['name']))
        previous=combined.get(name)
        if previous and previous['category']!=row['category']:
            raise ValueError('主目录存在类别冲突，未合并：'+name)
        if not previous:
            combined[name]=row
        elif row.get('method') and not previous.get('method'):
            combined[name]={**previous,'method':row['method'],'note':row.get('note',previous.get('note'))}
    merged=list(combined.values())
    backup=path.with_name(path.stem+'.before_external_merge.json')
    if merged==rows:
        return {'merged':True,'added':0,'items':len(rows),'backup':backup.name if backup.exists() else None}
    if not backup.exists():
        with backup.open('xb') as handle:
            handle.write(original)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='\n',dir=path.parent,delete=False,suffix='.tmp') as handle:
            temporary=Path(handle.name)
            json.dump(merged,handle,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()
    return {'merged':True,'added':len(merged)-len(rows),'items':len(merged),'backup':backup.name}


def ingest(source,compare=None,output=None,training_output=None,merge=False):
    source=Path(source)
    records=read_records(source)
    if compare is not None and Counter(json.dumps(row,sort_keys=True,ensure_ascii=False) for row in records)!=Counter(json.dumps(row,sort_keys=True,ensure_ascii=False) for row in read_records(compare)):
        raise ValueError('CSV 与 JSONL 内容不一致，请先核对；未输出新目录')
    existing=[row for row in read_json(DATA/'old'/'catalog.json') if row.get('provenance')!='external_dataset']
    accepted,report=audit(records,existing,read_json(DATA/'aliases.json'))
    if not accepted:
        raise ValueError('没有可接入的新记录，请检查字段或冲突')
    output=Path(output or DATA/'old'/'imported')
    training_output=Path(training_output or DATA/'old'/'processed_external')
    conflicts={row['name'] for row in report['conflicts']}
    training_rows=[row for row in existing if normalize(row['name']) not in conflicts]+accepted
    manifest=training_data(training_rows,training_output)
    report['summary'].update({'input_file':source.name,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                              'compared_file':Path(compare).name if compare else None,
                              'formats_match':True if compare else None,'active_catalog_items':len(existing)+len(accepted),
                              'training_sentences':{key:value['sentences'] for key,value in manifest['splits'].items()}})
    write_json(output/'catalog.json',accepted)
    write_json(output/'audit.json',report)
    write_jsonl(output/'conflicts.jsonl',report['conflicts'])
    write_jsonl(output/'rejected.jsonl',report['rejected'])
    if merge:
        result=merge_main_catalog(accepted)
        report['summary']['main_catalog_merge']=result
        report['summary']['active_catalog_items']=result['items']
        write_json(output/'audit.json',report)
    return report['summary']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--compare',type=Path)
    parser.add_argument('--output',type=Path,default=DATA/'old'/'imported')
    parser.add_argument('--training-output',type=Path,default=DATA/'old'/'processed_external')
    parser.add_argument('--merge-catalog',action='store_true',help='备份并合并到data/catalog.json，可重复执行而不重复入库')
    args=parser.parse_args()
    try:
        print(json.dumps(ingest(args.source,args.compare,args.output,args.training_output,args.merge_catalog),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as error:
        parser.error(str(error))


if __name__=='__main__':main()
