"""Add explicitly annotated synthetic syntax; preserve source item splits."""
import argparse
import hashlib
import random
from collections import Counter
from pathlib import Path
from .common import read_jsonl, write_jsonl, write_json, validate_sample, MAX_LEN


def sentence(parts, relations, group, template):
    text='';entities=[]
    for part in parts:
        if isinstance(part, tuple):
            name,kind=part
            entities.append({'text':name,'type':kind,'start':len(text),'end':len(text)+len(name)})
            text+=name
        else:text+=part
    if len(text)>MAX_LEN:return []
    rows=[]
    for head,tail,relation in relations:
        row={'text':text,'entities':entities,'head':head,'tail':tail,'relation':relation,
             'group':group,'template':'retrain_'+template,'provenance':'synthetic_syntax_augmentation',
             'annotation_note':'Explicit template spans; weak source categories; not human-reviewed natural text'}
        validate_sample(row);rows.append(row)
    return rows


def build(source,output):
    if output.exists():raise FileExistsError(output)
    data={s:read_jsonl(source/f'{s}.jsonl') for s in ('train','val','test')}
    groups={s:{r['group'] for r in rows} for s,rows in data.items()}
    assert all(not groups[a]&groups[b] for a,b in [('train','val'),('train','test'),('val','test')])
    added={};rng=random.Random(42)
    for split,rows in data.items():
        labels={}
        for r in rows:
            if r['relation']=='BELONGS_TO':
                labels.setdefault(r['group'],(r['entities'][r['head']]['text'],r['entities'][r['tail']]['text']))
        names=sorted(labels)
        new=[]
        for index,group in enumerate(names):
            item,category=labels[group];other,other_cat=labels[names[(index+1)%len(names)]]
            I=(item,'ITEM');C=(category,'CATEGORY');J=(other,'ITEM');D=(other_cat,'CATEGORY')
            action=['丢进','扔进','投入','放入','投放到'][index%5]+category+'桶里'
            M=(action,'METHOD')
            def add(parts,rels,template):new.extend(sentence(parts,rels,group,template))
            belongs=[(0,1,'BELONGS_TO')];method=[(0,1,'DISPOSE_WITH')]
            add([I,'是',C],belongs,'copula')
            add(['一个表面已经变色、需要单独分离处理的',I,'仍然属于',C,'。'],belongs,'modifier')
            add([I,['应该','应当','需要','必须','请'][index%5],M,'。'],method,'disposal')
            add([I,'属于',C,'，应该',M,'。'],[(0,1,'BELONGS_TO'),(0,2,'DISPOSE_WITH')],'category_and_method')
            add([I,['不应该','不能','不要'][index%3],M,'。'],[(0,1,'NO_RELATION')],'negative_method')
            add([I,'是否是',C,'？'],[(0,1,'NO_RELATION')],'copula_question')
            if index%4==0:
                add(['虽然之前和',J,'混放在一起，但在把其他物品分离后，剩下的',I,'仍然属于',C,'。'],
                    [(1,2,'BELONGS_TO'),(0,2,'NO_RELATION')],'background_scope')
                add([I,'和',J,'分别属于',C,'和',D,'。'],
                    [(0,2,'BELONGS_TO'),(1,3,'BELONGS_TO'),(0,3,'NO_RELATION'),(1,2,'NO_RELATION')],'parallel_scope')
        # Same-category parallel items both share the category; do not teach false negatives.
        new=[r for r in new if not (r['template']=='retrain_parallel_scope' and r['relation']=='NO_RELATION'
            and r['entities'][2]['text']==r['entities'][3]['text'])]
        seen={(r['text'],r['head'],r['tail'],r['relation']) for r in rows}
        fresh=[]
        for r in new:
            key=(r['text'],r['head'],r['tail'],r['relation'])
            if key not in seen:fresh.append(r);seen.add(key)
        added[split]=len(fresh);rows.extend(fresh);rng.shuffle(rows)
    output.mkdir(parents=True)
    for split,rows in data.items():write_jsonl(output/f'{split}.jsonl',rows)
    chars=sorted(set(''.join(r['text'] for r in data['train'])))
    write_json(output/'vocab.json',{'<PAD>':0,'<UNK>':1,**{c:i+2 for i,c in enumerate(chars)}})
    manifest={'seed':42,'source':str(source),'scope':'weak templates plus explicit synthetic syntax; not a natural-text benchmark',
        'split_policy':'preserve original canonical item groups; context items drawn only from same split',
        'source_hashes':{s:hashlib.sha256((source/f'{s}.jsonl').read_bytes()).hexdigest() for s in data},
        'added':added,'splits':{s:{'sentences':len(rows),'groups':len(groups[s]),'relations':dict(Counter(r['relation'] for r in rows))} for s,rows in data.items()}}
    # Exact sentence overlap and lexical item overlap across splits are audited separately.
    texts={s:{r['text'] for r in rows} for s,rows in data.items()}
    items={s:{e['text'] for r in rows for e in r['entities'] if e['type']=='ITEM'} for s,rows in data.items()}
    manifest['sentence_overlap']={a+'_'+b:len(texts[a]&texts[b]) for a,b in [('train','val'),('train','test'),('val','test')]}
    manifest['item_overlap']={a+'_'+b:len(items[a]&items[b]) for a,b in [('train','val'),('train','test'),('val','test')]}
    assert not any(manifest['sentence_overlap'].values())
    assert not any(manifest['item_overlap'].values())
    write_json(output/'manifest.json',manifest)
    print(manifest,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.source,a.output)
