#!/usr/bin/env python3
"""Produce reproducible corpus summaries used by the planning documents."""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "01_research_corpus"


def percentile(values: list[int], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    weight = pos - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def main() -> None:
    rows = json.loads((CORPUS_DIR / "papers_100.json").read_text(encoding="utf-8"))
    citations = [int(row["cited_by_count"]) for row in rows]
    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_type[row["sample_type"]].append(row)

    cross_tab: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        cross_tab[row["sample_type"]][row["research_paradigm"]] += 1

    summary = {
        "record_count": len(rows),
        "citation_snapshot_date": rows[0]["citation_snapshot_date"],
        "citation_stats": {
            "min": min(citations),
            "median": statistics.median(citations),
            "mean": round(statistics.mean(citations), 2),
            "p75": round(percentile(citations, 0.75), 2),
            "max": max(citations),
        },
        "classic": {
            "count": len(by_type["classic_high_cited"]),
            "median_citations": statistics.median(
                int(row["cited_by_count"]) for row in by_type["classic_high_cited"]
            ),
        },
        "recent_hot": {
            "count": len(by_type["recent_hot_2021_2025"]),
            "median_citations": statistics.median(
                int(row["cited_by_count"]) for row in by_type["recent_hot_2021_2025"]
            ),
            "median_recent_citations": statistics.median(
                int(row["citations_2024_2026"]) for row in by_type["recent_hot_2021_2025"]
            ),
        },
        "paradigm_counts": Counter(row["research_paradigm"] for row in rows),
        "method_counts": Counter(row["method_family"] for row in rows),
        "paradigm_by_sample_type": {key: dict(value) for key, value in cross_tab.items()},
        "domain_counts": Counter(row["domain"] for row in rows),
        "evidence_levels": Counter(row["extraction_evidence_level"] for row in rows),
        "data_types": Counter(row["inferred_data_type"] for row in rows),
    }
    (CORPUS_DIR / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    matrix_path = CORPUS_DIR / "paradigm_by_journal.csv"
    paradigms = sorted({row["research_paradigm"] for row in rows})
    journals = []
    for row in rows:
        if row["journal"] not in journals:
            journals.append(row["journal"])
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["journal", *paradigms, "total"])
        for journal in journals:
            counts = Counter(
                row["research_paradigm"] for row in rows if row["journal"] == journal
            )
            writer.writerow([journal, *[counts[p] for p in paradigms], sum(counts.values())])

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
