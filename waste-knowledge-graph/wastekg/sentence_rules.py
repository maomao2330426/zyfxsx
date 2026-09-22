"""Conservative, clause-scoped extraction of explicitly stated waste relations.

This is a rule layer, not a learned classifier or a source of classification facts.
Offsets refer to the original input, including category aliases and repeated mentions.
"""
import re
from functools import lru_cache
from .common import DATA, CATEGORIES, MAX_LEN, read_json
from .graph import load_catalog

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

def literal_occurrences(text, term):
    # Literal dictionary lookup does not need thousands of regex compilations per request.
    begin = text.find(term)
    while begin >= 0:
        finish = begin + len(term)
        yield begin, finish
        begin = text.find(term, finish)


def mentions(text):
    items, categories = lexicon()
    occupied = set()
    result = []
    # Categories take priority over catalog entries such as “厨余”.
    for terms, kind in [(categories,'CATEGORY'),(items,'ITEM')]:
        for term, canonical in sorted(terms.items(),key=lambda t:(-len(t[0]),t[0])):
            if not term:continue
            for begin, finish in literal_occurrences(text, term):
                if occupied.intersection(range(begin,finish)):continue
                if kind == 'ITEM' and len(term)==1:
                    # “面” in “表面” and “肉” in “果肉” are not standalone mentions.
                    if begin and text[begin-1] not in '，,。；;、 \n':continue
                    if not re.match(r'(?:是|属于|归入|需要|应|的投放|[、，,。；;\s]|$)',text[finish:]):continue
                result.append(entity(text,begin,finish,kind,canonical))
                occupied.update(range(begin,finish))
    return sorted(result,key=lambda e:(e['start'],e['end']))

# Explicit syntax is intentionally bounded: this layer extracts assertions, not facts.
ADVERBS = r'(?:(?:仍然|依然|仍|也|都|均|通常|一般|应当|应该|应|可以|可|就|则|主要|还|必须|需要|需|统一)\s*)*'
CATEGORY_LINK = re.compile(
    r'\s*(?:等(?:物品|垃圾)?\s*)?' + ADVERBS +
    r'(?:属于|是|为|归入|归为|归类为|归类到|划分为|划入|算作|算是|算|划为|视为|作为|按|按照|当作|'
    r'投入|丢进|放入|放到|投放到|的(?:垃圾)?(?:类别|类型|分类)(?:是|为|[:：])|[:：])\s*(?:一种|一类)?\s*')
COORDINATION = re.compile(r'\s*(?:、|/|／|和|与|及|以及|还有|或|或者)\s*')
UNCERTAIN = re.compile(r'还是|或者是|是否|是不是|能否|会不会|可不可以|能不能|不一定|未必|可能|也许|大概|似乎|听说|据说|有人说|有人认为|不知道|不清楚|未说明|没有说明|并未说明|没有说|并没有说|请问|怎么|如何|为什么|哪(?:类|种|个)|什么垃圾')
HYPOTHETICAL = re.compile(r'如果|假如|假设|倘若|假若|只要|只有|除非|(?<!主)要是|若是|(?:^|[，,；;])若')
NEGATIVE = re.compile(r'不是|不属于|不算|不可|不能|不应|不宜|不建议|不必|不得|不要|切勿|勿|严禁|禁止|并非|并不|别把|并未|没有|无需|不需要|不可以|不该')
HISTORY = re.compile(r'曾经|已经|刚刚|刚才|昨天|误把|错把|误将|被人|被扔|被丢|看见|看到|发现|以为')
METHOD_ACTION = re.compile(
    r'(?:使用|用)[^，,；;。！？]{1,12}?(?:包裹|包住|包扎|封住|缠绕|密封|装好)|'
    r'连同[^，,；;。！？]{1,12}?(?:投放|送交)|'
    r'轻拿轻放|小心轻放|熄灭|冷却|压平|洗干净|冲净|包住|包严|封装|拧紧|拧开|盖好|'
    r'沥干|沥净|滤干|倒空|清空|清洗|洗净|冲洗|晾干|擦干|保持|去除|去掉|拆除|拆开|拆解|分开|分离|'
    r'取下|拧下|拔掉|包裹|包好|装袋|破袋|密封|扎紧|压扁|折叠|清除|清理|排空|捆扎|打包|包扎|'
    r'交给|交由|交到|交至|送往|送到|送至|投入|投进|投到|投放(?:到|至|进)?|丢进|丢入|丢到|扔进|扔入|扔到|放进|放入|放到|放置(?:到|于)?|回收')
