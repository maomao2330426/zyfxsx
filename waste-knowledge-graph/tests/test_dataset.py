import json
import pytest
from wastekg.common import DATA, read_json, read_jsonl, validate_sample
from wastekg.dataset import audit, ingest, read_records, training_data, merge_main_catalog
from wastekg.graph import KnowledgeBase, build_graph, load_catalog
from wastekg.qa import answer


def record(name='测试物品',category='厨余垃圾',**fields):
    return {'name':name,'category':category,'url':'https://example.org/dataset','source':'test',**fields}


def test_merged_source_is_complete_and_has_methods():
    records=read_records(DATA/'garbage_cleaned_merged.jsonl')
    assert len(records)==3712
    assert all(r.get('method') and r['method'].strip() for r in records)


def test_normalization_deduplication_conflict_and_rejection():
    incoming=[record(' Ａ纸 '),record('A纸'),record('冲突物品'),record('冲突物品','其他垃圾'),
              record('竹签','可回收物'),record('',url=''),record('错误类别','建筑垃圾'),
              record('坏链接',url='javascript:alert(1)'),record(name=12)]
    aliases={'厨余垃圾':'湿垃圾','其他垃圾':'干垃圾'}
    accepted,report=audit(incoming,[{'name':'竹签','category':'干垃圾'}],aliases)
    assert [row['name'] for row in accepted]==['A纸']
    assert accepted[0]['category']=='湿垃圾'
    assert accepted[0]['source_records']==[1,2]
    assert accepted[0]['review_status']=='source_labeled'
    assert report['summary']['conflict_items']==2
    assert report['summary']['rejected_records']==4


def test_external_graph_does_not_invent_method_relationships():
    rows,_=audit([record()],[],{'厨余垃圾':'湿垃圾'})
    graph=build_graph(rows)
    assert len(graph['edges'])==1
    assert graph['edges'][0]['relation']=='BELONGS_TO'
    assert graph['edges'][0]['review_status']=='source_labeled'
    assert all(node['kind']!='METHOD' for node in graph['nodes'])


def test_ingestion_is_reproducible_and_preserves_source_files(tmp_path):
    source=DATA/'garbage_cleaned_merged.jsonl'
    before=(source.read_bytes(),(DATA/'old'/'catalog.json').read_bytes())
    outputs=tmp_path/'imported';training=tmp_path/'training'
    summary=ingest(source,None,outputs,training)
    first={path.name:path.read_bytes() for path in training.iterdir()}
    assert summary['formats_match'] is None
    assert summary['accepted_items']==3622
    assert summary['conflict_items']==1
    ingest(source,None,outputs,training)
    assert first=={path.name:path.read_bytes() for path in training.iterdir()}
    assert before==(source.read_bytes(),(DATA/'old'/'catalog.json').read_bytes())
    splits=[read_jsonl(training/f'{split}.jsonl') for split in ('train','val','test')]
    groups=[{row['group'] for row in samples} for samples in splits]
    assert not (groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2])
    assert all('竹签' not in names for names in groups)
    for samples in splits:
        for sample in samples:
            validate_sample(sample)
            assert sample['provenance']=='weak_template'
    vocabulary=read_json(training/'vocab.json')
    assert set(vocabulary)-{'<PAD>','<UNK>'}==set(''.join(sample['text'] for sample in splits[0]))


def test_mismatched_formats_fail_without_outputs(tmp_path):
    source=tmp_path/'one.jsonl';paired=tmp_path/'two.jsonl';output=tmp_path/'output'
    source.write_text(json.dumps(record()),encoding='utf8')
    paired.write_text(json.dumps(record('另一个')),encoding='utf8')
    with pytest.raises(ValueError,match='内容不一致'):
        ingest(source,paired,output,tmp_path/'training')
    assert not output.exists()


