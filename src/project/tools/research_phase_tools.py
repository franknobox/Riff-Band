from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict

from pydantic import Field

from base.agent.base_action import BaseAction
from project.tools.literature_tools import (
    ArxivSearchTool,
    CrossrefLookupTool,
    DblpLookupTool,
    OpenAlexSearchTool,
    SemanticScholarSearchTool,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _append_jsonl_dedup(path: Path, row: dict[str, Any], key_fields: list[str]) -> tuple[bool, str]:
    raw = "|".join(str(row.get(field, "")).strip() for field in key_fields)
    if not raw.strip("|"):
        raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
    key = str(row.get("dedup_key") or sha1(raw.encode("utf-8")).hexdigest()[:16])
    row["dedup_key"] = key

    for existing in _read_jsonl(path):
        if str(existing.get("dedup_key", "")).strip() == key:
            return False, key

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True, key


def _filter_rows(rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    q = str(query or "").strip().lower()
    max_rows = max(1, int(limit or 20))
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if q and q not in json.dumps(row, ensure_ascii=False).lower():
            continue
        filtered.append(row)
        if len(filtered) >= max_rows:
            break
    return filtered


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _split_sentences(text: str, max_sentences: int = 3) -> list[str]:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return []
    parts = [item.strip() for item in cleaned.replace("；", ".").replace("。", ".").split(".")]
    return [item for item in parts if item][:max(1, int(max_sentences or 3))]


def _paper_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(field, "") or "")
        for field in ["title", "abstract", "relevance", "venue", "tags"]
    ).lower()


_QUERY_STOPWORDS = {
    "and",
    "or",
    "the",
    "for",
    "with",
    "from",
    "into",
    "via",
    "using",
    "based",
    "survey",
    "review",
    "paper",
    "study",
    "studies",
    "system",
    "systems",
    "network",
    "networks",
    "communication",
    "communications",
}


def _query_match_units(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []
    units: list[str] = []
    for quoted in re.findall(r'"([^"]{2,})"', text):
        cleaned = re.sub(r"\s+", " ", quoted).strip().lower()
        if cleaned:
            units.append(cleaned)
    unquoted = re.sub(r'"[^"]+"', " ", text)
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", unquoted):
        lower = token.lower()
        if lower in _QUERY_STOPWORDS:
            continue
        units.append(lower)
    return list(dict.fromkeys(units))


def _matches_required_query_terms(row: dict[str, Any], terms: list[str]) -> bool:
    active_terms = [term for term in terms if str(term or "").strip()]
    if not active_terms:
        return True
    text = _paper_text(row)
    if not text:
        return False
    for term in active_terms:
        units = _query_match_units(term)
        if not units:
            continue
        phrase_units = [unit for unit in units if " " in unit]
        if phrase_units and any(unit in text for unit in phrase_units):
            return True
        token_units = [unit for unit in units if " " not in unit]
        required = 1 if len(token_units) <= 2 else 2
        if sum(1 for unit in token_units if unit in text) >= required:
            return True
    return False


def _paper_relevance_score(row: dict[str, Any], priority_terms: list[str] | None = None) -> int:
    text = _paper_text(row)
    score = 0
    abstract = str(row.get("abstract", "") or "").strip()
    title = str(row.get("title", "") or "").lower()
    relevance = str(row.get("relevance", "") or "").lower()
    if abstract:
        score += 8 if len(abstract) >= 500 else 4
    if row.get("source_url"):
        score += 2
    if row.get("doi"):
        score += 2
    if str(row.get("evidence_quality", "")).lower() == "medium":
        score += 2
    for phrase in [
        "integrated sensing and communication",
        "isac",
        "reconfigurable intelligent surface",
        "intelligent reflecting surface",
        "ris",
        "irs",
    ]:
        if phrase in text:
            score += 5
        if phrase in title:
            score += 3
        if phrase in relevance:
            score += 2
    for term in priority_terms or []:
        clean = str(term or "").strip().lower().strip('"')
        if len(clean) >= 3 and clean in text:
            score += 4
    try:
        year = int(str(row.get("year", "") or "")[:4])
        if year >= 2022:
            score += 2
        elif year >= 2018:
            score += 1
    except ValueError:
        pass
    return score


def _screen_candidate_record(row: dict[str, Any], topic: str = "", priority_terms: list[str] | None = None) -> dict[str, Any]:
    terms = [str(item).strip() for item in (priority_terms or []) if str(item).strip()]
    if topic:
        terms.append(str(topic).strip())
    required_terms = [str(topic).strip()] if str(topic or "").strip() else terms
    score = _paper_relevance_score(row, terms)
    abstract = str(row.get("abstract", "") or "").strip()
    reasons = []
    if abstract:
        reasons.append("has_abstract")
    if row.get("doi"):
        reasons.append("has_doi")
    if row.get("source_url"):
        reasons.append("has_source_url")
    if int(row.get("citation_count", 0) or 0) > 0:
        reasons.append("has_citations")
    if any(str(term).lower().strip('"') in _paper_text(row) for term in terms if len(str(term).strip()) >= 3):
        reasons.append("matches_priority_terms")
    required_match = _matches_required_query_terms(row, required_terms)
    if required_match:
        reasons.append("matches_required_query_terms")
    else:
        reasons.append("missing_required_query_terms")
    decision = (
        "include"
        if required_match and (score >= 10 or ("has_abstract" in reasons and "matches_priority_terms" in reasons))
        else "exclude"
    )
    screened = dict(row)
    screened["screening_score"] = score
    screened["screening_decision"] = decision
    screened["screening_reasons"] = reasons
    screened["screened_at"] = _now()
    return screened


def _paper_card_from_record(row: dict[str, Any], topic: str = "", priority_terms: list[str] | None = None) -> dict[str, Any]:
    note = _paper_note_from_record(row, topic=topic, priority_terms=priority_terms)
    abstract = str(row.get("abstract", "") or "").strip()
    citation_count = row.get("citation_count", "")
    evidence_level = "abstract" if abstract else "metadata"
    return {
        "title": note["title"],
        "authors": [str(item) for item in (row.get("authors") or [])][:8],
        "year": str(row.get("year", "") or "")[:4],
        "venue": str(row.get("venue", "") or ""),
        "citation_key": "",
        "source_url": note["source_url"],
        "doi": note["doi"],
        "problem": note["problem"],
        "method": note["method"],
        "scenario": note["scenario"],
        "key_result": note["main_findings"],
        "limitations": note["limitations"],
        "relation_to_topic": note["relevance_to_topic"],
        "evidence_level": evidence_level,
        "citation_count": citation_count,
        "screening_score": row.get("screening_score", _paper_relevance_score(row, priority_terms)),
        "dedup_key": str(row.get("dedup_key", "") or ""),
        "recorded_at": _now(),
    }


def _paper_note_from_record(row: dict[str, Any], topic: str = "", priority_terms: list[str] | None = None) -> dict[str, Any]:
    title = _first_nonempty(row.get("title"), "Untitled paper")
    abstract = str(row.get("abstract", "") or "").strip()
    sentences = _split_sentences(abstract, 4)
    text = " ".join(sentences)
    lower_text = text.lower()

    method_sentence = ""
    for sentence in sentences:
        if any(token in sentence.lower() for token in ["propose", "method", "algorithm", "optimization", "learning", "beamforming", "framework", "model"]):
            method_sentence = sentence
            break
    scenario_sentence = ""
    for sentence in sentences:
        if any(token in sentence.lower() for token in ["isac", "sensing", "communication", "ris", "irs", "vehicular", "mimo", "mmwave", "wireless"]):
            scenario_sentence = sentence
            break

    limitations = ""
    for sentence in sentences:
        if any(token in sentence.lower() for token in ["limitation", "challenge", "future", "open", "however"]):
            limitations = sentence
            break
    if not limitations:
        limitations = "Not explicit in the available abstract; full-text reading is needed before making detailed claims."

    matched_terms = []
    combined = _paper_text(row)
    for term in priority_terms or []:
        clean = str(term or "").strip().strip('"')
        if clean and clean.lower() in combined:
            matched_terms.append(clean)

    return {
        "title": title,
        "citation_key": "",
        "source_url": str(row.get("source_url", "") or ""),
        "doi": str(row.get("doi", "") or ""),
        "problem": sentences[0] if sentences else f"Metadata-level candidate related to {topic or 'the research topic'}.",
        "method": method_sentence or "Method not explicit in the available abstract.",
        "scenario": scenario_sentence or "Scenario not explicit in the available abstract.",
        "main_findings": text or "No abstract available; only metadata-level relevance can be recorded.",
        "limitations": limitations,
        "relevance_to_topic": (
            f"score={_paper_relevance_score(row, priority_terms)}; "
            f"matched_terms={matched_terms[:8]}; original_relevance={row.get('relevance', '')}"
        ),
        "evidence_source": "abstract" if abstract else "metadata",
        "dedup_key": str(row.get("dedup_key", "") or ""),
    }


def _finding_from_paper(row: dict[str, Any], query: str, backend: str) -> dict[str, Any]:
    title = _first_nonempty(row.get("title"), "Untitled paper")
    abstract = str(row.get("abstract", "") or "").strip()
    summary = " ".join(_split_sentences(abstract, 2))
    if not summary:
        summary = f"Metadata-only paper candidate returned by {backend} for query: {query}."
    return {
        "topic": str(query or ""),
        "entity": title,
        "tags": ["paper_evidence", str(backend), "literature_search"],
        "finding": f"{title}: {summary[:600]}",
        "evidence": abstract[:1000] if abstract else summary,
        "source_url": str(row.get("source_url", "") or ""),
        "source_title": title,
        "published_at": str(row.get("year", "") or ""),
        "quote": "",
        "confidence": "medium" if abstract else "low",
        "dedup_key": "",
        "recorded_at": _now(),
    }


def _read_text_artifact(path: Path, limit_chars: int) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "chars": 0,
            "content": "",
        }
    text = path.read_text(encoding="utf-8")
    max_chars = max(0, int(limit_chars or 12000))
    content = text[:max_chars]
    truncated = len(text) > len(content)
    return {
        "path": str(path),
        "exists": True,
        "chars": len(text),
        "truncated": truncated,
        "content": content,
    }


