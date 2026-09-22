"""Sentence families and adversarial neighbours; not an accuracy benchmark."""
import pytest
from wastekg.sentence_rules import extract_explicit


def relations(text, kind=None):
    result = extract_explicit(text)
    for e in result['entities']:
        assert text[e['start']:e['end']] == e['text']
    for t in result['triples']:
        assert text[t['head_start']:t['head_end']] == t['head']
        assert text[t['tail_start']:t['tail_end']] == t['tail']
    return {(t['head'], t['relation'], t['tail']) for t in result['triples'] if kind is None or t['relation'] == kind}


@pytest.mark.parametrize('verb', ['丢进','丢入','丢到','扔进','扔入','扔到','放进','放入','放到','投入','投进','投到','投放到','投放至'])
def test_disposal_destination_verbs(verb):
    assert relations(f'香蕉皮属于湿垃圾，应该{verb}垃圾桶里。') == {
        ('香蕉皮','BELONGS_TO','湿垃圾'), ('香蕉皮','DISPOSE_WITH',verb+'垃圾桶里')}
    assert not any(e['text']=='垃圾桶' for e in extract_explicit(f'香蕉皮应该{verb}垃圾桶里')['entities'])


@pytest.mark.parametrize('prefix', ['应该','应当','需要','需','必须','要','务必','建议','可以','请',''])
def test_modal_and_bare_disposal_predicate(prefix):
    assert relations(f'香蕉皮{prefix}丢进垃圾桶里。') == {('香蕉皮','DISPOSE_WITH','丢进垃圾桶里')}


@pytest.mark.parametrize('text', [
    '请把香蕉皮丢进垃圾桶里。','请将香蕉皮丢进垃圾桶里。',
    '香蕉皮的投放要求是丢进垃圾桶里。','香蕉皮的投放方式为丢进垃圾桶里。',
    '香蕉皮的处理方式：丢进垃圾桶里。','香蕉皮投放时应该丢进垃圾桶里。',
    '香蕉皮属于湿垃圾,应该丢进垃圾桶里',
    '香蕉皮属于湿垃圾，它应该丢进垃圾桶里。',
    '香蕉皮属于湿垃圾。它应该丢进垃圾桶里。',
])
def test_directives_and_implicit_subject(text):
    assert relations(text,'DISPOSE_WITH') == {('香蕉皮','DISPOSE_WITH','丢进垃圾桶里')}


@pytest.mark.parametrize('action', [
    '沥干水分','滤干水分','倒空残留物','清空内容物','清洗干净','洗净后晾干',
    '冲洗干净','擦干水分','去除包装','去掉包装','拆开包装','分离包装',
    '装袋投放','破袋投放','密封包装','扎紧袋口','压扁投放','折叠整齐',
    '清理残留物','排空液体','捆扎整齐','打包投放','交给回收人员','交由回收单位处理',
    '送到回收点','送往回收站','送至指定收集点',
])
def test_handling_action_families(action):
    # Tests syntax only; no claim that each instruction is appropriate for this item.
    assert relations('香蕉皮需要'+action+'。','DISPOSE_WITH') == {('香蕉皮','DISPOSE_WITH',action)}


def test_multistep_and_method_objects_do_not_replace_subject():
    assert relations('香蕉皮先沥干水分，再装袋，最后丢进垃圾桶里。') == {
        ('香蕉皮','DISPOSE_WITH','沥干水分'),('香蕉皮','DISPOSE_WITH','装袋'),
        ('香蕉皮','DISPOSE_WITH','丢进垃圾桶里')}
    assert relations('香蕉皮需要沥干水分后丢进垃圾桶里。') == {('香蕉皮','DISPOSE_WITH','沥干水分后丢进垃圾桶里')}
    assert relations('香蕉皮应该丢进垃圾桶里，然后去除包装。') == {
        ('香蕉皮','DISPOSE_WITH','丢进垃圾桶里'),('香蕉皮','DISPOSE_WITH','去除包装')}
    assert relations('香蕉皮应装袋投放，以免污染环境。') == {('香蕉皮','DISPOSE_WITH','装袋投放')}


def test_group_subjects_and_destination_category():
    assert relations('香蕉皮和苹果核应沥干水分，再丢进垃圾桶里。') == {
        (h,'DISPOSE_WITH',m) for h in ['香蕉皮','苹果核'] for m in ['沥干水分','丢进垃圾桶里']}
    assert relations('香蕉皮和苹果核属于湿垃圾，它们应该丢进垃圾桶里。','DISPOSE_WITH') == {
        (h,'DISPOSE_WITH','丢进垃圾桶里') for h in ['香蕉皮','苹果核']}
    result=relations('香蕉皮应投入湿垃圾收集容器。')
    assert ('香蕉皮','DISPOSE_WITH','投入湿垃圾收集容器') in result
    assert ('香蕉皮','BELONGS_TO','湿垃圾') in result


def test_independent_items_keep_their_own_method():
    assert relations('香蕉皮需要沥干水分，塑料袋应该送到回收点。') == {
        ('香蕉皮','DISPOSE_WITH','沥干水分'),('塑料袋','DISPOSE_WITH','送到回收点')}


@pytest.mark.parametrize('link', ['归类为','归类到','划分为','划入','算作','算是','视为','作为', '的分类是','：',':'])
def test_category_paraphrases(link):
    assert relations('香蕉皮'+link+'湿垃圾。') == {('香蕉皮','BELONGS_TO','湿垃圾')}


