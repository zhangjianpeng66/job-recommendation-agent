# -*- coding: utf-8 -*-
"""注入完整背景方案：对话框透明 + 背景低帧率动态 + 侧栏流动光效"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:\Users\23001\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\dsh-web-frontend\dist\index.html"
html = open(path, encoding='utf-8').read()

NEW_STYLE = """    <style>
      /* ==== furina-bg v3：对话框透明 + 背景动态 + 侧栏流动 ==== */
      :root, body {
        --dsw-alias-bg-base: transparent !important;
        --dsw-alias-bg-layer-1: transparent !important;
        --dsw-alias-bg-layer-2: transparent !important;
        --dsw-alias-bg-layer-3: transparent !important;
        --dsw-mask-blur: none !important;
        --dsw-mask-blur-heavy: none !important;
      }
      body { background: transparent !important; }

      /* 背景层：Ken Burns 缓慢动态（20s 周期，低耗） */
      body::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -2;
        background: url('/bg_furina.jpg') center/cover no-repeat;
        animation: furina-kenburns 24s ease-in-out infinite alternate;
        will-change: transform;
        pointer-events: none;
      }
      @keyframes furina-kenburns {
        0%   { transform: scale(1.02) translateX(0); }
        50%  { transform: scale(1.08) translateX(-1.2%); }
        100% { transform: scale(1.02) translateX(0); }
      }

      /* 对话/消息/输入区全部透明 */
      #root, #root > div, [data-ds-conversation], ._boot_9gj4p_6 {
        background: transparent !important;
      }

      /* 侧栏流动光效（DeepSeek 官网风格）：半透明渐变扫过 */
      [data-ds-sidebar], aside, nav {
        background: rgba(255, 255, 255, 0.18) !important;
        -webkit-backdrop-filter: blur(14px) !important;
        backdrop-filter: blur(14px) !important;
        position: relative;
        overflow: hidden;
      }
      [data-ds-sidebar]::after, aside::after, nav::after {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: conic-gradient(from 0deg, transparent 0deg, rgba(120, 180, 255, 0.12) 60deg, transparent 120deg, rgba(200, 160, 255, 0.10) 200deg, transparent 260deg, rgba(120, 255, 220, 0.08) 320deg, transparent 360deg);
        animation: furina-flow 12s linear infinite;
        pointer-events: none;
        z-index: 0;
      }
      @keyframes furina-flow {
        0%   { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }

      /* 消息气泡：半透明磨砂（保留可读性） */
      [data-ds-message], ._message, [class*="message"], [class*="bubble"], [class*="chat"] {
        background: rgba(255, 255, 255, 0.55) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        backdrop-filter: blur(8px) !important;
      }
    </style>"""

# 删除所有旧 <style> 块
html = re.sub(r'<style>[\s\S]*?</style>', '', html)

# 插入新样式
html = html.replace('<title>DeepSeek Harness</title>',
                    '<title>DeepSeek Harness</title>\n' + NEW_STYLE)

open(path, 'w', encoding='utf-8').write(html)
print('style 块:', html.count('<style>'))
print('kenburns:', 'furina-kenburns' in html)
print('flow:', 'furina-flow' in html)
print('mask-blur none:', '--dsw-mask-blur: none' in html)
print('transparent:', 'transparent !important' in html)
