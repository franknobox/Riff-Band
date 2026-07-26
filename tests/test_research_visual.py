from __future__ import annotations

from research.steps import RESEARCH_STEPS, VISUAL_STEPS


def test_visual_steps_keys_unique():
    keys = [s.key for s in VISUAL_STEPS]
    assert len(keys) == len(set(keys))


def test_visual_steps_all_have_skills():
    for step in VISUAL_STEPS:
        assert step.skill


def test_academic_steps_unchanged():
    assert len(RESEARCH_STEPS) == 9
    assert any(s.key == "literature_search" for s in RESEARCH_STEPS)


def test_visual_steps_count():
    assert len(VISUAL_STEPS) == 10


def test_visual_steps_include_visual_design():
    keys = [s.key for s in VISUAL_STEPS]
    assert "visual_design" in keys
    assert "quality_review" in keys


def test_visual_steps_decompose_has_no_report_required():
    step = VISUAL_STEPS[0]
    assert step.key == "decompose_topic"
    assert step.report_required is False


def test_registry_loads_academic_skill_from_root():
    from research.skills import ResearchSkillRegistry
    reg = ResearchSkillRegistry(mode="academic")
    text = reg.load_text("decompose-topic")
    assert "课题拆解" in text


def test_registry_loads_visual_skill_from_subdir():
    from research.skills import ResearchSkillRegistry
    reg = ResearchSkillRegistry(mode="visual")
    text = reg.load_text("decompose-topic")
    assert "课题拆解" in text


def test_registry_visual_has_all_ten_skills():
    from research.skills import ResearchSkillRegistry
    reg = ResearchSkillRegistry(mode="visual")
    for step in VISUAL_STEPS:
        text = reg.load_text(step.skill)
        assert len(text) > 50


def test_request_defaults_to_academic():
    from research.schema import ResearchRequest
    req = ResearchRequest(topic="test")
    assert req.mode == "academic"
    assert req.output_format == "latex"


def test_visual_request_defaults():
    from research.schema import ResearchRequest
    req = ResearchRequest(topic="test", mode="visual")
    assert req.mode == "visual"


def test_required_report_sections_by_mode():
    from research.steps import required_report_sections
    academic = required_report_sections("academic")
    visual = required_report_sections("visual")
    assert "文献检索与证据表" in academic
    assert "信息检索与证据表" in visual
    assert len(visual) == len([s for s in VISUAL_STEPS if s.report_required])


def test_artifacts_to_artifacts_visual_html():
    from pathlib import Path
    from research.artifacts import ResearchArtifacts
    from research.schema import ResearchRequest
    req = ResearchRequest(topic="test", mode="visual", output_format="html")
    arts = ResearchArtifacts.create(Path("/tmp/workspace"), req)
    arts.report_visual_html.write_text("<html></html>", encoding="utf-8")
    items = arts.to_artifacts("html", mode="visual")
    types = [i.type for i in items]
    assert "html" in types
    assert "sources" in types
    assert "material_notes" in types
    assert "insights" in types
    assert "papers" not in types
    assert "claims" not in types


def test_artifacts_to_artifacts_visual_omits_missing_html():
    from pathlib import Path
    from research.artifacts import ResearchArtifacts
    from research.schema import ResearchRequest
    req = ResearchRequest(topic="test", mode="visual", output_format="html")
    arts = ResearchArtifacts.create(Path("/tmp/workspace"), req)
    items = arts.to_artifacts("html", mode="visual")
    types = [i.type for i in items]
    assert "html" not in types


def test_artifacts_to_artifacts_academic_latex():
    from pathlib import Path
    from research.artifacts import ResearchArtifacts
    from research.schema import ResearchRequest
    req = ResearchRequest(topic="test", mode="academic", output_format="latex")
    arts = ResearchArtifacts.create(Path("/tmp/workspace"), req)
    items = arts.to_artifacts("latex", mode="academic")
    types = [i.type for i in items]
    assert "latex" in types
    assert "bibtex" in types
    assert "papers" in types
    assert "claims" in types
    assert "sources" not in types


def test_export_visual_html_generates_file():
    from pathlib import Path
    import tempfile
    from research.artifacts import export_visual_html
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "report.md"
        html = Path(tmp) / "report.html"
        md.write_text("# Title\n\n## Section A\n\n- bullet 1\n\n![chart](data:bar|{\"categories\":[\"a\"],\"values\":[1]})\n\n![table](data:{\"headers\":[\"h\"],\"rows\":[[\"v\"]]})\n", encoding="utf-8")
        export_visual_html(md, html, "Test Title")
        assert html.exists()
        content = html.read_text(encoding="utf-8")
        assert "Test Title" in content
        assert "chart-container" in content
        assert "table-container" in content
        assert "Section A" in content
        assert "echarts" in content


def test_export_visual_html_requires_nonempty_markdown():
    from pathlib import Path
    import tempfile
    import pytest
    from research.artifacts import export_visual_html
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "missing.md"
        html = Path(tmp) / "report.html"
        with pytest.raises(ValueError, match="markdown report is missing or empty"):
            export_visual_html(md, html, "Test Title")
        assert not html.exists()


def test_gatekeeper_visual_step_checks():
    from pathlib import Path
    import tempfile
    from research.artifacts import ResearchArtifacts
    from research.gates import ResearchGatekeeper
    from research.schema import ResearchRequest
    from research.steps import VISUAL_STEPS
    with tempfile.TemporaryDirectory() as tmp:
        req = ResearchRequest(topic="test", mode="visual")
        arts = ResearchArtifacts.create(Path(tmp), req)
        gate = ResearchGatekeeper(arts, mode="visual")
        info_search = [s for s in VISUAL_STEPS if s.key == "information_search"][0]
        result = gate.check_step(info_search)
        assert "sources count" in str(result.issues)


def test_gatekeeper_visual_final_checks_html():
    from pathlib import Path
    import tempfile
    from research.artifacts import ResearchArtifacts
    from research.gates import ResearchGatekeeper
    from research.schema import ResearchRequest
    with tempfile.TemporaryDirectory() as tmp:
        req = ResearchRequest(topic="test", mode="visual", output_format="html")
        arts = ResearchArtifacts.create(Path(tmp), req)
        arts.report_md.write_text("# Test\n\n## Section\n\nhttp://example.com\n", encoding="utf-8")
        gate = ResearchGatekeeper(arts, mode="visual")
        result = gate.check_final(min_findings=0, output_format="html", min_papers=0)
        assert "visual HTML report was not generated" in result.issues


def test_gatekeeper_visual_final_requires_rendering_script():
    from pathlib import Path
    import tempfile
    from research.artifacts import ResearchArtifacts
    from research.gates import ResearchGatekeeper
    from research.schema import ResearchRequest
    from research.steps import required_report_sections
    with tempfile.TemporaryDirectory() as tmp:
        req = ResearchRequest(topic="test", mode="visual", output_format="html")
        arts = ResearchArtifacts.create(Path(tmp), req)
        sections = "\n\n".join(
            f"## {section}\n\ncontent https://example.com/{idx}"
            for idx, section in enumerate(required_report_sections("visual"), start=1)
        )
        arts.report_md.write_text(f"# Test\n\n{sections}\n", encoding="utf-8")
        arts.report_visual_html.write_text(
            '<html><body><div class="chart-container"></div></body></html>',
            encoding="utf-8",
        )
        gate = ResearchGatekeeper(arts, mode="visual")
        result = gate.check_final(min_findings=0, output_format="html", min_papers=0)
        assert "visual HTML report does not include chart/table rendering script" in result.issues
