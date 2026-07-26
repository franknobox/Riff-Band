# 建议的最小增量目录（Sprint 0）

第一阶段不要做完整目标树，只新增下面结构：

```text
src/
  domains/
    __init__.py
    base.py
    management_science/
      __init__.py
      profile.yaml
      protocol.py
      screening.py
      extraction.py
      gates.py
  protocols/
    __init__.py
    models.py
    legacy_adapter.py
  artifacts_v2/
    __init__.py
    manifest.py
tests/
  benchmarks/
    management_science/
      causal_ai_adoption.yaml
      low_carbon_routing.yaml
      platform_supply_chain.yaml
```

接口最小定义：

```python
class DomainProfile(Protocol):
    name: str
    protocol_schema_version: str
    def expand_queries(self, protocol): ...
    def screen_paper(self, paper, protocol): ...
    def extract_schema(self): ...
    def gates_for(self, protocol): ...
```

`management_science/profile.yaml` 只保存通用学科配置：期刊池、研究目标、泳道、方法 ID、卡片字段和门禁映射；不得写某个具体课题词表。课题关键词属于 Protocol。

