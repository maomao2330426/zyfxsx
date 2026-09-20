"""仅对明确物品返回目录证据，不根据子串匹配猜测物态。"""
import re
from .common import MAX_LEN, identity
from .dataset import normalize


def answer(kb,question):
    if not isinstance(question,str) or not 1<=len(question.strip())<=MAX_LEN:
        raise ValueError('请输入 1 至 128 字的问题')
    subject=normalize(question).strip('？?。！! ')
    subject=re.sub(r'^(请问|请告诉我|帮我查一下)\s*','',subject)
    subject=re.sub(r'(属于什么垃圾|是什么垃圾|是哪类垃圾|怎么分类|如何分类|怎么扔|怎么投放|如何投放|怎么处理)$','',subject).strip()
    subject=kb.aliases.get(subject,subject)
    exact=next((row for row in kb.rows if row['name']==subject),None)
    if exact is None:
        candidates=kb.search(subject,limit=6)['items'] if subject else []
        return {'status':'clarify' if candidates else 'unknown','items':candidates,'triples':[],
                'answer':'请确认具体物品及物态；下方仅为名称匹配候选，不能据此直接判断。' if candidates else
                         '暂无可直接回答的证据，请使用具体物品名称。未知物品不会自动猜测分类。'}
    external=exact['provenance']=='external_dataset'
    prefix='外部数据集标注' if external else '教学目录标注'
    method=exact.get('method')
    edges=[edge for edge in kb.graph['edges'] if edge['source']==identity('ITEM',subject)]
    names={node['id']:node['name'] for node in kb.graph['nodes']}
    return {'status':'reference' if external else 'answered','items':[exact],
            'answer':f"{prefix}：{subject} → {exact['category']}。"+(f"投放要求：{method}。" if method else '来源未提供投放方法，不自动补造。'),
            'notice':exact['note'],'triples':[{**edge,'head':names[edge['source']],'tail':names[edge['target']]} for edge in edges]}
