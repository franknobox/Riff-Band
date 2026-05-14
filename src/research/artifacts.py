from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from research.schema import ResearchArtifact, ResearchRequest


def _slugify(text: str, max_len: int = 48) -> str:
    raw = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(text).lower()).strip("-")
    raw = re.sub(r"-{2,}", "-", raw)
    return (raw[:max_len].strip("-") or "research")


@dataclass(frozen=True)
class ResearchArtifacts:
    """Filesystem layout for one research-mode run."""

    run_dir: Path
    report_md: Path
    paper_tex: Path
    references_bib: Path
    report_html: Path
    findings: Path
    candidates: Path
    shortlist: Path
    papers: Path
    paper_notes: Path
    paper_cards: Path
    synthesis_digest: Path
    outline_context: Path
    claims: Path
    debate_log: Path
    outline: Path
    review: Path
    scratchpad: Path
    manifest: Path

    @classmethod
    def create(cls, workspace_dir: Path, request: ResearchRequest) -> "ResearchArtifacts":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = _slugify(request.topic)
        run_dir = workspace_dir / "output" / f"research_{stamp}_{slug}"
        artifacts = cls(
            run_dir=run_dir,
            report_md=run_dir / "research_report.md",
            paper_tex=run_dir / "paper.tex",
            references_bib=run_dir / "references.bib",
            report_html=run_dir / "report.html",
            findings=run_dir / "findings.jsonl",
            candidates=run_dir / "candidates.jsonl",
            shortlist=run_dir / "shortlist.jsonl",
            papers=run_dir / "papers.jsonl",
            paper_notes=run_dir / "paper_notes.jsonl",
            paper_cards=run_dir / "paper_cards.jsonl",
            synthesis_digest=run_dir / "synthesis_digest.json",
            outline_context=run_dir / "outline_context.json",
            claims=run_dir / "claims.jsonl",
            debate_log=run_dir / "debate_log.md",
            outline=run_dir / "outline.md",
            review=run_dir / "review_report.md",
            scratchpad=run_dir / "scratchpad" / "shared.md",
            manifest=run_dir / "manifest.json",
        )
        artifacts.ensure_dirs()
        return artifacts

    def ensure_dirs(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.scratchpad.parent.mkdir(parents=True, exist_ok=True)

    def to_artifacts(self, output_format: str) -> list[ResearchArtifact]:
        items = [
            ResearchArtifact(type="report", path=str(self.report_md), description="Canonical markdown research report"),
            ResearchArtifact(type="findings", path=str(self.findings), description="Structured research findings"),
            ResearchArtifact(type="candidates", path=str(self.candidates), description="Raw literature candidates before screening"),
            ResearchArtifact(type="shortlist", path=str(self.shortlist), description="Screened literature shortlist"),
            ResearchArtifact(type="papers", path=str(self.papers), description="Literature records and citation candidates"),
            ResearchArtifact(type="paper_notes", path=str(self.paper_notes), description="Lightweight structured notes extracted from paper abstracts or full text"),
            ResearchArtifact(type="paper_cards", path=str(self.paper_cards), description="Structured paper knowledge cards for literature review drafting"),
            ResearchArtifact(type="synthesis_digest", path=str(self.synthesis_digest), description="Clustered literature synthesis, research gaps, and evidence-quality digest"),
            ResearchArtifact(type="outline_context", path=str(self.outline_context), description="Compact outline-generation context derived from synthesis, claims, debate, and representative paper cards"),
            ResearchArtifact(type="claims", path=str(self.claims), description="Generated literature-review claims, research gaps, and future directions"),
            ResearchArtifact(type="debate", path=str(self.debate_log), description="Cross-perspective debate log"),
            ResearchArtifact(type="outline", path=str(self.outline), description="Structured report or paper outline"),
            ResearchArtifact(type="review", path=str(self.review), description="Multi-agent review notes"),
        ]
        if output_format == "latex":
            items.insert(0, ResearchArtifact(type="latex", path=str(self.paper_tex), description="LaTeX literature review draft"))
            items.insert(1, ResearchArtifact(type="bibtex", path=str(self.references_bib), description="BibTeX references for the LaTeX draft"))
        elif output_format == "html":
            items.insert(0, ResearchArtifact(type="html", path=str(self.report_html), description="HTML research report"))
        return items

    def write_manifest(self, request: ResearchRequest, step_records: list[dict[str, Any]]) -> None:
        payload = {
            "topic": request.topic,
            "depth": request.depth,
            "output_format": request.output_format,
            "constraints": request.constraints,
            "sources": request.sources,
            "artifacts": {
                "report_md": str(self.report_md),
                "paper_tex": str(self.paper_tex),
                "references_bib": str(self.references_bib),
                "report_html": str(self.report_html),
                "findings": str(self.findings),
                "candidates": str(self.candidates),
                "shortlist": str(self.shortlist),
                "papers": str(self.papers),
                "paper_notes": str(self.paper_notes),
                "paper_cards": str(self.paper_cards),
                "synthesis_digest": str(self.synthesis_digest),
                "outline_context": str(self.outline_context),
                "claims": str(self.claims),
                "debate_log": str(self.debate_log),
                "outline": str(self.outline),
                "review": str(self.review),
                "scratchpad": str(self.scratchpad),
            },
            "steps": step_records,
        }
        self.manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def ensure_text_artifact(path: Path, title: str, body: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")


def export_latex(markdown_path: Path, tex_path: Path, title: str, papers_path: Path | None = None, bib_path: Path | None = None) -> None:
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    papers = read_jsonl(papers_path) if papers_path is not None else []
    url_to_key = export_bibtex(papers, bib_path) if bib_path is not None else {}
    notes = read_jsonl(papers_path.parent / "paper_notes.jsonl") if papers_path is not None else []
    cards = read_jsonl(papers_path.parent / "paper_cards.jsonl") if papers_path is not None else []
    findings = read_jsonl(papers_path.parent / "findings.jsonl") if papers_path is not None else []
    claims = read_jsonl(papers_path.parent / "claims.jsonl") if papers_path is not None else []
    standard_lines = _standard_literature_review_latex(
        title=title,
        markdown=markdown,
        papers=papers,
        notes=notes,
        cards=cards,
        findings=findings,
        claims=claims,
        url_to_key=url_to_key,
        include_bibliography=bool(bib_path is not None and url_to_key),
    )
    tex_path.write_text("\n".join(standard_lines) + "\n", encoding="utf-8")
    return
    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{ctex}",
        r"\usepackage{geometry}",
        r"\usepackage{hyperref}",
        r"\geometry{margin=1in}",
        r"\title{" + _escape_latex(title) + "}",
        r"\author{Riff-Band Research Mode}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{abstract}",
        _escape_latex(_first_nonempty_paragraph(markdown) or f"本文围绕“{title}”整理已有文献、研究空白和未来方向。"),
        r"\end{abstract}",
        "",
    ]
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        line = _replace_urls_with_cites(line, url_to_key)
        if line.startswith("# "):
            lines.append(r"\section*{" + _escape_latex(line[2:].strip()) + "}")
        elif line.startswith("## "):
            lines.append(r"\section{" + _escape_latex(line[3:].strip()) + "}")
        elif line.startswith("### "):
            lines.append(r"\subsection{" + _escape_latex(line[4:].strip()) + "}")
        elif line.startswith("- "):
            lines.append(r"\noindent " + _escape_latex_preserving_citations(line[2:].strip()) + r"\\")
        elif re.match(r"^\d+\.\s+", line):
            lines.append(r"\noindent " + _escape_latex_preserving_citations(line) + r"\\")
        else:
            lines.append(_escape_latex_preserving_citations(line))
    if bib_path is not None and url_to_key:
        lines.extend(["", r"\bibliographystyle{plain}", r"\bibliography{references}"])
    lines.append(r"\end{document}")
    tex_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _legacy_standard_literature_review_latex(
    title: str,
    markdown: str,
    papers: list[dict[str, Any]],
    notes: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    url_to_key: dict[str, str],
    include_bibliography: bool,
) -> list[str]:
    citation = _first_citation(papers, url_to_key)
    note_summaries = [
        str(row.get("main_findings") or row.get("problem") or row.get("title") or "").strip()
        for row in notes[:5]
        if str(row.get("main_findings") or row.get("problem") or row.get("title") or "").strip()
    ]
    claim_texts = [str(row.get("claim", "")).strip() for row in claims[:5] if str(row.get("claim", "")).strip()]
    abstract = (
        f"本文围绕“{title}”开展文献综述，基于 {len(papers)} 条论文记录、{len(notes)} 条结构化论文笔记和 "
        f"{len(findings)} 条证据点，梳理研究背景、研究现状、关键方法、研究空白与未来方向。"
    )
    fallback = _first_nonempty_paragraph(markdown)
    sections = [
        (
            "研究背景、研究目的与意义",
            [
                f"智能反射面通过可编程调控无线传播环境，为通信感知一体化系统提供了新的系统设计自由度{citation}。",
                "本文的目的不是提出新的实验方案，而是基于已有论文记录总结该方向的研究脉络、证据强度和仍待解决的问题。",
            ],
        ),
        (
            "研究现状",
            [
                _join_or_default(note_summaries[:3], fallback or "现有论文主要围绕 RIS/IRS 辅助通信、感知增强和联合优化展开，但不同论文的证据深度并不一致。"),
                "从当前论文池看，直接面向 RIS-assisted ISAC 的论文与更宽泛的 RIS 通信论文同时存在；最终综述需要明确区分直接证据和背景性证据。",
            ],
        ),
        (
            "方法与主题综合",
            [
                "当前材料显示，相关研究通常围绕联合波束赋形、信道估计、资源分配、深度学习优化、STAR-RIS 或可移动 RIS 等主题展开。",
                "摘要级笔记可以支持主题分类和研究脉络梳理，但涉及性能优越性、实验设置和复杂度对比的判断仍需要全文阅读确认。",
            ],
        ),
        (
            "研究空白与未来方向",
            [
                _join_or_default(claim_texts, "主要研究空白包括动态场景鲁棒性、真实硬件约束、CSI 获取成本、感知与通信指标的统一评价，以及从仿真到实际部署的可迁移性。"),
                "未来工作可进一步围绕车联网、UAV、近场通信、STAR-RIS 和多目标资源优化展开，并补充可复现实验或公开数据支撑。",
            ],
        ),
        (
            "结论",
            [
                "总体而言，RIS/IRS 为 ISAC 提供了有潜力的环境可控层，但当前证据仍需要按来源强度分级使用。本文生成的综述草稿应作为后续人工全文阅读、引用核验和章节扩展的基础。"
            ],
        ),
    ]
    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{ctex}",
        r"\usepackage{geometry}",
        r"\usepackage{hyperref}",
        r"\geometry{margin=1in}",
        r"\title{" + _escape_latex(title) + "}",
        r"\author{Riff-Band Research Mode}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{abstract}",
        _escape_latex(abstract),
        r"\end{abstract}",
        "",
    ]
    for section_title, paragraphs in sections:
        lines.append(r"\section{" + _escape_latex(section_title) + "}")
        for paragraph in paragraphs:
            lines.append(_escape_latex_preserving_citations(paragraph))
            lines.append("")
    if include_bibliography:
        lines.extend(["", r"\bibliographystyle{plain}", r"\bibliography{references}"])
    lines.append(r"\end{document}")
    return lines