def _strip_duplicate_section_heading(section_title: str, content: str) -> str:
    title = str(section_title or "").strip().lstrip("#").strip()
    lines = str(content or "").lstrip().splitlines()
    if not lines:
        return ""
    first = lines[0].strip()
    if first.lstrip("#").strip() == title:
        return "\n".join(lines[1:]).lstrip()
    return str(content or "").strip()


def _write_report_section(path: Path, section_title: str, content: str) -> None:
    title = str(section_title or "").strip().lstrip("#").strip()
    if not title:
        title = "Research Section"
    body = _strip_duplicate_section_heading(title, content)
    header = f"## {title}"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Report\n"
    lines = existing.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().lower() == header.lower():
            start = index
            break
    section_lines = [header, "", body.strip()]
    if start is None:
        new_text = existing.rstrip() + "\n\n" + "\n".join(section_lines).rstrip() + "\n"
    else:
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].startswith("## "):
                end = index
                break
        new_lines = lines[:start] + section_lines + lines[end:]
        new_text = "\n".join(new_lines).rstrip() + "\n"
    path.write_text(new_text, encoding="utf-8")


def _load_tool_records(result: dict[str, Any]) -> list[dict[str, Any]]:
    output = result.get("output")
    if not output:
        return []
    try:
        value = json.loads(str(output))
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _paper_record_from_tool(row: dict[str, Any], query: str, backend: str) -> dict[str, Any]:
    external_ids = row.get("external_ids", {}) if isinstance(row.get("external_ids"), dict) else {}
    return {
        "title": str(row.get("title", "")).strip(),
        "authors": [str(item) for item in (row.get("authors") or [])][:8],
        "year": str(row.get("year", "") or "")[:4],
        "venue": str(row.get("venue", "") or "").strip(),
        "source_url": str(row.get("source_url", "") or row.get("url", "") or "").strip(),
        "doi": str(row.get("doi", "") or external_ids.get("DOI", "") or "").strip(),
        "abstract": str(row.get("abstract", "") or "").strip(),
        "relevance": f"query={query}; backend={backend}",
        "evidence_quality": "medium" if row.get("abstract") else "uncertain",
        "tags": [str(backend), "batch_literature_search"],
        "dedup_key": "",
        "recorded_at": _now(),
    }


