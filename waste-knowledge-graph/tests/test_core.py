import json
from pathlib import Path
import pytest
from wastekg.common import *
from wastekg.graph import KnowledgeBase,build_graph
from wastekg.prepare import catalog,example
from wastekg.review import approve,merge_catalog


def test_group_split_has_no_item_or_sentence_leakage():
    data=[read_jsonl(DATA/'processed'/f'{s}.jsonl') for s in ['train','val','test']]
    for a,b in [(0,1),(0,2),(1,2)]:
        assert not set(s['group'] for s in data[a]) & set(s['group'] for s in data[b])
        assert not set(s['text'] for s in data[a]) & set(s['text'] for s in data[b])
    for records in data:
        for record in records:validate_sample(record)


def test_bio_round_trip_and_invalid_span():
    s=example('香蕉皮属于湿垃圾。','香蕉皮','湿垃圾','CATEGORY','BELONGS_TO',0)
    assert spans(bio_tags(s),s['text'])==s['entities']
    s['entities'][0]['end']=2
    with pytest.raises(AssertionError):validate_sample(s)


def test_graph_is_deterministic_and_referentially_complete():
    rows=catalog();g=build_graph(rows)
    assert g==build_graph(rows+rows)
    ids={n['id'] for n in g['nodes']}
    assert len(ids)==len(g['nodes'])
    assert len(g['edges'])==2*len(rows)
    assert all(e['source'] in ids and e['target'] in ids and e['source_url'] for e in g['edges'])


@pytest.mark.parametrize('query,name,category', [('快递纸箱','纸箱','可回收物'),('香蕉皮','香蕉皮','湿垃圾'),('水银温度计','含汞温度计','有害垃圾'),('一次性口罩','一次性口罩','干垃圾')])
def test_alias_and_category_query(query,name,category):
    result=KnowledgeBase().search(query)
    assert result['items'][0]['name']==name
    assert result['items'][0]['category']==category


def test_unknown_is_not_guessed_and_bad_category_rejected():
    kb=KnowledgeBase()
    assert kb.search('火星岩石')['total']==0
    with pytest.raises(ValueError):kb.search('', '伪分类')


def test_review_requires_explicit_approval_and_rejects_conflict():
    candidate={'id':'a','head':'香蕉皮','relation':'BELONGS_TO','tail':'干垃圾','source_url':'https://example.org', 'evidence':'一条错误候选'}
    assert approve([candidate],[{'id':'a','approved':False,'reviewer':'A'}])==[]
    assert approve([candidate],[{'id':'a','approved':True,'reviewer':''}])==[]
    accepted=approve([candidate],[{'id':'a','approved':True,'reviewer':'A'}])
    with pytest.raises(ValueError):merge_catalog(catalog(),accepted)


def test_clean_text_is_idempotent():
    text='  香蕉皮[12]  属于\n湿垃圾。 '
    assert clean_text(clean_text(text))==clean_text(text)


def test_reviewed_method_keeps_its_own_evidence():
    c={'head':'香蕉皮','relation':'DISPOSE_WITH','tail':'分开投放','source_url':'https://example.org/method',
       'evidence':'香蕉皮需要分开投放。','review_status':'approved','provenance':'model_candidate'}
    graph=build_graph(merge_catalog(catalog(),[c]))
    edge=next(e for e in graph['edges'] if e['source']==identity('ITEM','香蕉皮') and e['relation']=='DISPOSE_WITH')
    assert edge['source_url']==c['source_url'] and edge['evidence']==c['evidence']
