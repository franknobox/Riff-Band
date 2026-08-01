from __future__ import annotations

import re
from typing import Any

from ai4ms.literature.normalize import normalize_doi, normalize_title


INLINE_SOURCE_MARKER = re.compile(
    r"\[(paper|claim|evidence):([A-Za-z0-9_.:-]+)\]"
)


class AcademicOutputQualityService:
    """Deterministic checks for traceability and academic-output consistency."""

    RULES_VERSION = "ai4ms.academic-output-quality.v1"

    @classmethod
    def audit(
        cls,
        project: dict[str, Any],
        delivery_content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stages = {
            str(stage.get("key")): stage
            for stage in project.get("stages", [])
            if isinstance(stage, dict)
        }
        problem = stages.get("problem", {}).get("content", {})
        evidence = stages.get("evidence", {}).get("content", {})
        delivery_stage = stages.get("delivery", {})
        delivery = delivery_content or delivery_stage.get("content", {})
        issues: list[dict[str, str]] = []

        def add(
            rule_id: str,
            severity: str,
            dimension: str,
            location: str,
            finding: str,
            required_action: str,
        ) -> None:
            issues.append(
                {
                    "rule_id": rule_id,
                    "severity": severity,
                    "dimension": dimension,
                    "location": location,
                    "finding": finding,
                    "required_action": required_action,
                }
            )

        profile = (
            delivery.get("document_profile")
            if isinstance(delivery.get("document_profile"), dict)
            else None
        )
        sections = [
            section
            for section in delivery.get("manuscript_sections", [])
            if isinstance(section, dict)
        ]
        if profile is None:
            add(
                "OUT-STRUCT-001",
                "should_improve",
                "structure",
                "document_profile",
                "尚未声明文档类型、研究范式、受众与引用格式。",
                "补充 document_profile；管理学检查必须按研究范式适用，而非套用单一实证模板。",
            )
        if not sections:
            add(
                "OUT-STRUCT-002",
                "should_improve",
                "structure",
                "manuscript_sections",
                "当前交付只有大纲，没有可逐节审阅和同步的正文。",
                "按 outline 生成 manuscript_sections，并为每节声明主张、证据和论文 ID。",
            )

        claim_registry = {
            str(item.get("claim_id")): item
            for item in evidence.get("claims", [])
            if isinstance(item, dict) and item.get("claim_id")
        }
        evidence_registry = {
            str(item.get("evidence_id")): item
            for claim in claim_registry.values()
            for item in claim.get("evidence", [])
            if isinstance(item, dict) and item.get("evidence_id")
        }
        literature = stages.get("literature", {}).get("content", {})
        evidence_library = {
            str(item.get("evidence_id")): item
            for item in literature.get("evidence_library", [])
            if isinstance(item, dict)
            and item.get("status", "active") == "active"
            and item.get("evidence_id")
        }
        known_papers = {
            str(item.get("paper_id")): item
            for item in evidence_library.values()
            if item.get("evidence_type") == "paper"
            and item.get("paper_id")
        }
        evidence_id_by_paper = {
            paper_id: str(item.get("evidence_id"))
            for paper_id, item in known_papers.items()
        }
        reference_ids = {
            str(item)
            for item in delivery.get("reference_paper_ids", [])
            if str(item).strip()
        }
        reference_evidence_ids = {
            str(item)
            for item in delivery.get("reference_evidence_ids", [])
            if str(item).strip()
        }

        cited_papers: set[str] = set()
        cited_claims: set[str] = set()
        cited_evidence: set[str] = set()
        cited_library_evidence: set[str] = set()
        seen_sections: set[str] = set()
        for section in sections:
            section_id = str(section.get("section_id") or "")
            if section_id in seen_sections:
                add(
                    "OUT-STRUCT-003",
                    "must_fix",
                    "structure",
                    section_id or "manuscript_sections",
                    f"正文 section_id 重复：{section_id}",
                    "为每个正文小节分配唯一 section_id。",
                )
            seen_sections.add(section_id)
            declared = {
                "paper": {str(item) for item in section.get("citation_paper_ids", [])},
                "claim": {str(item) for item in section.get("claim_ids", [])},
                "evidence": {str(item) for item in section.get("evidence_ids", [])},
            }
            declared_library_evidence = {
                str(item)
                for item in section.get("citation_evidence_ids", [])
                if str(item).strip()
            }
            markers: dict[str, set[str]] = {
                "paper": set(),
                "claim": set(),
                "evidence": set(),
            }
            for kind, identifier in INLINE_SOURCE_MARKER.findall(
                str(section.get("body_markdown") or "")
            ):
                markers[kind].add(identifier)

            cited_papers.update(declared["paper"] | markers["paper"])
            cited_claims.update(declared["claim"] | markers["claim"])
            cited_evidence.update(declared["evidence"] | markers["evidence"])
            cited_library_evidence.update(declared_library_evidence)
            for kind in ("paper", "claim", "evidence"):
                undeclared = markers[kind] - declared[kind]
                if undeclared:
                    add(
                        f"OUT-CITE-{kind.upper()}-001",
                        "must_fix",
                        "citation",
                        section_id,
                        f"正文标记未在本节 {kind} ID 清单中声明：{sorted(undeclared)}",
                        "同步正文标记与小节 ID 清单，避免不可见来源进入正文。",
                    )
                unused = declared[kind] - markers[kind]
                if unused and str(section.get("body_markdown") or "").strip():
                    add(
                        f"OUT-CITE-{kind.upper()}-002",
                        "should_improve",
                        "citation",
                        section_id,
                        f"本节声明了但正文未使用的 {kind} ID：{sorted(unused)}",
                        "删除未使用 ID，或在对应论述处加入显式来源标记。",
                    )
            expected_library_evidence = {
                evidence_id_by_paper[paper_id]
                for paper_id in declared["paper"]
                if paper_id in evidence_id_by_paper
            }
            if (
                len(expected_library_evidence) != len(declared["paper"])
                or not expected_library_evidence.issubset(
                    declared_library_evidence
                )
            ):
                add(
                    "OUT-CITE-LIB-001",
                    "must_fix",
                    "citation",
                    section_id,
                    "本节至少一条论文引用没有对应的 evidence_library 记录。",
                    "为每个 citation_paper_id 声明对应的 "
                    "citation_evidence_id；数据研究可额外直接声明 EVLIB_*。",
                )
            unknown_section_library = (
                declared_library_evidence - set(evidence_library)
            )
            outside_reference_library = (
                declared_library_evidence - reference_evidence_ids
            )
            if unknown_section_library or outside_reference_library:
                add(
                    "OUT-CITE-LIB-004",
                    "must_fix",
                    "citation",
                    section_id,
                    "本节引用了未批准或未进入参考文献权威清单的 "
                    f"evidence_library ID："
                    f"{sorted(unknown_section_library | outside_reference_library)}",
                    "只保留 active 的 EVLIB_*，并同步到 "
                    "reference_evidence_ids。",
                )

        unknown_papers = cited_papers - set(known_papers)
        unknown_claims = cited_claims - set(claim_registry)
        unknown_evidence = cited_evidence - set(evidence_registry)
        for rule_id, label, values in (
            ("OUT-CITE-003", "paper_id", unknown_papers),
            ("OUT-CITE-004", "claim_id", unknown_claims),
            ("OUT-CITE-005", "evidence_id", unknown_evidence),
        ):
            if values:
                add(
                    rule_id,
                    "must_fix",
                    "citation",
                    "manuscript_sections",
                    f"正文引用了不存在或不可用的 {label}：{sorted(values)}",
                    "删除该引用，或先把真实来源保存到相应上游资产。",
                )

        missing_references = cited_papers - reference_ids
        unused_references = reference_ids - cited_papers
        if missing_references:
            add(
                "OUT-CITE-006",
                "must_fix",
                "citation",
                "reference_paper_ids",
                f"正文论文引用未进入参考文献清单：{sorted(missing_references)}",
                "补齐 reference_paper_ids，并由服务端从 S1 元数据生成书目。",
            )
        if unused_references and sections:
            add(
                "OUT-CITE-007",
                "should_improve",
                "citation",
                "reference_paper_ids",
                f"参考文献清单存在正文未引用条目：{sorted(unused_references)}",
                "删除孤立条目，或在相关综合论述中准确引用。",
            )
        expected_reference_evidence = {
            evidence_id_by_paper[paper_id]
            for paper_id in reference_ids
            if paper_id in evidence_id_by_paper
        }
        if (
            len(expected_reference_evidence) != len(reference_ids)
            or not expected_reference_evidence.issubset(
                reference_evidence_ids
            )
        ):
            add(
                "OUT-CITE-LIB-002",
                "must_fix",
                "citation",
                "reference_evidence_ids",
                "至少一条论文参考文献没有链接到人工批准的 "
                "evidence_library 记录。",
                "为每个 reference_paper_id 声明对应的 "
                "reference_evidence_id；数据研究可直接使用 EVLIB_*。",
            )
        unknown_reference_evidence = (
            reference_evidence_ids - set(evidence_library)
        )
        if unknown_reference_evidence:
            add(
                "OUT-CITE-LIB-005",
                "must_fix",
                "citation",
                "reference_evidence_ids",
                "参考文献权威清单包含未批准或已归档的 evidence_library "
                f"记录：{sorted(unknown_reference_evidence)}",
                "删除该 ID，或先由研究者审核并激活对应证据记录。",
            )
        unused_reference_evidence = (
            reference_evidence_ids - cited_library_evidence
        )
        if unused_reference_evidence and sections:
            add(
                "OUT-CITE-LIB-006",
                "should_improve",
                "citation",
                "reference_evidence_ids",
                "权威参考清单存在正文未声明的证据记录："
                f"{sorted(unused_reference_evidence)}",
                "删除孤立记录，或在相关分节的 citation_evidence_ids "
                "中准确声明。",
            )

        seen_dois: dict[str, str] = {}
        seen_titles: dict[str, str] = {}
        references = [
            item
            for item in delivery.get("references", [])
            if isinstance(item, dict)
        ]
        generated_reference_evidence_ids = {
            str(item.get("evidence_id"))
            for item in references
            if item.get("evidence_id")
        }
        if generated_reference_evidence_ids != reference_evidence_ids:
            add(
                "OUT-CITE-LIB-007",
                "must_fix",
                "citation",
                "references",
                "确定性书目记录与 reference_evidence_ids 不一致。",
                "由服务端从 active evidence_library 重新生成全部书目记录。",
            )
        for reference in references:
            paper_id = str(reference.get("paper_id") or "")
            library_evidence_id = str(reference.get("evidence_id") or "")
            authority_record = evidence_library.get(library_evidence_id)
            is_paper = bool(
                authority_record
                and authority_record.get("evidence_type") == "paper"
            )
            invalid_paper_binding = bool(
                is_paper
                and (
                    not paper_id
                    or evidence_id_by_paper.get(paper_id)
                    != library_evidence_id
                )
            )
            if authority_record is None or invalid_paper_binding:
                add(
                    "OUT-CITE-LIB-003",
                    "must_fix",
                    "citation",
                    paper_id or library_evidence_id or "references",
                    "书目记录未绑定有效的 evidence_library ID。",
                    "由服务端从已批准证据记录重新生成参考文献。",
                )
            required_fields = (
                ("title", "authors", "year")
                if is_paper
                else ("title", "url")
            )
            missing = [
                field
                for field in required_fields
                if reference.get(field) in (None, "", [])
            ]
            if (
                paper_id in cited_papers
                or library_evidence_id in cited_library_evidence
            ) and missing:
                add(
                    "OUT-CITE-008",
                    "must_fix",
                    "citation",
                    paper_id or library_evidence_id,
                    f"已引用来源缺少必要书目字段：{missing}",
                    "回到 S1 核验权威记录；不得由模型猜测补全。",
                )
            doi = normalize_doi(reference.get("doi"))
            title = normalize_title(reference.get("title"))
            reference_id = paper_id or library_evidence_id
            duplicate_of = seen_dois.get(doi) if doi else seen_titles.get(title)
            if duplicate_of and duplicate_of != reference_id:
                add(
                    "OUT-CITE-009",
                    "must_fix",
                    "citation",
                    reference_id,
                    f"参考文献与 {duplicate_of} 疑似重复。",
                    "依据 DOI、规范化标题和作者年份人工核验并去重。",
                )
            if doi:
                seen_dois[doi] = reference_id
            if title:
                seen_titles[title] = reference_id

        closure = [
            item
            for item in delivery.get("logic_closure", [])
            if isinstance(item, dict)
        ]
        conclusion_ids = {
            str(item.get("conclusion_id"))
            for item in delivery.get("conclusions", [])
            if isinstance(item, dict) and item.get("conclusion_id")
        }
        if not closure:
            add(
                "OUT-LOGIC-001",
                "should_improve",
                "logic",
                "logic_closure",
                "尚未形成“研究问题—方法/设计—主张—结论”闭环表。",
                "为每个核心研究问题建立 logic_closure，并保留阻塞或缺失环节。",
            )
        else:
            linked_conclusions = {
                str(conclusion_id)
                for item in closure
                for conclusion_id in item.get("conclusion_ids", [])
            }
            missing_conclusions = conclusion_ids - linked_conclusions
            if missing_conclusions:
                add(
                    "OUT-LOGIC-002",
                    "must_fix",
                    "logic",
                    "logic_closure",
                    f"核心结论未进入逻辑闭环：{sorted(missing_conclusions)}",
                    "把结论连接到原研究问题、方法/设计与获批主张。",
                )
            for item in closure:
                if item.get("closure_status") != "closed":
                    add(
                        "OUT-LOGIC-003",
                        "should_improve",
                        "logic",
                        str(item.get("link_id") or "logic_closure"),
                        f"逻辑闭环状态为 {item.get('closure_status')}：{item.get('missing_link', '')}",
                        "在正文限制中披露缺口；补证前不得将其写成已闭合结论。",
                    )

        if profile and profile.get("common_method_bias_applicability") == "required":
            combined = "\n".join(str(section.get("body_markdown") or "") for section in sections)
            if not re.search(r"共同方法偏差|common method bias|\bCMB\b", combined, re.IGNORECASE):
                add(
                    "OUT-MGMT-001",
                    "should_improve",
                    "academic_style",
                    "manuscript_sections",
                    "文档声明共同方法偏差检查适用，但正文未见相应设计或检验说明。",
                    "说明程序控制与适用的统计检查；不要把 Harman 单因子检验机械套用于所有研究。",
                )

        absolute_patterns = (
            r"(?<!未)证明了",
            r"首次(?!作为候选)",
            r"完全空白",
            r"无人研究",
            r"\bproves?\b",
            r"\bno prior research\b",
        )
        prose = "\n".join(
            [
                str(delivery.get("abstract") or ""),
                str(delivery.get("executive_summary") or ""),
                *[str(section.get("body_markdown") or "") for section in sections],
            ]
        )
        hits = sorted(
            {
                match.group(0)
                for pattern in absolute_patterns
                for match in re.finditer(pattern, prose, re.IGNORECASE)
            }
        )
        if hits:
            add(
                "OUT-STYLE-001",
                "should_improve",
                "academic_style",
                "正文",
                f"检测到可能超过证据强度的绝对表述：{hits}",
                "结合研究设计与证据等级逐句核验，改为有边界的学术表达。",
            )

        for item in delivery.get("author_self_review", []):
            if not isinstance(item, dict) or item.get("severity") != "must_fix":
                continue
            add(
                f"OUT-SELF-{item.get('issue_id', 'UNKNOWN')}",
                "must_fix",
                str(item.get("dimension") or "logic"),
                str(item.get("location") or "author_self_review"),
                str(item.get("finding") or "作者自检标记为必须修复。"),
                str(item.get("required_action") or "修复后重新运行质量检查。"),
            )

        severity_order = {"must_fix": 0, "should_improve": 1, "note": 2}
        issues.sort(
            key=lambda item: (
                severity_order.get(item["severity"], 9),
                item["rule_id"],
                item["location"],
            )
        )
        counts = {
            severity: sum(1 for item in issues if item["severity"] == severity)
            for severity in ("must_fix", "should_improve", "note")
        }
        return {
            "schema_version": cls.RULES_VERSION,
            "delivery_revision": delivery_stage.get("revision", 0),
            "delivery_content_hash": delivery_stage.get("content_hash", ""),
            "status": (
                "needs_revision"
                if counts["must_fix"]
                else "ready_with_advisories"
                if counts["should_improve"]
                else "ready"
            ),
            "counts": counts,
            "issues": issues,
            "traceability": {
                "section_count": len(sections),
                "cited_paper_ids": sorted(cited_papers),
                "cited_claim_ids": sorted(cited_claims),
                "cited_evidence_ids": sorted(cited_evidence),
                "cited_evidence_library_ids": sorted(
                    cited_library_evidence
                ),
                "reference_paper_ids": sorted(reference_ids),
                "reference_evidence_ids": sorted(
                    reference_evidence_ids
                ),
                "approved_evidence_library_ids": sorted(
                    evidence_library
                ),
                "problem_question_count": len(
                    problem.get("question_candidates") or problem.get("questions") or []
                ),
            },
        }
