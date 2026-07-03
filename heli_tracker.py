#!/usr/bin/env python3
"""heli_tracker.py — Track helicopter registrations from the FAA Releasable Aircraft database.

Downloads the FAA ReleasableAircraft.zip, filters to rotorcraft (helicopters),
maintains a SQLite DB of registrant entities, and exports a JSON snapshot.
Stdlib only.
"""

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

DOWNLOAD_URL = "https://registry.faa.gov/database/ReleasableAircraft.zip"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
ZIP_PATH = os.path.join(CACHE_DIR, "ReleasableAircraft.zip")
DEFAULT_DB = os.path.join(DATA_DIR, "heli.db")
JSON_PATH = os.path.join(DATA_DIR, "entities.json")

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

REGISTRANT_TYPES = {
    "1": "Individual",
    "2": "Partnership",
    "3": "Corporation",
    "4": "Co-Owned",
    "5": "Government",
    "7": "LLC",
    "8": "Non Citizen Corporation",
    "9": "Non Citizen Co-Owned",
}

# Patterns identifying FEDERAL government registrants (word-boundary matched
# against the uppercased registrant name). Government entities that do NOT
# match any of these are considered state/local.
FEDERAL_PATTERNS = [
    r"\bUNITED STATES\b",
    r"\bU S \b", r"\bU S$", r"^US \b", r"\bUS GOVT\b", r"\bUS GOVERNMENT\b",
    r"\bU\.S\.?\b",
    r"\bUSA\b",
    r"\bFEDERAL\b",
    r"\bDEPT OF THE ARMY\b", r"\bDEPARTMENT OF THE ARMY\b", r"\bUS ARMY\b", r"\bU S ARMY\b",
    r"\bDEPT OF THE NAVY\b", r"\bDEPARTMENT OF THE NAVY\b", r"\bUS NAVY\b", r"\bU S NAVY\b",
    r"\bDEPT OF THE AIR FORCE\b", r"\bDEPARTMENT OF THE AIR FORCE\b", r"\bAIR FORCE\b",
    r"\bARMY\b", r"\bNAVY\b", r"\bNAVAL\b", r"\bMARINE CORPS\b", r"\bCOAST GUARD\b", r"\bNATIONAL GUARD\b",
    r"\bAIR SYSTEMS COMMAND\b", r"\bNAVAIR\b",
    r"\bFBI\b", r"\bFEDERAL BUREAU OF INVESTIGATION\b",
    r"\bDEA\b", r"\bDRUG ENFORCEMENT\b",
    r"\bCBP\b", r"\bCUSTOMS\b", r"\bBORDER PROTECTION\b", r"\bBORDER PATROL\b",
    r"\bHOMELAND SECURITY\b", r"\bIMMIGRATION\b", r"\bATF\b", r"\bSECRET SERVICE\b",
    r"\bNOAA\b", r"\bNATIONAL OCEANIC\b",
    r"\bNASA\b", r"\bNATL AERONAUTICS\b", r"\bNATIONAL AERONAUTICS\b",
    r"\bFOREST SERVICE\b", r"\bUSDA\b", r"\bDEPT OF AGRICULTURE\b",
    r"\bDEPT OF INTERIOR\b", r"\bDEPARTMENT OF INTERIOR\b", r"\bDEPT OF THE INTERIOR\b",
    r"\bBUREAU OF LAND MANAGEMENT\b", r"\bNATIONAL PARK\b", r"\bFISH AND WILDLIFE\b",
    r"\bDEPT OF ENERGY\b", r"\bDEPARTMENT OF ENERGY\b",
    r"\bDEPT OF JUSTICE\b", r"\bDEPARTMENT OF JUSTICE\b",
    r"\bDEPT OF DEFENSE\b", r"\bDEPARTMENT OF DEFENSE\b",
    r"\bDEPT OF TRANSPORTATION\b", r"\bFAA\b", r"\bFEDERAL AVIATION\b",
    r"\bSMITHSONIAN\b", r"\bTVA\b", r"\bTENNESSEE VALLEY AUTHORITY\b",
]
FEDERAL_RE = re.compile("|".join(FEDERAL_PATTERNS))


