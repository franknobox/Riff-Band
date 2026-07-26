from __future__ import annotations

import unittest

from modes.router import ModeRouter


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response

    async def __call__(self, prompt: str):
        return self.response


class TestModeRouter(unittest.IsolatedAsyncioTestCase):
    async def test_rule_hard_multi_for_parallel_report(self):
        router = ModeRouter(llm=None)
        decision = await router.decide(
            "请并行调研这个行业的政策、公司格局和投资风险，并输出带来源证据的报告"
        )
        self.assertEqual(decision.mode, "multi")
        self.assertEqual(decision.source, "rule_hard")

    async def test_rule_hard_single_for_short_rewrite(self):
        router = ModeRouter(llm=None)
        decision = await router.decide("把这句话改写得更正式")
        self.assertEqual(decision.mode, "single")
        self.assertEqual(decision.source, "rule_hard")

    async def test_rule_multi_for_verification_artifacts(self):
        router = ModeRouter(llm=None)
        decision = await router.decide(
            "阅读这些资料，提取 findings，写成结构化报告，并验证报告是否包含来源链接"
        )
        self.assertEqual(decision.mode, "multi")

    async def test_llm_assist_on_ambiguous_task(self):
        fake = _FakeLLM('{"mode":"multi","confidence":"high","reason":"Needs decomposition"}')
        router = ModeRouter(llm=fake)
        decision = await router.decide("研究这个问题")
        self.assertEqual(decision.mode, "multi")
        self.assertEqual(decision.source, "llm_assist")

    def test_normalize_requested_mode(self):
        self.assertEqual(ModeRouter.normalize_requested_mode("single"), "single")
        self.assertEqual(ModeRouter.normalize_requested_mode("multi"), "multi")
        self.assertEqual(ModeRouter.normalize_requested_mode("auto"), "auto")
        self.assertEqual(ModeRouter.normalize_requested_mode(""), "auto")
        with self.assertRaises(ValueError):
            ModeRouter.normalize_requested_mode("route")


if __name__ == "__main__":
    unittest.main()
