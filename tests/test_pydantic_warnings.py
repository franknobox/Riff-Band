from __future__ import annotations

import subprocess
import sys


def test_imports_do_not_emit_pydantic_v2_config_warnings():
    script = "\n".join(
        [
            "import warnings",
            "from pydantic.warnings import PydanticDeprecatedSince20",
            "warnings.simplefilter('error', PydanticDeprecatedSince20)",
            "import agents.main_agent",
            "import agents.sub_agent",
            "import orchestration_tools.delegate",
            "import project.tools.finding_tools",
            "import project.tools.literature_tools",
            "import project.tools.report_tools",
            "import project.tools.research_phase_tools",
            "import project.tools.scratchpad_tools",
            "import project.tools.source_tools",
            "import project.tools.verification_tools",
            "import project.tools.web_search_tool",
        ]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
        ],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
