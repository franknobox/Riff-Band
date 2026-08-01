from __future__ import annotations

import hashlib
import json
from typing import Any


class LiteratureCoverageAuditor:
    """Deterministic coverage metadata; it never infers scientific findings."""

    PLAN_FIELDS = (
        "topic_summary",
        "query_blocks",
        "databases",
        "languages",
        "year_from",
        "year_to",
        "inclusion_criteria",
        "exclusion_criteria",
        "screening_questions",
        "counter_searches",
    )
    PLAN_DEFAULTS: dict[str, Any] = {
        "topic_summary": "",
        "query_blocks": [],
        "databases": [],
        "languages": [],
        "year_from": None,
        "year_to": None,
        "inclusion_criteria": [],
        "exclusion_criteria": [],
        "screening_questions": [],
        "counter_searches": [],
    }

    @classmethod
    def plan_fingerprint(cls, content: dict[str, Any]) -> str:
        payload = {
            key: content.get(key, cls.PLAN_DEFAULTS[key])
            for key in cls.PLAN_FIELDS
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def available_evidence_level(paper: dict[str, Any]) -> str:
        if str(paper.get("full_text_excerpt") or paper.get("full_text_text") or "").strip():
            return "full_text"
        if str(paper.get("abstract") or "").strip():
            return "abstract"
        return "metadata"

    @classmethod
    def effective_evidence_level(
        cls,
        paper: dict[str, Any],
        decision: dict[str, Any] | None,
    ) -> str:
        rank = {"metadata": 0, "abstract": 1, "full_text": 2}
        available = cls.available_evidence_level(paper)
        declared = str((decision or {}).get("evidence_level") or available)
        if declared not in rank:
            return available
        return declared if rank[declared] <= rank[available] else available

    @staticmethod
    def audit(
        papers: list[dict[str, Any]],
        source_runs: list[dict[str, Any]] | None = None,
        screening_decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        clean_papers = [paper for paper in papers if isinstance(paper, dict)]
        decisions = {
            str(item.get("paper_id")): item
            for item in screening_decisions or []
            if isinstance(item, dict) and item.get("paper_id")
        }
        years = []
        backends: set[str] = set()
        abstract_count = 0
        doi_count = 0
        full_text_count = 0
        for paper in clean_papers:
            try:
                year = int(paper.get("year"))
                if 1800 <= year <= 2100:
                    years.append(year)
            except (TypeError, ValueError):
                pass
            if str(paper.get("abstract") or "").strip():
                abstract_count += 1
            if str(paper.get("doi") or "").strip():
                doi_count += 1
            if LiteratureCoverageAuditor.available_evidence_level(paper) == "full_text":
                full_text_count += 1
            for backend in paper.get("backends", []):
                if backend:
                    backends.add(str(backend))

        screening_counts = {
            "include": 0,
            "exclude": 0,
            "unsure": 0,
            "unreviewed": 0,
        }
        evidence_counts = {"metadata": 0, "abstract": 0, "full_text": 0}
        for paper in clean_papers:
            paper_id = str(paper.get("paper_id") or "")
            decision = decisions.get(paper_id)
            if decision is None:
                screening_counts["unreviewed"] += 1
                level = LiteratureCoverageAuditor.available_evidence_level(paper)
            else:
                screening_key = str(decision.get("decision") or "unreviewed")
                screening_counts[
                    screening_key if screening_key in screening_counts else "unreviewed"
                ] += 1
                level = LiteratureCoverageAuditor.effective_evidence_level(
                    paper,
                    decision,
                )
            if level in evidence_counts:
                evidence_counts[level] += 1

        runs = [run for run in source_runs or [] if isinstance(run, dict)]
        failed_runs = [
            {
                "backend": str(run.get("backend") or ""),
                "query": str(run.get("query") or ""),
                "error": str(run.get("error") or "")[:500],
            }
            for run in runs
            if not run.get("success")
        ]
        warnings: list[str] = []
        if not clean_papers:
            warnings.append("no_papers")
        if clean_papers and abstract_count == 0:
            warnings.append("no_abstract_evidence")
        if clean_papers and full_text_count == 0:
            warnings.append("no_full_text_evidence")
        if clean_papers and doi_count < len(clean_papers):
            warnings.append("incomplete_doi_metadata")
        if clean_papers and len(years) < len(clean_papers):
            warnings.append("incomplete_year_metadata")
        if screening_counts["unreviewed"]:
            warnings.append("screening_incomplete")
        if failed_runs:
            warnings.append("partial_source_failure")
        if any(
            str(decision.get("evidence_level") or "metadata")
            != LiteratureCoverageAuditor.effective_evidence_level(paper, decision)
            for paper in clean_papers
            if (decision := decisions.get(str(paper.get("paper_id") or ""))) is not None
        ):
            warnings.append("declared_evidence_unavailable")

        total = len(clean_papers)
        return {
            "schema_version": "ai4ms.literature-coverage.v1",
            "paper_count": total,
            "metadata_completeness": {
                "abstract_count": abstract_count,
                "doi_count": doi_count,
                "year_count": len(years),
                "full_text_count": full_text_count,
            },
            "evidence_levels": evidence_counts,
            "year_range": {
                "from": min(years) if years else None,
                "to": max(years) if years else None,
            },
            "backends": sorted(backends),
            "source_run_count": len(runs),
            "failed_source_runs": failed_runs,
            "screening": screening_counts,
            "warning_codes": warnings,
        }
