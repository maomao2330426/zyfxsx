"""Conservative, clause-scoped extraction of explicitly stated waste relations.

This is a rule layer, not a learned classifier or a source of classification facts.
Offsets refer to the original input, including category aliases and repeated mentions.
"""
import re
from functools import lru_cache
from .common import DATA, CATEGORIES, MAX_LEN, read_json
from .graph import load_catalog

CATEGORY_LINK = re.compile(
    r'\s*(?:(?:仍然|依然|仍|也|都|均|通常|一般|应当|应该|应|可以|可|就|则|主要|还)\s*)'
    r'*(?:属于|是|为|归入|归为|算作|算是|算|划为|视为|作为|按|当作|投入|丢进|放入|放到|投放到|'
    r'的(?:垃圾)?(?:类别|类型)(?:是|为))\s*(?:一种|一类)?\s*')
COORDINATION = re.compile(r'\s*(?:、|和|与|及|以及|还有)\s*')
UNCERTAIN = re.compile(r'还是|或者是|是否|是不是|能否|会不会|不一定|未必|可能|也许|大概|似乎|听说|据说|有人说|有人认为|不知道|不清楚|未说明|没有说明|并未说明|没有说|并没有说')
HYPOTHETICAL = re.compile(r'如果|假如|假设|倘若|假若|(?<!主)要是|若是|(?:^|[，,；;])若')
NEGATIVE = re.compile(r'不是|不属于|不算|不可|不能|不应|不要|并非|并不|别把|禁止|并未|没有|不需要|无需')
METHOD_ACTION = re.compile(r'(?:沥干|清空|清洗|洗净|保持|去除|去掉|拆除|拆开|分开|包裹|装袋|单独投放|交给|投入|投放|交由|送往|密封|包好|压扁|折叠|清除|排空)')
METHOD_LINK = re.compile(r'\s*(?:的投放要求是|的处理方式是|需要|应当|应该|应|要|务必|建议|需)(?:先)?\s*')

@lru_cache(maxsize=1)
def lexicon():
    aliases = read_json(DATA/'aliases.json')
    categories = {c:c for c in CATEGORIES}
    categories.update({k:v for k,v in aliases.items() if v in CATEGORIES})
    items = {r['name']:r['name'] for r in load_catalog() if r['name'] not in categories}
    items.update({k:v for k,v in aliases.items() if v in items and k not in categories})
    return items, categories

def entity(text, start, end, kind, canonical=None):
    result = {'start':start, 'end':end, 'text':text[start:end], 'type':kind}
    if canonical and canonical != result['text']:
        result['canonical'] = canonical
    return result

def mentions(text):
    items, categories = lexicon()
    occupied = set()
    result = []
    # Categories take priority over catalog entries such as “厨余”.
    for terms, kind in [(categories,'CATEGORY'),(items,'ITEM')]:
        for term, canonical in sorted(terms.items(),key=lambda t:(-len(t[0]),t[0])):
            if not term:continue
            for m in re.finditer(re.escape(term),text):
                if occupied.intersection(range(m.start(),m.end())):continue
                if kind == 'ITEM' and len(term)==1:
                    # “面” in “表面” and “肉” in “果肉” are not standalone mentions.
                    if m.start() and text[m.start()-1] not in '，,。；;、 \n':continue
                    if not re.match(r'(?:是|属于|归入|需要|应|的投放|[、，,。；;\s]|$)',text[m.end():]):continue
                result.append(entity(text,m.start(),m.end(),kind,canonical))
                occupied.update(range(m.start(),m.end()))
    return sorted(result,key=lambda e:(e['start'],e['end']))

def coordinated(text, items, last):
    selected=[last]
    for item in reversed([e for e in items if e['end']<=last['start']]):
        if COORDINATION.fullmatch(text[item['end']:selected[0]['start']]):
            selected.insert(0,item)
        else:break
    return selected

