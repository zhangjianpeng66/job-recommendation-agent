# -*- coding: utf-8 -*-
"""扫各 UI 插件注册的 details/slot 名"""
import sys, io, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
base = r"C:\Users\23001\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai"
pkgs = ["dsh-client-ui-deliverables","dsh-client-ui-goal","dsh-client-ui-plan","dsh-client-ui-subagent",
        "dsh-client-ui-skill","dsh-client-ui-workflow-run","dsh-client-ui-trajectory","dsh-client-ui-jobs",
        "dsh-client-ui-user-questions","dsh-client-ui-workspace","dsh-client-ui-model-selection",
        "dsh-client-ui-message-feedback","dsh-client-ui-attachment","dsh-client-ui-commands"]
for pkg in pkgs:
    d = os.path.join(base, pkg, "lib", "types")
    if not os.path.isdir(d):
        print(f"{pkg}: 无 types")
        continue
    slots = []
    for root, _, files in os.walk(d):
        for fn in files:
            if not fn.endswith(".d.ts"):
                continue
            p = os.path.join(root, fn)
            txt = open(p, encoding='utf-8', errors='ignore').read()
            # 找 SlotMap 里的键
            for m in re.finditer(r"['\"]([a-z]+\.[a-z.]+)['\"]\s*:\s*\{", txt):
                slots.append(m.group(1))
    uniq = sorted(set(slots))
    print(f"{pkg}: {uniq if uniq else '无 slot 注册'}")