def download_zip(force: bool, no_download: bool) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    if no_download:
        if not os.path.exists(ZIP_PATH):
            sys.exit(f"error: --no-download given but no cached zip at {ZIP_PATH}")
        return ZIP_PATH
    if os.path.exists(ZIP_PATH) and not force:
        age = time.time() - os.path.getmtime(ZIP_PATH)
        if age < 86400:
            print(f"Using cached zip ({age/3600:.1f}h old): {ZIP_PATH}")
            return ZIP_PATH
    print(f"Downloading {DOWNLOAD_URL} ...")
    req = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": USER_AGENT})
    tmp = ZIP_PATH + ".part"
    with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, ZIP_PATH)
    print(f"Downloaded {os.path.getsize(ZIP_PATH)/1e6:.1f} MB -> {ZIP_PATH}")
    return ZIP_PATH


def _open_csv(zf: zipfile.ZipFile, name: str):
    """Yield stripped-field rows (list[str]) from a comma-delimited FAA file, skipping header."""
    with zf.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
        reader = csv.reader(text)
        header = next(reader, None)  # skip header row
        for row in reader:
            if not row:
                continue
            yield [f.strip() for f in row]


def load_rotorcraft_ref(zf: zipfile.ZipFile) -> dict:
    """Return {code: (mfr, model)} for ACFTREF rows with TYPE-ACFT == '6'."""
    ref = {}
    for row in _open_csv(zf, "ACFTREF.txt"):
        if len(row) >= 4 and row[3] == "6":
            ref[row[0]] = (row[1], row[2])
    return ref


def parse_master(zf: zipfile.ZipFile, ref: dict) -> dict:
    """Return {n_number: entity dict} for helicopters."""
    entities = {}
    for row in _open_csv(zf, "MASTER.txt"):
        if len(row) < 21:
            continue
        # column 19 (index 18) TYPE AIRCRAFT: '6' = rotorcraft
        if row[18] != "6":
            continue
        code = row[2]
        mfr, model = ref.get(code, ("", ""))
        rt_code = row[5]
        rt = REGISTRANT_TYPES.get(rt_code, "")
        name = row[6]
        is_gov = 1 if rt_code == "5" else 0
        is_state_local = 1 if (is_gov and not FEDERAL_RE.search(name.upper())) else 0
        entities[row[0]] = {
            "n_number": row[0],
            "serial": row[1],
            "registrant_name": name,
            "street": row[7],
            "city": row[9],
            "state": row[10],
            "zip": row[11],
            "registrant_type_code": rt_code,
            "registrant_type": rt,
            "mfr": mfr,
            "model": model,
            "year_mfr": row[4],
            "cert_issue_date": row[16],
            "last_action_date": row[15],
            "is_government": is_gov,
            "is_state_local": is_state_local,
        }
    return entities


SCHEMA = """
CREATE TABLE IF NOT EXISTS entities(
    n_number TEXT PRIMARY KEY, serial TEXT, registrant_name TEXT, street TEXT,
    city TEXT, state TEXT, zip TEXT, registrant_type_code TEXT, registrant_type TEXT,
    mfr TEXT, model TEXT, year_mfr TEXT, cert_issue_date TEXT, last_action_date TEXT,
    is_government INTEGER, is_state_local INTEGER,
    first_seen TEXT, last_seen TEXT, status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS runs(
    run_id INTEGER PRIMARY KEY AUTOINCREMENT, ran_at TEXT,
    total INTEGER, new_count INTEGER, removed_count INTEGER
);
"""


