# 本地部署与验收报告

验收日期：2026-10-21，Asia/Shanghai。范围：除根目录 `client/**` 外的源码部署、Runtime、Gateway、Dashboard、CLI/TUI、扩展及相关测试。

版本说明：第 1–9 节保留初次本地验收快照，其源码哈希和测试数字对应当时版本。本轮代码评审后的五项修复与最终验证另见第 10 节，不能将历史服务进程视为已自动加载后续 Python 修改。

## 1. 总体结论

**部分验收完成：本地核心流程已真实运行并验证可用，不能据此宣称所有可选功能和外部集成全部通过。** 本次实际安装依赖、构建 Dashboard、启动完整 Gateway，并使用用户指定的 `https://new-api.kunkunout.com/v1`、`claude-opus-5-5` 完成真实推理和工具任务。没有使用 StubProvider 代替这些验收。

- CSV → 工具计算 → 文件生成 → 独立读回：数量 **10**，营收 **126**，通过。
- 长期记忆：独特事实写入、新会话召回、Gateway 重启后召回、修改、删除后重新检索，通过。
- 知识库：独特文档上传、索引、真实 `knowledge_search` 调用与引用、删除后重新查询，通过。
- 看板：真实执行只读计算任务；原场景失败经修复、同一任务重试后成功；结果重启后仍在。
- Cron：真实时钟触发、授权写文件、独立读回 `CLOCK-58`、接收端收到最终消息、历史完成；并发重复触发返回 409；通过。
- CLI、Textual TUI、另一隔离工作区的独立 `run` 均实际连接或启动、请求真实模型并正常退出。
- 确认并修复 11 项代码或交互问题，均有原故障回归证据。后端最终 **7788 passed / 47 skipped**，覆盖率 **82.43%**；前端 **240 passed**，生产构建通过。
- Chromium 对 11 个 Dashboard 页面分别巡检 1440、1280、1024 像素宽度，并补充中文 1024 像素截图；认证、乱序、断线恢复和看板 HTTP/WS 竞争经过实际浏览器注入时序验证。

尚未完成真实外部验收的主要范围：IM 测试账号、外部 MCP HTTP/OAuth 目标、完整技能进化晋升/回滚、语音/图像等可选服务、其他操作系统。自定义模型没有已知单价，费用显示 0 不代表免费，也不能作为美元预算正确的验收证据。具体状态见第 4、8 节。

## 2. 版本、环境与证据对应关系

| 项目 | 本次实际值 |
|---|---|
| 分支 / 基线 commit | `master` / `b7f31e43040da9e4c95498d113c44b7a46d81bf2` |
| 初始工作区 | 跟踪文件无已有修改；修复保留为本地未提交改动，没有推送或发布 |
| 操作系统 | macOS 15.8.1，Darwin 24.6，x86_64 |
| Python | 项目 `.venv`，3.11.13；editable 安装本工作区 `echo-agent 0.3.8` |
| 安装 | `uv pip install -e '.[all,dev]'`，144 个包；没有删除锁文件或整体升级项目声明 |
| Node / pnpm | 20.19.0 / 10.34.5（与 `web/package.json` 一致） |
| 核心依赖 | openai 3.35.1，aiohttp 3.14.5，textual 8.2.8，onnxruntime 1.23.2，ruff 0.15.12 |
| 浏览器 | 实际 Chromium 153；Node 版 Playwright 单独安装，未把 Python 包当作 Node 包使用 |
| 服务 | 源码 Gateway，`127.0.0.1:58231`；完整 Dashboard 来自 `web/dist` |
| 数据隔离 | `/private/tmp/echo-acceptance-20261021`，独立配置、工作区、缓存、checkpoint 和测试身份 |
| 安全配置 | 显式 `personal_cli`，仅 loopback、限制工作区；无人审批默认拒绝，未关闭审批来获取成功 |

后端修复后重启本次自有 Gateway；前端修复后重新构建并刷新浏览器。最终采集时验证 HTTP `/` 的字节与 `web/dist/index.html` 完全一致，SHA256 为 `2477216ff021ccb203af1edd8546ca574051a2854695a17b2a4748efa1bd77d5`。不是旧打包 Dashboard 或 playground 代替正式部署。最后的 playground HTML 修改另经真实浏览器和 90 项相关回归验证。

完整版本清单见 [environment.json](evidence/environment.json)，最终 API/工具调用摘要见 [final-state.json](evidence/final-state.json)。`/health` 返回 HTTP 200、`server_running=true`、`provider=ok`，总体状态为 `degraded`（没有在线外部通道），不能写成全面健康。`/ready` 返回 200、`ready=true`，同时明确 `provider_remote_verified=false`；远端可用性由独立的 [真实模型探测](evidence/model-probe.json) 和以下工具任务证明。

## 3. 部署、访问与复现

以下路径对应当前机器。运行密钥仅保存在权限受限的临时目录和进程环境，不写入仓库、报告或证据。根目录权限 700，私密配置与 secrets 文件权限 600。

### 当前服务

访问完整产品：<http://127.0.0.1:58231>。实际对话可用 <http://127.0.0.1:58231/playground>、CLI 或 TUI；Dashboard Sessions 用于会话历史查看和管理。