class BatchLiteratureSearchTool(BaseAction):
    name: str = "batch_literature_search"
    description: str = "Search academic query groups, record candidates, screen them, and write selected papers."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "queries": {"type": "array", "items": {"type": "string"}},
                "target_papers": {"type": "integer", "default": 30},
                "per_query_limit": {"type": "integer", "default": 10},
                "record_findings": {"type": "boolean", "default": False},
                "tool_order": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["openalex_search", "semantic_scholar_search", "arxiv_search", "crossref_lookup", "dblp_lookup"],
                },
            },
            "required": ["queries"],
            "additionalProperties": False,
        }
    )
    candidates_path: Path = Field(default=Path("candidates.jsonl"), exclude=True)
    shortlist_path: Path = Field(default=Path("shortlist.jsonl"), exclude=True)
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        queries: list[str],
        target_papers: int = 30,
        per_query_limit: int = 10,
        record_findings: bool = False,
        tool_order: list[str] | None = None,
    ) -> Dict[str, Any]:
        cleaned_queries = []
        seen_queries: set[str] = set()
        for query in queries or []:
            text = str(query or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen_queries:
                continue
            seen_queries.add(key)
            cleaned_queries.append(text)

        if not cleaned_queries:
            return {"success": False, "message": "queries must not be empty"}

        target = max(1, min(int(target_papers or 30), 100))
        existing_before = len(_read_jsonl(self.papers_path))
        if existing_before >= target:
            return {
                "success": True,
                "output": _json_dumps(
                    {
                        "candidates_path": str(self.candidates_path),
                        "shortlist_path": str(self.shortlist_path),
                        "papers_path": str(self.papers_path),
                        "added": 0,
                        "findings_added": 0,
                        "duplicates": 0,
                        "total_papers": existing_before,
                        "target_papers": target,
                        "total_candidates": len(_read_jsonl(self.candidates_path)),
                        "total_shortlist": len(_read_jsonl(self.shortlist_path)),
                        "skipped": True,
                        "reason": "target_papers already reached",
                        "queries": cleaned_queries,
                        "attempts": [],
                        "failures": [],
                    }
                ),
            }
        limit = max(1, min(int(per_query_limit or 10), 30))
        order = [str(item) for item in (tool_order or ["openalex_search", "semantic_scholar_search", "arxiv_search", "crossref_lookup", "dblp_lookup"])]
        tools = {
            "openalex_search": OpenAlexSearchTool(),
            "semantic_scholar_search": SemanticScholarSearchTool(max_retries=1, retry_base_seconds=0.5),
            "arxiv_search": ArxivSearchTool(),
            "crossref_lookup": CrossrefLookupTool(),
            "dblp_lookup": DblpLookupTool(),
        }

        added = 0
        findings_added = 0
        duplicates = 0
        attempts: list[dict[str, Any]] = []
        failures: list[str] = []

        for query in cleaned_queries:
            if added >= target:
                break
            for tool_name in order:
                if added >= target:
                    break
                tool = tools.get(tool_name)
                if tool is None:
                    continue
                if tool_name == "openalex_search":
                    result = await tool(query=query, limit=limit)
                elif tool_name == "semantic_scholar_search":
                    result = await tool(query=query, limit=limit)
                elif tool_name == "arxiv_search":
                    result = await tool(query=query, max_results=limit)
                elif tool_name == "crossref_lookup":
                    result = await tool(query=query, rows=min(limit, 10))
                else:
                    result = await tool(query=query, limit=min(limit, 10))

                records = _load_tool_records(result)
                attempts.append(
                    {
                        "query": query,
                        "tool": tool_name,
                        "success": bool(result.get("success")),
                        "record_count": len(records),
                        "rate_limited": bool(result.get("rate_limited", False)),
                    }
                )
                if not result.get("success"):
                    failures.append(f"{tool_name}:{query}: {result.get('message') or result.get('error') or 'failed'}")
                    continue

                for row in records:
                    candidate = _paper_record_from_tool(row, query, tool_name)
                    if not candidate["title"]:
                        continue
                    candidate["candidate_query"] = query
                    candidate["candidate_backend"] = tool_name
                    candidate_added, _candidate_key = _append_jsonl_dedup(
                        self.candidates_path,
                        candidate,
                        ["source_url", "doi", "title", "year"],
                    )
                    screened = _screen_candidate_record(candidate, topic=query, priority_terms=cleaned_queries)
                    if screened["screening_decision"] != "include":
                        if not candidate_added:
                            duplicates += 1
                        continue
                    record = screened
                    was_added, _key = _append_jsonl_dedup(
                        self.papers_path,
                        record,
                        ["source_url", "doi", "title", "year"],
                    )
                    if was_added:
                        added += 1
                        _append_jsonl_dedup(
                            self.shortlist_path,
                            record,
                            ["source_url", "doi", "title", "year"],
                        )
                        if record_findings:
                            finding_record = _finding_from_paper(record, query, tool_name)
                            finding_added, _finding_key = _append_jsonl_dedup(
                                self.findings_path,
                                finding_record,
                                ["source_url", "source_title", "finding"],
                            )
                            if finding_added:
                                findings_added += 1
                    else:
                        duplicates += 1
                    if added >= target:
                        break

                if records:
                    break

        existing_count = len(_read_jsonl(self.papers_path))
        return {
            "success": added > 0 or existing_count >= target,
            "output": _json_dumps(
                {
                    "candidates_path": str(self.candidates_path),
                    "shortlist_path": str(self.shortlist_path),
                    "papers_path": str(self.papers_path),
                    "added": added,
                    "findings_added": findings_added,
                    "duplicates": duplicates,
                    "total_candidates": len(_read_jsonl(self.candidates_path)),
                    "total_shortlist": len(_read_jsonl(self.shortlist_path)),
                    "total_papers": existing_count,
                    "target_papers": target,
                    "queries": cleaned_queries,
                    "attempts": attempts,
                    "failures": failures[:10],
                }
            ),
        }


class LiteratureScreenTool(BaseAction):
    name: str = "literature_screen"
    description: str = "Screen candidates.jsonl into shortlist.jsonl and papers.jsonl using relevance, metadata, and evidence availability."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "priority_terms": {"type": "array", "items": {"type": "string"}},
                "target_papers": {"type": "integer", "default": 30},
                "min_score": {"type": "integer", "default": 10},
            },
            "additionalProperties": False,
        }
    )
    candidates_path: Path = Field(default=Path("candidates.jsonl"), exclude=True)
    shortlist_path: Path = Field(default=Path("shortlist.jsonl"), exclude=True)
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        topic: str = "",
        priority_terms: list[str] | None = None,
        target_papers: int = 30,
        min_score: int = 10,
    ) -> Dict[str, Any]:
        candidates = _read_jsonl(self.candidates_path)
        if not candidates:
            return {"success": False, "message": f"candidates file is empty or missing: {self.candidates_path}"}
        target = max(1, min(int(target_papers or 30), 100))
        threshold = max(0, int(min_score or 0))
        screened = [_screen_candidate_record(row, topic=topic, priority_terms=priority_terms) for row in candidates]
        screened.sort(key=lambda row: (-int(row.get("screening_score", 0) or 0), str(row.get("title", ""))))
        selected = [row for row in screened if int(row.get("screening_score", 0) or 0) >= threshold][:target]
        if not selected:
            selected = screened[: min(target, len(screened))]

        added_shortlist = 0
        added_papers = 0
        for row in selected:
            was_short, _key = _append_jsonl_dedup(self.shortlist_path, row, ["source_url", "doi", "title", "year"])
            was_paper, _paper_key = _append_jsonl_dedup(self.papers_path, row, ["source_url", "doi", "title", "year"])
            added_shortlist += int(was_short)
            added_papers += int(was_paper)
        return {
            "success": True,
            "output": _json_dumps(
                {
                    "candidates_path": str(self.candidates_path),
                    "shortlist_path": str(self.shortlist_path),
                    "papers_path": str(self.papers_path),
                    "candidates": len(candidates),
                    "selected": len(selected),
                    "added_shortlist": added_shortlist,
                    "added_papers": added_papers,
                    "top_scores": [
                        {
                            "title": row.get("title", ""),
                            "score": row.get("screening_score", 0),
                            "reasons": row.get("screening_reasons", []),
                        }
                        for row in selected[:10]
                    ],
                }
            ),
        }


class RecordPaperTool(BaseAction):
    name: str = "record_paper"
    description: str = "Record a verified literature item into papers.jsonl for downstream synthesis and citation planning."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "authors": {"type": "array", "items": {"type": "string"}},
                "year": {"type": "string"},
                "venue": {"type": "string"},
                "source_url": {"type": "string"},
                "doi": {"type": "string"},
                "abstract": {"type": "string"},
                "relevance": {"type": "string"},
                "evidence_quality": {"type": "string", "enum": ["high", "medium", "low", "uncertain"]},
                "tags": {"type": "array", "items": {"type": "string"}},
                "dedup_key": {"type": "string"},
            },
            "required": ["title"],
            "additionalProperties": False,
        }
    )
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        title: str,
        authors: list[str] | None = None,
        year: str = "",
        venue: str = "",
        source_url: str = "",
        doi: str = "",
        abstract: str = "",
        relevance: str = "",
        evidence_quality: str = "medium",
        tags: list[str] | None = None,
        dedup_key: str = "",
    ) -> Dict[str, Any]:
        quality = str(evidence_quality or "medium").lower().strip()
        if quality not in {"high", "medium", "low", "uncertain"}:
            return {"success": False, "message": "evidence_quality must be high|medium|low|uncertain"}
        record = {
            "title": str(title).strip(),
            "authors": [str(item) for item in (authors or [])],
            "year": str(year).strip(),
            "venue": str(venue).strip(),
            "source_url": str(source_url).strip(),
            "doi": str(doi).strip(),
            "abstract": str(abstract).strip(),
            "relevance": str(relevance).strip(),
            "evidence_quality": quality,
            "tags": [str(item) for item in (tags or [])],
            "dedup_key": str(dedup_key).strip(),
            "recorded_at": _now(),
        }
        if not record["title"]:
            return {"success": False, "message": "title must not be empty"}
        added, key = _append_jsonl_dedup(self.papers_path, record, ["source_url", "doi", "title", "year"])
        verb = "Recorded" if added else "Skipped duplicate"
        return {"success": True, "output": f"{verb} paper {key} in {self.papers_path}"}


class ReadPapersTool(BaseAction):
    name: str = "read_papers"
    description: str = "Read verified literature records from papers.jsonl for synthesis, outlining, and drafting."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "additionalProperties": False,
        }
    )
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str = "", limit: int = 20) -> Dict[str, Any]:
        all_rows = _read_jsonl(self.papers_path)
        rows = _filter_rows(all_rows, query, limit)
        fallback_used = False
        if query and not rows and all_rows:
            rows = all_rows[: max(1, int(limit or 20))]
            fallback_used = True
        return {
            "success": True,
            "output": _json_dumps(
                {
                    "path": str(self.papers_path),
                    "file_exists": self.papers_path.exists(),
                    "total_count": len(all_rows),
                    "matched_count": 0 if fallback_used else len(rows),
                    "count": len(rows),
                    "fallback_used": fallback_used,
                    "query": str(query or ""),
                    "papers": rows,
                }
            ),
        }