def _standard_literature_review_latex(
    title: str,
    markdown: str,
    papers: list[dict[str, Any]],
    notes: list[dict[str, Any]],
    cards: list[dict[str, Any]] | None = None,
    findings: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
    url_to_key: dict[str, str] | None = None,
    include_bibliography: bool = False,
) -> list[str]:
    cards = cards or []
    findings = findings or []
    claims = claims or []
    url_to_key = url_to_key or {}
    citation = _first_citation(papers, url_to_key)
    evidence_rows = cards if cards else notes
    summaries = [_card_summary(row) for row in evidence_rows[:8] if _card_summary(row)]
    claim_texts = [str(row.get("claim", "")).strip() for row in claims[:6] if str(row.get("claim", "")).strip()]
    fallback = _first_nonempty_paragraph(markdown)
    abstract = (
        f"本文围绕“{title}”开展文献综述，基于 {len(papers)} 条论文记录、"
        f"{len(cards) or len(notes)} 条结构化论文阅读卡片和 {len(findings)} 条证据点，"
        "梳理研究背景、研究现状、主题方法、研究空白与未来方向。"
    )
    sections = [
        (
            "研究背景、研究目的与意义",
            [
                f"智能反射面通过可编程调控无线传播环境，为通信感知一体化系统提供了新的系统设计自由度{citation}。",
                "本文的目标不是提出新的实验方案，而是基于已检索论文和结构化阅读卡片，整理该方向的研究脉络、证据强度、关键方法和仍待解决的问题。",
            ],
        ),
        (
            "研究现状",
            [
                _join_or_default(summaries[:4], fallback or "现有论文主要围绕 RIS/IRS 辅助通信、感知增强和联合优化展开，但不同论文的证据深度并不一致。"),
                "从当前论文池看，直接面向 RIS-assisted ISAC 的论文与更宽泛的 RIS 通信论文同时存在；最终综述需要明确区分直接证据和背景性证据。",
            ],
        ),
        (
            "方法与主题综合",
            [
                _method_synthesis(cards or notes),
                "摘要级阅读卡片可以支持主题分类和研究脉络梳理，但涉及性能优越性、实验设置和复杂度对比的判断仍需要全文阅读确认。",
            ],
        ),
        (
            "研究空白与未来方向",
            [
                _join_or_default(claim_texts, "主要研究空白包括动态场景鲁棒性、真实硬件约束、CSI 获取成本、感知与通信指标的统一评价，以及从仿真到实际部署的可迁移性。"),
                "未来工作可进一步围绕车联网、UAV、近场通信、STAR-RIS 和多目标资源优化展开，并补充可复现实验或公开数据支撑。",
            ],
        ),
        (
            "结论",
            [
                "总体而言，RIS/IRS 为 ISAC 提供了有潜力的环境可控层，但当前证据仍需要按来源强度分级使用。本文生成的综述草稿应作为后续人工全文阅读、引用核验和章节扩展的基础。"
            ],
        ),
    ]
    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{ctex}",
        r"\usepackage{geometry}",
        r"\usepackage{hyperref}",
        r"\geometry{margin=1in}",
        r"\title{" + _escape_latex(title) + "}",
        r"\author{Riff-Band Research Mode}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{abstract}",
        _escape_latex(abstract),
        r"\end{abstract}",
        "",
    ]
    for section_title, paragraphs in sections:
        lines.append(r"\section{" + _escape_latex(section_title) + "}")
        for paragraph in paragraphs:
            lines.append(_escape_latex_preserving_citations(paragraph))
            lines.append("")
    if include_bibliography:
        lines.extend(["", r"\bibliographystyle{plain}", r"\bibliography{references}"])
    lines.append(r"\end{document}")
    return lines


