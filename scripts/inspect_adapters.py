# -*- coding: utf-8 -*-
"""只读调研：adapters.ts 已适配公司 + JobRadarUpdate 任务详情"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1) adapters.ts 适配的公司/平台
p = r'C:\Users\23001\AppData\Roaming\reasonix\global-workspace\job-recommendation\assets\job-aggregation-site\lib\adapters.ts'
src = open(p, encoding='utf-8').read()
print("=== adapters.ts 长度:", len(src))
# 常见模式：name: 'xx' / company: 'xx' / host: 'xx'
pats = re.findall(r"(?:name|company|host|site|platform|adapter)\s*[:=]\s*['\"]([^'\"]{2,40})['\"]", src)
uniq = list(dict.fromkeys(pats))
print("=== 提取的标识符（前60个）===")
for u in uniq[:60]:
    print(" ", u)