def extract_explicit(text):
    if not isinstance(text,str) or not text.strip() or len(text)>MAX_LEN:
        raise ValueError('请输入 1 至 128 字的文本')
    entities=mentions(text)
    triples=[]
    def add(head,tail,relation):
        key=(head.get('canonical',head['text']),relation,tail.get('canonical',tail['text']))
        if any(t['_key']==key for t in triples):return
        triples.append({'_key':key,'head':head['text'],'relation':relation,'tail':tail['text'],
                        'head_start':head['start'],'head_end':head['end'],
                        'tail_start':tail['start'],'tail_end':tail['end'],
                        'canonical_head':key[0],'canonical_tail':key[2],
                        'confidence':None,'extraction_source':'sentence_rule',
                        'review_status':'pending','evidence':text})
        if not any(e['start']==tail['start'] and e['end']==tail['end'] and e['type']==tail['type'] for e in entities):
            entities.append(tail)
    for sentence in re.finditer(r'[^。！？?!\n]+[。！？?!]?',text):
        s=sentence.group()
        if HYPOTHETICAL.search(s) or re.search(r'[？?]|(?:吗|么|呢)[。！!]?$',s):continue
        if re.search(r'(?:是|为)(?:错误|错的|不正确|不对)|说法(?:有误|不对|错误)|需要核实|尚未确认|有待确认',s):continue
        previous=[]
        cursor=0
        for clause in re.split(r'([，,；;。！？?!]|(?=而是|但是))',s):
            start=sentence.start()+cursor;cursor+=len(clause);end=sentence.start()+cursor
            if not clause or clause in '，,；;。！？?!':continue
            local=[e for e in entities if start<=e['start'] and e['end']<=end]
            items=[e for e in local if e['type']=='ITEM']
            cats=[e for e in local if e['type']=='CATEGORY']
            uncertain=bool(UNCERTAIN.search(clause))
            if not uncertain and not NEGATIVE.search(clause):
                for target in cats:
                    heads=[e for e in items if e['end']<=target['start']]
                    if heads:
                        head=heads[-1];gap=text[head['end']:target['start']]
                        if CATEGORY_LINK.fullmatch(gap):
                            # Copular statements about bins are not item classifications.
                            if not ('是' in gap and re.match(r'(?:桶|收集容器)',text[target['end']:end])):
                                for h in coordinated(text,heads,head):add(h,target,'BELONGS_TO')
                    # Correction/anaphora is allowed only with one unambiguous prior subject.
                    elif len(previous)==1 and re.fullmatch(r'\s*(?:而是|而应归入|其类别是|它是|它属于)\s*',text[start:target['start']]):
                        add(previous[0],target,'BELONGS_TO')
                    following=[e for e in items if e['start']>=target['end']]
                    if following and re.fullmatch(r'\s*(?:这一类别)?(?:包括|包含|有)\s*',text[target['end']:following[0]['start']]):
                        selected=[following[0]]
                        for h in following[1:]:
                            if not COORDINATION.fullmatch(text[selected[-1]['end']:h['start']]):break
                            selected.append(h)
                        for h in selected:add(h,target,'BELONGS_TO')
                # A disposal METHOD must start with an action, never a state like “沾有酸奶”.
                for match in METHOD_LINK.finditer(clause):
                    action_start=start+match.end()
                    if not METHOD_ACTION.match(text[action_start:end]):continue
                    if any(e['start']>=action_start for e in cats):continue
                    before=[e for e in items if e['end']<=start+match.start()]
                    heads=[]
                    if before and not text[before[-1]['end']:start+match.start()].strip():
                        heads=coordinated(text,before,before[-1])
                    elif not before and len(previous)==1 and re.fullmatch(r'\s*',clause[:match.start()]):
                        heads=previous
                    if heads:
                        target=entity(text,action_start,end,'METHOD')
                        for head in heads:add(head,target,'DISPOSE_WITH')
            # Don't carry subjects across unrelated, uncertain clauses or semicolons.
            previous=items if not uncertain else []
            if end<len(text) and text[end] in '；;':previous=[]
    for t in triples:t.pop('_key')
    # Remove lexical fragments contained in an accepted method phrase.
    methods=[e for e in entities if e['type']=='METHOD']
    entities=[e for e in entities if e['type']=='METHOD' or not any(m['start']<=e['start'] and e['end']<=m['end'] for m in methods)]
    return {'mode':'dictionary_baseline','entities':sorted(entities,key=lambda e:e['start']),
            'triples':triples,'note':'词典与句式规则抽取，不是神经网络预测；按原文提取陈述，未核对分类事实，候选需人工审核。'}

def combine(text, neural):
    """Apply explicit clause constraints and label rule backfills without fake scores."""
    result=extract_explicit(text)
    for triple in result['triples']:
        matching=next((n for n in neural['triples'] if n['head']==triple['head'] and n['tail']==triple['tail'] and n['relation']==triple['relation']),None)
        if matching:
            triple['extraction_source']='neural_and_rule'
            triple['confidence']=matching['confidence']
            triple['confidence_kind']=matching.get('confidence_kind','uncalibrated_relation_softmax')
    result.update({'mode':'hybrid','model_used':True,'pipeline_version':'clause_guard_v1',
                   'note':'BiLSTM-CRF + BiGRU-Attention 与词典边界、分句规则联合抽取。规则补全不显示模型分数；原始神经模型可单独对照。抽取只反映原文陈述，候选需人工审核。'})
    return result
