#!/usr/bin/env python3
"""Build a growing contacts list for state/local helicopter operators.

Reads data/entities.json (produced by heli_tracker.py), filters to
state/local government registrants, and appends any not-yet-listed
agencies to data/contacts.md with their registered address and ready-made
lookup links for official phone/email. Never removes existing entries;
manual edits below each entry's "Notes:" line are preserved.
"""
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTITIES = ROOT / "data" / "entities.json"
CONTACTS = ROOT / "data" / "contacts.md"

HEADER = "# State & Local Helicopter Operator Contacts\n\nAuto-appended by scripts/find_contacts.py — new agencies are added at the end; existing entries (and your notes) are never modified.\n"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


COMPANY_CODES = {"2", "3", "4", "7", "8", "9"}


def wanted(e: dict, segment: str) -> bool:
    if segment == "statelocal":
        return e.get("is_state_local") == 1
    if segment == "gov":
        return e.get("is_government") == 1
    if segment == "private":
        return e.get("registrant_type_code") in COMPANY_CODES
    if segment == "all":
        return e.get("is_government") == 1 or e.get("registrant_type_code") in COMPANY_CODES
    return False


def main() -> int:
    segment = "statelocal"
    min_fleet = 1
    for a in sys.argv[1:]:
        if a.startswith("--segment="):
            segment = a.split("=", 1)[1]
        elif a.startswith("--min-fleet="):
            min_fleet = int(a.split("=", 1)[1])

    if not ENTITIES.exists():
        print(f"no {ENTITIES} yet — run heli_tracker.py first")
        return 1
    data = json.loads(ENTITIES.read_text())
    # Exclude unmanned drones/UAS by default — they have no pilot to sell to.
    ents = [e for e in data.get("entities", [])
            if wanted(e, segment) and e.get("is_unmanned") != 1]

    # one entry per agency (name+state), not per aircraft
    agencies = {}
    for e in ents:
        key = (e.get("registrant_name", "").strip(), e.get("state", "").strip())
        agencies.setdefault(key, {"e": e, "n_numbers": []})
        agencies[key]["n_numbers"].append(e.get("n_number", ""))

    existing = CONTACTS.read_text() if CONTACTS.exists() else HEADER
    added = 0
    out = [existing.rstrip() + "\n"]
    for (name, state), info in sorted(agencies.items()):
        if len(set(info["n_numbers"])) < min_fleet:
            continue
        anchor = f"<!-- id:{slug(name)}-{state.lower()} -->"
        if anchor in existing:
            continue
        e = info["e"]
        q = urllib.parse.quote_plus(f"{name} {e.get('city','')} {state} phone contact")
        out.append(
            f"\n## {name} ({state})\n{anchor}\n"
            f"- Address: {e.get('street','')}, {e.get('city','')}, {state} {e.get('zip','')}\n"
            f"- Aircraft: {', '.join(sorted(set(info['n_numbers'])))}\n"
            f"- Lookup: https://www.google.com/search?q={q}\n"
            f"- Phone: _(fill in)_\n- Email: _(fill in)_\n- Notes:\n"
        )
        added += 1
    if added:
        CONTACTS.parent.mkdir(parents=True, exist_ok=True)
        CONTACTS.write_text("".join(out))
    print(f"{len(agencies)} operators in segment '{segment}' (min fleet {min_fleet}); {added} new appended to {CONTACTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
