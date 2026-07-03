#!/usr/bin/env python3
"""List agencies in data/contacts.md still missing phone/email, prioritized by fleet size."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
text = (ROOT / "data" / "contacts.md").read_text()
blocks = re.split(r"\n(?=## )", text)
todo = []
for b in blocks:
    m = re.match(r"## (.+)", b)
    if not m or "- Phone: _(fill in)_" not in b:
        continue
    aircraft = re.search(r"- Aircraft: (.+)", b)
    fleet = len(aircraft.group(1).split(",")) if aircraft else 0
    todo.append((fleet, m.group(1)))
todo.sort(reverse=True)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
print(f"{len(todo)} agencies missing contacts. Top {n} by fleet size:")
for fleet, name in todo[:n]:
    print(f"  {fleet:3d}  {name}")
