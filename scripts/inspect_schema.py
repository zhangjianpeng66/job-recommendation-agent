# -*- coding: utf-8 -*-
"""检查 jobs.json 字段结构、填充率、值分布（只读诊断，可复用）"""
import json, collections, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

p = r'C:\Users\23001\AppData\Roaming\reasonix\global-workspace\job-recommendation\assets\job-aggregation-site\data\jobs.json'
with open(p, encoding='utf-8') as f:
    jobs = json.load(f)

print('总条数:', len(jobs))
all_keys = set()
for j in jobs:
    all_keys.update(j.keys())

print('\n== 字段填充率 ==')
for k in sorted(all_keys):
    n = sum(1 for j in jobs if j.get(k) not in (None, '', [], {}))
    print(f'{k}: {n}/{len(jobs)}')

print('\n== 枚举值分布 ==')
for k in ['jobType', 'category', 'companyType', 'priorityLayer', 'status', 'sourceCredibility', 'education']:
    c = collections.Counter(str(j.get(k)) for j in jobs)
    print(f'{k}: {dict(c)}')

print('\n== 高频公司 TOP20 ==')
c = collections.Counter(j['company'] for j in jobs)
for name, n in c.most_common(20):
    print(f'{n:5d}  {name}')

print('\n== riskFlags 分布 ==')
c = collections.Counter(tuple(j.get('riskFlags') or []) for j in jobs)
for k, n in c.most_common(10):
    print(f'{n:5d}  {k}')

print('\n== location 样例 ==')
for j in jobs[:5]:
    print(repr(j['location']))

print('\n== qualityScore 分布 ==')
c = collections.Counter(j.get('qualityScore') for j in jobs)
print(dict(c))

print('\n== title 含"销售" 样例 ==')
s = [j for j in jobs if '销售' in j['title']]
print('数量:', len(s))
for j in s[:3]:
    print(j['company'], '|', j['title'], '|', j['jobType'])

print('\n== title 含"内容" 样例 ==')
s = [j for j in jobs if '内容' in j['title']]
print('数量:', len(s))
for j in s[:5]:
    print(j['company'], '|', j['title'], '|', j['jobType'], '|', j['category'])

print('\n== title 含"算法/研发/后端/前端/测试" 样例 ==')
s = [j for j in jobs if any(w in j['title'] for w in ['算法', '研发', '后端', '前端', '测试', '开发'])]
print('数量:', len(s))
for j in s[:5]:
    print(j['company'], '|', j['title'], '|', j['jobType'], '|', j['category'])
