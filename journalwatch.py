#!/usr/bin/env python3
"""JournalWatch – tägliche Abfrage der größten Journale nach AI- und
Computing-Publikationen (Nature Portfolio, Science/AAAS, MDPI).

Fragt über die Crossref-API die in journals.json konfigurierten Journale nach
neuen Artikeln ab, filtert breit aufgestellte Journale (Nature, Science,
Applied Sciences, …) per AI-/Computing-Keyword und schreibt einen nach Verlag
gruppierten Markdown-Report nach reports/YYYY-MM-DD.md
sowie reports/latest.md. Bereits gemeldete DOIs werden in data/seen_dois.json
gemerkt, damit kein Artikel doppelt auftaucht.

Benötigt nur die Python-Standardbibliothek (kein pip install).

Aufruf:
    python journalwatch.py            # Lookback: 2 Tage
    python journalwatch.py --days 7   # Lookback: 7 Tage
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "journals.json"
REPORTS_DIR = BASE_DIR / "reports"
SEEN_PATH = BASE_DIR / "data" / "seen_dois.json"

CROSSREF_URL = "https://api.crossref.org/journals/{issn}/works"
ROWS_PER_JOURNAL = 100
MAX_SEEN_DOIS = 20000

# Crossref bittet um einen identifizierenden User-Agent ("polite pool").
# Optional eigene Mail via Umgebungsvariable CROSSREF_MAILTO angeben.
MAILTO = os.environ.get("CROSSREF_MAILTO", "")
USER_AGENT = "JournalWatch/1.0 (https://github.com/erikiss/journalwatch{})".format(
    f"; mailto:{MAILTO}" if MAILTO else ""
)


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def http_get_json(url: str, retries: int = 3) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            if attempt == retries - 1:
                print(f"  WARN: Abfrage fehlgeschlagen ({exc}): {url}", file=sys.stderr)
                return None
            time.sleep(2 ** (attempt + 1))
    return None


def fetch_journal(issn: str, from_date: date) -> list[dict]:
    params = {
        "filter": f"from-pub-date:{from_date.isoformat()},type:journal-article",
        "sort": "published",
        "order": "desc",
        "rows": str(ROWS_PER_JOURNAL),
        "select": "DOI,title,abstract,published,published-online,published-print,container-title,author,URL",
    }
    url = CROSSREF_URL.format(issn=issn) + "?" + urllib.parse.urlencode(params)
    data = http_get_json(url)
    if not data:
        return []
    return data.get("message", {}).get("items", [])


def strip_jats(text: str) -> str:
    """Entfernt JATS-/HTML-Markup aus Crossref-Abstracts."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def item_date(item: dict) -> str:
    for key in ("published", "published-online", "published-print"):
        parts = item.get(key, {}).get("date-parts", [[]])[0]
        if parts:
            return "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts))
    return "?"


def item_authors(item: dict, limit: int = 3) -> str:
    names = []
    for author in item.get("author", [])[:limit]:
        family = author.get("family", "")
        given = author.get("given", "")
        name = f"{given} {family}".strip() or author.get("name", "")
        if name:
            names.append(name)
    if len(item.get("author", [])) > limit:
        names.append("et al.")
    return ", ".join(names)


def matches_keywords(item: dict, keywords: list[str]) -> bool:
    title = " ".join(item.get("title", []))
    abstract = item.get("abstract", "")
    haystack = strip_jats(f"{title} {abstract}").lower()
    return any(re.search(rf"\b{re.escape(kw)}", haystack) for kw in keywords)


def load_seen() -> set[str]:
    if SEEN_PATH.exists():
        with open(SEEN_PATH, encoding="utf-8") as fh:
            return set(json.load(fh))
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    dois = sorted(seen)[-MAX_SEEN_DOIS:]
    with open(SEEN_PATH, "w", encoding="utf-8") as fh:
        json.dump(dois, fh, indent=0)


def format_entry(item: dict) -> str:
    title = strip_jats(" ".join(item.get("title", ["(ohne Titel)"])))
    doi = item.get("DOI", "")
    url = f"https://doi.org/{doi}" if doi else item.get("URL", "")
    lines = [f"- **[{title}]({url})**"]
    meta = " · ".join(x for x in (item_authors(item), item_date(item)) if x and x != "?")
    if meta:
        lines.append(f"  {meta}")
    abstract = strip_jats(item.get("abstract", ""))
    if abstract:
        if len(abstract) > 400:
            abstract = abstract[:400].rsplit(" ", 1)[0] + " …"
        lines.append(f"  > {abstract}")
    return "\n".join(lines)


def build_report(results: list[tuple[dict, list[dict]]], run_date: date, from_date: date) -> str:
    total = sum(len(items) for _, items in results)
    out = [
        f"# JournalWatch – AI- & Computing-Report {run_date.isoformat()}",
        "",
        f"Neue AI-/Computing-Publikationen seit {from_date.isoformat()}: **{total}**",
        "",
    ]
    current_publisher = None
    for journal, items in results:
        if not items:
            continue
        if journal["publisher"] != current_publisher:
            current_publisher = journal["publisher"]
            out.append(f"## {current_publisher}")
            out.append("")
        out.append(f"### {journal['name']} ({len(items)})")
        out.append("")
        for item in items:
            out.append(format_entry(item))
        out.append("")
    if total == 0:
        out.append("_Keine neuen AI-/Computing-Publikationen im Abfragezeitraum gefunden._")
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tägliche AI-/Computing-Abfrage der größten Journale")
    parser.add_argument("--days", type=int, default=2, help="Lookback-Fenster in Tagen (Default: 2)")
    parser.add_argument("--no-dedupe", action="store_true", help="seen_dois.json ignorieren")
    args = parser.parse_args()

    config = load_config()
    keywords = [kw.lower() for kw in config["keywords"]]
    run_date = datetime.now(timezone.utc).date()
    from_date = run_date - timedelta(days=args.days)
    seen = set() if args.no_dedupe else load_seen()

    results: list[tuple[dict, list[dict]]] = []
    new_dois: set[str] = set()
    for journal in config["journals"]:
        name, issn = journal["name"], journal["issn"]
        print(f"Frage ab: {name} (ISSN {issn}) …")
        items = fetch_journal(issn, from_date)
        kept = []
        for item in items:
            doi = item.get("DOI", "")
            if doi and doi in seen:
                continue
            if journal.get("filter") and not matches_keywords(item, keywords):
                continue
            kept.append(item)
            if doi:
                new_dois.add(doi)
        results.append((journal, kept))
        print(f"  {len(items)} Artikel im Zeitraum, {len(kept)} neue Treffer")
        time.sleep(1)  # Crossref nicht fluten

    report = build_report(results, run_date, from_date)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{run_date.isoformat()}.md"
    report_path.write_text(report, encoding="utf-8")
    (REPORTS_DIR / "latest.md").write_text(report, encoding="utf-8")

    if not args.no_dedupe:
        save_seen(seen | new_dois)

    total = sum(len(items) for _, items in results)
    print(f"\nFertig: {total} neue AI-/Computing-Publikationen → {report_path.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
