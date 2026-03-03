"""知识库优化 Agent — Streamlit 主入口"""

import sys
import html as html_lib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd

from config import settings
from agent.registry import registry
from agent.main_agent import main_agent
from sub_agents.multi_q_expander import MultiQExpander
from utils.excel_handler import read_excel, df_to_excel_bytes

# --------------- 每次页面加载时刷新配置 ---------------
settings.reload()

# --------------- 注册子代理 ---------------
if not registry.list_all():
    registry.register(MultiQExpander())

# --------------- 页面配置 ---------------
st.set_page_config(
    page_title="知识库优化 Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------- 注入设计令牌 CSS ---------------
css_path = Path(__file__).parent / "style" / "design_tokens.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def _df_to_html_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """将 DataFrame 渲染为安全的 HTML 表格，避免 Arrow 渲染乱码。"""
    subset = df.head(max_rows) if max_rows else df
    header = "".join(
        f"<th>{html_lib.escape(str(c))}</th>" for c in subset.columns
    )
    rows_html = ""
    for _, row in subset.iterrows():
        cells = "".join(
            f"<td>{html_lib.escape(str(v))}</td>" for v in row
        )
        rows_html += f"<tr>{cells}</tr>"
    return (
        '<div style="overflow-x:auto;">'
        '<table class="preview-table">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )


# --------------- 侧边栏：LLM 配置状态 ---------------
with st.sidebar:
    st.markdown("### 模型配置")

    has_key = bool(settings.LLM_API_KEY and settings.LLM_API_KEY != "sk-your-api-key-here")
    if has_key:
        masked = settings.LLM_API_KEY[:8] + "****" + settings.LLM_API_KEY[-4:]
        st.success(f"API Key 已配置（{masked}）")
    else:
        st.error("API Key 未配置，请在 .env 文件中设置 LLM_API_KEY")

    st.caption(f"Base URL: {settings.LLM_BASE_URL}")
    st.caption(f"Model: {settings.LLM_MODEL}")
    st.caption("如需修改，请编辑项目根目录的 .env 文件")

    st.divider()
    st.markdown("### 关于")
    st.caption(
        "知识库优化 Agent MVP\n\n"
        "采用大 Agent + 子代理架构，\n"
        "支持可插拔的优化能力扩展。"
    )

# --------------- 主内容区 ---------------
st.markdown("# 知识库优化 Agent")
st.caption("上传知识库文件，选择优化方式，一键生成优化结果")

# ===== STEP 1: 文件上传 =====
st.markdown("### 上传知识库文件")

uploaded_file = st.file_uploader(
    "选择 Excel 文件（需包含 Q、A 列）",
    type=["xlsx", "xls"],
    help="支持 .xlsx / .xls 格式，文件中需要有问题列（Q）和答案列（A）",
)

df_preview: pd.DataFrame | None = None

if uploaded_file is not None:
    try:
        df_preview = read_excel(uploaded_file.getvalue())
        col_names = ", ".join(df_preview.columns[:5])
        if len(df_preview.columns) > 5:
            col_names += "..."
        c1, c2 = st.columns(2)
        with c1:
            st.metric(label="数据行数", value=len(df_preview))
        with c2:
            st.metric(label="列数", value=len(df_preview.columns), help=col_names)
        show_preview = st.toggle("预览文件前 5 行", value=False, key="preview_toggle")
        if show_preview:
            st.markdown(
                _df_to_html_table(df_preview, max_rows=5),
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"文件解析失败：{e}")
        df_preview = None

st.divider()

# ===== STEP 2: 选择优化目的（卡片） =====
st.markdown("### 选择优化方式")

agents = registry.list_all()

if not agents:
    st.markdown(
        '<div class="empty-state">'
        '<div class="empty-title">暂无可用的优化能力</div>'
        '<div class="empty-desc">请联系管理员注册子代理</div>'
        "</div>",
        unsafe_allow_html=True,
    )
else:
    if "selected_agent_id" not in st.session_state:
        st.session_state.selected_agent_id = None

    cols = st.columns(min(len(agents), 3))
    for i, agent in enumerate(agents):
        with cols[i % 3]:
            is_selected = st.session_state.selected_agent_id == agent.id
            selected_class = " selected" if is_selected else ""
            icon_map = {"multi_q_expander": "🔄"}
            icon = icon_map.get(agent.id, "🔧")

            st.markdown(
                f'<div class="avatar-card{selected_class}">'
                f'<div class="card-icon">{icon}</div>'
                f'<div class="card-title">{agent.name}</div>'
                f'<div class="card-desc">{agent.description}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            btn_label = "✓ 已选择" if is_selected else "选择"
            btn_type = "primary" if is_selected else "secondary"
            if st.button(btn_label, key=f"btn_{agent.id}", type=btn_type):
                st.session_state.selected_agent_id = agent.id
                st.rerun()

# ===== STEP 2.5: 参数配置 =====
selected_agent = None
user_params: dict = {}

if st.session_state.get("selected_agent_id"):
    selected_agent = registry.get(st.session_state.selected_agent_id)

if selected_agent:
    st.divider()
    st.markdown(f"### 配置参数 — {selected_agent.name}")

    schema = selected_agent.params_schema

    for key, spec in schema.items():
        param_type = spec.get("type", "str")
        label = spec.get("label", key)
        desc = spec.get("description", "")
        default = spec.get("default", "")

        if param_type == "int":
            user_params[key] = st.number_input(
                label, min_value=spec.get("min", 1),
                max_value=spec.get("max", 100),
                value=default, help=desc,
            )
            st.markdown(
                f'<div class="param-feedback">'
                f'<span class="feedback-label">当前值：</span>'
                f'<span class="feedback-value">{user_params[key]}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

        elif param_type == "select":
            options = spec.get("options", [])
            idx = options.index(default) if default in options else 0
            user_params[key] = st.selectbox(label, options, index=idx, help=desc)
            st.markdown(
                f'<div class="param-feedback">'
                f'<span class="feedback-label">已选择：</span>'
                f'<span class="feedback-value">{user_params[key]}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

        elif key == "keywords":
            st.markdown(f"**{label}**")
            st.caption(f"{desc}（用分号 ; 分隔多个关键词，按回车确认）")
            raw_kw = st.text_input(
                label, value=default, help=desc,
                placeholder="例如：退款;发票;会员权益;配送",
                label_visibility="collapsed",
            )
            user_params[key] = raw_kw

            if raw_kw.strip():
                tags = [t.strip() for t in raw_kw.replace("，", ";").replace(",", ";").split(";") if t.strip()]
                if tags:
                    tags_html = "".join(
                        f'<span class="keyword-tag">{t}</span>' for t in tags
                    )
                    st.markdown(
                        f'<div class="keyword-tags">{tags_html}</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(f"已添加 {len(tags)} 个关键词")
        else:
            user_params[key] = st.text_input(label, value=default, help=desc)

# ===== STEP 3: 执行 =====
st.divider()

can_execute = (
    uploaded_file is not None
    and df_preview is not None
    and selected_agent is not None
    and has_key
)

if not can_execute:
    hints = []
    if uploaded_file is None:
        hints.append("上传 Excel 文件")
    if not st.session_state.get("selected_agent_id"):
        hints.append("选择优化方式")
    if not has_key:
        hints.append("在 .env 文件中配置 LLM_API_KEY")
    st.info("请完成以下步骤后执行：" + "、".join(hints))

execute_clicked = st.button(
    "开始执行优化",
    type="primary",
    disabled=not can_execute,
)

if execute_clicked and can_execute:
    user_params["_api_key"] = settings.LLM_API_KEY
    user_params["_base_url"] = settings.LLM_BASE_URL
    user_params["_model"] = settings.LLM_MODEL

    progress_bar = st.progress(0, text="正在初始化...")

    with st.spinner("正在执行优化，请稍候..."):
        progress_bar.progress(10, text="正在校验文件...")
        response = main_agent.execute(
            agent_id=selected_agent.id,
            df=df_preview,
            params=user_params,
        )
        progress_bar.progress(100, text="执行完成")

    if not response.success:
        st.error(f"执行失败（阶段：{response.stage}）")
        if response.validation_errors:
            st.markdown("**校验错误：**")
            for err in response.validation_errors:
                st.warning(err)
        if response.error:
            st.error(response.error)
    else:
        result = response.result
        st.success("优化完成！")

        # --- 摘要 ---
        st.markdown("### 执行摘要")
        summary = result.summary
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("总处理条数", summary.get("total", 0))
        with c2:
            st.metric("成功", summary.get("success", 0))
        with c3:
            st.metric("失败", summary.get("failed", 0))
        with c4:
            st.metric("耗时", f'{summary.get("elapsed_seconds", 0)}s')

        # --- 差异对比 ---
        st.markdown("### 差异对比")
        st.caption("原始问题 vs 扩展生成的变体问题")

        diff_items = result.diff_items
        has_diff = any(item.expanded_qs for item in diff_items)
        if has_diff:
            for i, item in enumerate(diff_items):
                if not item.expanded_qs:
                    continue
                escaped_q = html_lib.escape(item.original_q)
                expanded_html = "".join(
                    f'<div class="expanded-q">{html_lib.escape(q)}</div>'
                    for q in item.expanded_qs
                )
                st.markdown(
                    f'<div class="diff-row">'
                    f'<div class="original-q">Q{i + 1}: {escaped_q}</div>'
                    f"{expanded_html}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("暂无差异数据")

        # --- 结果表格 ---
        st.markdown("### 完整结果预览")
        if result.output_df is not None:
            st.markdown(
                _df_to_html_table(result.output_df),
                unsafe_allow_html=True,
            )

        # --- 下载 ---
        st.markdown("### 下载结果文件")
        if result.output_df is not None:
            excel_bytes = df_to_excel_bytes(result.output_df)
            st.download_button(
                label="下载优化后 Excel",
                data=excel_bytes,
                file_name="优化结果.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # --- 错误明细 ---
        if summary.get("error_details"):
            show_errors = st.toggle("查看失败明细", value=False, key="error_toggle")
            if show_errors:
                for detail in summary["error_details"]:
                    st.warning(detail)
