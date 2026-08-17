# -*- coding: utf-8 -*-
"""处理芙卡洛斯壁纸：裁剪 16:9 + 压缩，输出到 dsh dist 静态目录"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from PIL import Image

src = r"D:\steam\steam\steamapps\workshop\content\431960\3069695514\preview.jpg"
outdir = r"C:\Users\23001\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\dsh-web-frontend\dist"

img = Image.open(src)
print('原图:', img.size, img.mode)

# 裁成 16:9：宽保持 1024，高裁成 1024*9/16=576，居中裁剪
w, h = img.size
target_ratio = 16 / 9
cur_ratio = w / h
if cur_ratio > target_ratio:
    new_w = int(h * target_ratio)
    x0 = (w - new_w) // 2
    img = img.crop((x0, 0, x0 + new_w, h))
else:
    new_h = int(w / target_ratio)
    y0 = (h - new_h) // 2
    img = img.crop((0, y0, w, y0 + new_h))
print('裁剪后:', img.size)

# 放大到 1920x1080（拉伸或保持比例——这里保持比例后补到目标）
img = img.resize((1920, 1080), Image.LANCZOS)
print('最终尺寸:', img.size)

# 压缩保存：quality 72 适中，progressive
out = os.path.join(outdir, "bg_furina.jpg")
img.save(out, "JPEG", quality=72, optimize=True, progressive=True)
print('已保存:', out)
print('大小: %.2f MB' % (os.path.getsize(out) / 1048576))
