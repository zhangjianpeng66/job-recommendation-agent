# -*- coding: utf-8 -*-
"""补充检查：subCat 分布、title+subCat 组合样例、与 public-static/jobs.json 差异"""
import json, collections, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
base = r'C:\Users\23001\AppData\Roaming\reasonix\global-workspace\job-recommendation\assets\job-aggregation-site'

with open(base + r'\data\jobs.json', encoding='utf-8') as f:
    jobs = json.load(f)

print('== subCat 分布 ==')
c = collections.Counter(str(j.get('subCat')) for j in jobs)
for k, n in c.most_common(40):
    print(f'{n:5d}  {k}')

print('\n== subCat 为空的样例 ==')
empty = [j for j in jobs if not j.get('subCat')]
for j in empty[:5]:
    print(j['company'], '|', j['title'], '|', j['jobType'])

print('\n== title+subCat 组合样例（每公司取2条） ==')
seen = collections.Counter()
for j in jobs:
    if seen[j['company']] >= 2:
        continue
    seen[j['company']] += 1
    print(j['company'], '|', j['title'], '|', j.get('subCat'), '|', j['jobType'], '|', j['category'])

print('\n== 实习+内容 category 的 subCat 分布 ==')
c = collections.Counter(str(j.get('subCat')) for j in jobs if j['jobType'] == '实习' and j['category'] == '内容')
for k, n in c.most_common(15):
    print(f'{n:5d}  {k}')

print('\n== 销售/商务 title 及 subCat ==')
for j in jobs:
    if any(w in j['title'] for w in ['销售', '商务', 'BD', '营销', '市场']):
        print(j['company'], '|', j['title'], '|', j.get('subCat'), '|', j['jobType'])
