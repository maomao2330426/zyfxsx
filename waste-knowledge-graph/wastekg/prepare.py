"""生成来源可追踪的教学目录与按实体隔离的数据划分。"""
import random
from collections import Counter
from .common import *

GOV = 'https://www.shanghai.gov.cn/gwk/search/content/40b9feaa-53db-472f-8a6b-2c3cf0465def'
GOV_2018 = 'https://www.shanghai.gov.cn/nw42851/20200823/0001-42851_55319.html'
WIKI = 'https://zh.wikipedia.org/wiki/上海市生活垃圾分类制度'

# 清洁度、家庭来源、物态会影响分类；以下是用于教学的典型物态。
GROUPS = [
 ('可回收物', '保持清洁干燥', '报纸 旧书 杂志 纸箱 纸板 打印纸 信封 练习本 宣传单 包装纸 纸袋 挂历 硬纸盒 说明书 纸质文件袋'),
 ('可回收物', '清空内容物后投放', '矿泉水瓶 饮料塑料瓶 洗发水瓶 沐浴露瓶 洗衣液瓶 塑料盆 塑料桶 塑料衣架 饼干铁盒 易拉罐 铁罐 不锈钢盆 铝锅 铁锅 金属衣架'),
 ('可回收物', '包裹尖锐边角', '玻璃瓶 玻璃杯 玻璃罐 平板玻璃 玻璃花瓶'),
 ('可回收物', '保持清洁干燥', '旧外套 旧衬衫 旧裤子 旧床单 旧棉被 旧窗帘 旧毛衣 旧围巾'),
 ('湿垃圾', '沥干水分并去除包装', '苹果皮 香蕉皮 橘子皮 西瓜皮 梨皮 土豆皮 胡萝卜皮 黄瓜皮 菜叶 菜根 玉米粒 米饭 面条 馒头 面包 饼干 蛋糕 茶叶渣 咖啡渣 中药药渣 鸡蛋壳 鸭蛋壳 鱼骨 鸡骨 鸭骨 虾壳 蟹壳 鱼内脏 猪肉 牛肉 鸡肉 鱼肉 果肉 葡萄皮 落花 枯叶 过期豆腐 过期酸奶 过期米饭 花生壳'),
 ('干垃圾', '装袋后投入干垃圾容器', '用过的纸巾 厕纸 湿巾 尿不湿 卫生巾 棉签 棉球 创可贴 胶带 口香糖 烟蒂 扫地灰尘 头发 尘土 猫砂 狗尿垫 污损塑料袋 污损食品袋 破陶瓷碗 破陶瓷杯 碎砖块 一次性筷子 牙签 竹签 木屑 铅笔 橡皮擦 圆珠笔 干燥剂 保鲜膜'),
 ('有害垃圾', '保持完整并单独投放', '废镍镉电池 废氧化汞电池 废荧光灯管 废节能灯 含汞温度计 含汞血压计 废胶片 废相纸'),
 ('有害垃圾', '连同包装单独投放', '过期药片 过期胶囊 过期药膏 过期药水 废油漆 油漆桶 废溶剂 溶剂瓶 废矿物油 矿物油瓶 废杀虫剂 杀虫剂罐 废消毒剂 消毒剂瓶'),
]

ALIASES = {'可回收垃圾': '可回收物', '厨余垃圾': '湿垃圾', '其他垃圾': '干垃圾', '其它垃圾': '干垃圾',
           '香蕉皮儿': '香蕉皮', '矿泉水空瓶': '矿泉水瓶', '快递纸箱': '纸箱', '水银温度计': '含汞温度计', '水银体温计': '含汞温度计'}


def catalog():
    result = []
    for category, method, names in GROUPS:
        for name in names.split():
            if name == '碎砖块':  # 建筑垃圾不混入四分类目录
                continue
            note = '家庭日常生活来源；采用上海四分类教学口径。'
            if category == '可回收物':
                note += '物品须清洁且具备回收条件，污损物品需重新判断。'
            if name == '过期酸奶':
                note += '指内容物，包装另行分类。'
            if name in {'创可贴','棉签','棉球'}:
                note += '指普通家庭少量废弃物，医疗机构废物不适用。'
            result.append({'name': name, 'category': category, 'method': method, 'note': note,
                           'region': '上海', 'provenance': 'curated_example',
                           'source_url': GOV, 'additional_source_url': GOV_2018 if category == '干垃圾' else GOV,
                           'evidence': f'依据分类定义人工编制的典型示例：{name}属于{category}。',
                           'review_status': 'teaching_seed', 'confidence': None})
    return result


def example(text, item, target, kind, relation, template):
    a, b = text.index(item), text.index(target)
    result = {'text': text, 'group': item, 'template': template, 'provenance': 'synthetic_template',
              'entities': [{'start': a, 'end': a+len(item), 'text': item, 'type': 'ITEM'},
                           {'start': b, 'end': b+len(target), 'text': target, 'type': kind}],
              'head': 0, 'tail': 1, 'relation': relation}
    validate_sample(result)
    return result


