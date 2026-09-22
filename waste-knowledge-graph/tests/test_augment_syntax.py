from wastekg.augment_syntax import sentence, build
from wastekg.common import write_jsonl, read_jsonl, read_json


def test_explicit_spans_and_length_guard():
    rows=sentence([('香蕉皮','ITEM'),'属于',('湿垃圾','CATEGORY'),'，应该',('丢进垃圾桶里','METHOD')],[(0,1,'BELONGS_TO'),(0,2,'DISPOSE_WITH')],'香蕉皮','mixed')
    assert len(rows)==2
    assert rows[1]['entities'][2]['text']=='丢进垃圾桶里'
    assert rows[1]['text'][rows[1]['entities'][2]['start']:rows[1]['entities'][2]['end']]=='丢进垃圾桶里'
    assert sentence(['字'*129,('纸','ITEM'),('湿垃圾','CATEGORY')],[(0,1,'BELONGS_TO')],'纸','long')==[]


def test_augmentation_keeps_items_disjoint_and_original_data(tmp_path):
    source=tmp_path/'source';source.mkdir()
    names={'train':['香蕉皮','苹果核'],'val':['茶叶渣','菜叶'],'test':['西瓜皮','鱼骨']}
    originals={}
    for split,items in names.items():
        rows=[sentence([(i,'ITEM'),'属于',('湿垃圾','CATEGORY')],[(0,1,'BELONGS_TO')],i,'base')[0] for i in items]
        write_jsonl(source/f'{split}.jsonl',rows)
        originals[split]=(source/f'{split}.jsonl').read_bytes()
    output=tmp_path/'output';build(source,output)
    manifest=read_json(output/'manifest.json')
    assert not any(manifest['item_overlap'].values())
    assert not any(manifest['sentence_overlap'].values())
    for split in names:
        assert (source/f'{split}.jsonl').read_bytes()==originals[split]
        for r in read_jsonl(output/f'{split}.jsonl'):
            assert all(e['text'] in names[split] for e in r['entities'] if e['type']=='ITEM')
            if r['template']=='retrain_parallel_scope':assert r['relation']=='BELONGS_TO'
    vocab=read_json(output/'vocab.json')
    assert '蕉' in vocab and '瓜' not in vocab
