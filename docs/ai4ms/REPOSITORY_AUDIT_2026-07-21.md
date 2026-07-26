# AI4MS 仓库完整性与本轮验收

更新时间：2026-07-21  
目标仓库：`franknobox/Riff-Band`  
目标分支：`ai4ms`

## 结论

用户手动提交并合并的上一轮前端文件没有少上传。核对时 `ai4ms` 的基线提交为：

```text
229d78e3894f27743a36614b7497f34c28f1394a
Merge pull request #6 from ctrlshift001/codex-ai4ms-frontend
```

上一轮计划中的 8 个文件均已出现在目标分支：

1. `src/web/app/page.tsx`
2. `src/web/app/deep-workspaces.tsx`
3. `src/web/app/globals.css`
4. `docs/ai4ms/README.md`
5. `docs/ai4ms/OPEN_SOURCE_BENCHMARK.md`
6. `docs/ai4ms/BACKEND_ARCHITECTURE_V2.md`
7. `docs/ai4ms/AGENT_TOOLING_AND_RULES.md`
8. `docs/ai4ms/IMPLEMENTATION_ROADMAP.md`

前端运行所需的 `package.json`、`package-lock.json`、`tsconfig.json`、`next.config.ts`、`layout.tsx`、`lib/api.ts` 和 `.env.local.example` 也都存在。仓库中没有 `src/web/app/chatgpt-auth.ts`，但当前代码没有引用它，因此它不是缺失依赖。

## 本轮发现的功能问题

| 问题 | 原因 | 本轮处理 |
|---|---|---|
| 页面写着 36 条诊断规则，只显示 4 条 | 使用了 4 组演示数据，没有真实规则注册表 | 新增 D01–D36 完整规则；支持检索、家族筛选、展开详情和加入计划 |
| “保存界面偏好”只出现提示 | 没有偏好状态、选择界面或持久化 | 新增石墨极简、冷蓝研究、论文纸张三套偏好，使用浏览器本地存储 |
| “使用说明”只是小弹窗 | 没有完整说明页 | 新增 `public/ai4ms-user-guide.html`，用户菜单直接打开 |
| 资产摘要“展开”只出现提示 | 按钮调用 toast，没有从属内容 | 六个章节均打开详情，显示来源、状态、血缘影响和正文编辑区 |
| 论文卡“查看证据片段 / 编辑连接”只出现提示 | 主张连接没有从属详情状态 | 新增证据定位、人工概括、连接类型、引用边界、备注和保存区 |
| 生产构建失败 | `globals.css` 引用了未安装且未使用的 `tailwindcss` | 删除残留导入；项目继续使用现有原生 CSS |
| React 19 lint 阻塞 | effect 中同步读取偏好后立即 setState | 改为下一帧恢复本地偏好并在卸载时取消任务 |

## 本轮新增或修改文件

```text
src/web/app/page.tsx
src/web/app/deep-workspaces.tsx
src/web/app/globals.css
src/web/public/ai4ms-user-guide.html
src/web/README.md
docs/ai4ms/README.md
docs/ai4ms/REPOSITORY_AUDIT_2026-07-21.md
```

## 已执行验收

```text
npm ci --cache /tmp/ai4ms-npm-cache     通过
npm run lint                            通过（0 error）
npm run build                           通过（Next.js 生产构建与 TypeScript）
诊断规则唯一编号计数                    36
```

生产构建结果包含 `/` 静态路由；`public/ai4ms-user-guide.html` 会由 Next.js 作为 `/ai4ms-user-guide.html` 提供。自动化云浏览器不允许访问本机 `127.0.0.1`，因此没有绕过策略执行浏览器点击；发布前需按下方清单做一次人工 smoke test。

## 发布前人工点击清单

- [ ] 进入“方法与公式库 → 诊断规则”，确认显示 `36 / 36`。
- [ ] 搜索 `平行趋势`，展开对应规则，确认出现证据、失败动作和实现提示。
- [ ] 点击右上角头像 → “界面偏好”，依次选择三种风格；刷新后确认上次选择仍保留。
- [ ] 点击右上角头像 → “使用说明”，确认新标签页打开完整手册并可打印。
- [ ] 进入人工审批中心 → 任一审批门 → 审批资产与版本。
- [ ] 在“资产摘要”依次展开六章；草稿状态可编辑保存，冻结状态只读。
- [ ] 创建新课题并完成向导，确认项目加入顶部项目列表且可重新编辑。
- [ ] 打开阶段草稿、一致性检查、整改页和待决定项，确认返回层级正确。
- [ ] 打开智能体对话，把候选内容预览后同步到阶段资产，再人工编辑并保存。

## 不是“少上传”，但仍需后端化的部分

当前顶层证据库、方法工作台和 Runs 中仍有演示数据。S0–S9 结构资产、revision、审批和部分检索/运行能力已经有 FastAPI 接口，但生产版还应继续完成：

1. 将前端 36 条诊断规则迁入后端权威注册表并提供版本化 API；
2. 将三套界面偏好同步到用户 profile（保留本地快速恢复）；
3. 将资产章节保存连接到 revision/patch API，而不是只更新当前前端会话；
4. 为 HTML 使用说明增加版本号自动注入和部署链接检查；
5. 完成 Stata Runner 的隔离执行、队列、取消、超时、日志与产物哈希；
6. 为深层页面补充端到端测试，覆盖创建项目、草稿整改、审批、资产下钻和智能体同步。

具体后端模块、接口和阶段工具规则分别见 `BACKEND_ARCHITECTURE_V2.md` 与 `AGENT_TOOLING_AND_RULES.md`。
