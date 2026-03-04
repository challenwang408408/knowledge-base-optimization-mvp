"""知识库优化 Agent 2.0 — Streamlit 主入口

三栏布局：左栏(输入) | 中栏(优化器配置) | 右栏(输出)
"""

import sys
import html as html_lib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd

from config import settings
from agent.registry import registry
from agent.agent_loader import load_agents
from utils.excel_handler import read_excel, df_to_excel_bytes
from services.optimization_service import optimization_service, ExecutionRequest

# --------------- 每次页面加载时刷新配置 ---------------
settings.reload()

# --------------- 通过配置文件注册子代理 ---------------
if not registry.list_all():
    load_agents(registry)

# --------------- 页面配置 ---------------
st.set_page_config(
    page_title="知识库优化 Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------- 注入设计令牌 CSS ---------------
css_path = Path(__file__).parent / "style" / "design_tokens.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# --------------- 初始化 session_state ---------------
if "selected_agent_id" not in st.session_state:
    st.session_state.selected_agent_id = None
if "execution_response" not in st.session_state:
    st.session_state.execution_response = None

# --------------- 占位优化器定义（仅前端展示）---------------
PLACEHOLDER_AGENTS = [
    {
        "id": "__placeholder_qa_check",
        "icon": "🔍",
        "name": "知识库质检",
        "desc": "自动检测知识库中的质量问题：重复项、矛盾回答、格式异常等",
    },
    {
        "id": "__placeholder_multi_a",
        "icon": "💡",
        "name": "多A扩展",
        "desc": "为每条问答对生成多种不同角度的答案表达，提升回答丰富度",
    },
    {
        "id": "__placeholder_dedup",
        "icon": "🧹",
        "name": "知识去重",
        "desc": "智能识别并合并语义相似的问答对，精简知识库体积",
    },
]


def _df_to_html_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """将 DataFrame 渲染为安全的 HTML 表格。"""
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


# --------------- 侧边栏：模型配置 ---------------
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
        "知识库优化 Agent v2.0\n\n"
        "采用大 Agent + 子代理架构，\n"
        "支持可插拔的优化能力扩展。"
    )

# ===============================================================
# 页面头部
# ===============================================================
st.markdown("# 知识库优化 Agent")
st.caption("上传知识库文件，选择优化方式，一键生成优化结果")
st.markdown("")

# ===============================================================
# 三栏布局
# ===============================================================
col_left, col_center, col_right = st.columns([1, 1.6, 1.4], gap="large")

