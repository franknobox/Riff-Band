from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_ROOT = Path(__file__).resolve().parent / "data"


def _search_terms(text: str) -> set[str]:
    normalized = str(text or "").lower()
    terms = set(re.findall(r"[a-z][a-z0-9_-]{2,}", normalized))
    for sequence in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        terms.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return terms


class KnowledgeRegistry:
    @staticmethod
    @lru_cache(maxsize=4)
    def _load(filename: str) -> tuple[dict[str, Any], ...]:
        path = DATA_ROOT / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"knowledge registry must contain a list: {path}")
        return tuple(item for item in data if isinstance(item, dict))

    @classmethod
    def methods(cls) -> list[dict[str, Any]]:
        return [dict(item) for item in cls._load("methods_library.json")]

    @classmethod
    def data_sources(cls) -> list[dict[str, Any]]:
        return [dict(item) for item in cls._load("data_sources_library.json")]

    @classmethod
    def formulas(cls) -> list[dict[str, Any]]:
        return [dict(item) for item in cls._load("formula_library.json")]

    @staticmethod
    @lru_cache(maxsize=1)
    def diagnostic_registry() -> dict[str, Any]:
        path = DATA_ROOT / "diagnostic_rules.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(
            document.get("rules"), list
        ):
            raise ValueError(
                f"diagnostic registry must contain a rules list: {path}"
            )
        rules = [
            dict(item) for item in document["rules"] if isinstance(item, dict)
        ]
        ids = [str(item.get("id") or "") for item in rules]
        if len(rules) != 36 or len(set(ids)) != 36 or ids != [
            f"D{index:02d}" for index in range(1, 37)
        ]:
            raise ValueError(
                "diagnostic registry must contain the unique ordered rules D01-D36"
            )
        return {
            "schema_version": str(document.get("schema_version") or ""),
            "registry_version": str(document.get("registry_version") or ""),
            "published_at": str(document.get("published_at") or ""),
            "authority": str(document.get("authority") or ""),
            "rules": rules,
        }

    @classmethod
    def diagnostic_rules(
        cls,
        query: str = "",
        family: str = "",
        level: str = "",
        stage: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_query = str(query or "").strip().lower()
        result: list[dict[str, Any]] = []
        for item in cls.diagnostic_registry()["rules"]:
            if family and item.get("family") != family:
                continue
            if level and item.get("level") != level:
                continue
            if stage and item.get("stage") != stage:
                continue
            if normalized_query:
                haystack = " ".join(str(value) for value in item.values()).lower()
                if normalized_query not in haystack:
                    continue
            result.append(dict(item))
        return result[: max(1, min(limit, 100))]

    @classmethod
    def diagnostic_rule(cls, rule_id: str) -> dict[str, Any] | None:
        normalized = str(rule_id or "").strip().upper()
        return next(
            (
                dict(item)
                for item in cls.diagnostic_registry()["rules"]
                if item.get("id") == normalized
            ),
            None,
        )

    @classmethod
    def method_candidates(cls, goal: str = "", query: str = "", limit: int = 10) -> list[dict[str, Any]]:
        goal_keywords = {
            "causal": "因果识别 因果推断 实验 统计实证",
            "explain": "机制解释 实证解释 测量模型 定性研究 实验",
            "predict": "预测计算 机器学习 时序预测 文本",
            "optimize": "规范决策 运筹优化 组合优化 动态决策 随机系统 运营模型 解析建模",
            "synthesize": "证据综合 综述 元分析",
            "theory_build": "理论生成 定性研究 机制解释 结构估计",
            "explore": "探索 基础统计 网络科学 文本",
        }
        terms = _search_terms(f"{query} {goal_keywords.get(goal, '')}")
        scored = []
        for index, item in enumerate(cls.methods()):
            haystack = " ".join(str(value) for value in item.values()).lower()
            score = sum(1 for term in terms if term in haystack)
            if item.get("method_id") == "M01":
                score += 1
            scored.append((score, -index, item))
        scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
        return [cls._compact_method(item) for _score, _index, item in scored[: max(1, min(limit, 28))]]

    @classmethod
    def data_source_candidates(cls, query: str = "", limit: int = 12) -> list[dict[str, Any]]:
        terms = _search_terms(query)
        scored = []
        for index, item in enumerate(cls.data_sources()):
            haystack = " ".join(str(value) for value in item.values()).lower()
            score = sum(1 for term in terms if term in haystack)
            if item.get("connector_priority") == "P0":
                score += 1
            scored.append((score, -index, item))
        scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
        return [cls._compact_source(item) for _score, _index, item in scored[: max(1, min(limit, 40))]]

    @classmethod
    def formula_candidates(
        cls,
        query: str = "",
        method_ids: list[str] | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        terms = _search_terms(query)
        linked_formula_ids: set[str] = set()
        selected_methods = set(method_ids or [])
        for method in cls.methods():
            if method.get("method_id") not in selected_methods:
                continue
            linked_formula_ids.update(
                part.strip()
                for part in re.split(r"[,;\s]+", str(method.get("formula_ids") or ""))
                if part.strip()
            )
        scored = []
        for index, item in enumerate(cls.formulas()):
            haystack = " ".join(str(value) for value in item.values()).lower()
            score = sum(1 for term in terms if term in haystack)
            if item.get("formula_id") in linked_formula_ids:
                score += 8
            scored.append((score, -index, item))
        scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
        return [cls._compact_formula(item) for _score, _index, item in scored[: max(1, min(limit, 47))]]

    @staticmethod
    def _compact_method(item: dict[str, Any]) -> dict[str, Any]:
        keys = ("method_id", "family", "name", "lane", "goal", "data", "assumptions", "diagnostics", "failure")
        return {key: item.get(key, "") for key in keys}

    @staticmethod
    def _compact_source(item: dict[str, Any]) -> dict[str, Any]:
        keys = ("source_id", "domain", "name", "geography", "access", "cost", "typical_data", "common_use", "compliance", "url")
        return {key: item.get(key, "") for key in keys}

    @staticmethod
    def _compact_formula(item: dict[str, Any]) -> dict[str, Any]:
        keys = ("formula_id", "category", "name", "latex", "use_when", "assumptions", "diagnostics", "warning")
        return {key: item.get(key, "") for key in keys}
