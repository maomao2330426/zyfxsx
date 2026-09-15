import argparse
import random
import time
import platform
import hashlib
from collections import Counter
import numpy as np
import tensorflow as tf
from .common import *
from .models import BiLSTMCRF, BiGRUAttention, encode


def prf(tp, predicted, gold):
    precision = tp/predicted if predicted else 0.
    recall = tp/gold if gold else 0.
    return {'precision': precision, 'recall': recall, 'f1': 2*precision*recall/(precision+recall) if precision+recall else 0.}


def evaluate(ner, re_model, records, vocab):
    tp = pred_count = gold_count = 0
    cm = np.zeros((3,3), dtype=int)
    mistakes = []
    for off in range(0,len(records),64):
        batch = records[off:off+64]
        x,y,lengths,hp,tp_pos = encode(batch,vocab)
        paths = ner.decode(ner(x, training=False).numpy(), lengths)
        labels = re_model((x,hp,tp_pos), training=False).numpy().argmax(axis=-1)
        for s, path, pred in zip(batch,paths,labels):
            p = {(e['start'],e['end'],e['type']) for e in spans([TAGS[i] for i in path],s['text'])}
            g = {(e['start'],e['end'],e['type']) for e in s['entities']}
            tp += len(p & g)
            pred_count += len(p)
            gold_count += len(g)
            target = RELATIONS.index(s['relation'])
            cm[target,int(pred)] += 1
            if (p != g or pred != target) and len(mistakes)<30:
                mistakes.append({'text':s['text'],'gold_entities':sorted(g),'predicted_entities':sorted(p),
                                 'gold_relation':RELATIONS[target],'predicted_relation':RELATIONS[int(pred)]})
    per_class = {name: prf(int(cm[i,i]),int(cm[:,i].sum()),int(cm[i,:].sum())) for i,name in enumerate(RELATIONS)}
    return {'ner': {**prf(tp,pred_count,gold_count), 'true_positive':tp,'predicted':pred_count,'gold':gold_count},
            'relation': {'accuracy':float(np.trace(cm)/cm.sum()),'macro_f1':float(np.mean([v['f1'] for v in per_class.values()])),
                         'per_class':per_class,'confusion_matrix':cm.tolist(),'label_order':RELATIONS,
                         'evaluation': 'gold entity spans; not end-to-end triple score'}, 'errors':mistakes}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs',type=int,default=18)
    p.add_argument('--batch-size',type=int,default=48)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--data-dir',type=Path,default=DATA/'processed')
    p.add_argument('--output',type=Path,default=ROOT/'models')
    p.add_argument('--balance-relations',action='store_true')
    args=p.parse_args()
    if args.epochs<1 or args.batch_size<1:
        p.error('epochs 和 batch-size 必须为正数')
    tf.keras.utils.set_random_seed(args.seed)
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    vocab = read_json(args.data_dir/'vocab.json')
    train,val,test = [read_jsonl(args.data_dir/f'{s}.jsonl') for s in ('train','val','test')]
    sets = [set(s['group'] for s in data) for data in (train,val,test)]
    assert not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2]), '实体分组存在泄漏'
    for data in (train,val,test):
        if not data:
            p.error('训练、验证与测试集均不能为空')
        for s in data: validate_sample(s)
    counts=Counter(sample['relation'] for sample in train)
    class_weights=np.ones(len(RELATIONS),dtype=np.float32)
    if args.balance_relations:
        class_weights=np.array([np.sqrt(len(train)/(len(RELATIONS)*max(1,counts[label]))) for label in RELATIONS],np.float32)
        class_weights/=sum(class_weights[index]*counts[label] for index,label in enumerate(RELATIONS))/len(train)
    ner,re_model = BiLSTMCRF(len(vocab)), BiGRUAttention(len(vocab))
    x,y,lengths,hp,tp = encode(train[:2],vocab)
    ner(x);re_model((x,hp,tp))
    opt_ner,opt_re = tf.keras.optimizers.Adam(.003,clipnorm=5),tf.keras.optimizers.Adam(.003,clipnorm=5)

    @tf.function(input_signature=[tf.TensorSpec([None,None],tf.int32),tf.TensorSpec([None,None],tf.int32),
                                  tf.TensorSpec([None],tf.int32),tf.TensorSpec([None,None],tf.int32),
                                  tf.TensorSpec([None,None],tf.int32),tf.TensorSpec([None],tf.int32)])
    def step(x,y,lengths,hp,tp,rel):
        with tf.GradientTape() as tape:
            nloss=ner.nll(ner(x,training=True),y,lengths)
        grads=tape.gradient(nloss,ner.trainable_variables)
        opt_ner.apply_gradients(zip(grads,ner.trainable_variables))
        with tf.GradientTape() as tape:
            logits=re_model((x,hp,tp),training=True)
            losses=tf.keras.losses.sparse_categorical_crossentropy(rel,logits,from_logits=True)
            rloss=tf.reduce_mean(losses*tf.gather(class_weights,rel))
        grads=tape.gradient(rloss,re_model.trainable_variables)
        opt_re.apply_gradients(zip(grads,re_model.trainable_variables))
        return nloss,rloss

    args.output.mkdir(parents=True,exist_ok=True)
    write_json(args.output/'vocab.json',vocab)
    history=[];best=-1.; started=time.perf_counter();rng=random.Random(args.seed)
    for epoch in range(1,args.epochs+1):
        rng.shuffle(train)
        losses=[]
        for off in range(0,len(train),args.batch_size):
            batch=train[off:off+args.batch_size]
            x,y,lengths,hp,tp=encode(batch,vocab)
            rel=np.array([RELATIONS.index(s['relation']) for s in batch],np.int32)
            nloss,rloss=step(x,y,lengths,hp,tp,rel)
            losses.append([float(nloss),float(rloss)])
        metrics=evaluate(ner,re_model,val,vocab)
        score=(metrics['ner']['f1']+metrics['relation']['macro_f1'])/2
        row={'epoch':epoch,'ner_loss':float(np.mean(losses,axis=0)[0]),'relation_loss':float(np.mean(losses,axis=0)[1]),
             'val_ner_f1':metrics['ner']['f1'],'val_relation_macro_f1':metrics['relation']['macro_f1']}
        history.append(row)
        print(json.dumps(row),flush=True)
        if score>best:
            best=score;best_epoch=epoch
            ner.save_weights(args.output/'ner.weights.h5')
            re_model.save_weights(args.output/'relation.weights.h5')
        write_json(args.output/'history.json',history)
    ner.load_weights(args.output/'ner.weights.h5'); re_model.load_weights(args.output/'relation.weights.h5')
    result=evaluate(ner,re_model,test,vocab)
    result.update({'best_epoch':best_epoch,'epochs':args.epochs,'seed':args.seed,'seconds':time.perf_counter()-started,
                   'tensorflow':tf.__version__,'python':platform.python_version(),
                   'dataset':{'train':len(train),'val':len(val),'test':len(test)},
                   'limitation':'模板生成语料，按物品隔离；只验证教学流程，不代表自然网页泛化性能。'})
    manifest_path=args.data_dir/'manifest.json'
    result['data_provenance']={'directory':args.data_dir.name,
        'manifest':read_json(manifest_path) if manifest_path.exists() else None,
        'split_sha256':{split:hashlib.sha256((args.data_dir/f'{split}.jsonl').read_bytes()).hexdigest() for split in ('train','val','test')},
        'relation_class_weights':dict(zip(RELATIONS,class_weights.tolist()))}
    result['model_signature']=model_signature(args.output)
    write_json(args.output/'metrics.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
