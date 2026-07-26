from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

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
    papers: Path
    paper_notes: Path
    claims: Path
    debate_log: Path
    outline: Path
    review: Path
    scratchpad: Path
    manifest: Path
    paper_cards: Path
    synthesis_digest: Path
    # visual-only paths
    report_visual_html: Path
    sources: Path
    material_notes: Path
    insights: Path
    review_notes: Path

    @classmethod
    def create(cls, workspace_dir: Path, request: ResearchRequest, mode: str | None = None) -> "ResearchArtifacts":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        slug = _slugify(request.topic)
        run_key = f"{stamp}_{uuid4().hex[:8]}_{slug}"
        run_dir = workspace_dir / "research" / run_key
        out_dir = workspace_dir / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        report_prefix = out_dir / run_key
        artifacts = cls(
            run_dir=run_dir,
            report_md=run_dir / "research_report.md",
            paper_tex=Path(str(report_prefix) + "_paper.tex"),
            references_bib=Path(str(report_prefix) + "_references.bib"),
            report_html=Path(str(report_prefix) + "_report.html"),
            findings=run_dir / "findings.jsonl",
            papers=run_dir / "papers.jsonl",
            paper_notes=run_dir / "paper_notes.jsonl",
            claims=run_dir / "claims.jsonl",
            debate_log=run_dir / "debate_log.md",
            outline=run_dir / "outline.md",
            review=run_dir / "review_report.md",
            scratchpad=run_dir / "scratchpad" / "shared.md",
            manifest=run_dir / "manifest.json",
            paper_cards=run_dir / "paper_cards.jsonl",
            synthesis_digest=run_dir / "synthesis_digest.json",
            report_visual_html=Path(str(report_prefix) + "_visual.html"),
            sources=run_dir / "sources.jsonl",
            material_notes=run_dir / "material_notes.jsonl",
            insights=run_dir / "insights.jsonl",
            review_notes=run_dir / "review_notes.md",
        )
        artifacts.ensure_dirs()
        return artifacts

    def ensure_dirs(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.scratchpad.parent.mkdir(parents=True, exist_ok=True)

    def to_artifacts(self, output_format: str, mode: str = "academic") -> list[ResearchArtifact]:
        if mode == "visual":
            items = [
                ResearchArtifact(type="report", path=str(self.report_md), description="Canonical markdown research report"),
                ResearchArtifact(type="findings", path=str(self.findings), description="Structured research findings"),
                ResearchArtifact(type="sources", path=str(self.sources), description="Information source records"),
                ResearchArtifact(type="material_notes", path=str(self.material_notes), description="Lightweight structured notes extracted from materials"),
                ResearchArtifact(type="insights", path=str(self.insights), description="Generated insights, trends, and conclusions"),
                ResearchArtifact(type="review_notes", path=str(self.review_notes), description="Insight review and priority notes"),
                ResearchArtifact(type="outline", path=str(self.outline), description="Structured report outline"),
                ResearchArtifact(type="review", path=str(self.review), description="Quality review notes"),
            ]
            if output_format == "html" and self.report_visual_html.exists() and self.report_visual_html.stat().st_size > 0:
                items.insert(0, ResearchArtifact(type="html", path=str(self.report_visual_html), description="Visual HTML research report"))
        else:
            items = [
                ResearchArtifact(type="report", path=str(self.report_md), description="Canonical markdown research report"),
                ResearchArtifact(type="findings", path=str(self.findings), description="Structured research findings"),
                ResearchArtifact(type="papers", path=str(self.papers), description="Literature records and citation candidates"),
                ResearchArtifact(type="paper_notes", path=str(self.paper_notes), description="Lightweight structured notes extracted from paper abstracts or full text"),
                ResearchArtifact(type="paper_cards", path=str(self.paper_cards), description="Structured paper knowledge cards for literature review drafting"),
                ResearchArtifact(type="claims", path=str(self.claims), description="Generated literature-review claims, research gaps, and future directions"),
                ResearchArtifact(type="debate", path=str(self.debate_log), description="Cross-perspective debate log"),
                ResearchArtifact(type="outline", path=str(self.outline), description="Structured report or paper outline"),
                ResearchArtifact(type="review", path=str(self.review), description="Multi-agent review notes"),
                ResearchArtifact(type="synthesis_digest", path=str(self.synthesis_digest), description="Clustered literature synthesis, research gaps, and evidence-quality digest"),
            ]
            if output_format == "latex":
                items.insert(0, ResearchArtifact(type="latex", path=str(self.paper_tex), description="LaTeX literature review draft"))
                items.insert(1, ResearchArtifact(type="bibtex", path=str(self.references_bib), description="BibTeX references for the LaTeX draft"))
            elif output_format == "html":
                items.insert(0, ResearchArtifact(type="html", path=str(self.report_html), description="HTML research report"))
        return items

    def write_manifest(self, request: ResearchRequest, step_records: list[dict[str, Any]]) -> None:
        artifacts = {
            "report_md": str(self.report_md),
            "paper_tex": str(self.paper_tex),
            "references_bib": str(self.references_bib),
            "report_html": str(self.report_html),
            "findings": str(self.findings),
            "papers": str(self.papers),
            "paper_notes": str(self.paper_notes),
            "paper_cards": str(self.paper_cards),
            "claims": str(self.claims),
            "debate_log": str(self.debate_log),
            "outline": str(self.outline),
            "review": str(self.review),
            "scratchpad": str(self.scratchpad),
            "synthesis_digest": str(self.synthesis_digest),
        }
        if request.mode == "visual":
            artifacts["report_visual_html"] = str(self.report_visual_html)
            artifacts["sources"] = str(self.sources)
            artifacts["material_notes"] = str(self.material_notes)
            artifacts["insights"] = str(self.insights)
            artifacts["review_notes"] = str(self.review_notes)
        payload = {
            "topic": request.topic,
            "mode": request.mode,
            "depth": request.depth,
            "output_format": request.output_format,
            "constraints": request.constraints,
            "sources": request.sources,
            "artifacts": artifacts,
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




import mistune

CSS_PATH = Path(__file__).resolve().parent / "visual_report.css"
JS_PATH = Path(__file__).resolve().parent / "visual_report.js"


def _preprocess_visual_markdown(markdown: str) -> str:
    """Convert custom chart/table annotations to HTML blocks before mistune."""
    lines: list[str] = []
    for index, line in enumerate(markdown.splitlines(), start=1):
        stripped = line.strip()
        chart_match = re.match(r"!\[chart\]\(data:(\w+)\|(.*)\)\s*", stripped)
        if chart_match:
            chart_type = chart_match.group(1)
            chart_data = _safe_visual_json(chart_match.group(2))
            chart_id = f"chart-{index}"
            lines.append(
                f'<div id="{chart_id}" class="chart-container" data-chart-type="{escape(chart_type, quote=True)}">'
                f'<script type="application/json" class="chart-data">{chart_data}</script>'
                "</div>"
            )
            continue
        table_match = re.match(r"!\[table\]\(data:(.*)\)\s*", stripped)
        if table_match:
            table_data = _safe_visual_json(table_match.group(1))
            lines.append(
                '<div class="table-container">'
                f'<script type="application/json" class="table-data">{table_data}</script>'
                "</div>"
            )
            continue
        lines.append(line)
    return "\n".join(lines)


def _safe_visual_json(raw: str) -> str:
    """Normalize chart/table JSON for safe embedding in inert script tags."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"raw": str(raw)}
    text = json.dumps(payload, ensure_ascii=False)
    return text.replace("</", "<\\/")


def _postprocess_visual_html(html: str) -> str:
    """Wrap h2 sections in <section class='card'> for card layout."""
    result: list[str] = []
    parts = re.split(r"(<h2\b[^>]*>.*?</h2>)", html, flags=re.DOTALL)
    in_section = False
    for part in parts:
        if re.match(r"<h2\b", part):
            if in_section:
                result.append("</section>")
            result.append(f"<section>{part}")
            in_section = True
        else:
            result.append(part)
    if in_section:
        result.append("</section>")
    return "".join(result)


def _extract_toc_items(html: str) -> str:
    """Extract h1-h3 headings from HTML and build TOC links with IDs."""
    items: list[str] = []
    for m in re.finditer(r"<(h[123])\b[^>]*>(.*?)</\1>", html, flags=re.DOTALL):
        level = int(m.group(1)[1])
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        anchor = text.lower().replace(" ", "-")
        anchor = re.sub(r"[^\w\u4e00-\u9fff-]", "", anchor)
        items.append(f'<a href="#{anchor}" class="toc-l{level}">{escape(text)}</a>')
    return "\n".join(items)


def _add_anchor_ids(html: str) -> str:
    """Add id attributes to h1-h3 elements based on text content."""
    def repl(m: re.Match) -> str:
        tag = m.group(1)
        level = m.group(2)
        rest = m.group(3)
        text = re.sub(r"<[^>]+>", "", m.group(4)).strip()
        anchor = text.lower().replace(" ", "-")
        anchor = re.sub(r"[^\w\u4e00-\u9fff-]", "", anchor)
        return f"<{tag}{level} id=\"{anchor}\"{rest}>{m.group(4)}</{tag}{level}>"
    return re.sub(r"<(h)([123])([^>]*)>(.*?)</h\2>", repl, html)


def export_visual_html(
    markdown_path: Path,
    html_path: Path,
    title: str,
    artifacts: "ResearchArtifacts" | None = None,
    mode_label: str | None = None,
    product_label: str = "RiffBand Research Mode",
) -> None:
    """Generate a styled visual HTML report from markdown.

    Uses mistune for GFM-compatible markdown conversion, standalone
    CSS/JS for styling, and adds cover header, TOC with scroll
    highlighting, card sections, callout blocks, print support.
    """
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    if not markdown.strip():
        raise ValueError("visual markdown report is missing or empty; skip HTML export")

    markdown = _preprocess_visual_markdown(markdown)
    body_html = mistune.html(markdown)
    body_html = _add_anchor_ids(body_html)
    body_html = _postprocess_visual_html(body_html)
    toc_html = _extract_toc_items(body_html)
    echarts_script = (
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>'
        if 'class="chart-data"' in body_html
        else ""
    )

    css = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.exists() else ""
    js = JS_PATH.read_text(encoding="utf-8") if JS_PATH.exists() else ""

    run_dir = str(artifacts.run_dir) if artifacts else ""
    resolved_mode_label = mode_label or (
        "Visual" if (artifacts and hasattr(artifacts, "run_dir")) else "Research"
    )
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  {echarts_script}
  <style>{css}</style>
</head>
<body>
  <div class="navbar">
    <div class="navbar-inner">
      <span class="navbar-title">{escape(title)}</span>
      <span class="navbar-badge">{escape(resolved_mode_label)}</span>
      <button class="navbar-btn" onclick="toggleTheme()">🌓</button>
    </div>
  </div>
  <div class="layout">
    <aside class="sidebar">
      <nav class="toc">
        <div class="toc-title">Contents</div>
        {toc_html}
      </nav>
    </aside>
    <main class="content">
      <div class="cover">
        <h1>{escape(title)}</h1>
        <div class="cover-meta">
          <span>{now_str}</span>
          <span>{escape(product_label)}</span>
        </div>
      </div>
      <div class="prose">
        {body_html}
      </div>
      <div class="footer">{run_dir}</div>
    </main>
  </div>
  <script>
    {js}
    function renderChart(id, type, data) {{
      var el = document.getElementById(id);
      if (!el || !window.echarts) return;
      var chart = echarts.init(el);
      chart.setOption({{
        tooltip: {{}},
        legend: data.legend ? {{ data: data.legend }} : undefined,
        xAxis: {{ type: "category", data: data.categories || [] }},
        yAxis: {{ type: "value" }},
        series: data.series || [{{ data: data.values || [], type: type === "bar" ? "bar" : "line" }}]
      }});
      window.addEventListener("resize", function() {{ chart.resize(); }});
    }}
  </script>
</body>
</html>"""
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
