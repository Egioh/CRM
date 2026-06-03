"""Audit i18n coverage — writes missing_i18n.txt."""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from i18n import _CZ, _EN  # noqa: E402

keys: set[str] = set()
for root, _, files in os.walk(os.path.join(ROOT, "templates")):
    for name in files:
        if not name.endswith(".html"):
            continue
        text = open(os.path.join(root, name), encoding="utf-8").read()
        for m in re.finditer(r"_\(['\"]([^'\"]+)['\"]\)", text):
            keys.add(m.group(1))

app_py = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
for m in re.finditer(r"_tr\(['\"]([^'\"]+)['\"]\)", app_py):
    keys.add(m.group(1))

# hardcoded Russian in templates without _()
hardcoded = []
for root, _, files in os.walk(os.path.join(ROOT, "templates")):
    for name in files:
        if not name.endswith(".html"):
            continue
        path = os.path.join(root, name)
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if re.search(r"[А-Яа-яЁё]{4,}", line) and "_(" not in line and "{{" in line:
                if "url_for" in line or "csrf" in line or "strftime" in line:
                    continue
            if 'placeholder="' in line and re.search(r'placeholder="[А-Яа-я]', line):
                hardcoded.append(f"{path}:{i}: {line.strip()}")

missing_en = sorted(k for k in keys if k not in _EN)
missing_cz = sorted(k for k in keys if k not in _CZ)

out = os.path.join(ROOT, "missing_i18n.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(f"Template+_tr keys: {len(keys)}\n\n")
    f.write(f"Missing EN ({len(missing_en)}):\n")
    for k in missing_en:
        f.write(f"  {k}\n")
    f.write(f"\nMissing CZ ({len(missing_cz)}):\n")
    for k in missing_cz:
        f.write(f"  {k}\n")
    f.write(f"\nHardcoded placeholders ({len(hardcoded)}):\n")
    for h in hardcoded:
        f.write(f"  {h}\n")

print("written", out)
