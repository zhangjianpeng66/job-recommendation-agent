# -*- coding: utf-8 -*-
"""干净重写：确保只有一个正确的透明背景 style 块"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:\Users\23001\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\dsh-web-frontend\dist\index.html"
html = open(path, encoding='utf-8').read()

NEW_STYLE = """    <style>
      /* furina-bg */
      :root, body {
        --dsw-alias-bg-base: transparent !important;
        --dsw-alias-bg-layer-1: transparent !important;
        --dsw-alias-bg-layer-2: transparent !important;
        --dsw-alias-bg-layer-3: transparent !important;
      }
      body { background: transparent !important; }
      body::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        background: url('/bg_furina.jpg') center/cover no-repeat fixed;
        pointer-events: none;
      }
    </style>"""

# 删除所有 <style> 块（无论内容）
html = re.sub(r'<style>[\s\S]*?</style>', '', html)

# 插入新样式
html = html.replace('<title>DeepSeek Harness</title>',
                    '<title>DeepSeek Harness</title>\n' + NEW_STYLE)

open(path, 'w', encoding='utf-8').write(html)
print('style 块数量:', html.count('<style>'))
print('透明背景:', 'transparent !important' in html)
print('bg_furina:', 'bg_furina' in html)
print('blur:', 'blur' in html)
print('z-index -1:', 'z-index: -1' in html)
