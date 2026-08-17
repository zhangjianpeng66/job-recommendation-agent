# -*- coding: utf-8 -*-
"""抽查 rejectFlags 判定质量"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
p = r'C:\Users\23001\AppData\Roaming\reasonix\global-workspace\job-recommendation\data\jobs_clean.json'
jobs = json.load(open(p, encoding='utf-8'))
print('=== 纯销售标记样例 ===')
for j in jobs:
    if '纯销售' in j['rejectFlags']:
        print(f"{j['company']} | {j['title']} | subCat={j['subCat']} | {j['jobType']}")
print('\n=== 纯技术标记样例 ===')
for j in jobs:
    if '纯技术' in j['rejectFlags']:
        print(f"{j['company']} | {j['title']} | subCat={j['subCat']}")
print('\n=== 未标记但 title 含敏感词（疑似漏网） ===')
import re
for j in jobs:
    if not j['rejectFlags'] and re.search(r'销售|研发|算法|开发|测试|运维', j['title']):
        print(f"{j['company']} | {j['title']} | subCat={j['subCat']}")