def build():
    rows = catalog()
    write_json(DATA / 'catalog.json', rows)
    write_json(DATA / 'aliases.json', ALIASES)
    write_json(DATA / 'sources.json', [
        {'id': 'shanghai_2024', 'url': GOV, 'kind': 'government', 'purpose': '分类定义与投放指导', 'access_date': '2026-09-14'},
        {'id': 'shanghai_2018', 'url': GOV_2018, 'kind': 'government', 'purpose': '历史分类示例补充，以2024指引为主要口径', 'access_date': '2026-09-14'},
        {'id': 'encyclopedia', 'url': WIKI, 'kind': 'encyclopedia', 'purpose': '网页采集与清洗实验', 'license': '页面许可见网站，维基文本通常为 CC BY-SA；保留链接与归属'}])
    rng = random.Random(42)
    groups = {}
    for category in CATEGORIES:
        names = [r['name'] for r in rows if r['category'] == category]
        rng.shuffle(names)
        n_train, n_val = int(len(names)*.7), max(1, int(len(names)*.15))
        for i, name in enumerate(names):
            groups[name] = 'train' if i < n_train else ('val' if i < n_train+n_val else 'test')
    datasets = {'train': [], 'val': [], 'test': []}
    templates = [
      ('{i}属于{t}。', 'CATEGORY', 'BELONGS_TO'),
      ('按照上海分类口径，{i}应归入{t}。', 'CATEGORY', 'BELONGS_TO'),
      ('{i}应投入{t}收集容器。', 'CATEGORY', 'BELONGS_TO'),
      ('日常生活中的{i}，其类别是{t}。', 'CATEGORY', 'BELONGS_TO'),
      ('{t}包括{i}。', 'CATEGORY', 'BELONGS_TO'),
      ('请将{i}按{t}进行分类。', 'CATEGORY', 'BELONGS_TO'),
      ('投放{i}时，需要{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('{i}的投放要求是{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('处置{i}前应当{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('对于{i}，建议{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('{i}不是{t}。', 'CATEGORY', 'NO_RELATION'),
      ('不要把{i}混入{t}。', 'CATEGORY', 'NO_RELATION'),
      ('关于{i}和{t}，这里未说明二者的关系。', 'CATEGORY', 'NO_RELATION'),
      ('{i}是否属于{t}？', 'CATEGORY', 'NO_RELATION'),
      ('假如{i}属于{t}，该如何处理？', 'CATEGORY', 'NO_RELATION'),
      ('{i}是一种{t}。', 'CATEGORY', 'BELONGS_TO'),
      ('丢弃的{i}可按{t}处置。', 'CATEGORY', 'BELONGS_TO'),
      ('分类时把{i}放到{t}桶中就可以。', 'CATEGORY', 'BELONGS_TO'),
      ('根据物品的情况，{i}可以划为{t}。', 'CATEGORY', 'BELONGS_TO'),
      ('请注意，{i}应该作为{t}处理。', 'CATEGORY', 'BELONGS_TO'),
      ('{i}这种东西算作{t}，请分类收集。', 'CATEGORY', 'BELONGS_TO'),
      ('一般而言，{t}这一类别包含{i}。', 'CATEGORY', 'BELONGS_TO'),
      ('清理房间发现了{i}，需要丢进{t}对应的容器。', 'CATEGORY', 'BELONGS_TO'),
      ('{i}该怎么扔？它是{t}。', 'CATEGORY', 'BELONGS_TO'),
      ('{i}的垃圾类型为{t}，需分类投放。', 'CATEGORY', 'BELONGS_TO'),
      ('准备丢弃{i}之前，应先{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('请对{i}采取以下处理方式：{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('为了方便收运，{i}需要{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('居民扔掉{i}时，务必{t}，再交给收集人员。', 'METHOD', 'DISPOSE_WITH'),
      ('有关{i}的处理，请记住要{t}。', 'METHOD', 'DISPOSE_WITH'),
      ('{i}到底是不是{t}，仍需要核实。', 'CATEGORY', 'NO_RELATION'),
      ('这份清单列出了{i}与{t}，并未解释分类。', 'CATEGORY', 'NO_RELATION'),
      ('将{i}说成{t}是错误的说法。', 'CATEGORY', 'NO_RELATION'),
      ('有人问{i}能否归到{t}，这里没有给出答案。', 'CATEGORY', 'NO_RELATION'),
      ('如果{i}被当成{t}，还需要进一步确认。', 'CATEGORY', 'NO_RELATION'),
    ]
    for row in rows:
        for ti, (template, kind, rel) in enumerate(templates):
            target = row['method'] if kind == 'METHOD' else row['category']
            if ti in (10, 11, 32):
                target = rng.choice([c for c in CATEGORIES if c != row['category']])
            text=template.format(i=row['name'], t=target)
            prefixes=['','日常生活中，','整理家务时，','请大家注意：','在这个例子里，','根据分类说明，','今天，','处理家庭废弃物时，']
            suffixes=['','请遵守投放点规定。','物品的状态也需要核对。','这里讨论的是生活废弃物。','大家应当认真分类。']
            if ti>=15:
                text=rng.choice(prefixes)+text+rng.choice(suffixes)
            datasets[groups[row['name']]].append(example(text, row['name'], target, kind, rel, ti))
    for split, records in datasets.items():
        rng.shuffle(records)
        write_jsonl(DATA / 'processed' / f'{split}.jsonl', records)
    # 字表仅从训练集拟合，验证/测试未知字使用 UNK。
    chars = sorted(set(''.join(r['text'] for r in datasets['train'])))
    write_json(DATA / 'processed' / 'vocab.json', {'<PAD>': 0, '<UNK>': 1, **{c:i+2 for i,c in enumerate(chars)}})
    manifest = {'seed': 42, 'split_policy': 'stratified_by_category_grouped_by_item',
                'scope': 'template smoke benchmark; not natural-corpus generalization',
                'catalog_items': len(rows), 'categories': dict(Counter(r['category'] for r in rows)),
                'splits': {k: {'sentences': len(v), 'items': sorted(set(s['group'] for s in v)),
                              'relations': dict(Counter(s['relation'] for s in v))} for k,v in datasets.items()}}
    write_json(DATA / 'processed' / 'manifest.json', manifest)
    print(json.dumps({k: len(v) for k,v in datasets.items()}, ensure_ascii=False))
    return rows


if __name__ == '__main__':
    build()
