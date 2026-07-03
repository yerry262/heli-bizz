---
name: heli-contacts
description: Find and fill in publicly listed contact info (official phone/email/website) for state & local helicopter operator agencies in heli-bizz/data/contacts.md. Use when the user asks to find contacts or outreach info for helicopter operators.
---

# heli-contacts

1. Run `python3 scripts/find_contacts.py` from the repo root to append any newly discovered state/local agencies to `data/contacts.md`.
2. Pick entries whose Phone/Email are still `_(fill in)_` (batch of ~5-10 per run).
3. For each, use WebSearch/WebFetch to find the agency's **official public** contact page (e.g. "<agency name> <city> <state> aviation unit contact"). Only record publicly listed office phone numbers, general emails, and websites from official government pages — no personal or scraped-from-directories info.
4. Edit `data/contacts.md` in place: replace the placeholder Phone/Email lines and add the official website URL under Notes, citing the source page.
5. Report how many entries were completed and how many remain.