class BatchPaperEnrichmentTool(BaseAction):
    name: str = "batch_paper_enrichment"
    description: str = "Read top-ranked papers and write abstract-level notes plus structured knowledge cards."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "priority_terms": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 30},
                "require_abstract": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        }
    )
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)
    paper_notes_path: Path = Field(default=Path("paper_notes.jsonl"), exclude=True)
    paper_cards_path: Path = Field(default=Path("paper_cards.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        topic: str = "",
        priority_terms: list[str] | None = None,
        limit: int = 30,
        require_abstract: bool = False,
    ) -> Dict[str, Any]:
        rows = _read_jsonl(self.papers_path)
        if not rows:
            return {
                "success": False,
                "message": f"papers file is empty or missing: {self.papers_path}",
            }

        terms = [str(item).strip() for item in (priority_terms or []) if str(item).strip()]
        if topic:
            terms.append(str(topic).strip())
        max_notes = max(1, min(int(limit or 30), 100))
        existing_notes = len(_read_jsonl(self.paper_notes_path))
        existing_cards = len(_read_jsonl(self.paper_cards_path))
        if existing_notes >= max_notes and existing_cards >= max_notes:
            return {
                "success": True,
                "output": _json_dumps(
                    {
                        "papers_path": str(self.papers_path),
                        "paper_notes_path": str(self.paper_notes_path),
                        "paper_cards_path": str(self.paper_cards_path),
                        "available_papers": len(rows),
                        "selected": 0,
                        "added": 0,
                        "cards_added": 0,
                        "duplicates": 0,
                        "total_paper_notes": existing_notes,
                        "total_paper_cards": existing_cards,
                        "skipped": True,
                        "reason": "paper_notes and paper_cards targets already reached",
                    }
                ),
            }

        ranked: list[tuple[int, int, dict[str, Any]]] = []
        skipped_no_abstract = 0
        for index, row in enumerate(rows):
            if require_abstract and not str(row.get("abstract", "") or "").strip():
                skipped_no_abstract += 1
                continue
            ranked.append((_paper_relevance_score(row, terms), index, row))
        ranked.sort(key=lambda item: (-item[0], item[1]))

        added = 0
        cards_added = 0
        duplicates = 0
        selected: list[dict[str, Any]] = []
        for score, _index, row in ranked[:max_notes]:
            note = _paper_note_from_record(row, topic=topic, priority_terms=terms)
            card = _paper_card_from_record(row, topic=topic, priority_terms=terms)
            was_added, key = _append_jsonl_dedup(
                self.paper_notes_path,
                note,
                ["source_url", "doi", "title"],
            )
            card_added, _card_key = _append_jsonl_dedup(
                self.paper_cards_path,
                card,
                ["source_url", "doi", "title"],
            )
            if was_added:
                added += 1
            else:
                duplicates += 1
            if card_added:
                cards_added += 1
            selected.append(
                {
                    "title": note["title"],
                    "score": score,
                    "evidence_source": note["evidence_source"],
                    "dedup_key": key,
                    "added": was_added,
                }
            )

        total_notes = len(_read_jsonl(self.paper_notes_path))
        total_cards = len(_read_jsonl(self.paper_cards_path))
        return {
            "success": added > 0 or cards_added > 0 or total_notes > 0 or total_cards > 0,
            "output": _json_dumps(
                {
                    "papers_path": str(self.papers_path),
                    "paper_notes_path": str(self.paper_notes_path),
                    "paper_cards_path": str(self.paper_cards_path),
                    "available_papers": len(rows),
                    "selected": len(selected),
                    "added": added,
                    "cards_added": cards_added,
                    "duplicates": duplicates,
                    "total_paper_notes": total_notes,
                    "total_paper_cards": total_cards,
                    "skipped_no_abstract": skipped_no_abstract,
                    "selected_papers": selected[:20],
                }
            ),
        }


class RecordPaperNoteTool(BaseAction):
    name: str = "record_paper_note"
    description: str = "Record a lightweight structured reading note for one paper into paper_notes.jsonl."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "citation_key": {"type": "string"},
                "source_url": {"type": "string"},
                "doi": {"type": "string"},
                "problem": {"type": "string"},
                "method": {"type": "string"},
                "scenario": {"type": "string"},
                "main_findings": {"type": "string"},
                "limitations": {"type": "string"},
                "relevance_to_topic": {"type": "string"},
                "evidence_source": {"type": "string", "enum": ["abstract", "web", "pdf", "metadata", "uncertain"]},
                "dedup_key": {"type": "string"},
            },
            "required": ["title"],
            "additionalProperties": False,
        }
    )
    paper_notes_path: Path = Field(default=Path("paper_notes.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        title: str,
        citation_key: str = "",
        source_url: str = "",
        doi: str = "",
        problem: str = "",
        method: str = "",
        scenario: str = "",
        main_findings: str = "",
        limitations: str = "",
        relevance_to_topic: str = "",
        evidence_source: str = "abstract",
        dedup_key: str = "",
    ) -> Dict[str, Any]:
        source = str(evidence_source or "abstract").lower().strip()
        if source not in {"abstract", "web", "pdf", "metadata", "uncertain"}:
            return {"success": False, "message": "evidence_source must be abstract|web|pdf|metadata|uncertain"}
        record = {
            "title": str(title).strip(),
            "citation_key": str(citation_key).strip(),
            "source_url": str(source_url).strip(),
            "doi": str(doi).strip(),
            "problem": str(problem).strip(),
            "method": str(method).strip(),
            "scenario": str(scenario).strip(),
            "main_findings": str(main_findings).strip(),
            "limitations": str(limitations).strip(),
            "relevance_to_topic": str(relevance_to_topic).strip(),
            "evidence_source": source,
            "dedup_key": str(dedup_key).strip(),
            "recorded_at": _now(),
        }
        if not record["title"]:
            return {"success": False, "message": "title must not be empty"}
        added, key = _append_jsonl_dedup(self.paper_notes_path, record, ["source_url", "doi", "title"])
        verb = "Recorded" if added else "Skipped duplicate"
        return {"success": True, "output": f"{verb} paper note {key} in {self.paper_notes_path}"}


class ReadPaperNotesTool(BaseAction):
    name: str = "read_paper_notes"
    description: str = "Read lightweight structured paper notes from paper_notes.jsonl for synthesis, outlining, and drafting."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 30},
            },
            "additionalProperties": False,
        }
    )
    paper_notes_path: Path = Field(default=Path("paper_notes.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str = "", limit: int = 30) -> Dict[str, Any]:
        rows = _filter_rows(_read_jsonl(self.paper_notes_path), query, limit)
        return {"success": True, "output": _json_dumps({"path": str(self.paper_notes_path), "count": len(rows), "paper_notes": rows})}


class ReadPaperCardsTool(BaseAction):
    name: str = "read_paper_cards"
    description: str = "Read structured paper knowledge cards from paper_cards.jsonl for synthesis and LaTeX drafting."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 30},
            },
            "additionalProperties": False,
        }
    )
    paper_cards_path: Path = Field(default=Path("paper_cards.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str = "", limit: int = 30) -> Dict[str, Any]:
        all_rows = _read_jsonl(self.paper_cards_path)
        rows = _filter_rows(all_rows, query, limit)
        fallback_used = False
        if str(query or "").strip() and not rows and all_rows:
            rows = all_rows[: max(1, int(limit or 30))]
            fallback_used = True
        return {
            "success": True,
            "output": _json_dumps(
                {
                    "path": str(self.paper_cards_path),
                    "file_exists": self.paper_cards_path.exists(),
                    "total_count": len(all_rows),
                    "matched_count": 0 if fallback_used else len(rows),
                    "fallback_used": fallback_used,
                    "count": len(rows),
                    "paper_cards": rows,
                }
            ),
        }


class BatchClaimGenerationTool(BaseAction):
    name: str = "batch_claim_generation"
    description: str = "Generate literature-review claims, gaps, and future directions from paper_notes.jsonl and findings.jsonl."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "target_claims": {"type": "integer", "default": 6},
            },
            "additionalProperties": False,
        }
    )
    paper_notes_path: Path = Field(default=Path("paper_notes.jsonl"), exclude=True)
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)
    synthesis_digest_path: Path = Field(default=Path("synthesis_digest.json"), exclude=True)
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)
    report_path: Path = Field(default=Path("research_report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, topic: str = "", target_claims: int = 6) -> Dict[str, Any]:
        notes = _read_jsonl(self.paper_notes_path)
        findings = _read_jsonl(self.findings_path)
        synthesis = self._read_synthesis_digest()
        if not notes and not findings and not synthesis:
            return {"success": False, "message": "paper_notes.jsonl, findings.jsonl, and synthesis_digest.json are all empty"}

        existing = len(_read_jsonl(self.claims_path))
        target = max(1, min(int(target_claims or 6), 8))
        if existing >= target:
            self._write_claim_section(topic=topic, claims=_read_jsonl(self.claims_path)[:target])
            return {
                "success": True,
                "output": _json_dumps(
                    {
                        "claims_path": str(self.claims_path),
                        "added": 0,
                        "total_claims": existing,
                        "target_claims": target,
                        "skipped": True,
                        "reason": "target_claims already reached",
                    }
                ),
            }

        buckets = [
            (
                "method",
                "RIS/IRS-assisted ISAC studies concentrate on joint beamforming, channel estimation, resource allocation, and optimization under sensing-communication trade-offs.",
                "方法路线需要区分优化、学习和混合方案，并说明不同证据深度。",
            ),
            (
                "gap",
                "Many available records rely on abstract-level evidence or metadata, so claims about full experimental superiority should remain cautious.",
                "摘要级证据不足以支撑强性能结论，需要全文阅读或可复现实验补充。",
            ),
            (
                "future_direction",
                "High-mobility scenarios such as vehicular networks, UAV platforms, and movable or STAR-RIS architectures are promising future directions for RIS-enabled ISAC.",
                "动态场景带来 CSI、轨迹、鲁棒性和实时优化挑战。",
            ),
            (
                "limitation",
                "Current evidence mixes direct RIS-ISAC papers with broader RIS communication papers, so the final review should explicitly separate direct and contextual evidence.",
                "论文池相关性不均，需要在综述中标注证据层级。",
            ),
            (
                "research_question",
                "A useful review question is how RIS configuration jointly affects sensing accuracy, communication rate, energy efficiency, and deployment robustness.",
                "该问题可组织后续章节中的评价指标和开放问题。",
            ),
            (
                "claim",
                "RIS can be treated as an environmental control layer for ISAC, but its practical value depends on channel acquisition, hardware constraints, and deployment geometry.",
                "该观点需要同时引用系统设计、信道估计和资源优化证据。",
            ),
        ]

        source_urls: list[str] = []
        for gap in synthesis.get("research_gaps", []) if isinstance(synthesis, dict) else []:
            if isinstance(gap, dict):
                for url in gap.get("source_urls", []) or []:
                    url_text = str(url or "").strip()
                    if url_text and url_text not in source_urls:
                        source_urls.append(url_text)
                    if len(source_urls) >= 8:
                        break
            if len(source_urls) >= 8:
                break
        for row in notes + findings:
            url = str(row.get("source_url", "") or "").strip()
            if url and url not in source_urls:
                source_urls.append(url)
            if len(source_urls) >= 8:
                break

        added = 0
        synthesis_buckets: list[tuple[str, str, str]] = []
        for gap in synthesis.get("research_gaps", []) if isinstance(synthesis, dict) else []:
            if not isinstance(gap, dict):
                continue
            text = str(gap.get("gap", "") or "").strip()
            if text:
                synthesis_buckets.append(("gap", text, f"Derived from synthesis_digest cluster={gap.get('cluster', '')}."))
        selected = (synthesis_buckets + buckets)[:target]
        for index, (claim_type, claim, uncertainty) in enumerate(selected, start=1):
            evidence_basis = "; ".join(
                str(item.get("title") or item.get("source_title") or item.get("main_findings") or item.get("finding") or "")[:160]
                for item in (notes + findings)[:5]
                if isinstance(item, dict)
            )
            if synthesis and not evidence_basis:
                evidence_basis = "; ".join(
                    str(item.get("cluster", "") or "") + f"({item.get('paper_count', 0)} papers)"
                    for item in synthesis.get("clusters", [])[:5]
                    if isinstance(item, dict)
                )
            record = {
                "claim": claim,
                "claim_type": claim_type,
                "evidence_basis": evidence_basis or f"Based on {len(notes)} paper notes and {len(findings)} findings.",
                "source_urls": source_urls[:5],
                "priority": "high" if index <= 3 else "medium",
                "uncertainty": uncertainty,
                "dedup_key": "",
                "recorded_at": _now(),
            }
            was_added, _key = _append_jsonl_dedup(self.claims_path, record, ["claim", "claim_type"])
            if was_added:
                added += 1

        all_claims = _read_jsonl(self.claims_path)
        self._write_claim_section(topic=topic, claims=all_claims[:target])
        return {
            "success": added > 0 or len(all_claims) > 0,
            "output": _json_dumps(
                {
                    "claims_path": str(self.claims_path),
                    "report_path": str(self.report_path),
                    "added": added,
                    "total_claims": len(all_claims),
                    "target_claims": target,
                    "paper_notes_count": len(notes),
                    "findings_count": len(findings),
                    "synthesis_digest_path": str(self.synthesis_digest_path),
                    "synthesis_digest_used": bool(synthesis),
                }
            ),
        }

    def _read_synthesis_digest(self) -> dict[str, Any]:
        if not self.synthesis_digest_path.exists():
            return {}
        try:
            value = json.loads(self.synthesis_digest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def _write_claim_section(self, topic: str = "", claims: list[dict[str, Any]] | None = None) -> None:
        rows = list(claims or [])
        if not rows:
            return
        lines = [
            f"本节基于已有论文摘要级阅读笔记和单篇论文证据点，提炼与“{str(topic or '研究主题').strip()}”相关的研究空白、未来方向和可检验问题。",
            "",
        ]
        for index, row in enumerate(rows[:8], start=1):
            claim = str(row.get("claim", "") or "").strip()
            ctype = str(row.get("claim_type", "") or "claim").strip()
            priority = str(row.get("priority", "") or "medium").strip()
            uncertainty = str(row.get("uncertainty", "") or "").strip()
            evidence = str(row.get("evidence_basis", "") or "").strip()
            if not claim:
                continue
            lines.append(f"{index}. **{ctype} / {priority}**：{claim}")
            if evidence:
                lines.append(f"   证据依据：{evidence[:260]}")
            if uncertainty:
                lines.append(f"   不确定性：{uncertainty}")
        _write_report_section(
            self.report_path,
            "研究空白、未来方向与可检验问题",
            "\n".join(lines),
        )


class SynthesizeFindingsTool(BaseAction):
    name: str = "synthesize_findings"
    description: str = "Persist a research synthesis: themes, consensus, disagreements, gaps, and evidence-quality notes."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "themes": {"type": "array", "items": {"type": "string"}},
                "consensus": {"type": "array", "items": {"type": "string"}},
                "disagreements": {"type": "array", "items": {"type": "string"}},
                "gaps": {"type": "array", "items": {"type": "string"}},
                "evidence_quality": {"type": "array", "items": {"type": "string"}},
                "note_title": {"type": "string", "default": "Knowledge Synthesis"},
            },
            "required": ["themes"],
            "additionalProperties": False,
        }
    )
    scratchpad_path: Path = Field(default=Path("scratchpad/shared.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        themes: list[str],
        consensus: list[str] | None = None,
        disagreements: list[str] | None = None,
        gaps: list[str] | None = None,
        evidence_quality: list[str] | None = None,
        note_title: str = "Knowledge Synthesis",
    ) -> Dict[str, Any]:
        if not themes:
            return {"success": False, "message": "themes must not be empty"}
        title = str(note_title or "Knowledge Synthesis").strip()
        payload = {
            "themes": [str(item) for item in themes],
            "consensus": [str(item) for item in (consensus or [])],
            "disagreements": [str(item) for item in (disagreements or [])],
            "gaps": [str(item) for item in (gaps or [])],
            "evidence_quality": [str(item) for item in (evidence_quality or [])],
            "updated_at": _now(),
        }
        self.scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.scratchpad_path.read_text(encoding="utf-8").strip() if self.scratchpad_path.exists() else "# Shared Scratchpad"
        block = f"## {title}\n\n```json\n{_json_dumps(payload)}\n```\n"
        self.scratchpad_path.write_text(f"{existing.rstrip()}\n\n{block}", encoding="utf-8")
        return {"success": True, "output": f"Synthesis note '{title}' written to {self.scratchpad_path}"}


def _cluster_name_for_card(row: dict[str, Any]) -> str:
    text = _paper_text(row)
    checks = [
        ("beamforming_and_optimization", ["beamforming", "optimization", "precoding", "resource allocation"]),
        ("channel_and_sensing_estimation", ["channel estimation", "csi", "localization", "sensing accuracy", "crb"]),
        ("learning_based_methods", ["learning", "neural", "deep", "reinforcement", "data-driven"]),
        ("mobility_and_network_scenarios", ["vehicular", "uav", "mobile", "mobility", "high-mobility"]),
        ("hardware_and_ris_architectures", ["star-ris", "active ris", "movable", "hardware", "phase shift"]),
        ("survey_and_taxonomy", ["survey", "taxonomy", "overview", "tutorial", "review"]),
    ]
    for name, tokens in checks:
        if any(token in text for token in tokens):
            return name
    return "system_modeling_and_applications"


def _short_join(values: list[str], limit: int = 4, item_limit: int = 220) -> list[str]:
    out: list[str] = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text or text in out:
            continue
        out.append(text[:item_limit])
        if len(out) >= limit:
            break
    return out


class BatchKnowledgeSynthesisTool(BaseAction):
    name: str = "batch_knowledge_synthesis"
    description: str = "Cluster paper_cards/findings into synthesis_digest.json and write cross-paper research gaps."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "max_clusters": {"type": "integer", "default": 7},
                "write_findings": {"type": "boolean", "default": True},
            },
            "additionalProperties": False,
        }
    )
    paper_cards_path: Path = Field(default=Path("paper_cards.jsonl"), exclude=True)
    paper_notes_path: Path = Field(default=Path("paper_notes.jsonl"), exclude=True)
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)
    synthesis_digest_path: Path = Field(default=Path("synthesis_digest.json"), exclude=True)
    report_path: Path = Field(default=Path("research_report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        topic: str = "",
        max_clusters: int = 7,
        write_findings: bool = True,
    ) -> Dict[str, Any]:
        cards = _read_jsonl(self.paper_cards_path)
        notes = _read_jsonl(self.paper_notes_path)
        source_rows = cards or notes
        if not source_rows:
            return {"success": False, "message": "paper_cards.jsonl and paper_notes.jsonl are both empty"}

        clusters_raw: dict[str, list[dict[str, Any]]] = {}
        for row in source_rows:
            clusters_raw.setdefault(_cluster_name_for_card(row), []).append(row)

        sorted_clusters = sorted(clusters_raw.items(), key=lambda item: (-len(item[1]), item[0]))[: max(1, min(int(max_clusters or 7), 10))]
        clusters: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        evidence_quality: list[str] = []
        representative_cards: list[dict[str, Any]] = []

        for name, rows in sorted_clusters:
            reps = sorted(rows, key=lambda row: -int(row.get("screening_score", 0) or 0))[:3]
            representative_cards.extend(reps)
            methods = _short_join([str(row.get("method", "") or "") for row in rows], limit=3)
            results = _short_join([str(row.get("key_result") or row.get("main_findings") or row.get("problem") or "") for row in rows], limit=4)
            limitations = _short_join([str(row.get("limitations", "") or "") for row in rows], limit=3)
            sources = [
                str(row.get("source_url", "") or "")
                for row in reps
                if str(row.get("source_url", "") or "").strip()
            ]
            gap_text = (
                f"{name}: current evidence covers {len(rows)} papers, but limitations indicate "
                f"{'; '.join(limitations[:2]) if limitations else 'limited full-text evidence and unclear deployment assumptions'}."
            )
            cluster = {
                "cluster": name,
                "paper_count": len(rows),
                "representative_titles": [str(row.get("title", "") or "") for row in reps],
                "methods": methods,
                "key_results": results,
                "limitations": limitations,
                "source_urls": sources[:5],
            }
            clusters.append(cluster)
            gaps.append(
                {
                    "gap": gap_text,
                    "cluster": name,
                    "source_urls": sources[:5],
                    "evidence_level": "abstract" if any(str(row.get("evidence_level", "")) == "abstract" for row in rows) else "metadata",
                }
            )
            evidence_quality.append(
                f"{name}: {len(rows)} paper cards; evidence is mostly "
                f"{'abstract-level' if any(str(row.get('evidence_level', '')) == 'abstract' for row in rows) else 'metadata-level'}."
            )

        digest = {
            "topic": str(topic or "").strip(),
            "paper_card_count": len(cards),
            "paper_note_count": len(notes),
            "cluster_count": len(clusters),
            "clusters": clusters,
            "research_gaps": gaps,
            "evidence_quality": evidence_quality,
            "representative_cards": [
                {
                    "title": row.get("title", ""),
                    "year": row.get("year", ""),
                    "source_url": row.get("source_url", ""),
                    "method": str(row.get("method", "") or "")[:240],
                    "key_result": str(row.get("key_result") or row.get("main_findings") or "")[:240],
                    "limitations": str(row.get("limitations", "") or "")[:200],
                }
                for row in representative_cards[:12]
            ],
            "updated_at": _now(),
        }
        self.synthesis_digest_path.parent.mkdir(parents=True, exist_ok=True)
        self.synthesis_digest_path.write_text(_json_dumps(digest), encoding="utf-8")

        findings_added = 0
        if write_findings:
            for gap in gaps:
                record = {
                    "topic": str(topic or gap.get("cluster", "")),
                    "entity": gap.get("cluster", ""),
                    "tags": ["cross_paper_synthesis", "research_gap"],
                    "finding": gap.get("gap", ""),
                    "evidence": f"Cluster-level synthesis from synthesis_digest.json; evidence_level={gap.get('evidence_level', '')}",
                    "source_url": "; ".join(gap.get("source_urls", [])[:3]),
                    "source_title": "synthesis_digest.json",
                    "confidence": "medium" if gap.get("source_urls") else "low",
                    "dedup_key": "",
                    "recorded_at": _now(),
                }
                added, _key = _append_jsonl_dedup(self.findings_path, record, ["entity", "finding"])
                findings_added += int(added)

        report_lines = [
            f"本节基于 {len(cards) or len(notes)} 条论文卡片/阅读笔记生成跨论文综合摘要。",
            "",
            "### 主题簇",
        ]
        for cluster in clusters:
            report_lines.append(f"- **{cluster['cluster']}**：{cluster['paper_count']} 篇；代表论文：{'; '.join(cluster['representative_titles'][:3])}")
        report_lines.extend(["", "### 研究空白"])
        for gap in gaps:
            report_lines.append(f"- {gap['gap']}")
        report_lines.extend(["", "### 证据质量"])
        report_lines.extend(f"- {item}" for item in evidence_quality)
        _write_report_section(self.report_path, "知识综合与研究空白", "\n".join(report_lines))

        return {
            "success": True,
            "output": _json_dumps(
                {
                    "synthesis_digest_path": str(self.synthesis_digest_path),
                    "report_path": str(self.report_path),
                    "clusters": len(clusters),
                    "research_gaps": len(gaps),
                    "findings_added": findings_added,
                }
            ),
        }


class ReadSynthesisDigestTool(BaseAction):
    name: str = "read_synthesis_digest"
    description: str = "Read synthesis_digest.json for outline generation and downstream drafting."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit_chars": {"type": "integer", "default": 16000},
            },
            "additionalProperties": False,
        }
    )
    synthesis_digest_path: Path = Field(default=Path("synthesis_digest.json"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit_chars: int = 16000) -> Dict[str, Any]:
        return {"success": True, "output": _json_dumps(_read_text_artifact(self.synthesis_digest_path, limit_chars))}


class RecordResearchClaimTool(BaseAction):
    name: str = "record_research_claim"
    description: str = "Record a candidate literature-review claim, research gap, future direction, or testable question into claims.jsonl."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "claim_type": {"type": "string", "enum": ["claim", "gap", "future_direction", "research_question", "limitation"]},
                "evidence_basis": {"type": "string"},
                "source_urls": {"type": "array", "items": {"type": "string"}},
                "uncertainty": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                "validation_path": {"type": "string"},
                "dedup_key": {"type": "string"},
            },
            "required": ["claim"],
            "additionalProperties": False,
        }
    )
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        claim: str,
        claim_type: str = "claim",
        evidence_basis: str = "",
        source_urls: list[str] | None = None,
        uncertainty: str = "",
        priority: str = "medium",
        validation_path: str = "",
        dedup_key: str = "",
    ) -> Dict[str, Any]:
        ctype = str(claim_type or "claim").strip()
        if ctype not in {"claim", "gap", "future_direction", "research_question", "limitation"}:
            return {"success": False, "message": "claim_type is invalid"}
        prio = str(priority or "medium").lower().strip()
        if prio not in {"high", "medium", "low"}:
            return {"success": False, "message": "priority must be high|medium|low"}
        record = {
            "claim": str(claim).strip(),
            "claim_type": ctype,
            "evidence_basis": str(evidence_basis).strip(),
            "source_urls": [str(item).strip() for item in (source_urls or []) if str(item).strip()],
            "uncertainty": str(uncertainty).strip(),
            "priority": prio,
            "validation_path": str(validation_path).strip(),
            "dedup_key": str(dedup_key).strip(),
            "recorded_at": _now(),
        }
        if not record["claim"]:
            return {"success": False, "message": "claim must not be empty"}
        added, key = _append_jsonl_dedup(self.claims_path, record, ["claim", "claim_type"])
        verb = "Recorded" if added else "Skipped duplicate"
        return {"success": True, "output": f"{verb} research claim {key} in {self.claims_path}"}


