# Developer Starter

这个目录不是完整可运行平台，而是把 PRD 转成第一批接口、表和配置，供你放进 Riff-Band 新分支。

## 建议使用顺序

1. 先复制 `config/management_science_profile.yaml`，实现 `DomainProfile`；
2. 用 `research_protocol.example.json`、`approval_record.example.json`、`stata_run_request.example.json` 和知识库 schema 建 Pydantic 模型；
3. 在旧 pipeline 上加 legacy adapter，不先重写全部 runtime；
4. 用 `db/schema.sql` 创建本地 PostgreSQL；
5. 让 CLI/MCP 调用同一 service 层；
6. 稳定后再实现 `api/openapi.yaml` 的 FastAPI 端点；
7. 实现 Revision/Approval 与 Stage Agent Registry 后，再接 Stata Runner；
8. 每个 backlog 项按 `05_roadmap/ACCEPTANCE_TESTS.md` 验收。

## 本地开发最小服务

```text
api             FastAPI
worker          Riff-Band orchestrator worker
postgres        project/protocol/papers/claims/runs
redis           task queue/event fan-out
minio           PDF/notebook/log/artifact
local-runner    optional Python/Stata BYOL execution
```

第一周可以没有 Redis/MinIO：任务同步运行、artifact 保存本地，但 service 接口与 ID/manifest 从第一天就按异步/对象存储设计。

## 三个递进竖切

竖切 1：

`Create Project → Create Protocol → Approve G1 → Search OpenAlex+Crossref → Dedupe → PaperCard v2 → Gate Report → Export JSON`

这个竖切通过前，不开发复杂 Web 图、沙箱集群或自动写作。

竖切 2：

`Research Idea → Topic Scout → RelatedResearchReport → Human edit → G0 → Protocol draft`

竖切 3：

`Analysis Plan draft → AI do-file patch → Human edit → G3 → Stata preflight/batch run → Robustness → G4`

Stata 只通过 `stata/README.md` 所述的自带许可 local/institution Runner 执行；开发仓库不包含 Stata 二进制、许可证或第三方 ado。
