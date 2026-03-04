# 知识库优化 Agent（v2.0）

基于"大 Agent + 子代理"架构的知识库优化工具。一期实现**多Q扩展**能力：为知识库中的每条问题自动生成多种变体表达，提升知识库的召回覆盖率。

## v2.0 升级说明

本版本在保留 MVP 全部功能的前提下，完成以下架构与前端升级：

| 升级项 | 说明 |
|--------|------|
| 统一结果协议 | 新增 `UnifiedResult` / `Artifact` / `Metrics`，支持异构产物（表格、文本报告、文件等） |
| 服务层抽离 | 新增 `services/optimization_service.py`，UI 不再直接操作 MainAgent |
| 配置化注册 | 通过 `agents_config.yaml` 管理子代理开关与元数据，支持安全回退 |
| 任务层抽象 | 新增 `services/task_manager.py`，提供 task_id、状态流转、耗时记录 |
| 前端三栏布局 | 左（输入）/ 中（优化器配置）/ 右（输出）三栏并列 |
| Claude AI 风格 | 温暖米色背景 + 暖橙主色 + 衬线标题字体 |

## 快速开始

### 1. 安装依赖

```bash
cd 知识库优化mvp
pip install -r requirements.txt
```

### 2. 配置 LLM

复制 `.env.example` 为 `.env`，填入你的 LLM 配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

支持任何兼容 OpenAI 标准协议的服务。

### 3. 启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 使用流程

1. **上传文件** — 在左栏上传 Excel 文件（需包含 Q、A 列）
2. **选择优化方式** — 在中栏点击"多Q扩展"卡片
3. **配置参数** — 设置扩展倍率、语气风格、领域关键词
4. **执行** — 点击"开始执行优化"
5. **查看结果** — 在右栏浏览执行摘要、差异对比
6. **下载** — 点击下载按钮获取优化后的 Excel 文件

## 架构说明（v2.0）

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit UI (三栏布局)                 │
│  左栏: 文件上传   中栏: 优化器选择+参数   右栏: 结果展示   │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────┐
│              OptimizationService (服务层)                   │
│   参数组装 → 任务创建 → 调用 Agent → 状态更新              │
├───────────────────────────────────────────────────────────┤
│              TaskManager (任务状态管理)                     │
│   task_id / pending → running → success/failed            │
└───────────────────────────┬───────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────┐
│               MainAgent (大 Agent 调度)                    │
│   1. 路由  2. 后置校验  3. 执行  4. 汇总                   │
└───────────────────────────┬───────────────────────────────┘
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
┌───────────────────────┐ ┌──────────────────┐
│  MultiQExpander       │ │ （未来子代理）     │
│  多Q扩展              │ │ 质检 / 去重 …     │
│  输出: V1 + V2 协议    │ └──────────────────┘
└───────────────────────┘
```

**关键设计：**

- **校验后置** — 文件校验在用户选择优化方式后，由大 Agent 根据子代理的 `input_schema` 执行
- **双协议并行** — `SubAgentResult` 同时包含 V1 旧字段和 V2 `UnifiedResult`，UI 渐进迁移
- **配置化注册** — `agents_config.yaml` 控制子代理加载，支持 enabled/disabled
- **任务追踪** — 每次执行自动创建 task，记录状态和耗时

## 项目结构

```
知识库优化mvp/
├── app.py                       # Streamlit 主入口（三栏布局）
├── config.py                    # 配置管理
├── agents_config.yaml           # 子代理配置清单
├── requirements.txt             # 依赖清单
├── .env.example                 # 环境变量示例
├── style/
│   └── design_tokens.css        # UI 设计令牌（Claude AI 风格）
├── agent/
│   ├── main_agent.py            # 大 Agent 调度
│   ├── registry.py              # 子代理注册中心
│   └── agent_loader.py          # 配置化加载器
├── sub_agents/
│   ├── base.py                  # 子代理协议基类（含 V2 统一协议）
│   └── multi_q_expander.py      # 多Q扩展子代理
├── services/
│   ├── optimization_service.py  # 优化编排服务
│   └── task_manager.py          # 任务状态管理
├── utils/
│   ├── excel_handler.py         # Excel 工具
│   └── llm_client.py            # LLM 客户端
├── tests/
│   ├── test_basic.py            # V1 基础测试（44 项）
│   ├── test_protocol_compat.py  # V2 协议兼容测试（34 项）
│   ├── test_service_layer.py    # 服务层测试（15 项）
│   ├── test_config_loader.py    # 配置加载测试（16 项）
│   ├── test_task_manager.py     # 任务管理测试（38 项）
│   ├── test_regression_v2.py    # 综合回归测试（51 项）
│   ├── generate_test_data.py    # 测试数据生成
│   ├── baseline_v1_output.txt   # V1 基线快照
│   └── test_data/               # 20 份测试文件
├── sample_data/
│   └── sample_qa.xlsx           # 示例文件
└── README.md
```

## 测试

```bash
# 生成测试数据（如尚未生成）
python3 tests/generate_test_data.py

# V1 基础测试（44 项，不需要 LLM）
python3 tests/test_basic.py

# V2 协议兼容测试（34 项）
python3 tests/test_protocol_compat.py

# 服务层测试（15 项）
python3 tests/test_service_layer.py

# 配置加载测试（16 项）
python3 tests/test_config_loader.py

# 任务管理测试（38 项）
python3 tests/test_task_manager.py

# 综合回归测试（51 项，覆盖 12 项功能点）
python3 tests/test_regression_v2.py

# 端到端测试（需要配置 .env 中的 LLM）
python3 tests/test_basic.py --e2e
```

全部测试合计 **198 项**，覆盖：
- 12 项 MVP 功能点的完整性验证
- V1/V2 协议兼容性
- 服务层行为一致性
- 配置加载正常/异常/回退场景
- 任务状态完整生命周期

## 子代理配置

编辑 `agents_config.yaml` 可控制子代理的加载：

```yaml
agents:
  - id: multi_q_expander
    module: sub_agents.multi_q_expander
    class_name: MultiQExpander
    enabled: true      # 设为 false 可禁用
    icon: "🔄"
    order: 1
```

配置文件不存在或格式错误时，系统自动回退到默认注册。

## 常见报错

| 现象 | 原因 | 解决方式 |
|------|------|----------|
| `LLM_API_KEY 未设置` | 未配置 API Key | 在 `.env` 文件中填入 |
| `缺少必要列：Q, A` | Excel 中无 Q/A 列 | 确认文件包含 Q 和 A 列 |
| `LLM API 错误` | API Key 无效或额度不足 | 检查 Key 有效性和账户余额 |
| `LLM 调用在 3 次重试后仍失败` | 网络不稳或服务端限流 | 稍后重试，或检查 Base URL |
| `文件解析失败` | Excel 格式损坏 | 确认是 .xlsx 格式 |

## 技术栈

- **Streamlit** — 应用框架
- **OpenAI Python SDK** — LLM 调用
- **openpyxl / pandas** — Excel 处理
- **python-dotenv** — 环境变量管理
- **PyYAML** — 配置文件解析