def test_training_spans_when_item_contains_category_word(tmp_path):
    rows=[]
    for category in ('干垃圾','湿垃圾','可回收物','有害垃圾'):
        for suffix in ('桶','袋','盒'):
            rows.append({'name':category+suffix,'category':category,'method':None,
                         'source_url':'https://example.org','review_status':'source_labeled'})
    training_data(rows,tmp_path)
    for split in ('train','val','test'):
        for sample in read_jsonl(tmp_path/f'{split}.jsonl'):
            validate_sample(sample)


def test_large_catalog_pagination_reaches_every_item_once():
    kb=KnowledgeBase();offset=0;names=[]
    while offset is not None:
        page=kb.search(limit=150,offset=offset)
        names.extend(row['name'] for row in page['items'])
        offset=page['next_offset']
    assert len(names)==len(set(names))==len(kb.rows)
    assert len(names)>150
    assert kb.search(offset=len(names))['items']==[]


@pytest.mark.parametrize('limit',[1,3,7,24,80,100])
def test_graph_respects_requested_item_limit(limit):
    graph=KnowledgeBase().subgraph(limit=limit)
    assert sum(node['kind']=='ITEM' for node in graph['nodes'])==min(limit,80)


def test_scope_and_evidence_qa_do_not_claim_external_labels_are_reviewed():
    kb=KnowledgeBase()
    assert all(row['provenance']=='external_dataset' for row in kb.search(scope='external')['items'])
    assert all(row['provenance']!='external_dataset' for row in kb.search(scope='teaching')['items'])
    result=answer(kb,'阿司匹林是什么垃圾？')
    assert result['status']=='reference'
    assert result['items'][0]['method']
    assert result['items'][0]['review_status']=='source_labeled'
    assert result['triples'][0]['source_url']
    assert answer(kb,'快递纸箱怎么扔')['items'][0]['name']=='纸箱'
    assert answer(kb,'沾满油漆的纸箱怎么扔')['status'] in ('clarify','unknown')
    assert answer(kb,'火星不存在的物质是什么垃圾')['status']=='unknown'


@pytest.mark.parametrize('question',['','a'*129,None,[]])
def test_bad_qa_input_rejected(question):
    with pytest.raises(ValueError):answer(KnowledgeBase(),question)


def test_main_catalog_merge_is_idempotent_and_preserves_backup(tmp_path):
    path=tmp_path/'catalog.json'
    seed=[{'name':'纸箱','category':'可回收物','method':'保持干燥','provenance':'curated_example'}]
    original=json.dumps(seed,ensure_ascii=False).encode('utf-8')
    path.write_bytes(original)
    additions=[{'name':'测试药品','category':'有害垃圾','method':None,'provenance':'external_dataset'}]
    first=merge_main_catalog(additions+additions,path)
    assert first['items']==2 and first['added']==1
    merged=path.read_bytes()
    second=merge_main_catalog(additions,path)
    assert second['added']==0 and path.read_bytes()==merged
    assert (tmp_path/'catalog.before_external_merge.json').read_bytes()==original
    with pytest.raises(ValueError,match='类别冲突'):
        merge_main_catalog([{'name':'纸箱','category':'干垃圾'}],path)
    assert path.read_bytes()==merged


def test_graph_page_matches_catalog_page_and_teaching_filter():
    kb=KnowledgeBase()
    first=kb.subgraph(category='有害垃圾',limit=12,offset=0)
    following=kb.subgraph(category='有害垃圾',limit=12,offset=12)
    expected={row['name'] for row in kb.search(category='有害垃圾',limit=12,offset=12)['items']}
    actual={node['name'] for node in following['nodes'] if node['kind']=='ITEM'}
    assert actual==expected
    assert not actual&{node['name'] for node in first['nodes'] if node['kind']=='ITEM'}
    assert following['item_offset']==12 and following['total_items']>=len(actual)
    assert all(row['provenance']!='external_dataset' for row in load_catalog(False))