MOVE_ACTION = re.compile(r'^(?:投入|投进|投到|丢进|丢入|丢到|扔进|扔入|扔到|放进|放入|放到|放置)')
DISPOSAL_DESTINATION = re.compile(r'垃圾|回收|收集|投放|处理|废物')
MODAL = r'(?:(?:请|应当|应该|建议|务必|必须|需要|可直接|可以|应|需|要|宜|可)\s*)*'
ACTION_ADVERBS = r'(?:(?:首先|先|然后|再|最后|直接|单独|分类|集中|统一|妥善|轻轻|小心|分别)\s*)*'
# Modal prefixes are excluded from METHOD text, while action ordering is retained.
METHOD_PREFIX = re.compile(
    r'\s*(?:(?:在)?(?:投放|丢弃|处理)(?:之)?(?:前|时)|的(?:投放要求|处理方式|投放方式|处置方法)(?:是|为|[:：]))?\s*'
    + MODAL + r'(?P<sequence>' + ACTION_ADVERBS + r')')
CONTEXT_PREFIX = re.compile(r'\s*(?:(?:但是|但|却|而|并且|并|还|同时|随后|接着|然后|再|最后)\s*)*(?:(?P<pronoun>它们|它|其|这些物品|该物品|该垃圾)\s*)?')


def coordinated(text, items, last):
    selected = [last]
    for item in reversed([e for e in items if e['end'] <= last['start']]):
        if COORDINATION.fullmatch(text[item['end']:selected[0]['start']]):
            selected.insert(0, item)
        else:
            break
    return selected


def context_gap(gap, previous):
    """Strip discourse/anaphora only when the carried subject is unambiguous."""
    if not previous:
        return None
    match = CONTEXT_PREFIX.match(gap)
    pronoun = match.group('pronoun')
    if pronoun in ('它', '其', '该物品', '该垃圾') and len(previous) != 1:
        return None
    if pronoun in ('它们', '这些物品') and len(previous) < 2:
        return None
    return gap[match.end():], match.end()


def is_topic(text, start, end, items):
    """Only a noun list or a disposal topic may establish an implicit subject."""
    if not items:
        return []
    group = coordinated(text, items, items[-1])
    prefix = text[start:group[0]['start']]
    suffix = text[group[-1]['end']:end]
    if re.fullmatch(r'\s*(?:对于|关于|至于|投放|处理|丢弃)?\s*', prefix) and re.fullmatch(
            r'\s*(?:等(?:物品|垃圾)?|(?:在)?(?:投放|处理|丢弃)?(?:前|时)|的投放要求)?\s*', suffix):
        return group
    return []


def split_clauses(sentence, offset, lexical):
    boundaries = {0, len(sentence)}
    for match in re.finditer(r'[，,；;。！？?!]|(?=而(?:是|属于|应)|但是|但(?:它|应|属于|是))', sentence):
        boundaries.update((match.start(), match.end()))
    for item in lexical:
        if item['type'] != 'ITEM' or not offset <= item['start'] < offset + len(sentence):
            continue
        prefix = sentence[:item['start'] - offset]
        conjunction = re.search(r'(?:并且|而且|同时|但是|而|但|并)\s*$', prefix)
        following = sentence[item['end'] - offset:]
        if conjunction and re.match(r'(?:是|属于|归为|应|需要|需|必须|要)', following):
            boundaries.add(conjunction.start())
    points = sorted(boundaries)
    return [sentence[a:b] for a, b in zip(points, points[1:])]


