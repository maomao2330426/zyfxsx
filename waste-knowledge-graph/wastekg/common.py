import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DEFAULT_MODEL_DIR = ROOT / 'models_manual'
CATEGORIES = ['可回收物', '干垃圾', '湿垃圾', '有害垃圾']
TAGS = ['O', 'B-ITEM', 'I-ITEM', 'B-CATEGORY', 'I-CATEGORY', 'B-METHOD', 'I-METHOD']
RELATIONS = ['NO_RELATION', 'BELONGS_TO', 'DISPOSE_WITH']
REL_NAMES = {'BELONGS_TO': '属于', 'DISPOSE_WITH': '投放要求'}
MAX_LEN = 128


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def write_jsonl(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')


def clean_text(text):
    text = re.sub(r'\[\d+\]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def identity(kind, name):
    return hashlib.sha256((kind + ':' + name).encode()).hexdigest()[:20]


def model_signature(directory):
    digest=hashlib.sha256()
    for name in ('ner.weights.h5','relation.weights.h5','vocab.json'):
        path=Path(directory)/name
        if not path.exists():return None
        digest.update(name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def spans(tags, text):
    result = []
    start, kind = None, None
    for i, tag in enumerate(list(tags) + ['O']):
        if start is not None and tag != 'I-' + kind:
            result.append({'start': start, 'end': i, 'type': kind, 'text': text[start:i]})
            start, kind = None, None
        if tag.startswith('B-'):
            start, kind = i, tag[2:]
    return result


def validate_sample(sample):
    text = sample['text']
    if not text or len(text) > MAX_LEN:
        raise ValueError('句子为空或超过 128 字，请先切分')
    occupied = set()
    for ent in sample['entities']:
        start, end = ent['start'], ent['end']
        assert 0 <= start < end <= len(text)
        assert text[start:end] == ent['text']
        assert ent['type'] in {'ITEM', 'CATEGORY', 'METHOD'}
        assert not occupied.intersection(range(start, end))
        occupied.update(range(start, end))
    assert sample['relation'] in RELATIONS
    assert 0 <= sample['head'] < len(sample['entities'])
    assert 0 <= sample['tail'] < len(sample['entities'])
    assert sample['head'] != sample['tail']


def bio_tags(sample):
    validate_sample(sample)
    tags = ['O'] * len(sample['text'])
    for ent in sample['entities']:
        tags[ent['start']] = 'B-' + ent['type']
        tags[ent['start'] + 1:ent['end']] = ['I-' + ent['type']] * (ent['end'] - ent['start'] - 1)
    return tags
