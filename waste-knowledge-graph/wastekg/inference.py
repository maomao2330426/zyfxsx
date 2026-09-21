"""神经网络抽取和显式命名的词典基线，均不自动覆盖目录事实。"""
import argparse
import itertools
import numpy as np
from .common import *
from .graph import load_catalog


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
    from .sentence_rules import extract_explicit
    return extract_explicit(text)


def assisted_extract(model,text):
    from .sentence_rules import combine
    return combine(text,model.extract(text))


def main():
    p=argparse.ArgumentParser();p.add_argument('text',nargs='?');p.add_argument('--baseline',action='store_true')
    p.add_argument('--input',type=Path);p.add_argument('--output',type=Path,default=DATA/'candidates.jsonl')
    p.add_argument('--model-dir',type=Path,default=ROOT/'models')
    args=p.parse_args();model=None if args.baseline else Extractor(args.model_dir)
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
