# AI4MS 六项完成度审计

日期：2026-07-25
目标分支：`ai4ms`
审计范围：诊断注册表、界面偏好、资产版本、HTML 使用说明、Stata Runner、深层页面端到端测试。

## 结论

六项均已实现并进入自动测试。代码以 `ai4s` 的最新 Runner 为运行时基线，同时保留 `ai4ms` 原有论文语料、产品方案、非技术介绍和开发包。

| # | 要求 | 状态 | 权威实现 |
|---|---|---|---|
| 1 | 36 条诊断规则迁入后端并提供版本化 API | 已完成 | `diagnostic_rules.json`；`GET /api/v1/knowledge/diagnostics`；单条规则 API；版本头、ETag、数量与顺序校验 |
| 2 | 三套界面偏好同步到用户 profile，保留本地恢复 | 已完成 | SQLite `user_profiles`；`GET/PATCH /api/v1/profile`；前端 localStorage-first、profile reconciliation |
| 3 | 资产章节保存连接 revision/patch API | 已完成 | `PATCH /api/v1/projects/{project_id}/stages/{stage_key}/asset-sections/{section_key}`；乐观 revision 冲突；章节进入阶段不可变 revision |
| 4 | HTML 使用说明自动注入版本和检查部署链接 | 已完成 | `prepare-user-guide.mjs`；`predev/prebuild`；本地链接清单；可选线上 HEAD/GET 检查 |
| 5 | Stata 隔离、队列、取消、超时、日志、产物哈希 | 已完成 | Local Runner 临时目录与签名 Bundle；任务状态持久化与单实例执行队列；并发槽；排队/运行取消；进程组超时终止；日志 API；下载前再次校验 SHA-256 |
| 6 | 深层页面 E2E | 已完成 | Playwright 覆盖项目创建、单项整改、智能体同步、资产下钻/保存、人工审批；FastAPI 契约测试覆盖持久化和冲突 |

## 关键 API

```text
GET   /api/v1/knowledge/diagnostics
GET   /api/v1/knowledge/diagnostics/{rule_id}
GET   /api/v1/profile
PATCH /api/v1/profile
PATCH /api/v1/projects/{project_id}/stages/{stage_key}/asset-sections/{section_key}

GET   /api/v1/runners/stata
POST  /api/v1/projects/{project_id}/stages/analysis/runs
GET   /api/v1/projects/{project_id}/stages/analysis/runs
GET   /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}
GET   /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/result
GET   /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/artifacts/{path}
POST  /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/cancel
POST  /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/rerun
```

## Stata 的可执行边界

- 平台不打包 Stata，也不处理许可证密钥；研究者使用自己合法安装且有权使用的 Stata。
- Local Runner 每个任务创建独立临时目录，只接收签名运行包，复核 do-file 与输入哈希，并只返回允许类型且逐项登记哈希的产物。
- `AI4MS_ANALYSIS_MAX_CONCURRENCY` 控制真正的执行槽；超出槽位的任务保持 `queued`。
- 取消贯通工作台、任务服务、Local Runner 和活动进程；POSIX 超时会终止整个新建进程组，避免子进程继续占用日志管道。
- 这是应用级工作目录、输入和进程隔离，不宣称等价于操作系统级沙箱。处理受限数据时，应部署到机构专用账户/节点，并通过防火墙、RBAC 与主机策略补齐 OS 级边界。
- Windows 可使用 `scripts/stata-runner/` 下的 `SETUP`、`START`、`CHECK` 脚本完成配对和自检。

## 自动验证

```bash
# 后端
.venv/bin/python -m pytest -q

# 前端静态质量
cd src/web
npm run test:guide
npm run lint
npx tsc --noEmit
npm run build

# 深层页面（需 Playwright Chromium）
AI4MS_PYTHON=../../.venv/bin/python npm run test:e2e
```

验收重点：

- 注册表恰好包含有序且唯一的 `D01`–`D36`；
- profile 在应用重启后仍保留选择；
- 资产章节保存增加 revision，陈旧 revision 返回 `409 revision_conflict`；
- 日志文件若在运行后被修改，下载 API 返回 `409`；
- 额外任务保持 `queued`，排队任务可取消；
- 超时不会等待子进程自然退出；
- UI 端到端流程最终在后端出现资产新 revision 与人工审批事件。

## 仓库完整性

- 已恢复原 `ai4ms` 分支的 100 篇论文语料、方法/公式/数据源库、产品文档、
  路线图、开发包、工作簿和非技术介绍 PDF。
- 非技术介绍的 DOCX 与 Markdown 已由新基线等内容迁移到
  `docs/reference/`，不再在旧目录重复保存。
- `src/web/static/` 是被 Next.js `src/web/app/` 完整替代的旧静态前端，
  因此不恢复。
- 旧 `src/execution_logic.md` 描述的是早期 Runtime 控制逻辑，不属于当前
  AI4MS 产品运行入口；当前架构、开发和 Runner 约束分别由
  `docs/ARCHITECTURE.md`、`docs/DEVELOPMENT.md` 与 `docs/RUNNER.md` 维护。

## 提交边界

本次只整理和验证本地 `ai4ms` 工作树，不推送远端、不创建 PR。提交 PR 前应再次查看 `git diff --check`、完整测试结果和目标分支差异。
