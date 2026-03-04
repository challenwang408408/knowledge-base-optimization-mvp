"""知识库优化 Agent 2.0 — Streamlit 主入口

三栏布局：左栏(输入) | 中栏(优化器配置) | 右栏(输出)
仅重构交互与视觉，不变更业务逻辑。
"""

from __future__ import annotations

import sys
import html as html_lib
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from agent.agent_loader import load_agents
from agent.registry import registry
from config import settings
from services.optimization_service import ExecutionRequest, optimization_service
from sub_agents.base import DiffItem, SubAgentResult
from utils.excel_handler import df_to_excel_bytes, read_excel

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


def _inject_css() -> None:
    css_path = Path(__file__).parent / "style" / "design_tokens.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def _init_session_state() -> None:
    defaults = {
        "selected_agent_id": None,
        "execution_response": None,
        "output_state_mode": "自动",
        "global_top_tab": "知识库",
        "global_side_menu": "知识优化工作台",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _df_to_html_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """将 DataFrame 渲染为安全的 HTML 表格。"""
    subset = df.head(max_rows) if max_rows else df
    header = "".join(f"<th>{html_lib.escape(str(c))}</th>" for c in subset.columns)
    rows_html = ""
    for _, row in subset.iterrows():
        cells = "".join(f"<td>{html_lib.escape(str(v))}</td>" for v in row)
        rows_html += f"<tr>{cells}</tr>"
    return (
        '<div style="overflow-x:auto;">'
        '<table class="preview-table">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )


def _build_agent_options() -> list[dict]:
    icon_map = {"multi_q_expander": "🔄"}
    opts: list[dict] = []

    for agent in registry.list_all():
        opts.append(
            {
                "id": agent.id,
                "icon": icon_map.get(agent.id, "🔧"),
                "name": agent.name,
                "desc": agent.description,
                "is_placeholder": False,
            }
        )

    for ph in PLACEHOLDER_AGENTS:
        opts.append(
            {
                "id": ph["id"],
                "icon": ph["icon"],
                "name": ph["name"],
                "desc": ph["desc"],
                "is_placeholder": True,
            }
        )

    return opts


def _has_valid_api_key() -> bool:
    return bool(settings.LLM_API_KEY and settings.LLM_API_KEY != "sk-your-api-key-here")


def _render_global_top_tabs() -> None:
    st.markdown(
        '<div class="system-topbar">'
        '<div class="system-brand"><span class="brand-dot">◎</span><span class="brand-text">AVATAR</span></div>'
        '<div class="system-tabs">'
        '<span class="sys-tab">探索</span>'
        '<span class="sys-tab active">应用开发</span>'
        '<span class="sys-tab">模型服务</span>'
        '<span class="sys-tab">模型体验</span>'
        '<span class="sys-tab">实验室</span>'
        "</div>"
        '<div class="system-top-actions">'
        '<span class="top-icon">◌</span>'
        '<span class="top-icon">◍</span>'
        '<span class="top-avatar"></span>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_workspace_header() -> None:
    st.markdown(
        '<div class="workspace-header">'
        '<div class="workspace-header-left"><span class="back-chip">‹</span><span class="workspace-title">知识库优化 Agent</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_step_bar() -> None:
    st.markdown(
        '<div class="step-bar">'
        '<span class="step-pill active">1 上传文件</span>'
        '<span class="step-pill">2 选择优化器</span>'
        '<span class="step-pill">3 参数配置</span>'
        '<span class="step-pill">4 查看与下载</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def _build_global_sidebar_html() -> str:
    return (
        '<div class="system-sidebar-wrap"><div class="system-side-html">'
        '<div class="biz-select"><span class="biz-icon">◌</span><span>体验业务</span><span class="biz-arrow">⌄</span></div>'
        '<div class="menu-group">'
        '<div class="system-menu-item active"><span class="menu-icon">◫</span><span>应用管理</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>知识广场</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>模板市场</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>插件市场</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>MCP市场</span></div>'
        '</div>'
        '<div class="menu-group">'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>应用评测</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>发布管理</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>场景管理</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>Badcase 管理</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>对话日志</span></div>'
        '<div class="system-menu-item"><span class="menu-icon">◫</span><span>对话分析</span></div>'
        '</div>'
        "</div></div>"
    )


def _render_footer_hint() -> None:
    st.markdown(
        '<div class="workspace-footer">'
        '<span class="footer-hint">支持 .xlsx / .xls，建议单次不超过 5000 行。</span>'
        '<span class="ghost-chip">上一步</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_input_panel() -> tuple[object | None, pd.DataFrame | None]:
    st.markdown('<div class="panel-title">输入区</div>', unsafe_allow_html=True)

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
                    f"</div>",
                    unsafe_allow_html=True,
                )
        except Exception as e:
            st.error(f"文件解析失败：{e}")
            df_preview = None

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    st.markdown('<div class="panel-title panel-title--sub">文件列表</div>', unsafe_allow_html=True)

    if uploaded_file is not None:
        size_kb = round(len(uploaded_file.getvalue()) / 1024, 1)
        st.markdown(
            f'<div class="file-list-item">'
            f'<span class="file-icon">📄</span>'
            f'<span class="file-name">{html_lib.escape(uploaded_file.name)}</span>'
            f'<span class="file-size">{size_kb} KB</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("暂无文件，请在上方上传")

    st.caption("未来将支持从已有知识库导入文件夹")
    return uploaded_file, df_preview


def _render_param_control(key: str, spec: dict) -> object:
    param_type = spec.get("type", "str")
    label = spec.get("label", key)
    desc = spec.get("description", "")
    default = spec.get("default", "")

    if param_type == "int":
        value = st.number_input(
            label,
            min_value=spec.get("min", 1),
            max_value=spec.get("max", 100),
            value=default,
            help=desc,
        )
        st.markdown(
            f'<div class="param-feedback">'
            f'<span class="feedback-label">当前值</span>'
            f'<span class="feedback-value">{value}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        return value

    if param_type == "select":
        options = spec.get("options", [])
        idx = options.index(default) if default in options else 0
        value = st.selectbox(label, options, index=idx, help=desc)
        st.markdown(
            f'<div class="param-feedback">'
            f'<span class="feedback-label">已选择</span>'
            f'<span class="feedback-value">{value}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        return value

    if key == "keywords":
        st.markdown(f"**{label}**")
        st.caption("用英文分号 ; 分隔多个关键词（注意不要用中文分号 ；）")
        value = st.text_input(
            label,
            value=default,
            help=desc,
            placeholder="例如：退款;发票;会员权益;配送",
            label_visibility="collapsed",
        )

        if value.strip():
            tags = [
                t.strip()
                for t in value.replace("，", ";").replace(",", ";").split(";")
                if t.strip()
            ]
            if tags:
                tags_html = "".join(f'<span class="keyword-tag">{html_lib.escape(t)}</span>' for t in tags)
                st.markdown(f'<div class="keyword-tags">{tags_html}</div>', unsafe_allow_html=True)
                st.caption(f"已添加 {len(tags)} 个关键词")
        return value

    return st.text_input(label, value=default, help=desc)


def _render_config_panel(uploaded_file: object | None, df_preview: pd.DataFrame | None, has_key: bool):
    st.markdown('<div class="panel-title">优化器配置</div>', unsafe_allow_html=True)

    all_opts = _build_agent_options()
    opt_labels = [
        f'{o["icon"]}  {o["name"]}' + ("  ·  即将上线" if o["is_placeholder"] else "")
        for o in all_opts
    ]

    chosen_label = st.selectbox("选择优化方式", opt_labels)
    chosen = all_opts[opt_labels.index(chosen_label)]

    if chosen["is_placeholder"]:
        st.session_state.selected_agent_id = None
        st.markdown(
            f'<div class="selected-agent-card placeholder">'
            f'<div class="sac-icon">{chosen["icon"]}</div>'
            f'<div class="sac-body">'
            f'<div class="sac-title">{chosen["name"]}</div>'
            f'<div class="sac-desc">{chosen["desc"]}</div>'
            f'<span class="coming-soon-badge">即将上线</span>'
            f"</div></div>",
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
            f"</div></div>",
            unsafe_allow_html=True,
        )

    user_params: dict = {}
    selected_agent = None
    if st.session_state.get("selected_agent_id"):
        selected_agent = registry.get(st.session_state.selected_agent_id)

    if selected_agent:
        st.divider()
        st.markdown(f"**参数配置 · {selected_agent.name}**")
        for key, spec in selected_agent.params_schema.items():
            user_params[key] = _render_param_control(key, spec)

    st.divider()
    can_execute = (
        uploaded_file is not None
        and df_preview is not None
        and selected_agent is not None
        and has_key
    )

    if not can_execute:
        hints: list[str] = []
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

    return selected_agent, user_params, can_execute, execute_clicked


def _execute_if_needed(
    execute_clicked: bool,
    can_execute: bool,
    selected_agent,
    df_preview: pd.DataFrame | None,
    user_params: dict,
) -> None:
    if not (execute_clicked and can_execute and selected_agent and df_preview is not None):
        return

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
        progress_bar.progress(60, text="正在生成结果...")
        progress_bar.progress(100, text="执行完成")

    st.session_state.execution_response = response


def _build_mock_response(mode: str):
    if mode == "空态":
        return None

    if mode == "失败态":
        return SimpleNamespace(
            success=False,
            stage="演示",
            validation_errors=["示例：缺少必要列 A"],
            error="示例：文件校验未通过，请检查模板格式",
        )

    demo_df = pd.DataFrame(
        {
            "Q": ["怎么申请退款？", "发票如何开具？", "会员有效期多久？"],
            "A": ["进入订单页申请", "在订单详情提交", "默认一年"],
            "扩展问题": [
                "如何发起退款流程？ || 退款要在哪里申请？",
                "开发票在哪操作？ || 发票抬头怎么填写？",
                "会员时长是多久？ || 会员期限怎么算？",
            ],
        }
    )

    summary = {
        "total": 3,
        "success": 3,
        "failed": 0,
        "elapsed_seconds": 1.2,
        "error_details": [],
    }
    result = SubAgentResult(
        success=True,
        output_df=demo_df,
        summary=summary,
        diff_items=[
            DiffItem(
                original_q="怎么申请退款？",
                expanded_qs=["如何发起退款流程？", "退款要在哪里申请？"],
            ),
            DiffItem(
                original_q="发票如何开具？",
                expanded_qs=["开发票在哪操作？", "发票抬头怎么填写？"],
            ),
        ],
    )
    return SimpleNamespace(
        success=True,
        stage="完成",
        validation_errors=None,
        error=None,
        result=result,
    )


def _resolve_output_response(real_response):
    mode = st.selectbox(
        "状态演示",
        ["自动", "空态", "失败态", "成功态"],
        help="用于快速复现输出区状态稿。自动模式下展示真实执行结果。",
        key="output_state_mode",
    )
    if mode == "自动":
        return real_response
    return _build_mock_response(mode)


def _render_summary(summary: dict) -> None:
    m1, m2 = st.columns(2)
    with m1:
        st.metric("总处理", summary.get("total", 0))
        st.metric("失败", summary.get("failed", 0))
    with m2:
        st.metric("成功", summary.get("success", 0))
        st.metric("耗时", f"{summary.get('elapsed_seconds', 0)}s")


def _render_diff(diff_items: list[DiffItem]) -> None:
    has_diff = any(item.expanded_qs for item in diff_items)
    if not has_diff:
        st.info("暂无差异数据")
        return

    diff_html_parts = []
    for i, item in enumerate(diff_items):
        if not item.expanded_qs:
            continue
        escaped_q = html_lib.escape(item.original_q)
        expanded_html = "".join(
            f'<div class="expanded-q">{html_lib.escape(q)}</div>' for q in item.expanded_qs
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
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_output_panel() -> None:
    st.markdown('<div class="panel-title">执行结果</div>', unsafe_allow_html=True)
    response = _resolve_output_response(st.session_state.get("execution_response"))

    if response is None:
        st.markdown(
            '<div class="output-placeholder">'
            '<div class="placeholder-icon">📋</div>'
            '<div class="placeholder-title">等待执行</div>'
            '<div class="placeholder-text">执行优化后，结果将展示在这里</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    if not response.success:
        st.error(f"执行失败（阶段：{response.stage}）")
        if response.validation_errors:
            with st.expander("查看校验错误", expanded=True):
                for err in response.validation_errors:
                    st.warning(err)
        if response.error:
            st.error(response.error)
        return

    result = response.result
    st.success("优化完成")

    st.markdown("**执行摘要**")
    summary = result.summary
    _render_summary(summary)

    st.markdown("**差异对比**")
    st.caption("原始问题 vs 扩展变体")
    _render_diff(result.diff_items)

    st.markdown("**完整结果**")
    if result.output_df is not None:
        st.markdown(
            f'<div class="scroll-panel scroll-panel--result">'
            f'{_df_to_html_table(result.output_df)}'
            f"</div>",
            unsafe_allow_html=True,
        )

    if result.output_df is not None:
        excel_bytes = df_to_excel_bytes(result.output_df)
        st.download_button(
            label="下载优化后 Excel",
            data=excel_bytes,
            file_name="优化结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    if summary.get("error_details"):
        show_errors = st.toggle("查看失败明细", value=False, key="error_toggle")
        if show_errors:
            for detail in summary["error_details"]:
                st.warning(detail)


def main() -> None:
    _inject_css()
    _init_session_state()

    has_key = _has_valid_api_key()
    _render_global_top_tabs()

    app_side, app_main = st.columns([0.86, 4.14], gap="small")

    with app_side:
        st.markdown(_build_global_sidebar_html(), unsafe_allow_html=True)
        st.markdown('<div class="side-resizer">‹</div>', unsafe_allow_html=True)

    with app_main:
        with st.container(key="workspace_shell"):
            _render_workspace_header()
            _render_step_bar()

            with st.container(key="workspace_main_cols"):
                col_left, col_center, col_right = st.columns([1, 1.6, 1.4], gap="large")

                with col_left:
                    uploaded_file, df_preview = _render_input_panel()

                with col_center:
                    selected_agent, user_params, can_execute, execute_clicked = _render_config_panel(
                        uploaded_file=uploaded_file,
                        df_preview=df_preview,
                        has_key=has_key,
                    )
                    _execute_if_needed(
                        execute_clicked=execute_clicked,
                        can_execute=can_execute,
                        selected_agent=selected_agent,
                        df_preview=df_preview,
                        user_params=user_params,
                    )

                with col_right:
                    _render_output_panel()

            _render_footer_hint()


if __name__ == "__main__":
    main()