def extract_explicit(text):
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_LEN:
        raise ValueError('请输入 1 至 128 字的文本')
    entities = mentions(text)
    lexical = list(entities)
    triples, seen = [], set()

    def add(head, tail, relation):
        key = (head.get('canonical', head['text']), relation, tail.get('canonical', tail['text']))
        if key in seen:
            return
        seen.add(key)
        triples.append({'head': head['text'], 'relation': relation, 'tail': tail['text'],
                        'head_start': head['start'], 'head_end': head['end'],
                        'tail_start': tail['start'], 'tail_end': tail['end'],
                        'canonical_head': key[0], 'canonical_tail': key[2],
                        'confidence': None, 'extraction_source': 'sentence_rule',
                        'review_status': 'pending', 'evidence': text})
        if tail not in entities:
            entities.append(tail)

    previous = []
    for sentence in re.finditer(r'[^。！？?!\n]+[。！？?!]?', text):
        s = sentence.group()
        if (HYPOTHETICAL.search(s) or re.search(r'[？?]|(?:吗|么|呢)[。！!]?$', s)
                or re.search(r'(?:是|为)(?:错误|错的|不正确|不对)|说法(?:有误|不对|错误)|需要核实|尚未确认|有待确认', s)):
            previous = []
            continue
        # Cross-sentence ellipsis requires an explicit pronoun; do not guess a new topic.
        if not re.match(r'\s*(?:它们|它|其|这些物品|该物品|该垃圾)', s):
            previous = []
        cursor = 0
        for clause in split_clauses(s, sentence.start(), lexical):
            start = sentence.start() + cursor
            cursor += len(clause)
            end = sentence.start() + cursor
            if not clause or clause in '，,；;。！？?!':
                if clause and clause in '；;':
                    previous = []
                continue
            local = [e for e in lexical if start <= e['start'] and e['end'] <= end]
            items = [e for e in local if e['type'] == 'ITEM']
            cats = [e for e in local if e['type'] == 'CATEGORY']
            active = []
            if UNCERTAIN.search(clause):
                previous = []
                continue
            if NEGATIVE.search(clause):
                # Retain only the grammatical subject for an immediately following correction.
                before = [e for e in items if e['end'] <= start + NEGATIVE.search(clause).start()]
                previous = coordinated(text, before, before[-1]) if before else []
                continue

            # Ordered parallel classifications require equal-length explicit lists.
            parallel = re.search(r'分别(?:属于|是|为|归为)', clause)
            parallel_handled = bool(parallel)
            if parallel:
                before = [e for e in items if e['end'] <= start + parallel.start()]
                heads = coordinated(text, before, before[-1]) if before else previous
                targets = [e for e in cats if e['start'] >= start + parallel.end()]
                if (heads and len(heads) == len(targets)
                        and all(COORDINATION.fullmatch(text[a['end']:b['start']]) for a, b in zip(targets, targets[1:]))
                        and (not before or not text[before[-1]['end']:start + parallel.start()].strip())):
                    for head, tail in zip(heads, targets):
                        add(head, tail, 'BELONGS_TO')
                    active = heads

            for target in ([] if parallel_handled else cats):
                # An unqualified category list is ambiguous, not two classifications.
                if any(other != target and (COORDINATION.fullmatch(text[min(target['end'], other['end']):max(target['start'], other['start'])])) for other in cats):
                    continue
                heads = [e for e in items if e['end'] <= target['start']]
                gap = None
                selected = []
                if heads:
                    selected = coordinated(text, heads, heads[-1])
                    gap = text[heads[-1]['end']:target['start']]
                else:
                    carried = context_gap(text[start:target['start']], previous)
                    if carried:
                        gap, _ = carried
                        selected = previous
                if gap is not None and CATEGORY_LINK.fullmatch(gap):
                    # “香蕉皮是湿垃圾桶” describes a container, not category membership.
                    if not (re.search(r'是|为|[:：]', gap) and re.match(r'(?:桶|收集容器|容器|箱)', text[target['end']:end])):
                        for head in selected:
                            add(head, target, 'BELONGS_TO')
                        active = selected
                following = [e for e in items if e['start'] >= target['end']]
                if following and re.fullmatch(r'\s*(?:这一类别)?(?:的(?:物品|垃圾)?)?(?:主要)?(?:包括|包含|有|例如|比如|如)\s*[:：]?\s*', text[target['end']:following[0]['start']]):
                    selected = [following[0]]
                    for head in following[1:]:
                        if not COORDINATION.fullmatch(text[selected[-1]['end']:head['start']]):
                            break
                        selected.append(head)
                    for head in selected:
                        add(head, target, 'BELONGS_TO')
                    active = selected

            # Scan actions, binding their subject before consuming container/tool mentions.
            consumed = start
            for action in METHOD_ACTION.finditer(clause):
                action_start = start + action.start()
                if (action_start < consumed or re.match(r'(?:之)?(?:前|时)', clause[action.end():])
                        or (action.group() == '投放' and clause[action.end():].startswith('后'))):
                    continue
                before = [e for e in items if e['end'] <= action_start]
                selected, prefix, prefix_start = [], None, action_start
                if before:
                    head = before[-1]
                    candidate = METHOD_PREFIX.fullmatch(text[head['end']:action_start])
                    # Instrument/location mentions are not the subject of a disposal action.
                    if candidate and not re.search(r'(?:用|在|从|向|往|到)\s*$', text[start:head['start']]):
                        selected = coordinated(text, before, head)
                        prefix, prefix_start = candidate, head['end']
                    elif active and head in active:
                        # A classification may be followed immediately by its handling predicate.
                        linked = [t for t in triples if t['relation'] == 'BELONGS_TO'
                                  and t['head_start'] == head['start']
                                  and head['end'] <= t['tail_end'] <= action_start]
                        if linked:
                            boundary = linked[-1]['tail_end']
                            carried = context_gap(text[boundary:action_start], active)
                            if carried:
                                gap, offset = carried
                                candidate = METHOD_PREFIX.fullmatch(gap)
                                if candidate:
                                    selected, prefix, prefix_start = active, candidate, boundary + offset
                else:
                    carried = context_gap(text[start:action_start], previous)
                    if carried:
                        gap, offset = carried
                        candidate = METHOD_PREFIX.fullmatch(gap)
                        if candidate:
                            selected, prefix, prefix_start = previous, candidate, start + offset
                if not selected or HISTORY.search(text[start:action_start]):
                    continue
                # Bare movement to an arbitrary place (“放入书包”) is not a disposal requirement.
                tail_end = end
                reason = re.search(r'以免|以便|从而|因为|防止|避免|这样', text[action_start:end])
                if reason:
                    tail_end = action_start + reason.start()
                while tail_end > action_start and text[tail_end-1].isspace():
                    tail_end -= 1
                if MOVE_ACTION.match(action.group()) and not DISPOSAL_DESTINATION.search(text[action_start:tail_end]):
                    continue
                # Do not infer handling of every member in a “分别” statement.
                if '分别' in text[prefix_start:action_start] and len(selected) > 1:
                    continue
                method_start = action_start
                sequence = prefix.group('sequence')
                if sequence and sequence.strip() not in ('先', '首先'):
                    method_start = prefix_start + prefix.start('sequence')
                target = entity(text, method_start, tail_end, 'METHOD')
                for head in selected:
                    add(head, target, 'DISPOSE_WITH')
                active = selected
                consumed = tail_end
            previous = active or is_topic(text, start, end, items)

    # Keep entities used as relation endpoints; suppress only fragments of a method.
    methods = [e for e in entities if e['type'] == 'METHOD']
    endpoints = {(t[k + '_start'], t[k + '_end']) for t in triples for k in ('head', 'tail')}
    entities = [e for e in entities if e['type'] == 'METHOD' or (e['start'], e['end']) in endpoints
                or not any(m['start'] <= e['start'] and e['end'] <= m['end'] for m in methods)]
    return {'mode': 'dictionary_baseline', 'entities': sorted(entities, key=lambda e: e['start']),
            'triples': triples,
            'note': '词典与句式规则抽取，不是神经网络预测；按原文提取陈述，未核对分类事实，候选需人工审核。'}


def combine(text, neural):
    """Apply explicit clause constraints and label rule backfills without fake scores."""
    result=extract_explicit(text)
    for triple in result['triples']:
        matching=next((n for n in neural['triples'] if n['head']==triple['head'] and n['tail']==triple['tail'] and n['relation']==triple['relation']),None)
        if matching:
            triple['extraction_source']='neural_and_rule'
            triple['confidence']=matching['confidence']
            triple['confidence_kind']=matching.get('confidence_kind','uncalibrated_relation_softmax')
    result.update({'mode':'hybrid','model_used':True,'pipeline_version':'clause_guard_v2',
                   'note':'BiLSTM-CRF + BiGRU-Attention 与词典边界、分句规则联合抽取。规则补全不显示模型分数；原始神经模型可单独对照。抽取只反映原文陈述，候选需人工审核。'})
    return result
