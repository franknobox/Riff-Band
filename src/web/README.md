# AI4MS 前端

Next.js、React 和 TypeScript 实现的 S0-S9 科研工作台。

## 目录

- `app/page.tsx`：主工作台和当前顶层视图；
- `app/deep-workspaces.tsx`：深层资产、检查、决策和审批页面；
- `app/globals.css`：当前视觉系统；
- `lib/api.ts`：FastAPI 类型化客户端；
- `public/`：用户指南和静态资源。

## 开发

先在仓库根目录启动后端：

```powershell
pip install -e .
ai4ms-web
```

再启动前端：

```powershell
Set-Location src/web
npm ci
npm run dev
```

打开 `http://127.0.0.1:3000`。默认 API 地址为 `http://127.0.0.1:8000`；其他地址通过 `.env.local` 中的 `AI4MS_API_INTERNAL_URL` 配置。

## 检查

```powershell
npm run lint
npm run build
```

Docker 构建使用 `AI4MS_STATIC_EXPORT=1` 生成 `out/`，再复制到 Python 镜像。仓库不再保留第二套静态兼容前端。

## 契约

- 规范阶段内容来自后端 `content`；
- 长文本工作区只写 `content._workspace`；
- 保存工作区必须携带 `expected_revision`；
- S6 使用真实 Runner、Preflight、后台任务和 Result API；
- 正式数值、论文和 Claim 不得由前端构造。

完整开发规则见 [`docs/DEVELOPMENT.md`](../../docs/DEVELOPMENT.md)。
