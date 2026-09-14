"""人工撰写的改写开发挑战集；曾用于指导数据增强方向。"""
from .common import *
from .prepare import example

CASES=[
 ('吃完留下的香蕉皮，分类投放时算作湿垃圾。','香蕉皮','湿垃圾','CATEGORY','BELONGS_TO'),
 ('纸箱要是没有被弄脏，就可以作为可回收物处理。','纸箱','可回收物','CATEGORY','BELONGS_TO'),
 ('这支含汞温度计已经坏了，应交到有害垃圾收集处。','含汞温度计','有害垃圾','CATEGORY','BELONGS_TO'),
 ('用过的纸巾即使看着干净，也应该放进干垃圾桶。','用过的纸巾','干垃圾','CATEGORY','BELONGS_TO'),
 ('把矿泉水瓶扔进可回收物桶之前，要先倒空。','矿泉水瓶','可回收物','CATEGORY','BELONGS_TO'),
 ('今天整理出了旧毛衣，可以投放到可回收物收集点。','旧毛衣','可回收物','CATEGORY','BELONGS_TO'),
 ('茶叶渣沥水后归到湿垃圾这一类。','茶叶渣','湿垃圾','CATEGORY','BELONGS_TO'),
 ('胶带既不能回收也不易腐烂，按干垃圾处理即可。','胶带','干垃圾','CATEGORY','BELONGS_TO'),
 ('废油漆不能乱倒，其分类应为有害垃圾。','废油漆','有害垃圾','CATEGORY','BELONGS_TO'),
 ('处理苹果皮，请先沥干水分并去除包装。','苹果皮','沥干水分并去除包装','METHOD','DISPOSE_WITH'),
 ('为了避免划伤，玻璃杯在丢弃前需包裹尖锐边角。','玻璃杯','包裹尖锐边角','METHOD','DISPOSE_WITH'),
 ('旧床单若准备回收，应尽量保持清洁干燥。','旧床单','保持清洁干燥','METHOD','DISPOSE_WITH'),
 ('将过期药片交给收集点时，请连同包装单独投放。','过期药片','连同包装单独投放','METHOD','DISPOSE_WITH'),
 ('废荧光灯管请勿敲碎，需要保持完整并单独投放。','废荧光灯管','保持完整并单独投放','METHOD','DISPOSE_WITH'),
 ('有人认为香蕉皮可以放入干垃圾，实际并非如此。','香蕉皮','干垃圾','CATEGORY','NO_RELATION'),
 ('我不确定玻璃瓶是不是可回收物。','玻璃瓶','可回收物','CATEGORY','NO_RELATION'),
 ('这页只提到猫砂和湿垃圾两个词，并没有给出分类结论。','猫砂','湿垃圾','CATEGORY','NO_RELATION'),
 ('若把过期药片视为干垃圾，将造成分类错误。','过期药片','干垃圾','CATEGORY','NO_RELATION'),
 ('旧书能不能算作有害垃圾呢？','旧书','有害垃圾','CATEGORY','NO_RELATION'),
 ('老师让大家讨论：鱼骨的类别到底是不是干垃圾。','鱼骨','干垃圾','CATEGORY','NO_RELATION'),
]


def main():
    from .inference import Extractor,baseline
    from .train import evaluate,prf
    records=[example(*case,template='challenge') for case in CASES]
    for r in records:r['provenance']='authored_paraphrase_challenge'
    write_jsonl(DATA/'processed'/'challenge.jsonl',records)
    model=Extractor();metrics=evaluate(model.ner,model.re,records,model.vocab)
    output=[];counts={'neural':[0,0,0],'baseline':[0,0,0]}
    for s in records:
        gold=set() if s['relation']=='NO_RELATION' else {(s['entities'][0]['text'],s['relation'],s['entities'][1]['text'])}
        result={'text':s['text'],'gold':[list(x) for x in gold]}
        for mode in ['neural','baseline']:
            d=model.extract(s['text']) if mode=='neural' else baseline(s['text'])
            predicted={(t['head'],t['relation'],t['tail']) for t in d['triples']}
            result[mode]=[list(x) for x in predicted]
            counts[mode][0]+=len(predicted&gold);counts[mode][1]+=len(predicted);counts[mode][2]+=len(gold)
        output.append(result)
    metrics.update({'sentences':len(records),'scope':'authored development challenge; informed augmentation; not blind or web test',
                    'end_to_end':{mode:{**prf(*c),'true_positive':c[0],'predicted':c[1],'gold':c[2]} for mode,c in counts.items()},'cases':output})
    write_json(ROOT/'reports'/'challenge_metrics.json',metrics)
    print(json.dumps({k:v for k,v in metrics.items() if k not in ('cases','errors')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