def update_db(db_path: str, entities: dict):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    today = datetime.now(timezone.utc).date().isoformat()

    existing = {r[0]: r[1] for r in conn.execute("SELECT n_number, status FROM entities")}
    new_count = 0
    for e in entities.values():
        if e["n_number"] in existing:
            conn.execute(
                """UPDATE entities SET serial=?, registrant_name=?, street=?, city=?, state=?,
                   zip=?, registrant_type_code=?, registrant_type=?, mfr=?, model=?, year_mfr=?,
                   cert_issue_date=?, last_action_date=?, is_government=?, is_state_local=?,
                   last_seen=?, status='active' WHERE n_number=?""",
                (e["serial"], e["registrant_name"], e["street"], e["city"], e["state"],
                 e["zip"], e["registrant_type_code"], e["registrant_type"], e["mfr"],
                 e["model"], e["year_mfr"], e["cert_issue_date"], e["last_action_date"],
                 e["is_government"], e["is_state_local"], today, e["n_number"]))
        else:
            new_count += 1
            conn.execute(
                """INSERT INTO entities(n_number, serial, registrant_name, street, city, state,
                   zip, registrant_type_code, registrant_type, mfr, model, year_mfr,
                   cert_issue_date, last_action_date, is_government, is_state_local,
                   first_seen, last_seen, status)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active')""",
                (e["n_number"], e["serial"], e["registrant_name"], e["street"], e["city"],
                 e["state"], e["zip"], e["registrant_type_code"], e["registrant_type"],
                 e["mfr"], e["model"], e["year_mfr"], e["cert_issue_date"],
                 e["last_action_date"], e["is_government"], e["is_state_local"],
                 today, today))

    # Mark rows no longer present in the file as removed (only newly-removed count)
    current = set(entities)
    newly_removed = [n for n, st in existing.items() if n not in current and st == "active"]
    conn.executemany("UPDATE entities SET status='removed' WHERE n_number=?",
                     [(n,) for n in newly_removed])

    ran_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("INSERT INTO runs(ran_at, total, new_count, removed_count) VALUES(?,?,?,?)",
                       (ran_at, len(entities), new_count, len(newly_removed)))
    run_id = cur.lastrowid
    conn.commit()
    return conn, run_id, today, new_count, len(newly_removed)


def export_json(conn: sqlite3.Connection, run_id: int, latest_run_date: str):
    conn.row_factory = sqlite3.Row
    run = dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
    rows = []
    for r in conn.execute("SELECT * FROM entities ORDER BY n_number"):
        d = dict(r)
        d["is_new"] = d["first_seen"] == latest_run_date
        rows.append(d)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": run,
        "entities": rows,
    }
    with open(JSON_PATH, "w") as f:
        json.dump(out, f, indent=1)
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="Track FAA helicopter registrations")
    ap.add_argument("--force", action="store_true", help="force re-download of the FAA zip")
    ap.add_argument("--no-download", action="store_true", help="use cached zip, never download")
    ap.add_argument("--db", default=DEFAULT_DB, help="path to SQLite DB")
    args = ap.parse_args()

    zip_path = download_zip(args.force, args.no_download)
    with zipfile.ZipFile(zip_path) as zf:
        ref = load_rotorcraft_ref(zf)
        print(f"Rotorcraft models in ACFTREF: {len(ref)}")
        entities = parse_master(zf, ref)
    print(f"Helicopters in MASTER: {len(entities)}")

    conn, run_id, today, new_count, removed = update_db(args.db, entities)
    exported = export_json(conn, run_id, today)

    sl = conn.execute("SELECT COUNT(*) FROM entities WHERE is_state_local=1 AND status='active'").fetchone()[0]
    conn.close()

    print("--- Summary ---")
    print(f"Total active helicopters: {len(entities)}")
    print(f"New this run:             {new_count}")
    print(f"Removed this run:         {removed}")
    print(f"State/local government:   {sl}")
    print(f"Exported {exported} entities to {JSON_PATH}")


if __name__ == "__main__":
    main()