在仓库根目录执行以下命令可在本地获取登录 Token（命令会显示本次随机生成的本地管理员 Token，勿提交输出）：

```bash
.venv/bin/python /private/tmp/echo-acceptance-20261021/manage.py token
```

接入已启动 Gateway（配置中已有本地认证信息）：

```bash
.venv/bin/echo-agent cli --config /private/tmp/echo-acceptance-20261021/echo-agent.yaml --workspace /private/tmp/echo-acceptance-20261021/workspace
.venv/bin/echo-agent cli --tui --config /private/tmp/echo-acceptance-20261021/echo-agent.yaml --workspace /private/tmp/echo-acceptance-20261021/workspace
```

停止本次服务：

```bash
.venv/bin/python /private/tmp/echo-acceptance-20261021/manage.py stop
```

等待原 PID 退出、端口释放后，再启动同一隔离实例：

```bash
.venv/bin/python /private/tmp/echo-acceptance-20261021/manage.py start
```

`gateway.pid` 只记录本次拥有的 Gateway。不要对其他实例批量杀进程。启动后检查 `/api/v1/health`、`/api/v1/ready` 及实际模型请求；启动器输出 PID 本身不证明就绪。

### 从当前源码重新部署

```bash
uv venv --python 3.11 .venv
UV_CACHE_DIR=/private/tmp/echo-qa-uv-cache uv pip install --python .venv/bin/python -e '.[all,dev]'
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
```

已存在 `.venv` 时不重复创建。重新部署应使用新隔离目录，显式指定配置和工作区。核心配置结构如下，认证值需自行生成并放在私有配置中：

```yaml
workspace: /private/tmp/echo-qa/workspace
security:
  profile: personal_cli
gateway:
  host: 127.0.0.1
  port: 58231
  auth:
    api_tokens: [REPLACE_WITH_LOCAL_API_TOKEN]
    admin_tokens: [REPLACE_WITH_LOCAL_ADMIN_TOKEN]
models:
  default_model: claude-opus-5-5
  providers:
    - name: openai
      api_base: https://new-api.kunkunout.com/v1
      api_key_env: ECHO_QA_LLM_API_KEY
      models: [claude-opus-5-5]
      timeout_seconds: 90
      max_retries: 1
tools:
  restrict_to_workspace: true
memory:
  embedding_backend: local
  local_embedding_cache_dir: /private/tmp/echo-qa/models
checkpoint:
  store_path: /private/tmp/echo-qa/checkpoints
agent:
  heartbeat:
    enabled: false
observability:
  otel_enabled: false
```

通过私有环境变量注入模型密钥，然后运行：

```bash
.venv/bin/echo-agent gateway --config /private/tmp/echo-qa/echo-agent.yaml --workspace /private/tmp/echo-qa/workspace --host 127.0.0.1 --port 58231
```

测试记忆跨会话时，本次额外绑定了合成身份 `gateway:cli:qa-owner`、`cli:qa-owner`；不能推广到任意真实身份。独立 `run` 使用了另一个 `run-workspace`，未绕过实例锁。首次配置确实以干净文件运行了交互向导的模型部分、完成真实验证并检查保存字段；没有声称完整走完全部配置章节。[向导记录](evidence/wizard-result.json)

### 重跑验证工具

```bash
.venv/bin/ruff check . --extend-exclude client
.venv/bin/python -m pytest tests/ --cov=echo_agent --cov-report=term-missing
pnpm --dir web test --run
pnpm --dir web build
.venv/bin/python scripts/validate-server-process.py --output /private/tmp/echo-process-recheck
.venv/bin/python scripts/validate-local-extensions.py --output /private/tmp/echo-extensions-recheck
```

进程脚本使用受控本地模型端点，只能证明 L3。浏览器脚本需要单独可用的 Node Playwright 和 Chromium；设置 `ECHO_UI_BASE_URL`、`PLAYWRIGHT_MODULE`、`ECHO_UI_BROWSER_PATH`、`ECHO_UI_OUTPUT` 后执行 `node scripts/validate-gateway-web.mjs`，并通过私有环境提供 `ECHO_UI_TOKEN`；真实模型可设 `ECHO_UI_TIMEOUT_MS=120000`。脚本会临时保存/恢复 `memory.enabled`，只能用于测试工作区。

新增 `scripts/validate-dashboard-acceptance.mjs` 保存本次全站与竞争条件审计步骤。它需要本报告中的 `cli:qa-csv-v2`、`cli:qa-memory-after-restart` 会话数据，以及 `ECHO_UI_CREDENTIALS_FILE` 指向含 `admin_token`、`api_token` 的私有 JSON。会创建三个待办测试任务，不自动执行。其环境参数化版本经语法检查；本次实测结果来自相同步骤的隔离脚本，见 [browser-final.json](evidence/browser-final.json)。

## 4. 功能地图与覆盖矩阵

层级：L1 源码/文档；L2 单元、组件、Mock；L3 真实本机进程、浏览器、文件、存储或受控协议服务；L4 用户指定真实模型或真实外部服务。下表按实际执行区分，不依赖测试文件名推定层级。`PASS` 只覆盖该行列出的断言。

