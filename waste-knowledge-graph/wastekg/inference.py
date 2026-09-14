"""神经网络抽取和显式命名的词典基线，均不自动覆盖目录事实。"""
import argparse
import itertools
import numpy as np
from .common import *


class Extractor:
    def __init__(self, model_dir=None):
        from .models import BiLSTMCRF, BiGRUAttention, tf
        try:
            if tf.config.threading.get_intra_op_parallelism_threads()==0:
                tf.config.threading.set_intra_op_parallelism_threads(4)
                tf.config.threading.set_inter_op_parallelism_threads(2)
        except RuntimeError:
            pass  # 已初始化的调用方自行管理 TensorFlow 线程池。
        path=Path(model_dir or ROOT/'models')
        self.vocab=read_json(path/'vocab.json')
        self.ner=BiLSTMCRF(len(self.vocab));self.re=BiGRUAttention(len(self.vocab))
        dummy=np.ones((1,4),np.int32)
        self.ner(dummy);self.re((dummy,dummy,dummy))
        self.ner.load_weights(path/'ner.weights.h5');self.re.load_weights(path/'relation.weights.h5')

    def extract(self,text,threshold=.8):
        from .models import encode
        if not text.strip() or len(text)>MAX_LEN:
            raise ValueError('请输入 1 至 128 字的单句')
        x,_,lengths,_,_=encode([{'text':text}],self.vocab)
        path=self.ner.decode(self.ner(x).numpy(),lengths)[0]
        entities=spans([TAGS[i] for i in path],text)
        triples=[]
        pairs=[(a,b) for a,b in itertools.permutations(range(len(entities)),2)
               if entities[a]['type']=='ITEM' and entities[b]['type'] in {'CATEGORY','METHOD'}]
        if pairs:
            samples=[{'text':text,'entities':entities,'head':a,'tail':b} for a,b in pairs]
            x,_,_,hp,tp=encode(samples,self.vocab)
            batch_logits,batch_weights=self.re((x,hp,tp),return_attention=True)
            batch_logits,batch_weights=batch_logits.numpy(),batch_weights.numpy()
        for pair_index,(a,b) in enumerate(pairs):
            h,t=entities[a],entities[b]
            logits=batch_logits[pair_index];probs=np.exp(logits-logits.max());probs/=probs.sum()
            idx=int(probs.argmax());relation=RELATIONS[idx]
            expected='BELONGS_TO' if t['type']=='CATEGORY' else 'DISPOSE_WITH'
            if relation!=expected or float(probs[idx])<threshold:
                continue
            # 疑问、否定、假设上下文禁止作为肯定知识入库候选。
            if any(cue in text for cue in ['不是','不属于','不要','是否','吗','？','?','假如','假设','未说明']):
                continue
            triples.append({'head':h['text'],'relation':relation,'tail':t['text'],
                            'confidence':float(probs[idx]),'confidence_kind':'uncalibrated_relation_softmax',
                            'review_status':'pending','evidence':text,
                            'attention':[{'char':c,'weight':float(w)} for c,w in zip(text,batch_weights[pair_index])]})
        return {'mode':'neural','entities':entities,'triples':triples,'threshold':threshold,
                'note':'模型分数不是事实正确率；候选需要人工审核。'}


def baseline(text):
    if not text.strip() or len(text)>MAX_LEN:
        raise ValueError('请输入 1 至 128 字的单句')
    rows=read_json(DATA/'catalog.json')
    terms={r['name']:'ITEM' for r in rows}
    terms.update({c:'CATEGORY' for c in CATEGORIES})
    terms.update({r['method']:'METHOD' for r in rows})
    occupied=set();entities=[]
    for term,kind in sorted(terms.items(),key=lambda t:-len(t[0])):
        for match in re.finditer(re.escape(term),text):
            if not occupied.intersection(range(match.start(),match.end())):
                entities.append({'start':match.start(),'end':match.end(),'type':kind,'text':term})
                occupied.update(range(match.start(),match.end()))
    entities.sort(key=lambda e:e['start'])
    triples=[]
    if not any(c in text for c in ['不是','不要','不属于','是否','吗','？','?','假如','假设','未说明']):
        for h in entities:
            for t in entities:
                if h['type']=='ITEM' and t['type'] in {'CATEGORY','METHOD'}:
                    # 基线只处理一个物品和一个目标的明确陈述，拒绝多实体交叉配对。
                    if sum(e['type']=='ITEM' for e in entities)!=1 or sum(e['type']!='ITEM' for e in entities)!=1:
                        continue
                    if t['type']=='CATEGORY' and not any(w in text for w in ['属于','归入','类别是','包括','投入','进行分类']):
                        continue
                    triples.append({'head':h['text'],'relation':'BELONGS_TO' if t['type']=='CATEGORY' else 'DISPOSE_WITH',
                                    'tail':t['text'],'confidence':None,'review_status':'pending','evidence':text})
    return {'mode':'dictionary_baseline','entities':entities,'triples':triples,'note':'词典与规则基线，不是神经网络预测。'}


def main():
    p=argparse.ArgumentParser();p.add_argument('text',nargs='?');p.add_argument('--baseline',action='store_true')
    p.add_argument('--input',type=Path);p.add_argument('--output',type=Path,default=DATA/'candidates.jsonl')
    args=p.parse_args();model=None if args.baseline else Extractor()
    if args.input:
        candidates=[]
        processed=skipped=0
        for source in read_jsonl(args.input):
            for text in re.split(r'(?<=[。！？；])',source['text']):
                if not text.strip():continue
                if len(text)>MAX_LEN:
                    skipped+=1
                    continue
                processed+=1
                result=baseline(text) if args.baseline else model.extract(text)
                for triple in result['triples']:
                    triple.pop('attention',None)
                    triple.update({'source_url':source.get('source_url',''),'provenance':'model_candidate' if model else 'rule_candidate',
                                   'id':identity('candidate',text+triple['head']+triple['relation']+triple['tail'])})
                    candidates.append(triple)
        write_jsonl(args.output,candidates)
        write_json(args.output.with_suffix('.audit.json'),{'processed_sentences':processed,'skipped_over_length':skipped,'candidate_count':len(candidates)})
        print(f'候选三元组 {len(candidates)} 条，写入 {args.output}')
    elif args.text:
        print(json.dumps(baseline(args.text) if args.baseline else model.extract(args.text),ensure_ascii=False,indent=2))
    else: p.error('请提供 text 或 --input')


if __name__=='__main__':main()