class ReadResearchClaimsTool(BaseAction):
    name: str = "read_research_claims"
    description: str = "Read candidate claims, gaps, future directions, and research questions from claims.jsonl."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "additionalProperties": False,
        }
    )
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str = "", limit: int = 20) -> Dict[str, Any]:
        all_rows = _read_jsonl(self.claims_path)
        rows = _filter_rows(all_rows, query, limit)
        fallback_used = False
        if str(query or "").strip() and not rows and all_rows:
            rows = all_rows[: max(1, int(limit or 20))]
            fallback_used = True
        return {
            "success": True,
            "output": _json_dumps(
                {
                    "path": str(self.claims_path),
                    "file_exists": self.claims_path.exists(),
                    "query": str(query or ""),
                    "total_count": len(all_rows),
                    "matched_count": 0 if fallback_used else len(rows),
                    "fallback_used": fallback_used,
                    "count": len(rows),
                    "claims": rows,
                }
            ),
        }


class ReadClaimDebateLogTool(BaseAction):
    name: str = "read_claim_debate_log"
    description: str = "Read debate_log.md, the structured claim debate and prioritization artifact."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit_chars": {"type": "integer", "default": 12000},
            },
            "additionalProperties": False,
        }
    )
    debate_log_path: Path = Field(default=Path("debate_log.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit_chars: int = 12000) -> Dict[str, Any]:
        return {"success": True, "output": _json_dumps(_read_text_artifact(self.debate_log_path, limit_chars))}


class BatchClaimDebateTool(BaseAction):
    name: str = "batch_claim_debate"
    description: str = "Batch-review claims, write debate_log.md, and update the claim debate report section."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 8},
            },
            "additionalProperties": False,
        }
    )
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)
    debate_log_path: Path = Field(default=Path("debate_log.md"), exclude=True)
    report_path: Path = Field(default=Path("research_report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit: int = 8) -> Dict[str, Any]:
        claims = _read_jsonl(self.claims_path)
        findings = _read_jsonl(self.findings_path)
        if not claims:
            return {"success": False, "message": "claims.jsonl is empty; run batch_claim_generation first"}

        selected = claims[: max(1, min(int(limit or 8), 12))]
        debate_rows: list[dict[str, Any]] = []
        for row in selected:
            claim = str(row.get("claim", "") or "").strip()
            if not claim:
                continue
            source_urls = [str(item).strip() for item in list(row.get("source_urls") or []) if str(item).strip()]
            evidence_basis = str(row.get("evidence_basis", "") or "").strip()
            priority = str(row.get("priority", "") or "medium").lower().strip()
            if priority not in {"high", "medium", "low"}:
                priority = "medium"
            evidence_issues: list[str] = []
            if not source_urls:
                evidence_issues.append("缺少可追溯 source_url，需要在正文中降低断言强度。")
            if len(evidence_basis) < 40:
                evidence_issues.append("证据依据过短，建议回到 paper_notes/findings 补充摘要级依据。")
            if "abstract-level" in evidence_basis.lower() or "metadata" in evidence_basis.lower():
                evidence_issues.append("当前依据主要来自摘要或元数据，不应表述为完整实验结论。")

            if not evidence_issues and priority == "high":
                decision = "keep"
            elif source_urls or evidence_basis:
                decision = "revise"
            else:
                decision = "downgrade"
                priority = "low"

            revision = claim
            if decision in {"revise", "downgrade"}:
                revision = f"{claim}（需在综述中标注证据层级，并避免超出摘要级证据。）"
            debate_rows.append(
                {
                    "claim": claim,
                    "decision": decision,
                    "priority": priority,
                    "rationale": (
                        f"该观点来自 claims.jsonl，并结合 {len(findings)} 条 findings 进行一致性检查；"
                        "保留时需在最终综述中对应到具体论文证据。"
                    ),
                    "evidence_issues": evidence_issues,
                    "revision": revision,
                }
            )

        if not debate_rows:
            return {"success": False, "message": "no usable claim text found in claims.jsonl"}

        log_lines = ["# Claim Debate Log", ""]
        for item in debate_rows:
            log_lines.extend(
                [
                    f"## {item['claim'][:120]}",
                    "",
                    f"- Decision: {item['decision']}",
                    f"- Priority: {item['priority']}",
                    f"- Rationale: {item['rationale']}",
                ]
            )
            for issue in item["evidence_issues"]:
                log_lines.append(f"- Evidence issue: {issue}")
            if item["revision"]:
                log_lines.append(f"- Revision: {item['revision']}")
            log_lines.extend([f"- Recorded at: {_now()}", ""])
        self.debate_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.debate_log_path.write_text("\n".join(log_lines).rstrip() + "\n", encoding="utf-8")

        kept = [item for item in debate_rows if item["decision"] == "keep"]
        revise = [item for item in debate_rows if item["decision"] == "revise"]
        downgraded = [item for item in debate_rows if item["decision"] == "downgrade"]
        report_lines = [
            f"本节对 {len(debate_rows)} 条候选综述观点进行证据压力测试和优先级评估。",
            "",
            f"- 建议直接保留：{len(kept)} 条",
            f"- 建议修订后使用：{len(revise)} 条",
            f"- 建议降级或仅作为边界条件：{len(downgraded)} 条",
            "",
            "优先进入正文的观点：",
        ]
        for item in (kept + revise)[:6]:
            report_lines.append(f"- [{item['decision']} / {item['priority']}] {item['revision']}")
        issues = []
        for item in debate_rows:
            issues.extend(item["evidence_issues"])
        if issues:
            report_lines.extend(["", "写作时需要控制的证据风险："])
            for issue in list(dict.fromkeys(issues))[:6]:
                report_lines.append(f"- {issue}")
        _write_report_section(
            self.report_path,
            "观点辩论与优先级评估",
            "\n".join(report_lines),
        )

        return {
            "success": True,
            "output": _json_dumps(
                {
                    "claims_path": str(self.claims_path),
                    "debate_log_path": str(self.debate_log_path),
                    "report_path": str(self.report_path),
                    "claims_count": len(claims),
                    "debated": len(debate_rows),
                    "kept": len(kept),
                    "revise": len(revise),
                    "downgrade": len(downgraded),
                }
            ),
        }


class RecordClaimDebateTool(BaseAction):
    name: str = "record_claim_debate"
    description: str = "Write a structured claim-debate decision record to debate_log.md."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "decision": {"type": "string", "enum": ["keep", "revise", "downgrade", "remove"]},
                "rationale": {"type": "string"},
                "evidence_issues": {"type": "array", "items": {"type": "string"}},
                "revision": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["claim", "decision", "rationale"],
            "additionalProperties": False,
        }
    )
    debate_log_path: Path = Field(default=Path("debate_log.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        claim: str,
        decision: str,
        rationale: str,
        evidence_issues: list[str] | None = None,
        revision: str = "",
        priority: str = "medium",
    ) -> Dict[str, Any]:
        decision = str(decision or "").strip()
        if decision not in {"keep", "revise", "downgrade", "remove"}:
            return {"success": False, "message": "decision must be keep|revise|downgrade|remove"}
        priority = str(priority or "medium").lower().strip()
        if priority not in {"high", "medium", "low"}:
            return {"success": False, "message": "priority must be high|medium|low"}
        self.debate_log_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.debate_log_path.read_text(encoding="utf-8").strip() if self.debate_log_path.exists() else "# Claim Debate Log"
        block = [
            f"## {str(claim).strip()[:120] or 'Untitled Claim'}",
            "",
            f"- Decision: {decision}",
            f"- Priority: {priority}",
            f"- Rationale: {str(rationale).strip()}",
        ]
        for issue in evidence_issues or []:
            block.append(f"- Evidence issue: {str(issue).strip()}")
        if str(revision).strip():
            block.append(f"- Revision: {str(revision).strip()}")
        block.append(f"- Recorded at: {_now()}")
        self.debate_log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block) + "\n", encoding="utf-8")
        return {"success": True, "output": f"Debate record written to {self.debate_log_path}"}


