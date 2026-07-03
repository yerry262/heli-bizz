#!/usr/bin/env python3
"""Build a CRM-ready sales leads CSV: one row per operator, ranked by fleet size.

Joins the per-operator fleet counts from data/entities.json with any
phone/email/website already captured in data/contacts.md. Fleet size is the
key sales signal (more airframes -> more pilots -> more helmets), so rows are
sorted largest-fleet first. Output: data/leads.csv, ready to import into any CRM.

Usage: python3 scripts/export_leads.py [--segment gov|statelocal|private|all]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTITIES = ROOT / "data" / "entities.json"
CONTACTS = ROOT / "data" / "contacts.md"
OUT = ROOT / "data" / "leads.csv"

COMPANY_CODES = {"2", "3", "4", "7", "8", "9"}


def parse_contacts() -> dict:
    """Map 'NAME|ST' -> {phone, email, website} from contacts.md blocks."""
    out = {}
    if not CONTACTS.exists():
        return out
    for b in re.split(r"\n(?=## )", CONTACTS.read_text()):
        m = re.match(r"## (.+?) \(([A-Z]{2})\)", b)
        if not m:
            continue
        key = f"{m.group(1)}|{m.group(2)}"
        def grab(field):
            g = re.search(rf"- {field}: (.+)", b)
            v = g.group(1).strip() if g else ""
            return "" if v.startswith("_(") else v
        out[key] = {"phone": grab("Phone"), "email": grab("Email"), "website": grab("Website")}
    return out


def segment_of(e: dict) -> str:
    if e.get("is_state_local") == 1:
        return "statelocal"
    if e.get("is_government") == 1:
        return "gov"
    if e.get("registrant_type_code") in COMPANY_CODES:
        return "private"
    return "individual"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", default="all",
                    choices=["all", "gov", "statelocal", "private", "individual"])
    ap.add_argument("--include-drones", action="store_true",
                    help="include unmanned rotorcraft (default: manned helicopters only — "
                         "drones have no pilot, so no helmet buyer)")
    args = ap.parse_args()

    if not ENTITIES.exists():
        print(f"no {ENTITIES} — run heli_tracker.py first")
        return 1
    ents = json.loads(ENTITIES.read_text())["entities"]
    contacts = parse_contacts()

    dropped = 0
    ops = {}
    for e in ents:
        if not args.include_drones and e.get("is_unmanned") == 1:
            dropped += 1
            continue
        key = f"{e['registrant_name']}|{e['state']}"
        o = ops.setdefault(key, {
            "operator": e["registrant_name"], "state": e["state"],
            "city": e["city"], "street": e["street"], "zip": e["zip"],
            "segment": segment_of(e), "fleet": 0,
            "models": {}, "n_numbers": [],
        })
        o["fleet"] += 1
        o["n_numbers"].append(e["n_number"])
        mk = f"{e['mfr']} {e['model']}".strip()
        o["models"][mk] = o["models"].get(mk, 0) + 1

    rows = []
    for key, o in ops.items():
        if args.segment != "all" and o["segment"] != args.segment:
            continue
        c = contacts.get(key, {})
        top_models = ", ".join(k for k, _ in sorted(o["models"].items(), key=lambda x: -x[1])[:3])
        rows.append({
            "operator": o["operator"], "segment": o["segment"], "fleet_size": o["fleet"],
            "city": o["city"], "state": o["state"], "zip": o["zip"], "street": o["street"],
            "phone": c.get("phone", ""), "email": c.get("email", ""),
            "website": c.get("website", "").split(" —")[0],
            "has_contact": "yes" if (c.get("phone") or c.get("email")) else "no",
            "top_models": top_models,
            "sample_tail_numbers": " ".join("N" + n for n in o["n_numbers"][:5]),
        })
    rows.sort(key=lambda r: -r["fleet_size"])

    fields = ["operator", "segment", "fleet_size", "phone", "email", "website",
              "has_contact", "city", "state", "zip", "street", "top_models",
              "sample_tail_numbers"]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    withc = sum(1 for r in rows if r["has_contact"] == "yes")
    if dropped:
        print(f"Excluded {dropped} unmanned drone/UAS airframes (no pilot). "
              f"Use --include-drones to keep them.")
    print(f"Wrote {len(rows)} leads ({args.segment}) to {OUT}")
    print(f"  {withc} have a phone/email; top lead: {rows[0]['operator']} "
          f"({rows[0]['fleet_size']} aircraft)" if rows else "  (no rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
