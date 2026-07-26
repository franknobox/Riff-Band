from __future__ import annotations

from typing import Any, List, Optional

from pydantic import Field
import json
import re
from base.agent.base_agent import BaseAgent
from base.engine.logs import LogLevel, logger
from base.engine.utils import parse_llm_action_response
from agents.memory import Memory
from core.interfaces import Action, TaskContext
from core.message import ContentPart



def _extract_optional_memory(resp: str) -> Optional[str]:
    """Best-effort extraction for the optional memory field without warning noise."""
    if not resp:
        return None

    candidates: list[str] = []
    json_block = re.search(r"```json\s*([\s\S]*?)```", resp)
    if json_block:
        candidates.append(json_block.group(1).strip())
    generic_block = re.search(r"```\s*([\s\S]*?)```", resp)
    if generic_block:
        candidates.append(generic_block.group(1).strip())
    if "{" in resp and "}" in resp:
        blob = re.search(r"\{[\s\S]*\}", resp)
        if blob:
            candidates.append(blob.group(0))
    candidates.append(resp.strip())

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict) and "memory" in payload:
            value = payload.get("memory")
            return str(value) if value is not None else None
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and "memory" in item:
                    value = item.get("memory")
                    return str(value) if value is not None else None

    match = re.search(r"memory\s*[:=]\s*(.+)", resp)
    return match.group(1).strip() if match else None


