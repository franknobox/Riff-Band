from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from base.engine.async_llm import AsyncLLM, LLMsConfig, create_llm_instance
from core.utils import parse_json_response


@dataclass
class ModeDecision:
    mode: str
    source: str
    reason: str
    signals: Dict[str, Any]


class ModeRouter:
    """Route auto mode to the final execution mode: single or multi."""

    SINGLE_MODE = "single"
    MULTI_MODE = "multi"
    VALID_FINAL_MODES = {SINGLE_MODE, MULTI_MODE}

    def __init__(self, llm: Optional[AsyncLLM] = None):
        self.llm = llm

    @classmethod
    def from_model_name(cls, model_name: str) -> "ModeRouter":
        llm = create_llm_instance(LLMsConfig.default().get(model_name))
        return cls(llm=llm)

    @staticmethod
    def normalize_requested_mode(mode: str | None) -> str:
        normalized = (mode or "auto").strip().lower()
        if not normalized:
            return "auto"
        if normalized not in {"single", "multi", "auto"}:
            raise ValueError(
                f"Invalid mode `{mode}`. Supported modes are: single, multi, auto."
            )
        return normalized

    @staticmethod
    def _matched_terms(text: str, terms: List[str]) -> List[str]:
        return [term for term in terms if term in text]

    def _rule_signals(self, task_text: str) -> Dict[str, Any]:
        text = (task_text or "").strip().lower()
        length = len(text)
        words = re.findall(r"[a-zA-Z0-9_\u4e00-\u9fff]+", text)

        parallel_terms = [
            "parallel",
            "concurrently",
            "multi-agent",
            "multi agent",
            "多个agent",
            "多agent",
            "多智能体",
            "并行",
            "同时",
        ]
        decomposition_terms = [
            "decompose",
            "break down",
            "multi-step",
            "subtask",
            "workflow",
            "拆解",
            "分解",
            "多步骤",
            "子任务",
            "流程",
        ]
        research_terms = [
            "research",
            "investigate",
            "analyze",
            "analysis",
            "evaluate",
            "compare",
            "调研",
            "研究",
            "分析",
            "评估",
            "比较",
            "对比",
        ]
        report_terms = [
            "report",
            "briefing",
            "recommendation",
            "recommendations",
            "报告",
            "简报",
            "建议",
            "结论",
        ]
        evidence_terms = [
            "evidence",
            "source",
            "sources",
            "citation",
            "citations",
            "finding",
            "findings",
            "引用",
            "来源",
            "证据",
            "依据",
            "材料",
        ]
        verification_terms = [
            "verify",
            "verification",
            "validate",
            "quality gate",
            "cross-check",
            "cross verify",
            "验证",
            "校验",
            "检查",
            "交叉验证",
        ]
        single_terms = [
            "quick",
            "brief",
            "one step",
            "simple",
            "summarize",
            "rewrite",
            "format",
            "translate",
            "快速",
            "简短",
            "简单",
            "单步",
            "总结",
            "改写",
            "润色",
            "翻译",
            "格式化",
        ]

        matched = {
            "parallel": self._matched_terms(text, parallel_terms),
            "decomposition": self._matched_terms(text, decomposition_terms),
            "research": self._matched_terms(text, research_terms),
            "report": self._matched_terms(text, report_terms),
            "evidence": self._matched_terms(text, evidence_terms),
            "verification": self._matched_terms(text, verification_terms),
            "single": self._matched_terms(text, single_terms),
        }

        numbered_steps = len(re.findall(r"(?:^|\n|\s)(?:\d+[\.\)]|[一二三四五六七八九十]+[、.])", text))
        bullet_count = len(re.findall(r"(?:^|\n)\s*[-*]\s+", text))
        question_count = len(re.findall(r"[?？]", text))
        clause_count = len(re.findall(r"[;；。]\s*", text))

        multi_score = 0
        multi_score += 5 if matched["parallel"] else 0
        multi_score += 3 if matched["decomposition"] else 0
        multi_score += 2 * min(len(matched["research"]), 3)
        multi_score += 3 if matched["report"] else 0
        multi_score += 3 if matched["evidence"] else 0
        multi_score += 3 if matched["verification"] else 0
        multi_score += min(numbered_steps + bullet_count, 4)
        multi_score += 2 if question_count >= 2 else 0
        multi_score += 1 if clause_count >= 3 else 0
        multi_score += 1 if length >= 180 else 0
        multi_score += 2 if length >= 360 else 0

        single_score = 0
        single_score += 3 if length <= 80 else 0
        single_score += 1 if 80 < length <= 160 else 0
        single_score += 2 if matched["single"] else 0
        single_score += 1 if not any(matched[key] for key in ["research", "report", "evidence", "verification"]) else 0

        hard_multi_reasons: List[str] = []
        if matched["parallel"]:
            hard_multi_reasons.append("explicit parallel or multi-agent intent")
        if matched["report"] and (matched["research"] or matched["evidence"]):
            hard_multi_reasons.append("report task with research/evidence requirements")
        if matched["verification"] and (matched["report"] or matched["evidence"] or matched["research"]):
            hard_multi_reasons.append("verification task with artifact/evidence requirements")
        if numbered_steps >= 3 or bullet_count >= 3:
            hard_multi_reasons.append("three or more explicit steps/items")
        if multi_score >= 8:
            hard_multi_reasons.append("high multi-agent complexity score")

        hard_single_reasons: List[str] = []
        if (
            length <= 100
            and not matched["parallel"]
            and not matched["decomposition"]
            and not matched["research"]
            and not matched["report"]
            and not matched["evidence"]
            and not matched["verification"]
            and numbered_steps == 0
            and bullet_count == 0
            and question_count <= 1
        ):
            hard_single_reasons.append("short one-step task without orchestration signals")

        return {
            "length": length,
            "word_count": len(words),
            "matched_terms": matched,
            "numbered_steps": numbered_steps,
            "bullet_count": bullet_count,
            "question_count": question_count,
            "clause_count": clause_count,
            "multi_score": multi_score,
            "single_score": single_score,
            "hard_multi_reasons": hard_multi_reasons,
            "hard_single_reasons": hard_single_reasons,
        }

    # 硬规则+软规则+LLM辅助决策mode
    async def decide(self, task_text: str) -> ModeDecision:
        signals = self._rule_signals(task_text)

        if signals["hard_multi_reasons"]:
            return ModeDecision(
                mode=self.MULTI_MODE,
                source="rule_hard",
                reason="; ".join(signals["hard_multi_reasons"]),
                signals=signals,
            )

        if signals["hard_single_reasons"]:
            return ModeDecision(
                mode=self.SINGLE_MODE,
                source="rule_hard",
                reason="; ".join(signals["hard_single_reasons"]),
                signals=signals,
            )

        multi_score = int(signals["multi_score"])
        single_score = int(signals["single_score"])
        score_delta = multi_score - single_score
        ambiguous = abs(score_delta) <= 2 or 2 <= multi_score <= 5

        if self.llm is not None and ambiguous:
            suggestion = await self._llm_suggest(task_text, signals)
            llm_mode = str(suggestion.get("mode", "")).strip().lower()
            llm_conf = str(suggestion.get("confidence", "")).strip().lower()
            llm_reason = str(suggestion.get("reason", "")).strip()

            if llm_mode in self.VALID_FINAL_MODES and llm_conf in {"medium", "high"}:
                return ModeDecision(
                    mode=llm_mode,
                    source="llm_assist",
                    reason=llm_reason or f"LLM suggests {llm_mode} with {llm_conf} confidence.",
                    signals={**signals, "llm_confidence": llm_conf},
                )

        if score_delta >= 2:
            return ModeDecision(
                mode=self.MULTI_MODE,
                source="rule_soft",
                reason=f"multi_score={multi_score} exceeds single_score={single_score}.",
                signals=signals,
            )

        return ModeDecision(
            mode=self.SINGLE_MODE,
            source="rule_soft",
            reason=f"single_score={single_score} is sufficient for a direct task; multi_score={multi_score}.",
            signals=signals,
        )

    async def _llm_suggest(self, task_text: str, signals: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are a routing assistant for an agent runtime.
Choose the final execution mode and return JSON only.

Allowed modes:
- single: one direct agent; use for short, one-step, low-evidence tasks.
- multi: coordinator plus workers; use for decomposable, evidence-heavy, report, research, comparison, verification, or parallel tasks.

Important:
- Do not return "auto". Auto is only the selection strategy.
- Return only one of "single" or "multi".

Rule signals:
{signals}

Task:
{task_text}

JSON schema:
{{
  "mode": "single|multi",
  "confidence": "low|medium|high",
  "reason": "short reason"
}}
""".strip()
        try:
            raw = await self.llm(prompt)
            parsed = parse_json_response(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