@pytest.mark.parametrize('text', [
    '香蕉皮和苹果核，都属于湿垃圾。','香蕉皮以及苹果核等物品属于湿垃圾。',
    '湿垃圾包括：香蕉皮和苹果核。','湿垃圾主要有香蕉皮和苹果核。',
    '属于湿垃圾的有香蕉皮和苹果核。',
])
def test_category_lists_and_reverse_order(text):
    assert relations(text) == {(h,'BELONGS_TO','湿垃圾') for h in ['香蕉皮','苹果核']}


def test_ordered_categories_not_cartesian_product():
    expected={('香蕉皮','BELONGS_TO','湿垃圾'),('塑料袋','BELONGS_TO','干垃圾')}
    assert relations('香蕉皮和塑料袋分别属于湿垃圾和干垃圾。') == expected
    assert relations('香蕉皮和塑料袋，分别是湿垃圾、干垃圾。') == expected
    assert relations('香蕉皮和塑料袋分别属于湿垃圾。') == set()
    assert relations('香蕉皮是湿垃圾和干垃圾。') == set()


@pytest.mark.parametrize('prefix', ['不应','不宜','不建议','不得','不能','不要','不该','切勿','严禁','禁止','不必','无需'])
def test_prohibitions_never_become_positive_disposal(prefix):
    assert relations('香蕉皮'+prefix+'丢进垃圾桶里。') == set()


@pytest.mark.parametrize('text', [
    '香蕉皮应该丢进垃圾桶里吗？','请问香蕉皮应该丢进垃圾桶里',
    '香蕉皮能不能丢进垃圾桶里','香蕉皮也许应该丢进垃圾桶里。',
    '如果香蕉皮属于湿垃圾，就应该丢进垃圾桶里。',
    '香蕉皮已经丢进垃圾桶里了。','昨天把香蕉皮丢进垃圾桶里。',
    '香蕉皮被人丢进垃圾桶里。','我看到香蕉皮被丢进垃圾桶里。',
    '香蕉皮表面沾有酸奶。','香蕉皮放入书包里。',
    '香蕉皮和塑料袋混在一起，应该丢进垃圾桶里。',
    '香蕉皮和塑料袋属于湿垃圾，它应该丢进垃圾桶里。',
    '香蕉皮属于湿垃圾，天气很好，应该丢进垃圾桶里。',
    '香蕉皮属于湿垃圾；应该丢进垃圾桶里。',
])
def test_ambiguous_descriptive_and_uncertain_clauses_do_not_invent_methods(text):
    assert relations(text,'DISPOSE_WITH') == set()


def test_corrections_keep_positive_scope_and_methods():
    assert relations('香蕉皮不是干垃圾，而是湿垃圾，应该丢进垃圾桶里。') == {
        ('香蕉皮','BELONGS_TO','湿垃圾'),('香蕉皮','DISPOSE_WITH','丢进垃圾桶里')}
    assert relations('香蕉皮不要装袋，应该沥干水分。') == {('香蕉皮','DISPOSE_WITH','沥干水分')}


def test_unknown_subject_is_not_replaced_by_known_container():
    assert relations('火星矿石应该丢进垃圾桶里。') == set()
    assert relations('香蕉皮需要清洗，火星矿石应该丢进垃圾桶里。','DISPOSE_WITH') == {('香蕉皮','DISPOSE_WITH','清洗')}


@pytest.mark.parametrize('connector', ['', '并', '并且', '同时'])
def test_category_then_disposal_without_comma(connector):
    assert relations('香蕉皮属于湿垃圾'+connector+'应该丢进垃圾桶里。') == {
        ('香蕉皮','BELONGS_TO','湿垃圾'),('香蕉皮','DISPOSE_WITH','丢进垃圾桶里')}


@pytest.mark.parametrize('connector', ['并且','而且','同时','而','但'])
def test_conjunction_introducing_new_subject_ends_previous_method(connector):
    assert relations('香蕉皮应沥干水分'+connector+'塑料袋应送到回收点。') == {
        ('香蕉皮','DISPOSE_WITH','沥干水分'),('塑料袋','DISPOSE_WITH','送到回收点')}


@pytest.mark.parametrize('action', ['轻拿轻放','保持完整','保持干燥','压平后投放','洗干净后投放',
                                  '冲净后投放','包严后投放','拧紧瓶盖','盖好瓶盖',
                                  '用报纸包裹好再投放','使用纸巾包住后投放','连同包装一起投放'])
def test_protection_and_packaging_requirements(action):
    assert relations('玻璃瓶应该'+action+'。') == {('玻璃瓶','DISPOSE_WITH',action)}


def test_tool_mentions_do_not_receive_or_steal_handling_relations():
    result=extract_explicit('玻璃瓶应该用报纸包裹好再投放，然后送到回收点。')
    assert relations(result['triples'][0]['evidence']) == {
        ('玻璃瓶','DISPOSE_WITH','用报纸包裹好再投放'),('玻璃瓶','DISPOSE_WITH','送到回收点')}
    assert not any(e['text']=='报纸' for e in result['entities'])


def test_post_disposal_description_is_not_a_new_instruction():
    assert relations('香蕉皮投放后属于湿垃圾。','DISPOSE_WITH') == set()


@pytest.mark.parametrize('correction', ['但它属于','但是属于','而属于','而应该属于'])
def test_contrast_corrections(correction):
    assert relations('香蕉皮不是干垃圾，'+correction+'湿垃圾。') == {('香蕉皮','BELONGS_TO','湿垃圾')}


def test_slash_category_alternative_is_not_a_confident_classification():
    assert relations('香蕉皮是湿垃圾/干垃圾。') == set()
