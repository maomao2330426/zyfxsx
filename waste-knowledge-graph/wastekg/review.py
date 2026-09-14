"""将逐条人工批准的候选转为可复核导入文件，拒绝无证据或类别冲突。"""
import argparse
from .common import *


def approve(candidates,decisions):
    result=[]
    decisions={d['id']:d for d in decisions if d.get('approved') is True and d.get('reviewer','').strip()}
    for c in candidates:
        decision=decisions.get(c['id'])
        if not decision:continue
        if c['relation'] not in REL_NAMES or not c.get('evidence') or not c.get('source_url'):
            raise ValueError('候选缺少合法关系、证据或来源')
        if c['relation']=='BELONGS_TO' and c['tail'] not in CATEGORIES:
            raise ValueError('分类不在四分类白名单')
        result.append({**c,'review_status':'approved','reviewer':decision['reviewer'],'review_note':decision.get('note','')})
    return result


def merge_catalog(rows,approved):
    by_name={r['name']:dict(r) for r in rows}
    for c in approved:
        if c.get('review_status')!='approved':raise ValueError('只能合并已批准候选')
        r=by_name.get(c['head'])
        if c['relation']=='BELONGS_TO':
            if r and r['category']!=c['tail']:raise ValueError('已有类别冲突，请人工修改目录后重试：'+c['head'])
            if not r:
                by_name[c['head']]={'name':c['head'],'category':c['tail'],'method':'按当地投放点指引投放',
                    'note':'经人工审核的网页候选。','region':'上海','provenance':c.get('provenance','model_candidate'),
                    'source_url':c['source_url'],'evidence':c['evidence'],'review_status':'approved','confidence':c.get('confidence')}
    for c in approved:
        if c['relation']=='DISPOSE_WITH' and c['head'] in by_name:
            by_name[c['head']]['method']=c['tail']
            by_name[c['head']]['method_provenance']={'source_url':c['source_url'],'method_evidence':c['evidence'],
                'provenance':c.get('provenance','model_candidate'),'review_status':'approved'}
    return list(by_name.values())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidates');p.add_argument('decisions');p.add_argument('--merge',action='store_true');args=p.parse_args()
    approved=approve(read_jsonl(args.candidates),read_jsonl(args.decisions))
    write_jsonl(DATA/'approved.jsonl',approved)
    if args.merge:
        rows=read_json(DATA/'catalog.json')
        updated=merge_catalog(rows,approved)
        write_json(DATA/'catalog.before_review.json',rows)
        write_json(DATA/'catalog.json',updated)
    print(f'批准 {len(approved)} 条；请重新构图并重启服务。')
