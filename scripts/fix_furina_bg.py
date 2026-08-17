# -*- coding: utf-8 -*-
"""重写 index.html：替换旧背景注入为新的透明背景方案"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:\Users\23001\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\dsh-web-frontend\dist\index.html"
html = open(path, encoding='utf-8').read()

NEW_STYLE = """    <style>
      /* 动态背景：芙卡洛斯壁纸（覆盖 dsh 默认白色背景） */
      :root, body {
        --dsw-alias-bg-base: transparent !important;
        --dsw-alias-bg-layer-1: transparent !important;
        --dsw-alias-bg-layer-2: transparent !important;
        --dsw-alias-bg-layer-3: transparent !important;
      }
      body {
        background: transparent !important;
      }
      body::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        background: url('/bg_furina.jpg') center/cover no-repeat fixed;
        pointer-events: none;
      }
    </style>"""

# 删除所有旧 <style> 注入块（含 bg_furina 的）
html = re.sub(r'<style>\s*/\* 动态背景[^*]*\*/.*?</style>', '', html, flags=re.S)
html = re.sub(r'<style>\s*/\* 动态背景层[^*]*\*/.*?</style>', '', html, flags=re.S)

# 在 <title> 后插入新样式
if 'bg_furina' in html and '透明背景' not in html:
    html = html.replace('<title>DeepSeek Harness</title>',
                        '<title>DeepSeek Harness</title>\n' + NEW_STYLE)
elif '透明背景' not in html:
    html = html.replace('<title>DeepSeek Harness</title>',
                        '<title>DeepSeek Harness</title>\n' + NEW_STYLE)

open(path, 'w', encoding='utf-8').write(html)
print('完成。检查:')
print('  含透明背景:', 'transparent !important' in html)
print('  含 z-index -1:', 'z-index: -1' in html)
print('  含 bg_furina:', 'bg_furina' in html)
print('  旧 blur 残留:', 'blur' in html)
