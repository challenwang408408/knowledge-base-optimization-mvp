# 知识库优化 Agent（MVP）

基于"大 Agent + 子代理"架构的知识库优化工具。一期实现**多Q扩展**能力：为知识库中的每条问题自动生成多种变体表达，提升知识库的召回覆盖率。

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

支持任何兼容 OpenAI 标准协议的服务（OpenAI、Azure、本地部署等）。也可以在启动后通过页面侧边栏实时修改。

### 3. 启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 使用流程

1. **上传文件** — 在页面上方上传 Excel 文件（需包含 Q、A 列）
2. **选择优化方式** — 点击"多Q扩展"卡片
3. **配置参数** — 设置扩展倍率、语气风格、领域关键词（均可选）
4. **执行** — 点击"开始执行优化"，等待结果返回
5. **查看结果** — 浏览执行摘要、差异对比
6. **下载** — 点击下载按钮获取优化后的 Excel 文件

## 样例文件格式

输入 Excel 需包含 **Q**（问题）和 **A**（答案）两列，列名大小写不敏感：

| Q | A |
|---|---|
| 如何重置密码？ | 您可以在登录页面点击「忘记密码」链接进行重置。 |
| 退款需要多长时间？ | 退款通常在3-5个工作日内到账。 |

可在 `sample_data/sample_qa.xlsx` 找到示例文件。

输出 Excel 在原有列基础上新增 **扩展问题** 列，多条变体用 `||` 分隔。

## 架构说明

```
┌─────────────────────────────────────────────────┐
│                  Streamlit UI                    │
│  上传文件 → 选择优化方式 → 配置参数 → 查看结果    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│               大 Agent (MainAgent)                │
│                                                   │
│  1. 路由：根据用户选择找到对应子代理               │
│  2. 后置校验：用子代理的 input_schema 验证文件     │
│  3. 执行：调用子代理的 run() 方法                  │
│  4. 汇总：封装摘要、差异对比、输出文件             │
└──────────────────────┬───────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────┐  ┌─────────────────┐
│  multi_q_expander │  │  （未来子代理）  │
│  多Q扩展          │  │  质检 / 去重 …  │
└──────────────────┘  └─────────────────┘
```

**关键设计：校验后置**

不同子代理对输入文件的要求不同。文件校验不在上传时做，而是在用户选择了优化方式后，由大 Agent 根据对应子代理的 `input_schema` 来执行。这样新增子代理时不需要修改大 Agent 的调度逻辑。

**子代理统一协议**

每个子代理必须实现 `SubAgentBase` 定义的接口：

- `id` / `name` / `description` — 标识与说明
- `input_schema` — 声明式文件要求
- `params_schema` — 可配置参数定义
- `validate_input(df)` — 文件校验逻辑
- `run(df, params)` — 核心执行逻辑
- `output_schema` — 结果结构定义

## 项目结构

```
知识库优化mvp/
├── app.py                       # Streamlit 主入口
├── config.py                    # 配置管理
├── requirements.txt             # 依赖清单
├── .env.example                 # 环境变量示例
├── style/
│   └── design_tokens.css        # UI 设计令牌
├── agent/
│   ├── main_agent.py            # 大 Agent 调度
│   └── registry.py              # 子代理注册中心
├── sub_agents/
│   ├── base.py                  # 子代理协议基类
│   └── multi_q_expander.py      # 多Q扩展子代理
├── utils/
│   ├── excel_handler.py         # Excel 工具
│   └── llm_client.py            # LLM 客户端
├── tests/
│   ├── test_basic.py            # 自测脚本
│   ├── generate_test_data.py    # 测试数据生成
│   └── test_data/               # 20份测试文件
├── sample_data/
│   └── sample_qa.xlsx           # 示例文件
└── README.md
```

## 测试

```bash
# 生成测试数据（如尚未生成）
python3 tests/generate_test_data.py

# 运行单元测试（不需要 LLM）
python3 tests/test_basic.py

# 运行端到端测试（需要配置 .env 中的 LLM）
python3 tests/test_basic.py --e2e
```

## 常见报错

| 现象 | 原因 | 解决方式 |
|------|------|----------|
| `LLM_API_KEY 未设置` | 未配置 API Key | 在 `.env` 文件或侧边栏中填入 |
| `缺少必要列：Q, A` | Excel 中无 Q/A 列 | 确认文件包含 Q 和 A 列 |
| `LLM API 错误` | API Key 无效或额度不足 | 检查 Key 有效性和账户余额 |
| `LLM 调用在 3 次重试后仍失败` | 网络不稳或服务端限流 | 稍后重试，或检查 Base URL |
| `文件解析失败` | Excel 格式损坏 | 确认是 .xlsx 格式，用 Excel 重新保存 |

## 技术栈

- **Streamlit** — 应用框架
- **OpenAI Python SDK** — LLM 调用
- **openpyxl / pandas** — Excel 处理
- **python-dotenv** — 环境变量管理