class SubAgent(BaseAgent):
    """通用子智能体，用于执行委派的研究、验证和产物生成任务。"""

    name: str = Field(default="SubAgent")
    description: str = Field(default="执行聚焦委派任务的子智能体")
    task_instruction: str = Field(default="")
    context: str = Field(default="")
    original_question: str = Field(default="")
    allowed_tools: Optional[List[str]] = Field(default=None)
    current_env_instruction: str = Field(default="")
    current_action_space: str = Field(default="")
    memory: Memory = Field(default=None)
    preserve_memory_on_reset: bool = Field(default=False)
    prompt_builder: Any = Field(default=None) 
    task_label: str = Field(default="")



    def reset(self, task_context: TaskContext) -> None:
        if self.memory is None:
            self.memory = Memory(llm=self.llm, max_memory=10)
        elif not self.preserve_memory_on_reset:
            self.memory.clear()

        self.current_action_space = task_context.action_space

        if not self.original_question:
            self.original_question = task_context.instruction

        # Tool filtering (if allowed_tools specified)
        label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
        if self.allowed_tools:
            self.current_action_space = self._filter_action_space(
                task_context.action_space, 
                self.allowed_tools
            )
            logger.info(
                f"[ResearchSubAgent] {label} = {self.task_instruction} "
                f"Filtered to tools: {self.allowed_tools}"
            )
        else:
            self.current_action_space = task_context.action_space

    def _normalize_tool_name(self, name: str) -> str:
        normalized = name.lower().replace("_", "")
        if normalized.endswith("action"):
            normalized = normalized[:-6]
        return normalized
    
    def _tool_matches(self, tool_name: str, allowed_tools: List[str]) -> bool:
        if tool_name in allowed_tools:
            return True

        normalized_tool = self._normalize_tool_name(tool_name)
        for allowed in allowed_tools:
            if self._normalize_tool_name(allowed) == normalized_tool:
                return True
        return False

    # 过滤LLM返回的action space，保留allowed_tools中允许的工具
    def _filter_action_space(self, action_space: str, allowed_tools: List[str]) -> str:
        if not allowed_tools:
            return action_space

        blocks = re.split(r"\n(?=### )", action_space)
        filtered_blocks = []

        for block in blocks:
            if block.startswith("Available actions") or block.startswith("可用操作"):
                filtered_blocks.append(block.rstrip())
                continue

            match = re.match(r"### (\w+)", block)
            if match:
                tool_name = match.group(1)
                if self._tool_matches(tool_name, allowed_tools):
                    filtered_blocks.append(block.rstrip())

        return "\n\n".join(filtered_blocks)        

    def _get_memory(self) -> str:
        return self.memory.as_text() if self.memory else "无"

    def _build_fast_partial_finish(self) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "由于没有本地资料且联网搜索不可用，已提前停止。",
                "completed": [],
                "issues": [
                    "没有可用本地资料。",
                    "缺少 SERPER_API_KEY，联网搜索未启用。",
                ],
                "result": "请在 sources_dir 下添加本地资料，或配置 SERPER_API_KEY 后重试。",
            },
            "memory": "由于数据来源不可用，执行已提前停止。",
        }

    def _build_no_access_finish(self, error: str) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "由于本地资料为空且联网搜索访问失败，已提前停止。",
                "completed": [],
                "issues": [
                    "没有可用本地资料。",
                    f"联网搜索错误: {error}",
                ],
                "result": "请添加本地资料，或修复 Serper 授权后重试。",
            },
            "memory": "由于本地资料为空且联网搜索授权失败，执行已停止。",
        }
    

    def _build_search_disabled_finish(self) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "联网搜索未启用，无法完成需要外部信息的任务。",
                "completed": [],
                "issues": [
                    "缺少可用联网搜索能力。",
                    "请配置 SERPER_API_KEY，或启用可用的搜索后端。",
                ],
                "result": "请配置可用搜索凭据后重试。",
            },
            "memory": "由于联网搜索不可用，执行已提前停止。",
        }

    def _build_search_access_finish(self, error: str) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "联网搜索授权失败，无法继续收集外部证据。",
                "completed": [],
                "issues": [f"联网搜索错误: {error}"],
                "result": "请修复 Serper 授权或启用可用搜索后端后重试。",
            },
            "memory": "由于联网搜索授权失败，执行已停止。",
        }

    async def step(
        self,
        observation: Any,
        history: Any,
        current_step: int = 1,
        max_steps: int = 20,
    ) -> tuple[Action, str, str]:
        if self.prompt_builder is None:
            raise ValueError("SubAgent requires a prompt_builder")

        if isinstance(observation, dict) and current_step == 1:
            source_count = int(observation.get("source_count", 0))
            search_enabled = bool(observation.get("search_enabled", False))
            if source_count == 0 and not search_enabled:
                action = self._build_search_disabled_finish()
                raw_response = "自动结束：本地资料为空且联网搜索未启用。"
                raw_response = "auto finish: web search is not enabled."
                label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
                logger.agent_action(f"[ResearchSubAgent] {label}Action: {action}")
                return action, raw_response, "No prompt sent due to fast-finish guard."

        if isinstance(observation, dict):
            is_web_fail = (
                observation.get("action") == "web_search"
                and observation.get("success") is False
                and isinstance(observation.get("error"), str)
            )
            if is_web_fail:
                error_text = str(observation.get("error", "web_search failed"))
                unauthorized = ("403" in error_text) or ("Unauthorized" in error_text)
                first_obs = history[0].observation if history else {}
                source_count = int(first_obs.get("source_count", 0)) if isinstance(first_obs, dict) else 0
                if source_count == 0 and unauthorized:
                    action = self._build_search_access_finish(error_text)
                    raw_response = "自动结束：本地资料为空且联网搜索未授权。"
                    raw_response = "auto finish: web search is unauthorized."
                    label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
                    logger.agent_action(f"[ResearchSubAgent] {label}Action: {action}")
                    return action, raw_response, "No prompt sent due to web-access guard."

        prompt = self.prompt_builder.build_prompt(
            task_instruction=self.task_instruction,
            context=self.context,
            original_question=self.original_question,
            action_space=self.current_action_space,
            observation=observation,
            memory=self._get_memory(),
            current_step=current_step,
            max_steps=max_steps,
        )
        
        label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
        logger.log_to_file(LogLevel.INFO, f"[ResearchSubAgent] {label}Prompt:\n{prompt}\n")

        response = await self.llm(prompt)
        

        # Parse response
        thinking = _extract_optional_memory(response)
        action = parse_llm_action_response(response)

        
        logger.agent_action(f"[ResearchSubAgent] {label}Action: {action}")

        # 记忆存储
        if self.memory:
            previous_obs = history[-1].info.get("last_action_result") if history else observation
            await self.memory.add_memory(
                obs=previous_obs,
                action=action,
                thinking=thinking,
                raw_response=response,
            )

        return action, response, prompt

    async def stream_step(
        self,
        observation: Any,
        history: Any,
        current_step: int = 1,
        max_steps: int = 20,
    ):
        """Like step(), but yields ContentPart chunks during LLM generation."""
        # Reuse fast-finish guards
        if self.prompt_builder is None:
            raise ValueError("SubAgent requires a prompt_builder")

        if isinstance(observation, dict) and current_step == 1:
            source_count = int(observation.get("source_count", 0))
            search_enabled = bool(observation.get("search_enabled", False))
            if source_count == 0 and not search_enabled:
                action = self._build_search_disabled_finish()
                raw_response = "自动结束：本地资料为空且联网搜索未启用。"
                raw_response = "auto finish: web search is not enabled."
                yield action, raw_response, "No prompt sent due to fast-finish guard."
                return

        if isinstance(observation, dict):
            is_web_fail = (
                observation.get("action") == "web_search"
                and observation.get("success") is False
                and isinstance(observation.get("error"), str)
            )
            if is_web_fail:
                error_text = str(observation.get("error", "web_search failed"))
                unauthorized = ("403" in error_text) or ("Unauthorized" in error_text)
                first_obs = history[0].observation if history else {}
                source_count = int(first_obs.get("source_count", 0)) if isinstance(first_obs, dict) else 0
                if source_count == 0 and unauthorized:
                    action = self._build_search_access_finish(error_text)
                    raw_response = "自动结束：本地资料为空且联网搜索未授权。"
                    raw_response = "auto finish: web search is unauthorized."
                    yield action, raw_response, "No prompt sent due to web-access guard."
                    return

        prompt = self.prompt_builder.build_prompt(
            task_instruction=self.task_instruction,
            context=self.context,
            original_question=self.original_question,
            action_space=self.current_action_space,
            observation=observation,
            memory=self._get_memory(),
            current_step=current_step,
            max_steps=max_steps,
        )

        # Stream LLM response
        full_response_parts: list[str] = []
        async for chunk in self.llm.stream_response(prompt):
            full_response_parts.append(chunk)
            yield ContentPart(text=chunk)

        full_response = "".join(full_response_parts)

        # Parse response
        thinking = _extract_optional_memory(full_response)
        action = parse_llm_action_response(full_response)

        # Memory
        if self.memory:
            previous_obs = history[-1].info.get("last_action_result") if history else observation
            await self.memory.add_memory(
                obs=previous_obs,
                action=action,
                thinking=thinking,
                raw_response=full_response,
            )

        yield action, full_response, prompt

    async def run(self, request: Optional[str] = None) -> str:
        return request or ""


# Backward compatibility alias
ResearchSubAgent = SubAgent