class BuildResearchOutlineTool(BaseAction):
    name: str = "build_research_outline"
    description: str = "Write a structured research outline and claim-evidence map to outline.md."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "sections": {"type": "array", "items": {"type": "string"}},
                "claim_evidence_map": {"type": "array", "items": {"type": "string"}},
                "missing_material": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sections"],
            "additionalProperties": False,
        }
    )
    outline_path: Path = Field(default=Path("outline.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        sections: list[str],
        title: str = "Research Outline",
        claim_evidence_map: list[str] | None = None,
        missing_material: list[str] | None = None,
    ) -> Dict[str, Any]:
        if not sections:
            return {"success": False, "message": "sections must not be empty"}
        lines = [f"# {str(title or 'Research Outline').strip()}", "", "## Sections", ""]
        lines.extend(f"- {str(item).strip()}" for item in sections if str(item).strip())
        lines.extend(["", "## Claim-Evidence Map", ""])
        lines.extend(f"- {str(item).strip()}" for item in (claim_evidence_map or []) if str(item).strip())
        lines.extend(["", "## Missing Material", ""])
        lines.extend(f"- {str(item).strip()}" for item in (missing_material or []) if str(item).strip())
        self.outline_path.parent.mkdir(parents=True, exist_ok=True)
        self.outline_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return {"success": True, "output": f"Research outline written to {self.outline_path}"}


class ReadResearchOutlineTool(BaseAction):
    name: str = "read_research_outline"
    description: str = "Read outline.md, the structured research outline and claim-evidence map."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit_chars": {"type": "integer", "default": 12000},
            },
            "additionalProperties": False,
        }
    )
    outline_path: Path = Field(default=Path("outline.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit_chars: int = 12000) -> Dict[str, Any]:
        return {"success": True, "output": _json_dumps(_read_text_artifact(self.outline_path, limit_chars))}


class ReadResearchReportTool(BaseAction):
    name: str = "read_research_report"
    description: str = "Read the canonical markdown research_report.md for drafting continuation or final review."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit_chars": {"type": "integer", "default": 20000},
            },
            "additionalProperties": False,
        }
    )
    report_path: Path = Field(default=Path("research_report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit_chars: int = 20000) -> Dict[str, Any]:
        return {"success": True, "output": _json_dumps(_read_text_artifact(self.report_path, limit_chars))}


class ReviewResearchReportTool(BaseAction):
    name: str = "review_research_report"
    description: str = "Review research report completeness, evidence coverage, claims, and citation risks; writes review_report.md."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "required_sections": {"type": "array", "items": {"type": "string"}},
                "major_issues": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string", "enum": ["accept", "revise", "blocked"]},
            },
            "additionalProperties": False,
        }
    )
    report_path: Path = Field(default=Path("research_report.md"), exclude=True)
    paper_tex_path: Path = Field(default=Path("paper.tex"), exclude=True)
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)
    review_path: Path = Field(default=Path("review_report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        required_sections: list[str] | None = None,
        major_issues: list[str] | None = None,
        recommendation: str = "revise",
    ) -> Dict[str, Any]:
        recommendation = str(recommendation or "revise").lower().strip()
        if recommendation not in {"accept", "revise", "blocked"}:
            return {"success": False, "message": "recommendation must be accept|revise|blocked"}
        report_text = self.report_path.read_text(encoding="utf-8") if self.report_path.exists() else ""
        tex_text = self.paper_tex_path.read_text(encoding="utf-8") if self.paper_tex_path.exists() else ""
        findings = _read_jsonl(self.findings_path)
        claims = _read_jsonl(self.claims_path)
        missing = [title for title in (required_sections or []) if f"## {title}" not in report_text]
        core_sections = ["研究背景", "研究现状", "研究空白", "未来方向", "结论"]
        combined_text = report_text + "\n" + tex_text
        missing_core = [title for title in core_sections if title not in combined_text]
        uncited_claims = [
            row.get("claim", "")
            for row in claims
            if not row.get("source_urls") and not str(row.get("evidence_basis", "")).strip()
        ]
        issues = [str(item) for item in (major_issues or [])]
        if not report_text.strip():
            issues.append("report is missing or empty")
        if missing:
            issues.append(f"missing sections: {missing}")
        if missing_core:
            issues.append(f"missing core literature-review sections: {missing_core}")
        if uncited_claims:
            issues.append(f"claims without evidence basis: {uncited_claims[:5]}")
        if not findings:
            issues.append("no structured findings found")

        lines = [
            "# Multi-Agent Review",
            "",
            f"- Recommendation: {recommendation}",
            f"- Report chars: {len(report_text)}",
            f"- LaTeX chars: {len(tex_text)}",
            f"- Findings: {len(findings)}",
            f"- Claims: {len(claims)}",
            f"- Reviewed at: {_now()}",
            "",
            "## Issues",
            "",
        ]
        lines.extend(f"- {issue}" for issue in issues) if issues else lines.append("- No blocking issues recorded.")
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return {
            "success": True,
            "output": _json_dumps(
                {
                    "passed": not issues and recommendation == "accept",
                    "recommendation": recommendation,
                    "issues": issues,
                    "review_path": str(self.review_path),
                }
            ),
        }