| 模块 / 用户目标 | 入口与前置条件 | 操作与预期 | 层级 / 实际结果 | 证据 / 问题 |
|---|---|---|---|---|
| 安装、源码加载、完整 Dashboard | `.venv`、`web/dist` | editable 安装、冻结锁构建、校验服务 HTML | L3 PASS | environment；构建日志 |
| 首次配置模型 | 干净 setup 配置、密钥环境变量 | 选择自定义兼容端点、验证、保存、提示接续 Gateway | L4 PASS（模型章节）；完整向导 NOT_TESTED | wizard-result |
| health / ready / 缺模型 | 正常及未配置 Gateway | 分别检查存活、就绪；缺模型 ready=503 | L3 PASS；不把 ready 当远端探测 | final-state；process-results |
| 启停、锁、冲突、恢复 | 真实子进程、隔离工作区 | 重复启动和占用端口拒绝；SIGTERM；立即重启；持久结果不重复执行 | L3 PASS | process-results；restart-before/after；QA003 |
| HTTP、交互 WS、Dashboard WS | 有效/无效/普通/管理员认证 | 请求、流式帧、最终回复、事件、幂等与权限 | L3 PASS；真实模型 HTTP/WS L4 PASS | process-results；original-ui-verified；QA004、QA011 |
| 可核对的工具任务 | 合成 qa-sales.csv | 读 CSV→计算→写 JSON→独立读回 10/126 | L4 PASS | real-tasks；artifacts；histories/cli_qa-csv-v2 |
| 工具失败、超时、轮次/Token 预算、中断 | 故障注入 / 受控 Provider | 不能当成功、停止副作用、释放等待 | L2 PASS；完整外部故障组合 NOT_TESTED | 全量后端测试；真实拒绝见 controls |
| 澄清 | 真实模型、交互 WS | 提问→回答 BETA→继续；断开后新请求仍可执行 | L4 PASS | controls；histories/cli_qa-controls-v2 |
| 审批拒绝 | 真实 cronjob 工具审批 | 拒绝 QA-DENY-ONLY；核对无 job 新增 | L4 PASS | controls 的 rejection-no-side-effect |
| 审批批准 / 到期 / 迟到回复 | 管理器、看板执行身份 | 决策隔离、过期与旧结果不覆盖新运行 | L2 PASS；完整真实等待到期 NOT_TESTED | 全量相关回归；未伪造实际等待 |
| 会话、快速切换 | 已有 A/B 历史，浏览器网络延迟 | A 历史迟到时 B 内容不被污染；重启保留 | L3 PASS | browser-final；histories |
| 会话搜索、分页、重置 | API、组件与已有回归 | 参数、列表、范围、重置行为 | L2 PASS；全部 UI 操作组合 NOT_TESTED | 全量测试 |
| 长期记忆闭环 | 绑定的合成身份 qa-owner | 5279→新会话/重启→8402→删除→空检索 | L4 PASS | lifecycle、memory-delete-confirmed、final-workflows、histories |
| 记忆身份/来源隔离 | owner 绑定、来源等级 | 普通删除高来源事实返回403；显式 override 后删除 | L3 PASS；跨所有通道身份的 L4 NOT_TESTED；L2 PASS | memory-delete-confirmed；权限回归 |
| 本地向量 / reranker | 实际权重、ONNX CPU | warmup；相关文档评分大于无关文档；3 次冷导入不死锁 | L3 PASS | rerank-real、cold-imports；QA008、QA009 |
| 知识库闭环 | qa-osprey.md、独特事实 | 上传/索引→调用检索→CERULEAN-6184、37及[K1]→删除后无引用 | L4 PASS | real-tasks、lifecycle、知识会话 histories |
| 知识库失败/空文件/重名/取消 | API、索引任务及组件 | 校验、失败状态、取消与重连后权威状态 | L2 PASS；全部实际文件类型/取消时机 NOT_TESTED | 全量测试；禁用服务实测 |
| 看板实际执行 / 重试 | 同一任务 t_e6e7d5f30dc7 | 原失败→修复→重试→只读计算正确、success持久化 | L4 PASS | final-workflows、final-state、task history；QA005 |
| 看板无人值守写权限 | 默认审批拒绝 | 不授权写文件任务应失败，不能假成功 | L4 PASS（正确拒绝） | real-tasks 中 t_21cf643b942d，无产物 |
| 看板创建竞争 / 重复提交 | HTTP 或 WS 分别先到 | 一次创建只显示一张卡、刷新前后一致；阻止连点 | L3 / L2 PASS | browser-final；前后截图；QA010 |
| 看板重试身份 / 并发与迟到结果 | retry、transition、详情、store | 次数限制一致，旧 attempt 不得覆盖新结果 | L2 PASS；全部真实交互入口组合 NOT_TESTED | 后端/前端全量回归 |
| Cron 实际时钟、交付与历史 | 已授权写文件、真实接收端 | 每分钟调度→CLOCK-58→收到最终 WS→completed | L4 PASS | clock-cron；artifacts/qa-clock.txt |
| Cron 无目标、重复运行、暂停 | 无接收者 / 当前 active run | 无目标必须error；并发409；暂停未来触发不伪造当前完成 | L4 / L3 PASS | lifecycle、clock-cron、final-state；QA004 |
| Cron 时区 / 重启旧运行恢复 | scheduler 状态与受控时钟 | 不重复副作用、不同 run 结果隔离 | L2 PASS；本次真实跨时区/崩溃恢复组合 NOT_TESTED | 全量 scheduler 回归 |
| Skills / 工具发现 | 技能目录、API、Dashboard | 列表、路径参数、依赖和权限校验 | L3 页面/API PASS；执行/安装失败 L2 PASS；每个内置技能实用效果 NOT_TESTED | 截图、输入回归；QA001、QA002 |
| Plugins | 真实临时 Python 模块、严格权限 | load→注册 qa 工具→PLUGIN-QA-58→unload 后移除 | L3 PASS；第三方插件 L4 NOT_TESTED | extensions-results；可复现脚本 |
| MCP 本地 | 真实 stdio JSON-RPC 子进程 | initialize→tools/list→19+23=42→断开→重新连接再调 | L3 PASS | extensions-results |
| MCP 外部 HTTP/OAuth | 未提供目标和账号 | 连接/授权/掉线恢复需真实服务 | L4 BLOCKED；协议异常 L2 PASS | 需要测试服务配置 |
| 多 Agent 分工 | 真实 delegate_task、两个只读 worker | 独立读 CSV、分别数量/金额、汇总10/126 | L4 PASS | delegation；histories/cli_qa-delegate |
| 评估 | CLI、两条合成可判定数据 | 实际模型跑数据集→2/2、平均1.0 | L4 PASS（小样本，不代表泛化能力） | evaluation |
| 进化候选/审核/晋升/回滚 | 默认关闭的进化配置 | 按已有引擎/边界/治理测试验证 | L2 PASS；完整 L4 NOT_TESTED | 需隔离真实候选及效果数据集 |
| 配置保存值 / 运行值 | Dashboard Config、Gateway | 修改 memory.enabled→保存→运行值不变→刷新保留待重启→恢复原值 | L3 PASS | original-ui-verified；config截图 |
| 可选模块关闭 | 单独 Gateway，四模块关闭 | cron503、knowledge404未配置、skills503、memory409，无500 | L3 PASS | disabled-after；QA006 |
| 通道配置与投递失败 | 无真实 IM 凭据 | 页面反映离线；无 handler 不得伪成功；生命周期回归 | L3 / L2 PASS；真实 IM L4 BLOCKED | final-state、delivery回归；QA004 |
| 日志与 Token | 已执行真实任务 | 会话 tool trace、日志、按通道/日期累计 usage | L3 / L4 PASS（来源核对到 Provider 返回 usage） | final-state analytics、histories、model-probe |
| 美元成本与预算 | 自定义模型未知价格 | 需要可信单价才能核对；现有0值不等于费用为0 | L4 BLOCKED；已知单价预算 L2 PASS | 需配置真实 pricing overrides 后复验 |
| Dashboard 全站与语言 | 11页×3宽度，中文窄屏 | 页面可见、无根级横向溢出、无pageerror | L3 PASS；全面辅助技术审计 NOT_TESTED | browser-final；screenshots |
| 登录与权限切换 | 无效/普通/管理员 Token | 错误留登录；普通不能写；退出能重新登录；管理员能力刷新 | L3 / L2 PASS | browser-final；auth截图；QA007 |
| 断网重连 | 关闭真实WS、阻断网络，另客户端建任务 | 重连后补齐漏掉的任务事件 | L3 PASS | browser-final |
| CLI / TUI | PTY、当前 Gateway | 实际模型回复；CLI读结果；TUI回复TUI-QA-83；退出0 | L4 PASS | final-workflows；CLI/TUI histories |
| 独立 run | 单独 run-workspace | 读run-marker.txt→RUN-ISOLATED-12；/quit退出 | L4 PASS（PTY实测）；未做截图 | 本次独立终端实测；数据仍在临时目录 |
| Agent 浏览器、OCR、ASR/TTS、图像/视频、容器 | 各自依赖/服务 | 浏览器用于产品验收，不等于 Agent 浏览工具全链路通过 | L2可执行测试 PASS；完整 L4 NOT_TESTED/BLOCKED | 需各类测试资产、服务和运行条件 |
| wheel / Windows / Linux / 移动端 | 本轮为macOS源码、桌面Dashboard | 未采用wheel部署；不做跨平台通过声明 | NOT_TESTED；client/** N/A | 明确范围 |

## 5. 确认问题与修复闭环

以下问题最终均为 **已验证关闭**。严重度用于排序：P1 为结果真实性或可用性关键问题，P2 为输入、恢复或明确交互缺陷。完整测试日志保留了修复前失败，没有删除或降低原有断言。

### QA001 · P2 · 非对象 JSON 导致 500（已实现功能缺陷）

前置：有效权限，向 tasks/cron/memory/skills 的对象请求入口发送 `[]`、数字等合法 JSON。预期 4xx，原行为直接 `.get` 引发 500。根因是只验证 JSON 解码、未验证顶层对象。修复 `gateway/api/{tasks,cron_api,memory,skills}.py`，包含任务 transition。原请求改为可解释的 4xx；输入回归首轮 70 项中 63 项失败，修复后通过。[失败证据](evidence/input-tests-before.log)；`tests/test_gateway_input_validation.py`。

### QA002 · P2 · 字段类型无校验，错误数据可持久化（已实现功能缺陷）

前置：tasks.title 为数组、Cron enabled 为字符串、memory limit 为 bool/负数等。预期拒绝，原来接受或后续异常。补齐任务文本/空标题、Cron 字符串/布尔/payload、记忆 query/type/limit/session_key 和 skills path 的边界校验，拒绝 bool 冒充 int。修复同上 API 文件；真实非法参数复测与回归通过。[前后 API 记录](evidence/invalid-before.json)、[修复后](evidence/invalid-after.json)。旧测试工作区内保留一条已取消的错误类型记录作为故障证据，未对用户数据做迁移。

### QA003 · P2 · 快速重启误报端口占用（部署恢复断点）

前置：POSIX Gateway 刚释放、socket 处于 TIME_WAIT。原 bind 探测未沿用 asyncio 的地址复用策略，端口实际上可启动却被误拒绝。`app.py` 的探测在 POSIX 设置 `SO_REUSEADDR`，活跃监听仍然拒绝。真实停止/立即启动复测成功，增加真实 TIME_WAIT 与活跃端口对照测试。[修复前](evidence/restart-before.log)、[后](evidence/restart-after.log)；`test_gateway_loopback_trust.py`。

### QA004 · P1 · Cron 无投递目标却被记为完成（结果真实性缺陷）

前置：真实模型任务写出 CRON-91，但没有接收 handler。原全局观察者回调 `None` 被当作接收成功，history 错记 completed。修复 `bus/queue.py`、`channels/manager.py`、`gateway/{server,router}.py`：识别明确 DeliveryResult，非所属观察者返回 NO_HANDLER，路由传递实际下游回执；保留既有 legacy None 兼容与 progress 过滤语义。

同一 Cron 重新触发后准确为 `error: delivery failed`。另建明确接收目标的 Cron，确认 CRON-DELIVERED-64 文件、真实 WS 最终消息和 completed 三者一致；随后真实时钟任务 CLOCK-58 也通过。`test_delivery_receipt_truth.py`、`test_gateway_advanced.py` 覆盖无目标和失败传播；原 mock 路由按新回执契约更新，未删除断言。[前故障](evidence/delivery-before.log)、[前后历史](evidence/lifecycle.json)、[实际交付](evidence/final-workflows.json)。

### QA005 · P2 · 否定输出要求误触发 artifact 模式（Agent 主流程断点）

前置：看板只读指令含 “Do not create files” 或工具名 `write_file`。原启发式把否定句/标识符当生成长文产物指令，强制不可用操作而失败。`agent/pipeline/context_stage.py` 增加英文边界、局部否定判断及句子边界，不跨语句吞掉后续真实正向输出要求。增加 6 条回归（修复前 5 失败）。重启后同一任务 t_e6e7d5f30dc7 重试成功、算出10/126、状态持久化。[原故障](evidence/artifact-routing-before.log)、[原任务复测](evidence/final-workflows.json)。模型还曾自行尝试 task 工具并收到无人审批拒绝，最终叙述对状态的说法不准确；计算与权威状态分别核对，未将叙述当作状态事实。

### QA006 · P2 · scheduler 禁用时 Cron API 500（可选能力状态缺陷）

前置：`scheduler.enabled=false`。原 handler 假设 scheduler 存在。`gateway/api/cron_api.py` 在认证后检查可用性，全部读写入口给503和禁用说明。12 条用例、真实禁用配置的独立 Gateway 复测通过；其他禁用模块也检查明确响应。[实际结果](evidence/disabled-after.log)。

### QA007 · P1 · 主动退出后空白页（认证状态交互断点）

前置：已登录后点击 Sign out，或切换普通/管理员 Token。能力缓存重置但 hook 未依赖 generation，布局永久等待空的认证状态。`web/src/stores/capabilities.ts` 两个 hook 订阅 generation 重新探测；新增两条组件测试修复前失败、修复后通过。实际浏览器完成普通登录→退出→管理员登录，按钮权限正确，无白屏。[修复前测试](evidence/auth-before.log)、[浏览器结果](evidence/browser-final.json)、[退出后截图](evidence/screenshots/auth-logout-after-1440.png)。

### QA008 · P2 · 合法模型归档软链接被拒绝（依赖安装缺陷）

前置：真实 reranker release tar 中 tokenizer_config.json 使用 Hugging Face snapshot 相对链接，原解包器全部拒绝。`memory/local_rerank.py` 只允许指向同一归档内普通文件的安全相对链接；拒绝越界、绝对路径、重复目标、目录链接、链接链及特殊文件；先解普通文件再建链接，保留校验/原子安装。实际本地归档回归验证合法链接成功、外部链接拒绝。真实 ONNX reranker 已加载并评分通过；本次权重由 HF 回退路径获取，**没有把修复后重新下载完整远端 release 记作通过**。[原失败](evidence/rerank-before.log)、[实际评分](evidence/rerank-real.json)；`test_rerank_release_fetch.py`。

### QA009 · P1 · embedding/reranker 并行冷导入死锁（启动稳定性缺陷）

前置：首次并发加载 vendored FastEmbed。实际运行捕获 `_ModuleLock` 死锁。新增 `memory/model_import.py` 用 RLock 串行化导入；`local_embed.py`、`local_rerank.py` 共用入口，推理仍可并发。补充锁回归；三个新解释器实际冷导入全部完成，最终 Gateway 两模型 warmup 成功。[冷导入复测](evidence/cold-imports.log)；`test_model_import_serialization.py`。

### QA010 · P2 · HTTP/WS 竞争导致重复卡片，创建无提交中保护（交互与状态缺陷）

前置：真实 `task_created` 先到，延迟 POST 响应。后端仅一个 t_4b93409e11dd，前端出现两张，刷新恢复一张。`web/src/stores/kanban.ts` 以 ID 合并且保留更新的 WS 状态；`pages/Kanban.tsx` 加同步提交锁、按钮/输入禁用、Creating 文案及 aria-busy，失败保留输入；补充中英文文案。两个时序的 store 回归及组件连点测试均通过。最终真实浏览器分别放行 HTTP/WS，刷新前后都是一张。

相同视口、相同记录的比较：[修复前两张](evidence/kanban-duplicate-before-1440.png)、[修复后一张](evidence/kanban-duplicate-after-1440.png)。相关 `kanban.fetch.test.ts`、`Kanban.test.tsx`；[修复前断言](evidence/kanban-create-before.log)。

### QA011 · P1 · 默认 playground 会话不满足 loopback 信任边界（交互入口断点）

前置：当前安全配置、正确 Token，playground 未显式提供 session_key，HTTP 原来403，WS同样无法完成认证。服务器 Gate B 要求显式 `cli:` 会话，本次保留安全校验。`gateway/static/index.html` 增加可见 Session key，为每个标签页生成独立 `cli:playground:<uuid>`，HTTP 和 WS 共用；sessionStorage 仅尽力保存，访问受限时仍工作。`scripts/validate-gateway-web.mjs` 增加 session 一致性断言和实际非200错误说明。原真实浏览器入口复测 HTTP completed、WS connected/回复、配置保存与运行值检查全部通过。[最终验证日志](evidence/original-ui-verified.log)、[实测截图](evidence/screenshots/fallback-auth-custom-paths.png)。

## 6. 产品体验评审

保留现有导航和视觉体系。11 个页面的三档桌面宽度均无根级横向溢出或 pageerror；初始巡检还检查了无名称按钮。窄屏看板采用内部横向浏览多列，不能把根页面无溢出理解为同时展示全部列。中文/英文内容、长测试任务名和空知识库状态有截图留存。[全部页面巡检](evidence/browser-final.json)、[截图目录](evidence/screenshots/)

| 页面与状态 | 具体困难与任务影响 | 本次处理 / 验证 |
|---|---|---|
| 登录退出 / Token切换 | 空白页令用户无法再次进入、旧权限残留风险 | QA007：重新探测认证能力；实际普通/管理员切换和退出截图 |
| 看板创建等待与事件竞争 | 连点可重复请求，两个通道让一个任务显示成两张 | QA010：提交状态、同步锁和按ID合并；相同数据前后截图与两种到达顺序实测 |
| playground首次发送 | 正确Token仍403，用户没有可见的session修正入口 | QA011：显式会话输入和自动合法默认值；HTTP/WS真实模型复测 |
| Cron禁用 | API500不能解释“功能未开启”，阻碍诊断 | QA006：认证后503和具体禁用信息；独立真实配置复测 |
| Config保存后 | 保存值和运行值容易混淆 | 现有实现回归通过；修改后提示需重启，刷新仍保留，运行值不伪热更新；未为已正确行为改代码 |
| Sessions | 主要查看历史，没有产品内完整聊天入口 | 合理边界；通过CLI/TUI/playground验收对话，不新增聊天大模块 |
| Dashboard无外部通道 | 显示degraded/Offline | 与本次运行状态相符，没有用样式隐藏真实降级 |

可访问性验证包含现有组件套件、表单标签定位、图标按钮名称巡检及实际键盘输入/提交；尚未做完整屏幕阅读器、全站焦点顺序、所有弹窗焦点陷阱和缩放组合的人工审计，不能宣称 WCAG 全面符合。拖拽之外已有详情/开始执行入口，本轮未另建交互体系。未发现需要全站换肤的可复现证据，未做偏好性重设计。

## 7. 本次实际测试结果

| 命令 / 验证 | 结果 | 层级与证据 |
|---|---|---|
| 基线 `pytest tests/ --cov=echo_agent --cov-report=term-missing` | 7693 passed、47 skipped、5 warnings；82.40%；424.98s；退出0 | L2/L3混合；[基线日志](evidence/backend-tests.log) |
| 最终同命令 | 7788 passed、47 skipped、4 warnings；82.43%，超过75%门禁；402.49s；退出0 | L2/L3混合；[最终日志](evidence/backend-delivery.log)，不代表所有用例使用远端模型 |
| 前端基线 `pnpm --dir web test --run` | 235 passed；退出0 | [基线日志](evidence/web-tests.log) |
| 前端最终同命令 | 30文件、240 passed；13.54s；退出0 | [最终日志](evidence/web-delivery-tests.log) |
| 最终 `pnpm --dir web build` | TypeScript/Vite/bundle检查通过；退出0 | [构建日志](evidence/web-delivery-build.log) |
| 最后 playground / Gateway 相关测试 | 90 passed；退出0 | [日志](evidence/last-gateway-regression.log) |
| `ruff check . --extend-exclude client` | PASS；退出0 | 最终检查另见 final-checks.log |
| `uv pip check` / `git diff --check` | 144包依赖兼容 / 无空白错误；退出0 | final-checks.log |
| `validate-server-process.py` | 3场景通过，28次受控Provider调用；退出0 | L3，明确 `real_external_model=false`；[结果](evidence/process-results.json) |
| `validate-gateway-web.mjs` | 实际模型HTTP/WS及配置保存/运行差异通过；退出0 | L3/L4；[日志](evidence/original-ui-verified.log) |
| Dashboard完整审计 | 33页面状态、11中文截图、8项关键交互断言；无pageerror；退出0 | L3；[结果](evidence/browser-final.json) |
| 本地MCP / Plugin复现脚本 | 两次连接调用42、卸载恢复；退出0 | L3；[结果](evidence/extensions-results.json) |
| 实际模型独立eval | 2/2，平均1.0；退出0 | L4；[结果](evidence/evaluation.json) |
| ONNX / 冷导入 | 8.91118 > -10.19289；三个冷进程完成 | L3；rerank-real、cold-imports |

47 个跳过不是通过：7 个 SILK 编码用例缺少 ffmpeg/pilk 运行组合；1 个既有绝对首Token延迟用例无条件标为需独立真实网络对比；33 个技能文档示例没有子命令、6 个脚本本身不使用子命令，相关文档用例条件跳过。[依赖/延迟跳过诊断](evidence/skip-reasons.log)、[39个文档跳过诊断](evidence/skip-docs-reasons.log) 单独保留，不增加到上述全量通过数。4 个 warning 是既有旧 embedding 缓存格式的 FutureWarning；进程退出还出现 SWIG DeprecationWarning，未掩盖。

中途失败经过保留和处理：新增输入、artifact、auth、归档软链接、看板竞争测试先失败再修复；扩大回归时出现路由 mock 新回执契约与 progress 过滤相关失败，修正实现/fixture 后全量通过。浏览器脚本也曾因错误的 ellipsis 定位、返回路由假设、测试期间服务重启、帧嵌套字段提取失败而中断，这些是测试夹具问题，没有当作产品缺陷或通过记录。最终通过日志是修正后的独立复测。

最初真实文件任务还暴露配置问题：未显式配置安全profile，`write_file` 被过滤，模型却声称已经写出文件；独立读回失败，所以没有验收通过。显式使用本地profile后重做，真实文件及工具历史才通过。这说明模型文字、HTTP 200 和业务完成必须分别核对。[原始失败](evidence/real-tasks-initial.json)、[真实复测](evidence/real-tasks.json)、[独立产物](evidence/artifacts/qa-sales-result.json)。

## 8. 剩余事项与继续验证条件

| 状态 | 范围 / 原因 | 继续方法 |
|---|---|---|
| BLOCKED | 真实Telegram/飞书/邮件等通道没有明确测试账号及接收者 | 提供专用测试配置，在授权测试目标验证入站、审批、附件、启停、失败恢复；本轮未向真实联系人发消息 |
| BLOCKED | 外部MCP HTTP/OAuth无指定测试目标/凭据 | 接入隔离服务后跑认证、发现、超时、断线与恢复；本地stdio已通过 |
| BLOCKED | 自定义claude-opus-5-5单价未知，无法核对真实美元费用 | 填入可信pricing overrides，结合服务商账单核对费用及美元预算；不能用0值当通过 |
| NOT_TESTED | 进化完整真实候选效果、审核晋升及回滚 | 启用隔离演化配置、给真实技能目标和独立评估集，核对每步状态与实际能力变化 |
| NOT_TESTED/BLOCKED | 全部内置Skills、Agent浏览器任务、OCR/音频/图像/视频/容器 | 按具体能力准备资产、运行依赖、测试服务；安装all不代表运行条件齐备 |
| NOT_TESTED | 全向导、全部会话管理UI操作、审批真实到期、所有知识导入格式、全站辅助技术、长时压测 | 已有L2覆盖不能替代这些手工/长时真实流程；按矩阵补充 |
| NOT_TESTED | Linux/Windows、wheel独立安装、移动端 | 在对应环境独立构建/部署/验收；本轮macOS源码与桌面宽度结论不能外推 |
| N/A | client/** | 用户明确排除；未构建、未测试、未修改 |

没有剩余“已确认且在当前条件下可修复但仅留建议”的问题；以上是明确未验证或环境阻塞项。仍不能承诺绝对没有Bug，也不能用本次小样本模型成功推定复杂任务普遍可靠。

## 9. 当前本地状态与证据清理

交付前保留本次 Gateway 在 `127.0.0.1:58231` 运行；CLI/TUI、独立run、禁用功能Gateway、受控进程验证服务和扩展子进程均已退出。三个 Cron 测试job全部 `enabled=false`，无活动run，不会继续按分钟消耗模型请求。待办看板记录仅为竞争/重连合成数据；一条默认无人审批失败任务和旧失败历史保留，以免掩盖真实结果。

测试目录：`/private/tmp/echo-acceptance-20261021`。其中有权限受限的密钥、工作区、模型缓存、日志、PID与启动器；不会提交到仓库。报告证据仅复制脱敏 JSON/日志、合成产物和必要截图，没有复制运行数据库、私密配置、虚拟环境或模型缓存。证据清单及文件SHA256见 [manifest.json](evidence/manifest.json)。

需要清理时先用第3节的stop命令，确认本次 PID 已退出，再删除该专属临时目录；这也会移除本次密钥副本、合成工作区及约2.3GB模型/下载缓存。不要删除用户原有的模型目录。本次新装的 `.venv`、`web/node_modules`、`web/dist` 是忽略的本地部署产物，可以保留继续运行。最终源码和报告尚未提交；`client/**` 无改动。

## 10. 代码评审后的五项修复与复审

本节对应用户要求的五项完整修复。基线 commit 保持 `b7f31e43040da9e4c95498d113c44b7a46d81bf2`，保留原有未提交改动，没有提交或推送。本轮证据在独立的 [review-fixes](evidence/review-fixes/) 目录，原验收快照不覆盖。

| 评审问题 | 最终实现 | 回归验证 |
|---|---|---|
| Playground 不同会话共享 Chat ID 时串流 | 连接按投递目标与会话联合绑定；入站关联记录统一由 `GatewayDeliveryScopes` 管理，支持新建 metadata 的出站、工具发送及持久化恢复的 typed origin；关联不明时拒绝猜测接收者 | 两个真实 WebSocket 同 Chat ID 不同会话、HTTP A 不进入 WS B、切换后的迟到回复、旧 CLI 和派生会话兼容 |
| 修改 Session key 仍使用旧连接 | 更换身份后关闭旧连接并重新鉴权；清空旧会话展示；忽略旧 socket 的消息/关闭事件和迟到 HTTP 响应；增加 New conversation、发送中保护及状态播报；sessionStorage 不可用时仍可切换 | 实际 HTML 脚本的六项 DOM 回归，加真实 Chrome 编辑 key、新建会话、刷新恢复和 HTTP 中途切换 |
| 中文否定吞掉后续肯定请求 | 按分句判断否定，保留主题列表、版本号及英文缩写，处理连接词；完整 artifact 工具可用性和明确聊天输出约束继续生效 | 中文逗号/分号/换行混合命令、英文否定、禁止下载、版本号、U.S. 缩写及既有长报告用例 |
| 多目标路由掩盖无人接收 | 未匹配路由继续弃权；已匹配但无 handler 的目标明确失败；`DeliveryResult.merge` 统一合并规则并保留各路由结果与投递未知状态 | 成功/缺失目标的两种顺序、主目标成功、部分失败、未知投递、恢复与重复发送保护 |
| 模型归档软链接安装后悬空 | 相对链接的目标必须是最终安装子目录内的归档普通文件；非法归档不迁入缓存并清理临时目录；合法 HF blob 链接继续支持 | 包外链接、包内其他顶层文件/模型目录链接拒绝；合法软链接及分卷/摘要/下载恢复既有测试 |

会话复审另修复一项关联边界：同一会话重新连接后，旧 socket 关闭不会取消新连接正在等待的追问。关联缓存有容量上限；过期关联不会转投其他会话，持久化恢复优先使用事件自带的 origin。

验证记录：

- 后端完整测试：第一次 7815 passed、47 skipped；最终源码独立全量复跑为 **7818 passed、47 skipped、5 warnings，328.91s，退出 0**，见 [backend-final.log](evidence/review-fixes/backend-final.log)。5 个 warning 均为既有旧格式模型缓存的 FutureWarning，退出时另有 SWIG DeprecationWarning。本轮没有重新测量覆盖率。
- 前端完整测试：31 文件、246 passed，见 [web-tests.log](evidence/review-fixes/web-tests.log)；最终 HTML 再单独复测六项生命周期用例，见 [playground-final.log](evidence/review-fixes/playground-final.log)。
- TypeScript、Vite 生产构建和包体门禁通过，见 [web-build.log](evidence/review-fixes/web-build.log)；Ruff 与 `git diff --check` 通过。
- 真实 Chrome 四项交互场景通过，无 pageerror，见 [browser.json](evidence/review-fixes/browser.json) 和 [页面截图](evidence/review-fixes/playground.png)。该 Gateway 使用本地合成回复验证真实 HTTP/WS 通信，`real_external_model=false`，不能外推为新增远端模型或真实 IM 验收。
- 最终源码哈希、测试摘要和本节证据校验值见 [manifest.json](evidence/review-fixes/manifest.json)。

复审覆盖全部当前未提交源代码及其调用链，重点核对会话隔离、重连清理、旧客户端、跨通道发送、审批/追问、恢复回执、长文输出和缓存安装。未发现本轮修复引入的新增待修复问题。可选外部集成、其他操作系统及依赖环境限制仍沿用第 8 节边界，跳过用例不计为通过。没有重启历史的本地验收实例；使用这些后端修改需要正常重启相应 Gateway。本轮临时浏览器 Gateway 已退出。
