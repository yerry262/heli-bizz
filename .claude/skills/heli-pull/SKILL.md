---
name: heli-pull
description: Refresh the heli-bizz FAA helicopter registry data, report what's new, and update the state/local contacts list. Use when the user says "pull latest heli data", "refresh registry", or "/heli-pull".
---

# heli-pull

1. From the repo root (`/home/yerry/CLAUDE_CORNER/heli-bizz`), run `bash scripts/auto_pull.sh` (add `--force` to redownload even if the cache is fresh). Let output stream; never pipe through tail.
2. Read the summary it prints (total, new this run, removed, state/local count).
3. If new entities appeared, list them for the user with registrant name, city/state, and N-number (query `data/heli.db`: `SELECT n_number, registrant_name, city, state FROM entities WHERE first_seen = (SELECT max(ran_at) ... )` or use the `is_new` flag in `data/entities.json`).
4. Mention any new state/local agencies appended to `data/contacts.md`.
5. Offer to open the dashboard (`python3 serve.py`).
