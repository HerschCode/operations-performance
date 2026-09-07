"""
Streams the real BPI Challenge 2019 event log (4TU.ResearchData, 729MB IEEE-XES XML,
1.6M events / 251K cases) and writes out the first N complete cases as a CSV in the
shape src/ingestion/load_event_log.py already expects -- WITHOUT downloading the whole
file. The connection is closed as soon as N_CASES traces have been parsed, so this stays
fast and fits comfortably in a free-tier Postgres instance (Neon's free tier is 0.5GB;
the full 251K-case log would not fit, a genuine constraint of this deployment, not a
reason to fake the data -- these are real events from real cases in the real dataset,
just not all 251K of them).

Uses stdlib xml.etree.ElementTree.iterparse on the streamed response body rather than
loading the file into memory -- a <trace> element is only fully buffered by iterparse
once its closing tag arrives, and is discarded (element.clear()) immediately after each
case is written, so memory stays bounded regardless of how large the source file is.
"""
import csv
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

BPI2019_URL = (
    "https://data.4tu.nl/file/35ed7122-966a-484e-a0e1-749b64e3366d/"
    "864493d1-3a58-47f6-ad6f-27f95f995828"
)

# The event-level and case-level (trace) attribute keys src/ingestion/load_event_log.py
# looks for, per RAW_COLUMN_MAP. Anything else in the source XES is real but unused by
# this pipeline and dropped here rather than carried through unused.
EVENT_KEYS = ["concept:name", "time:timestamp", "org:resource"]
CASE_KEYS = ["concept:name", "Purchasing Document", "Item", "Spend area text", "Vendor"]
FIELDNAMES = (
    [f"case:{k}" for k in CASE_KEYS] + [k for k in EVENT_KEYS]
)


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct_attrs(elem) -> dict:
    """Case-level (trace) or event-level attributes are direct <string>/<date>/...
    children with key="..." value="..." -- nested <event> children of a <trace> are a
    different tag and are correctly ignored here."""
    attrs = {}
    for child in elem:
        if _localname(child.tag) in ("string", "date", "int", "float", "boolean"):
            key = child.get("key")
            if key:
                attrs[key] = child.get("value")
    return attrs


def download_sample(n_cases: int, out_path: Path, url: str = BPI2019_URL) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cases_written = 0
    rows_written = 0

    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        response.raw.decode_content = True

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()

            context = ET.iterparse(response.raw, events=("end",))
            for _, elem in context:
                if _localname(elem.tag) != "trace":
                    continue

                case_attrs = _direct_attrs(elem)
                case_row_prefix = {f"case:{k}": case_attrs.get(k, "") for k in CASE_KEYS}

                for event_elem in elem:
                    if _localname(event_elem.tag) != "event":
                        continue
                    event_attrs = _direct_attrs(event_elem)
                    row = dict(case_row_prefix)
                    row.update({k: event_attrs.get(k, "") for k in EVENT_KEYS})
                    writer.writerow(row)
                    rows_written += 1

                cases_written += 1
                elem.clear()  # bound memory -- don't keep every parsed trace around

                if cases_written % 500 == 0:
                    print(f"  ...{cases_written} cases, {rows_written} events so far")

                if cases_written >= n_cases:
                    break  # closes the response (the `with` block) without reading the rest

    return cases_written, rows_written


def main():
    n_cases = int(os.environ.get("BPI_SAMPLE_CASES", "5000"))
    out_path = Path(os.environ.get("RAW_EVENT_LOG_PATH", "data/raw/bpi2019_events.csv"))
    print(f"Streaming real BPI Challenge 2019 data from 4TU, sampling first {n_cases} cases...")
    cases, rows = download_sample(n_cases, out_path)
    print(f"Done: {cases} real cases, {rows} real events written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
