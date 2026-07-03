#!/usr/bin/env python3
"""Auto-scrape phone/email from the official websites already listed in contacts.md.

For every agency entry that has a `- Website:` URL but still shows
`_(fill in)_` (or a placeholder) for phone/email, this fetches the page,
extracts the first plausible US phone number and any non-noreply email,
and fills them in — tagging the source as (scraped). Politeness: a real
User-Agent, a per-request timeout, and a delay between hosts. Best effort:
many government sites block bots or hide numbers in images, so this
complements — does not replace — the web-search-backed /heli-contacts flow.

Usage: python3 scripts/scrape_contacts.py [--limit N] [--delay SECONDS]
"""
import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTACTS = ROOT / "data" / "contacts.md"

UA = "Mozilla/5.0 (compatible; heli-bizz-contacts/1.0; +https://github.com/yerry262/heli-bizz)"
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_SKIP = ("noreply", "no-reply", "example.", "@sentry", "@2x", ".png", ".jpg", "wixpress")


def fetch(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(600_000)
    return raw.decode("utf-8", "ignore")


def strip_tags(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", html)


def best_phone(text: str) -> str:
    for m in PHONE_RE.finditer(text):
        area = m.group(1)
        if area in ("800", "888", "877", "866", "855", "844"):
            continue  # skip toll-free; prefer a local direct line, keep looking
        return f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
    m = PHONE_RE.search(text)  # fall back to any (incl. toll-free)
    return f"({m.group(1)}) {m.group(2)}-{m.group(3)}" if m else ""


def best_email(text: str) -> str:
    for m in EMAIL_RE.finditer(text):
        e = m.group(0)
        if any(s in e.lower() for s in EMAIL_SKIP):
            continue
        return e
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="max agencies to scrape this run")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args()

    if not CONTACTS.exists():
        print(f"no {CONTACTS} — run find_contacts.py first")
        return 1
    text = CONTACTS.read_text()
    blocks = re.split(r"\n(?=## )", text)

    scraped = filled_phone = filled_email = 0
    for bi, b in enumerate(blocks):
        if scraped >= args.limit:
            break
        name_m = re.match(r"## (.+)", b)
        site_m = re.search(r"- Website: (\S+)", b)
        needs_phone = "- Phone: _(fill in)_" in b
        needs_email = "- Email: _(fill in)_" in b
        if not (name_m and site_m and (needs_phone or needs_email)):
            continue
        url = site_m.group(1).split(" ")[0].rstrip("—").strip()
        if not url.startswith("http"):
            continue
        try:
            plain = strip_tags(fetch(url, args.timeout))
        except Exception as exc:
            print(f"  skip {name_m.group(1)[:40]:40} ({type(exc).__name__})")
            time.sleep(args.delay)
            continue
        scraped += 1
        nb = b
        if needs_phone:
            ph = best_phone(plain)
            if ph:
                nb = nb.replace("- Phone: _(fill in)_", f"- Phone: {ph} (scraped)")
                filled_phone += 1
        if needs_email:
            em = best_email(plain)
            if em:
                nb = nb.replace("- Email: _(fill in)_", f"- Email: {em} (scraped)")
                filled_email += 1
        blocks[bi] = nb
        print(f"  ok   {name_m.group(1)[:40]:40} phone={'Y' if needs_phone and nb!=b else '-'} email={'Y' if needs_email and nb!=b else '-'}")
        time.sleep(args.delay)

    CONTACTS.write_text("\n".join(blocks))
    print(f"\nScraped {scraped} sites; filled {filled_phone} phones, {filled_email} emails.")
    print(f"{CONTACTS.read_text().count('- Phone: _(fill in)_')} agencies still need a phone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
