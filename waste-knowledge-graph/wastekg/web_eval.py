"""直接从抓取文本建立小型人工标注网页评测集，不改写网页原句。"""
from .common import *
import argparse


def make_records():
    sources=read_jsonl(DATA/'processed'/'web_sentences.jsonl')
    specs=[
        ('可回收物：指废纸张', ['废纸张','废塑料','废玻璃制品','废金属','废织物'],['可回收物'],'可回收物'),
        ('有害垃圾：指废电池',['废电池','废灯管','废药品','废油漆'],['有害垃圾'],'有害垃圾'),
        ('湿垃圾：即易腐垃圾',['食材废料','剩菜剩饭','过期食品','瓜皮果核','花卉绿植','中药药渣'],['湿垃圾'],'湿垃圾'),
        ('有害垃圾 废镍镉电池',['废镍镉电池','废氧化汞电池'],['有害垃圾'],'有害垃圾'),
        ('盛放湿垃圾的废弃塑料袋',['废弃塑料袋'],['湿垃圾','干垃圾'],'干垃圾'),
    ]
    records=[]
    for prefix,items,categories,target in specs:
        source=next(s for s in sources if s['text'].startswith(prefix))
        text=source['text'];entities=[]
        for kind,names in [('ITEM',items),('CATEGORY',categories)]:
            for name in names:
                start=text.index(name)
                entities.append({'text':name,'start':start,'end':start+len(name),'type':kind})
        entities.sort(key=lambda e:e['start'])
        for item in items:
            record={'text':text,'entities':entities,'head':next(i for i,e in enumerate(entities) if e['text']==item),
                    'tail':next(i for i,e in enumerate(entities) if e['text']==target),'relation':'BELONGS_TO',
                    'group':'web:'+source['id'],'source_url':source['source_url'], 'provenance':'web_manual_annotation',
                    'annotation_note':'为课程演示编制的单人标注，未做双人一致性检验'}
            validate_sample(record);records.append(record)
    return records


def main():
    from .inference import Extractor
    from .train import evaluate,prf
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-dir',type=Path,default=ROOT/'models')
    parser.add_argument('--output',type=Path,default=ROOT/'reports'/'web_metrics.json')
    args=parser.parse_args()
    records=make_records()
    model=Extractor(args.model_dir);result=evaluate(model.ner,model.re,records,model.vocab)
    # NER 按唯一网页句子计数，关系评估按有向实体对计数。
    unique={r['text']:r for r in records}
    result['ner']=evaluate(model.ner,model.re,list(unique.values()),model.vocab)['ner']
    tp=predicted=gold=0;cases=[]
    for text in unique:
        g={(r['entities'][r['head']]['text'],r['relation'],r['entities'][r['tail']]['text']) for r in records if r['text']==text}
        out=model.extract(text)
        p={(r['head'],r['relation'],r['tail']) for r in out['triples']}
        tp+=len(g&p);predicted+=len(p);gold+=len(g)
        cases.append({'text':text,'gold':sorted(g),'predicted':sorted(p)})
    result.update({'unique_sentences':len(unique),'relation_pairs':len(records),
                   'scope':'small single-annotator web sample; not a representative benchmark',
                   'end_to_end':{**prf(tp,predicted,gold),'true_positive':tp,'predicted':predicted,'gold':gold},'cases':cases})
    result['model_name']=args.model_dir.name
    result['model_signature']=model_signature(args.model_dir)
    write_json(args.output,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