def _card_summary(row: dict[str, Any]) -> str:
    title = str(row.get("title", "") or "").strip()
    method = str(row.get("method", "") or "").strip()
    result = str(row.get("key_result") or row.get("main_findings") or row.get("problem") or "").strip()
    if title and result:
        return f"{title}：{result[:320]}"
    return result or title


def _method_synthesis(rows: list[dict[str, Any]]) -> str:
    methods = []
    for row in rows[:8]:
        text = str(row.get("method", "") or "").strip()
        if text and text not in methods:
            methods.append(text[:220])
    return _join_or_default(
        methods,
        "当前材料显示，相关研究通常围绕联合波束赋形、信道估计、资源分配、学习优化、STAR-RIS 或可移动 RIS 等主题展开。",
    )


def _first_citation(papers: list[dict[str, Any]], url_to_key: dict[str, str]) -> str:
    for row in papers:
        url = str(row.get("source_url", "") or "").strip()
        key = url_to_key.get(url)
        if key:
            return f" \\cite{{{key}}}"
    return ""


def _join_or_default(items: list[str], default: str) -> str:
    if not items:
        return default
    return " ".join(item.rstrip(".。") + "。" for item in items)


def export_bibtex(papers: list[dict[str, Any]], bib_path: Path | None) -> dict[str, str]:
    if bib_path is None:
        return {}
    entries: list[str] = []
    url_to_key: dict[str, str] = {}
    used: set[str] = set()
    for row in papers:
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        authors = [str(item).strip() for item in (row.get("authors", []) or []) if str(item).strip()]
        year = str(row.get("year", "") or row.get("published", "") or "n.d.")[:4]
        key_base = _bib_key(authors[0] if authors else "ref", year, title)
        key = key_base
        suffix = 2
        while key in used:
            key = f"{key_base}{suffix}"
            suffix += 1
        used.add(key)
        source_url = str(row.get("source_url", "")).strip()
        if source_url:
            url_to_key[source_url] = key
        fields = {
            "title": title,
            "author": " and ".join(authors),
            "year": year if year.isdigit() else "",
            "journal": row.get("venue", ""),
            "doi": row.get("doi", "") or (row.get("external_ids", {}) or {}).get("DOI", ""),
            "url": row.get("source_url", ""),
        }
        body = "\n".join(
            f"  {name} = {{{_escape_bibtex(value)}}},"
            for name, value in fields.items()
            if str(value or "").strip()
        )
        entries.append(f"@article{{{key},\n{body}\n}}")
    bib_path.parent.mkdir(parents=True, exist_ok=True)
    bib_path.write_text("\n\n".join(entries) + ("\n" if entries else ""), encoding="utf-8")
    return url_to_key


