# 服务端评审与修复验证

本页记录 2026-10-21 服务端评审发现的问题、修复后的行为和复现方法。适用范围是当前源码与由该源码构建的发布包；外部服务的兼容性应以实际联调为准。

## 修复后的使用约定

| 场景 | 用户可观察到的行为 |
| --- | --- |
| 保存运行配置 | 文件按叶字段合并、校验并原子保存；当前 Runtime 保持原值。页面持续显示待重启项。 |
| 环境变量或启动参数管理的设置 | 保持启动优先级，页面锁定对应设置；API 对修改请求返回 `409/config_managed`，避免保存一个不会生效的值。 |
| 配置文件损坏 | 启动、重启渠道前要求修正文件；已有渠道仍可直接停止，无须重启整个服务。 |
| 步骤超时后重试 | 旧 attempt 的终态和澄清结果不能改变新 attempt；问题与阻塞状态通过一次 CAS 写入。 |
| 调度器派发前保存失败 | 不发布工作，释放执行名额并记录失败；未派发的一次性任务仍可重试。 |
| 多 Provider 的隔离评估 | 复用可用模型客户端，重建独立路由和回退状态；不共享在线会话、数据库、文件或路由健康记录。 |
| 手输审批或澄清命令 | 显示成功、权限、参数和过期请求反馈；控制回复不结束正在运行的业务回合。 |
| 摘要失败或处于冷却期 | 保留原历史，不重复归档；获得可用摘要后才归档并替换历史。 |

“停止渠道”是本次进程中的即时操作，服务下次启动仍遵循保存配置、环境变量和启动参数。永久停用受启动设置管理的渠道，需要修改对应环境变量或服务参数。

## 验证方法

在开发环境安装依赖后执行：

```bash
python -m pytest tests/ -q
ruff check . --extend-exclude client
pnpm --dir web test --run
pnpm --dir web build
mkdocs build --strict
```

针对本页问题的回归覆盖位于 `tests/test_review_remediation.py`、`tests/test_gateway_review_regressions.py`、`tests/test_server_state_regressions.py`、`tests/test_scheduler_run_identity.py`、`tests/test_evaluation_runtime_isolation.py`、`tests/test_compression.py` 和 `tests/cli/tui/test_typed_control_integrity.py`。前端覆盖配置锁定、渠道即时停止以及保存后的状态反馈。

使用实际发布 wheel 的解释器运行 `scripts/validate-server-process.py --output /tmp/echo-process-check`，可检查独立工作区中的 HTTP/WS、受控模型工具调用、产物投递、重复请求、进程重启、端口冲突及 SIGTERM。该脚本使用本机受控 OpenAI 兼容端点，不调用真实外部模型。

`scripts/validate-gateway-web.mjs` 用于在测试工作区检查简化页认证、HTTP/WS 和 Dashboard 配置保存。它需要单独安装 Playwright，连接测试 Gateway，并按脚本开头说明传入地址和令牌；不要针对生产工作区运行验收脚本。

## 本次验收结果（2026-10-21）

| 检查 | 结果 |
| --- | --- |
| 后端全量测试 | 7,638 通过，100 跳过 |
| 最后补充的启动参数及网关回归 | 147 通过；与全量用例有重叠，不累加统计 |
| 前端测试 | 235 通过 |
| TypeScript、前端生产构建和包体预算 | 通过 |
| Ruff、Git 差异格式检查、文档严格构建 | 通过 |
| 最终 wheel 安装及进程验收 | 3 组场景通过，使用受控本地模型端点 |
| 浏览器验收 | 登录、HTTP/WS、配置保存、运行值保持及刷新后待重启提示均通过 |

本机进程与浏览器测试使用独立临时工作区。真实外部模型、IM 平台账号和其他操作系统未在本次验收中联调；跳过用例不计入通过数。

## 兼容性与边界

- Gemini 使用 `google-genai>=2.32,<3`；真实 SDK 的序列化、工具返回和流关闭由本地合同测试覆盖。测试不等价于真实 Google API 联调。
- MCP 的兼容版本和 A2A 入站子集见[兼容性说明](../reference/compatibility.md)。未实现的协议版本不作兼容承诺。
- FastEmbed 的 vendoring、许可与补丁见仓库中的 `echo_agent/_vendor/fastembed/VENDOR.md`。PyMuPDF 暂限制 `<2`；具体依赖以 `pyproject.toml` 为准。
- 隔离评估允许工作区内文件操作及技能元数据读取；外部、进程工具和无法复现的必需运行扩展产生“无法判定”，不能作为候选晋升证据。
- 超时、中断和回滚不能撤销已经发生的外部副作用。重新执行前应核对结果，仅对可安全重复的步骤启用自动重试。
- 本地验证运行于 macOS；Linux 发布包进程检查由 CI 执行。没有实测结果时，不宣称某个 Linux 主机或 Docker 镜像已经验证通过。

升级前备份配置、数据库、技能、调度状态和凭据密钥；回退时保持代码、依赖和备份版本一致，按[升级与迁移](../operations/upgrade-migrations.md)恢复。`/ready` 只验证本地执行条件，真实模型是否可用应通过实际工具任务确认。
