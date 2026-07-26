from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai4ms.literature.broker import LiteratureBroker, SUPPORTED_BACKENDS
from ai4ms.services.models import LiteratureSearchRequest


class LiteratureSearchInputError(ValueError):
    pass


class LiteratureSearchService:
    def __init__(self, projects_dir: str | Path, broker: LiteratureBroker | None = None) -> None:
        self.projects_dir = Path(projects_dir)
        self.broker = broker or LiteratureBroker()

    async def search(
        self,
        project_id: str,
        stage_content: dict[str, Any],
        request: LiteratureSearchRequest,
    ) -> dict[str, Any]:
        queries = list(request.queries)
        if not queries:
            for block in stage_content.get("query_blocks", []):
                if not isinstance(block, dict):
                    continue
                queries.extend([str(block.get("query_en") or ""), str(block.get("query_zh") or "")])
        queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))[: request.max_queries]
        if not queries:
            raise LiteratureSearchInputError("literature search requires explicit queries or an S1 model-generated query plan")

        backends = list(request.backends or SUPPORTED_BACKENDS)
        result = await self.broker.search(
            queries,
            backends,
            limit_per_backend=request.limit_per_backend,
            year_from=request.year_from or stage_content.get("year_from"),
            year_to=request.year_to or stage_content.get("year_to"),
        )
        payload = result.as_dict()
        relative_path = Path("artifacts") / "literature" / f"{result.search_id}.json"
        target = self.projects_dir / project_id / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
        payload["snapshot_path"] = relative_path.as_posix()
        return payload
