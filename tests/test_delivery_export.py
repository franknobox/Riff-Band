from __future__ import annotations

import json
from zipfile import ZipFile

from ai4ms.delivery import DeliveryExportService


def _project() -> dict:
    evidence_content = {
        "claims": [
            {
                "claim_id": "C1",
                "claim_text": "现有论文支持 AI 采用与企业创新关系的有限文献综合判断。",
                "claim_type": "literature_synthesis",
                "status": "supported",
                "confidence": "medium",
                "scope": {
                    "population_or_system": "企业",
                    "time": "论文覆盖期",
                    "geography": "论文覆盖地区",
                    "boundary_conditions": ["不包含本地因果估计"],
                },
                "evidence": [
                    {
                        "evidence_id": "EV1",
                        "evidence_type": "paper",
                        "artifact_id": "paper_a",
                        "locator": "title and abstract",
                        "direction": "supports",
                        "strength": "moderate",
                    }
                ],
                "assumptions": [],
                "counterevidence": [],
                "uncertainty_note": "未完成本地估计，结论不能提升为因果判断。",
                "robustness_check_ids": [],
                "mechanism_ids": [],
            }
        ],
        "mechanisms": [],
        "heterogeneity": [],
        "limitations": ["本地估计尚未形成。"],
        "interpretation": "只报告有论文依据的有限关系，不补造运行结果。",
        "unknowns": ["本地估计结果"],
    }
    delivery_content = {
        "title": "AI 采用与创新 <script>alert(1)</script>",
        "executive_summary": "现有论文支持有限关系判断，但本地估计尚未形成，因此不能确认因果效应。",
        "conclusions": [
            {
                "conclusion_id": "CON1",
                "statement": "当前证据只能支持 AI 采用与创新关系的有限文献综合结论。",
                "claim_ids": ["C1"],
                "evidence_ids": ["EV1"],
                "status": "supported",
                "scope_note": "限于论文覆盖范围。",
            }
        ],
        "policy_implications": [],
        "outline": [
            {"section_id": "SEC1", "title": "研究问题", "purpose": "说明研究边界。", "claim_ids": [], "evidence_ids": []},
            {"section_id": "SEC2", "title": "证据", "purpose": "展示可追溯证据。", "claim_ids": ["C1"], "evidence_ids": ["EV1"]},
            {"section_id": "SEC3", "title": "结论", "purpose": "形成有限结论。", "claim_ids": ["C1"], "evidence_ids": ["EV1"]},
        ],
        "reference_paper_ids": ["paper_a"],
        "approved_claims": ["C1"],
        "references": [{"paper_id": "paper_a", "title": "Paper A", "authors": ["Li"], "year": 2025}],
        "limitations": ["没有本地估计。"],
        "reproducibility_notes": ["结论保留 claim_id 与 evidence_id。"],
        "disclosure": "报告为 AI 辅助草稿，最终内容由研究者审批。",
        "release_notes": "首次交付。",
        "unknowns": ["本地估计结果"],
        "exports": [],
        "visual_report_path": "",
        "research_package_path": "",
    }
    return {
        "project_id": "prj_export",
        "title": "AI 采用与创新",
        "initial_idea": "AI 采用是否影响企业创新？",
        "stages": [
            {"key": "problem", "code": "S0", "title": "问题识别", "status": "approved", "revision": 1, "content_hash": "0" * 64, "content": {}},
            {"key": "literature", "code": "S1", "title": "文献综述", "status": "approved", "revision": 2, "content_hash": "1" * 64, "content": {"papers": [{"paper_id": "paper_a", "title": "Paper A", "authors": ["Li"], "year": 2025}]}},
            {"key": "analysis", "code": "S6", "title": "结果分析", "status": "approved", "revision": 3, "content_hash": "6" * 64, "content": {"runs": [{"run_id": "run_1", "status": "succeeded", "reason_code": "completed", "exit_code": 0, "do_file_sha256": "a" * 64, "structured_results": [{"name": "beta", "value": 0.2}], "output_artifacts": [{"path": "artifacts/runs/run_1/results.csv"}, {"path": "artifacts/runs/run_1/raw.dta"}], "manifest_path": "artifacts/runs/run_1/manifest.json"}]}},
            {"key": "robustness", "code": "S7", "title": "稳健性检验", "status": "approved", "revision": 1, "content_hash": "7" * 64, "content": {"robustness_matrix": []}},
            {"key": "evidence", "code": "S8", "title": "机制与异质性", "status": "approved", "revision": 2, "content_hash": "8" * 64, "content": evidence_content},
            {"key": "delivery", "code": "S9", "title": "结论与政策含义", "status": "needs_review", "revision": 1, "content_hash": "9" * 64, "content": delivery_content},
        ],
        "approvals": [],
    }


def test_delivery_export_is_traceable_visual_and_excludes_raw_data(tmp_path):
    project = _project()
    run_dir = tmp_path / "prj_export" / "artifacts" / "runs" / "run_1"
    run_dir.mkdir(parents=True)
    (run_dir / "results.csv").write_text("term,estimate\nai_adoption,0.2\n", encoding="utf-8")
    (run_dir / "raw.dta").write_bytes(b"private raw data")
    (run_dir / "manifest.json").write_text('{"run_id":"run_1"}', encoding="utf-8")

    service = DeliveryExportService(tmp_path)
    record = service.export(project)
    export_dir = tmp_path / "prj_export" / record["visual_report_path"].rsplit("/", 1)[0]
    html = (export_dir / "report.html").read_text(encoding="utf-8")
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))

    assert "Claim-Evidence 可追溯矩阵" in html
    assert "renderVisualArtifacts" in html
    assert 'class="table-data"' in html
    assert "cdn.jsdelivr.net" not in html
    assert "<script>alert(1)</script>" not in html
    assert manifest["source_revisions"]["evidence"]["content_hash"] == "8" * 64
    assert manifest["data_policy"]["raw_data_included"] is False
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])

    with ZipFile(export_dir / "research_package.zip") as archive:
        names = set(archive.namelist())
    assert "artifacts/runs/run_1/results.csv" in names
    assert "artifacts/runs/run_1/manifest.json" in names
    assert not any(name.endswith(".dta") for name in names)
    assert {"report/report.html", "report/report.md", "project/project_snapshot.json", "manifest.json"} <= names


def test_delivery_fingerprint_changes_only_for_scientific_content():
    content = _project()["stages"][-1]["content"]
    first = DeliveryExportService.delivery_fingerprint(content)
    content["exports"] = [{"export_id": "export_1"}]
    content["visual_report_path"] = "exports/export_1/report.html"
    content["_workspace"] = {"human_confirmed": True}
    assert DeliveryExportService.delivery_fingerprint(content) == first

    content["conclusions"][0]["statement"] = "修改后的结论内容必须触发重新导出。"
    assert DeliveryExportService.delivery_fingerprint(content) != first