def _first_nonempty_paragraph(markdown: str) -> str:
    for block in re.split(r"\n\s*\n", markdown):
        text = " ".join(line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("#"))
        if text:
            return text[:800]
    return ""


def _replace_urls_with_cites(text: str, url_to_key: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        url = match.group(0).rstrip(".,;)")
        suffix = match.group(0)[len(url):]
        key = url_to_key.get(url)
        if key:
            return f"\\cite{{{key}}}{suffix}"
        return f"\\url{{{url}}}{suffix}"

    return re.sub(r"https?://[^\s)\]>\"']+", repl, text)


def _escape_latex_preserving_citations(text: str) -> str:
    escaped = _escape_latex(text)
    escaped = escaped.replace(r"\textbackslash{}cite\{", r"\cite{")
    escaped = escaped.replace(r"\textbackslash{}url\{", r"\url{")
    escaped = escaped.replace(r"\}", "}")
    return escaped


def _bib_key(author: str, year: str, title: str) -> str:
    family = str(author or "ref").split()[-1]
    raw = f"{family}-{year}-{title}"
    key = re.sub(r"[^A-Za-z0-9]+", "", raw.title())
    return key[:64] or "ref"


def _escape_bibtex(value: Any) -> str:
    return str(value or "").replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def export_html(markdown_path: Path, html_path: Path, title: str) -> None:
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    body: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            body.append(f"<h1>{escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{escape(line[3:].strip())}</h2>")
        elif line.startswith("- "):
            body.append(f"<p class=\"bullet\">{escape(line[2:].strip())}</p>")
        elif line:
            body.append(f"<p>{escape(line)}</p>")
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #172026; background: #f7f8fa; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 40px 24px 72px; background: #fff; min-height: 100vh; }}
    h1 {{ font-size: 32px; line-height: 1.2; margin: 0 0 24px; }}
    h2 {{ font-size: 21px; margin: 32px 0 12px; border-bottom: 1px solid #d8dee4; padding-bottom: 8px; }}
    p {{ line-height: 1.7; margin: 10px 0; }}
    .bullet {{ padding-left: 18px; position: relative; }}
    .bullet::before {{ content: "•"; position: absolute; left: 0; color: #59636e; }}
  </style>
</head>
<body><main>
{chr(10).join(body)}
</main></body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in str(text))
