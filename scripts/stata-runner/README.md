# Windows Stata Local Runner

AI4MS 不分发 Stata 或许可证。以下脚本只连接研究者已经合法安装并有权使用的 Stata。

1. 在 PowerShell 或命令提示符中运行：

   ```bat
   SETUP_STATA_RUNNER.bat -StataExecutable "C:\Program Files\Stata19\StataMP-64.exe"
   ```

2. 运行 `START_STATA_RUNNER.bat`，并在分析期间保持窗口开启。
3. 可运行 `CHECK_STATA_RUNNER.bat` 自检，或在网页的 Stata 工作台点击“重新检查”。

配置写入仓库根目录的 `.env.stata-runner.local`。该文件已被 Git 忽略，包含工作台与本机 Runner 配对用的随机令牌，不应上传或分享。

Runner 默认只监听 `127.0.0.1:8765`。如通过 Docker 访问，请按 `docs/RUNNER.md` 配置 `host.docker.internal` 和主机防火墙。