# ===================================================================
# 左栏：输入区
# ===================================================================
with col_left:
    st.markdown(
        '<div class="panel-title">📂 输入区</div>',
        unsafe_allow_html=True,
    )

    # --- 文件上传 ---
    uploaded_file = st.file_uploader(
        "选择 Excel 文件（需包含 Q、A 列）",
        type=["xlsx", "xls"],
        help="支持 .xlsx / .xls 格式",
    )

    df_preview: pd.DataFrame | None = None

    if uploaded_file is not None:
        try:
            df_preview = read_excel(uploaded_file.getvalue())
            c1, c2 = st.columns(2)
            with c1:
                st.metric(label="行数", value=len(df_preview))
            with c2:
                st.metric(label="列数", value=len(df_preview.columns))

            show_preview = st.toggle("预览前 5 行", value=False, key="preview_toggle")
            if show_preview:
                st.markdown(
                    f'<div class="scroll-panel scroll-panel--preview">'
                    f'{_df_to_html_table(df_preview, max_rows=5)}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:
            st.error(f"文件解析失败：{e}")
            df_preview = None

    # --- 已上传文件列表 ---
    st.markdown("")
    st.markdown(
        '<div class="panel-title">📋 文件列表</div>',
        unsafe_allow_html=True,
    )

    if uploaded_file is not None:
        size_kb = round(len(uploaded_file.getvalue()) / 1024, 1)
        st.markdown(
            f'<div class="file-list-item">'
            f'<span class="file-icon">📄</span>'
            f'<span class="file-name">{html_lib.escape(uploaded_file.name)}</span>'
            f'<span class="file-size">{size_kb} KB</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("暂无文件，请在上方上传")

    st.markdown("")
    st.caption("💡 未来将支持从已有知识库导入文件夹")


# ===================================================================
# 中栏：优化器配置
# ===================================================================
with col_center:
    st.markdown(
        '<div class="panel-title">⚙️ 优化器配置</div>',
        unsafe_allow_html=True,
    )

    # --- 优化器选择（下拉列表 + 单卡片展示）---
    agents = registry.list_all()
    icon_map = {"multi_q_expander": "🔄"}

    _all_opts = []
    for agent in agents:
        _all_opts.append({
            "id": agent.id,
            "icon": icon_map.get(agent.id, "🔧"),
            "name": agent.name,
            "desc": agent.description,
            "is_placeholder": False,
        })
    for ph in PLACEHOLDER_AGENTS:
        _all_opts.append({
            "id": ph["id"],
            "icon": ph["icon"],
            "name": ph["name"],
            "desc": ph["desc"],
            "is_placeholder": True,
        })

    _opt_labels = [
        f'{o["icon"]}  {o["name"]}' + ("  ·  即将上线" if o["is_placeholder"] else "")
        for o in _all_opts
    ]

    chosen_label = st.selectbox("选择优化方式", _opt_labels)
    chosen_idx = _opt_labels.index(chosen_label)
    chosen = _all_opts[chosen_idx]

    if chosen["is_placeholder"]:
        st.session_state.selected_agent_id = None
        st.markdown(
            f'<div class="selected-agent-card placeholder">'
            f'<div class="sac-icon">{chosen["icon"]}</div>'
            f'<div class="sac-body">'
            f'<div class="sac-title">{chosen["name"]}</div>'
            f'<div class="sac-desc">{chosen["desc"]}</div>'
            f'<span class="coming-soon-badge">即将上线</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.session_state.selected_agent_id = chosen["id"]
        st.markdown(
            f'<div class="selected-agent-card">'
            f'<div class="sac-icon">{chosen["icon"]}</div>'
            f'<div class="sac-body">'
            f'<div class="sac-title">{chosen["name"]}</div>'
            f'<div class="sac-desc">{chosen["desc"]}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # --- 参数配置 ---
    selected_agent = None
    user_params: dict = {}

    if st.session_state.get("selected_agent_id"):
        selected_agent = registry.get(st.session_state.selected_agent_id)

    if selected_agent:
        st.divider()
        st.markdown(f"**参数配置 — {selected_agent.name}**")

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
                st.caption("用英文分号 ; 分隔多个关键词（注意不要用中文分号 ；）")
                raw_kw = st.text_input(
                    label, value=default, help=desc,
                    placeholder="例如：退款;发票;会员权益;配送",
                    label_visibility="collapsed",
                )
                user_params[key] = raw_kw

                if raw_kw.strip():
                    tags = [
                        t.strip()
                        for t in raw_kw.replace("，", ";").replace(",", ";").split(";")
                        if t.strip()
                    ]
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

    # --- 执行按钮 ---
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
            hints.append("配置 LLM API Key")
        st.info("请完成以下步骤后执行：" + "、".join(hints))

    execute_clicked = st.button(
        "开始执行优化",
        type="primary",
        disabled=not can_execute,
        use_container_width=True,
    )

    if execute_clicked and can_execute:
        request = ExecutionRequest(
            agent_id=selected_agent.id,
            df=df_preview,
            user_params=user_params,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
        )

        progress_bar = st.progress(0, text="正在初始化...")
        with st.spinner("正在执行优化，请稍候..."):
            progress_bar.progress(10, text="正在校验文件...")
            response = optimization_service.execute(request)
            progress_bar.progress(100, text="执行完成")

        st.session_state.execution_response = response


# ===================================================================
# 右栏：输出区
# ===================================================================
with col_right:
    st.markdown(
        '<div class="panel-title">📊 输出区</div>',
        unsafe_allow_html=True,
    )

    response = st.session_state.get("execution_response")

    if response is None:
        st.markdown(
            '<div class="output-placeholder">'
            '<div class="placeholder-icon">📋</div>'
            '<div class="placeholder-text">执行优化后，结果将显示在这里</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    elif not response.success:
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
        st.markdown("**执行摘要**")
        summary = result.summary
        m1, m2 = st.columns(2)
        with m1:
            st.metric("总处理", summary.get("total", 0))
            st.metric("失败", summary.get("failed", 0))
        with m2:
            st.metric("成功", summary.get("success", 0))
            st.metric("耗时", f'{summary.get("elapsed_seconds", 0)}s')

        # --- 差异对比 ---
        st.markdown("**差异对比**")
        st.caption("原始问题 vs 扩展变体")

        diff_items = result.diff_items
        has_diff = any(item.expanded_qs for item in diff_items)
        if has_diff:
            diff_html_parts = []
            for i, item in enumerate(diff_items):
                if not item.expanded_qs:
                    continue
                escaped_q = html_lib.escape(item.original_q)
                expanded_html = "".join(
                    f'<div class="expanded-q">{html_lib.escape(q)}</div>'
                    for q in item.expanded_qs
                )
                diff_html_parts.append(
                    f'<div class="diff-row">'
                    f'<div class="original-q">Q{i + 1}: {escaped_q}</div>'
                    f"{expanded_html}"
                    f"</div>"
                )
            st.markdown(
                f'<div class="scroll-panel scroll-panel--diff">'
                f'{"".join(diff_html_parts)}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("暂无差异数据")

        # --- 结果表格 ---
        st.markdown("**完整结果**")
        if result.output_df is not None:
            st.markdown(
                f'<div class="scroll-panel scroll-panel--result">'
                f'{_df_to_html_table(result.output_df)}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # --- 下载 ---
        if result.output_df is not None:
            excel_bytes = df_to_excel_bytes(result.output_df)
            st.download_button(
                label="下载优化后 Excel",
                data=excel_bytes,
                file_name="优化结果.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        # --- 错误明细 ---
        if summary.get("error_details"):
            show_errors = st.toggle("查看失败明细", value=False, key="error_toggle")
            if show_errors:
                for detail in summary["error_details"]:
                    st.warning(detail)
