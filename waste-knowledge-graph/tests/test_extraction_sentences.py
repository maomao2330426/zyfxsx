"""Regression cases describe desired semantics, not model benchmark accuracy."""
import pytest
from wastekg.sentence_rules import extract_explicit,combine

LONG='虽然这个香蕉皮曾经和塑料袋、卫生纸以及一次性餐盒混放在一起，而且表面还沾有少量酸奶和米饭，但在把其他物品分离后，剩下的香蕉皮仍然属于厨余垃圾。'
MODIFIED='一个表面已经发黑、还残留少量果肉和酸奶，并且刚刚从塑料保鲜袋里取出来的香蕉皮属于厨余垃圾。'

def triples(text):
    return {(t['head'],t['relation'],t['tail']) for t in extract_explicit(text)['triples']}

@pytest.mark.parametrize('text',[
    '香蕉皮是湿垃圾','香蕉皮是湿垃圾。','香蕉皮是一种湿垃圾。','香蕉皮仍然属于湿垃圾。',
    '香蕉皮主要是湿垃圾。','香蕉皮应归入湿垃圾。','香蕉皮的类别是湿垃圾。','香蕉皮的垃圾类型为湿垃圾。',
    '请将香蕉皮按湿垃圾进行分类。','香蕉皮属于湿垃圾！',
])
def test_simple_affirmative_forms(text):
    assert triples(text)=={('香蕉皮','BELONGS_TO','湿垃圾')}

@pytest.mark.parametrize('text',[LONG,MODIFIED])
def test_screenshot_complex_subject_not_background_items(text):
    r=extract_explicit(text)
    assert triples(text)=={('香蕉皮','BELONGS_TO','厨余垃圾')}
    assert r['triples'][0]['canonical_tail']=='湿垃圾'
    assert not any(e['type']=='METHOD' or e['text'] in ('面','肉','厨余') for e in r['entities'])
    for e in r['entities']:assert text[e['start']:e['end']]==e['text']
    t=r['triples'][0]
    assert text[t['head_start']:t['head_end']]=='香蕉皮'
    assert text[t['tail_start']:t['tail_end']]=='厨余垃圾'

@pytest.mark.parametrize('text',[
    '香蕉皮不是湿垃圾。','香蕉皮不属于湿垃圾。','香蕉皮是否是湿垃圾','香蕉皮是湿垃圾吗',
    '香蕉皮是不是湿垃圾？','假如香蕉皮是湿垃圾。','如果香蕉皮是湿垃圾，就分类投放。',
    '香蕉皮可能是湿垃圾。','有人说香蕉皮是湿垃圾。','香蕉皮是湿垃圾的说法是错误的。',
    '香蕉皮不能投入湿垃圾容器。','不要把香蕉皮混入湿垃圾。','香蕉皮不一定是湿垃圾。',
    '香蕉皮无需沥干水分。','香蕉皮是湿垃圾桶。','香蕉皮和湿垃圾的关系未说明。','香蕉皮是湿垃圾还是干垃圾','香蕉皮是湿垃圾，但需要核实。','若香蕉皮是湿垃圾，就分类投放。',
])
def test_no_positive_assertions_for_negated_uncertain_questions_or_bins(text):
    assert triples(text)==set()

def test_two_subjects_are_bound_to_their_own_clause():
    assert triples('香蕉皮是湿垃圾，塑料袋是干垃圾。')=={
        ('香蕉皮','BELONGS_TO','湿垃圾'),('塑料袋','BELONGS_TO','干垃圾')}

@pytest.mark.parametrize('text',['香蕉皮和苹果核是湿垃圾。','湿垃圾包括香蕉皮和苹果核。'])
def test_explicit_coordination(text):
    assert triples(text)=={('香蕉皮','BELONGS_TO','湿垃圾'),('苹果核','BELONGS_TO','湿垃圾')}

def test_negation_scope_does_not_hide_independent_positive_or_correction():
    assert triples('香蕉皮不是干垃圾而是湿垃圾。')=={('香蕉皮','BELONGS_TO','湿垃圾')}
    assert triples('香蕉皮不是干垃圾，而是湿垃圾。')=={('香蕉皮','BELONGS_TO','湿垃圾')}
    assert triples('香蕉皮不是干垃圾，塑料袋是干垃圾。')=={('塑料袋','BELONGS_TO','干垃圾')}

def test_action_method_requires_actual_disposal_instruction():
    assert triples('香蕉皮需要沥干水分并去除包装。')=={('香蕉皮','DISPOSE_WITH','沥干水分并去除包装')}
    assert triples('投放香蕉皮时，需要沥干水分。')=={('香蕉皮','DISPOSE_WITH','沥干水分')}
    assert triples('香蕉皮表面沾有少量酸奶和米饭。')==set()

def test_alias_and_repeated_mentions_are_preserved_and_deduplicated():
    assert triples('香蕉皮是湿垃圾，香蕉皮属于湿垃圾。')=={('香蕉皮','BELONGS_TO','湿垃圾')}
    r=extract_explicit('快递纸箱是可回收垃圾。')
    assert r['triples'][0]['canonical_head']=='纸箱'
    assert r['triples'][0]['canonical_tail']=='可回收物'

def test_extraction_does_not_silently_replace_text_with_catalog_fact():
    assert triples('香蕉皮是干垃圾。')=={('香蕉皮','BELONGS_TO','干垃圾')}
    assert triples('火星岩石属于湿垃圾。')==set()

def test_assisted_output_filters_false_method_and_has_no_fabricated_model_score():
    r=combine(LONG,{'triples':[{'head':'香蕉皮','relation':'DISPOSE_WITH','tail':'且表面还沾有少量酸奶','confidence':.98}]})
    assert len(r['triples'])==1
    assert r['triples'][0]['confidence'] is None
    assert r['triples'][0]['extraction_source']=='sentence_rule'
    assert r['mode']=='hybrid'

def test_actual_model_agreement_retains_original_score():
    r=combine('香蕉皮是湿垃圾',{'triples':[{'head':'香蕉皮','relation':'BELONGS_TO','tail':'湿垃圾','confidence':.91}]})
    assert r['triples'][0]['confidence']==.91
    assert r['triples'][0]['extraction_source']=='neural_and_rule'

@pytest.mark.parametrize('text',['','x'*129,None])
def test_invalid_input(text):
    with pytest.raises(ValueError):extract_explicit(text)
