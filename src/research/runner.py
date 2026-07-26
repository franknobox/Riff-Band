from __future__ import annotations

import asyncio
from typing import Callable

from config import AgentConfig
from research.schema import ResearchRequest, ResearchResult
from research.pipeline import ResearchPipeline


async def run_research(
    request: ResearchRequest,
    config: AgentConfig,
    progress_callback: Callable[[str], None] | None = None,
    cancel_event: asyncio.Event | None = None,
) -> ResearchResult:
    """Run the fixed research-mode workflow.

    This boundary is shared by the CLI slash command and the MCP tool. The
    implementation intentionally keeps workflow control in code while reusing
    the existing MainAgent/SubAgent runtime for step execution.
    """
    pipeline = ResearchPipeline(
        request=request,
        config=config,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
    )
    return await pipeline.run()
