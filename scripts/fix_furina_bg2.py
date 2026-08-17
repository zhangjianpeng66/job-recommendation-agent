# -*- coding: utf-8 -*-
"""删除旧的 blur 版注入块，只保留新透明版"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:\Users\23001\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\dsh-web-frontend\dist\index.html"
html = open(path, encoding='utf-8').read()

# 删除包含 blur(6px) 的 style 块（旧注入）
html = re.sub(r'<style>[\s\S]*?blur\(6px\)[\s\S]*?</style>', '', html)

open(path, 'w', encoding='utf-8').write(html)

# 验证
print('blur 残留:', 'blur(6px)' in html)
print('透明版保留:', 'transparent !important' in html)
print('style 块数量:', html.count('<style>'))
# 打印所有 style 块
for m in re.finditer(r'<style>[\s\S]*?</style>', html):
    print('--- 块 ---')
    print(m.group(0)[:300])
