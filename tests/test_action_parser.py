from __future__ import annotations

from base.engine.utils import parse_llm_action_response


def test_action_parser_ignores_think_json_and_uses_later_action():
    response = """
<think>
{"plan": "Need one more step before finishing."}
</think>

{"action": "finish", "params": {"answer": "done"}}
"""

    action = parse_llm_action_response(response)

    assert action["action"] == "finish"
    assert action["params"]["answer"] == "done"


def test_action_parser_recovers_common_jsonish_action():
    response = """
<think>Need to call a tool.</think>

```json
{
  action: 'search_sources',
  params: {
    query: 'low altitude economy Shenzhen',
  },
}
```
"""

    action = parse_llm_action_response(response)

    assert action["action"] == "search_sources"
    assert action["params"]["query"] == "low altitude economy Shenzhen"
