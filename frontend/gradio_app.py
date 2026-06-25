"""Gradio demo UI for the AI Customer Support Agent.

Submits a ticket directly through the LangGraph agent (no FastAPI server
required) and renders the full structured output across tabbed panels.

Run:
    python frontend/gradio_app.py

Access at: http://localhost:7860
"""
from __future__ import annotations

import time
import uuid

import gradio as gr

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

_CSS = """
/* ---- global ----------------------------------------------------------- */
.gradio-container {
    max-width: 1280px !important;
    margin: 0 auto !important;
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}

/* ---- header ----------------------------------------------------------- */
#app-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    border-radius: 14px;
    padding: 2rem 2.5rem 1.75rem;
    margin-bottom: 1.25rem;
}
#app-header h1 {
    color: #ffffff !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    margin: 0 0 0.5rem 0 !important;
    letter-spacing: -0.01em !important;
}
#app-header p {
    color: #bfdbfe !important;
    margin: 0 !important;
    font-size: 0.95rem !important;
    line-height: 1.5 !important;
}

/* ---- submit panel ----------------------------------------------------- */
#submit-panel {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 1.4rem !important;
}

/* ---- section divider labels ------------------------------------------- */
.gr-markdown.panel-label p {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: #94a3b8 !important;
    margin: 0 0 0.75rem 0 !important;
    padding-bottom: 0.5rem !important;
    border-bottom: 1px solid #e2e8f0 !important;
}

/* ---- analyze button --------------------------------------------------- */
#analyze-btn {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.02em !important;
    box-shadow: 0 2px 6px rgba(37,99,235,0.35) !important;
    transition: box-shadow 0.15s ease, opacity 0.15s ease !important;
    color: #ffffff !important;
}
#analyze-btn:hover {
    box-shadow: 0 4px 12px rgba(37,99,235,0.45) !important;
    opacity: 0.95 !important;
}

/* ---- output column ---------------------------------------------------- */
#output-col {
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* ---- tabs ------------------------------------------------------------- */
#output-tabs .tab-nav {
    background: #f1f5f9 !important;
    border-bottom: 1px solid #e2e8f0 !important;
    padding: 0.5rem 0.75rem 0 !important;
    gap: 0.25rem !important;
    flex-wrap: wrap !important;
}
#output-tabs .tab-nav button {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 0.4rem 0.85rem !important;
    border-radius: 6px 6px 0 0 !important;
    color: #64748b !important;
    border: 1px solid transparent !important;
    transition: background 0.1s ease !important;
}
#output-tabs .tab-nav button.selected {
    background: #ffffff !important;
    color: #2563eb !important;
    font-weight: 600 !important;
    border-color: #e2e8f0 !important;
    border-bottom-color: #ffffff !important;
}
#output-tabs > .tabitem {
    padding: 1.25rem 1.5rem !important;
    background: #ffffff !important;
    min-height: 220px !important;
}

/* ---- output markdown areas -------------------------------------------- */
.output-area .prose table {
    width: 100% !important;
    border-collapse: collapse !important;
    font-size: 0.9rem !important;
}
.output-area .prose td, .output-area .prose th {
    padding: 0.6rem 0.85rem !important;
}

/* ---- examples --------------------------------------------------------- */
.gr-samples-table {
    font-size: 0.82rem !important;
}

/* ---- footer ----------------------------------------------------------- */
#app-footer p {
    text-align: center !important;
    color: #94a3b8 !important;
    font-size: 0.78rem !important;
    margin: 0 !important;
}
"""

# ---------------------------------------------------------------------------
# Graph -- lazy-loaded so the UI starts instantly
# ---------------------------------------------------------------------------

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from agents.graph import build_graph  # noqa: PLC0415
        _graph = build_graph()
    return _graph


def _initial_state(ticket) -> dict:
    return {
        "ticket": ticket,
        "customer_history": [],
        "similar_cases": [],
        "classification": "",
        "confidence_score": 0.0,
        "retrieved_policies": [],
        "draft_response": "",
        "routing_decision": "",
        "escalation_required": False,
        "escalation_reason": "",
        "escalation_payload": {},
        "summary": "",
        "audit_log": {},
        "langfuse_trace_id": "",
        "messages": [],
    }


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _badge(text: str, color: str = "blue") -> str:
    """Return an inline HTML badge span."""
    palettes = {
        "green":  ("color:#166534", "background:#dcfce7"),
        "red":    ("color:#991b1b", "background:#fee2e2"),
        "blue":   ("color:#1e40af", "background:#dbeafe"),
        "orange": ("color:#9a3412", "background:#ffedd5"),
        "gray":   ("color:#374151", "background:#f3f4f6"),
    }
    fg, bg = palettes.get(color, palettes["blue"])
    return (
        f'<span style="{bg};{fg};padding:2px 10px;border-radius:9999px;'
        f'font-weight:600;font-size:0.82rem;display:inline-block">{text}</span>'
    )


def _conf_bar(confidence: float) -> str:
    """Return an HTML progress bar for confidence."""
    pct = int(confidence * 100)
    bar_color = "#16a34a" if confidence >= 0.8 else "#d97706" if confidence >= 0.5 else "#dc2626"
    return (
        f'<div style="display:flex;align-items:center;gap:10px">'
        f'<div style="width:130px;height:8px;background:#e5e7eb;border-radius:4px;overflow:hidden">'
        f'<div style="width:{pct}%;height:100%;background:{bar_color};border-radius:4px;'
        f'transition:width 0.4s ease"></div></div>'
        f'<span style="font-weight:700;color:{bar_color}">{pct}%</span>'
        f'</div>'
    )


def _kv_table(rows: list[tuple[str, str]], striped: bool = True) -> str:
    """Render a clean key-value HTML table."""
    html = '<table style="width:100%;border-collapse:collapse;font-size:0.9rem">'
    for i, (key, val) in enumerate(rows):
        bg = ' style="background:#f9fafb"' if striped and i % 2 == 1 else ""
        html += (
            f'<tr{bg}>'
            f'<td style="padding:0.6rem 1rem;border-bottom:1px solid #f1f5f9;'
            f'color:#6b7280;font-weight:600;width:160px;white-space:nowrap">{key}</td>'
            f'<td style="padding:0.6rem 1rem;border-bottom:1px solid #f1f5f9">{val}</td>'
            f'</tr>'
        )
    html += "</table>"
    return html


def _section(title: str, content: str) -> str:
    """Wrap content in a labelled section card."""
    return (
        f'<div style="margin-bottom:1.25rem">'
        f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.1em;color:#94a3b8;margin:0 0 0.6rem 0;padding-bottom:0.4rem;'
        f'border-bottom:1px solid #e2e8f0">{title}</p>'
        f'{content}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------

def analyze_ticket(
    ticket_id: str,
    customer_id: str,
    subject: str,
    message: str,
    channel: str,
    priority: str,
) -> tuple:
    """Run the LangGraph agent and return formatted outputs for each UI panel."""
    if not subject.strip() or not message.strip():
        err = (
            '<div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;'
            'padding:1rem 1.25rem;color:#92400e;font-weight:500">'
            'Subject and Message are required fields.</div>'
        )
        return err, "", "", "", "", "", ""

    from api.schemas.ticket_schema import TicketInput  # noqa: PLC0415
    from config.settings import settings               # noqa: PLC0415

    tid = ticket_id.strip() or f"TKT-{int(time.time())}"
    cid = customer_id.strip() or f"CUST-DEMO-{uuid.uuid4().hex[:6].upper()}"

    ticket = TicketInput(
        ticket_id=tid,
        customer_id=cid,
        subject=subject.strip(),
        message=message.strip(),
        channel=channel,
        priority=priority,
    )

    try:
        result: dict = _get_graph().invoke(_initial_state(ticket))
    except Exception as exc:  # noqa: BLE001
        err = (
            '<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;'
            f'padding:1rem 1.25rem;color:#991b1b;font-weight:500">Agent error: {exc}</div>'
        )
        return err, "", "", "", "", "", ""

    # -- Extract state fields ------------------------------------------------
    classification = result.get("classification") or "--"
    confidence     = float(result.get("confidence_score") or 0.0)
    response_text  = result.get("draft_response") or "--"
    routing        = result.get("routing_decision") or "--"
    escalated      = bool(result.get("escalation_required"))
    esc_reason     = result.get("escalation_reason") or ""
    esc_payload    = result.get("escalation_payload") or {}
    summary_text   = result.get("summary") or "--"
    trace_id       = result.get("langfuse_trace_id") or ""
    audit          = result.get("audit_log") or {}
    policies       = result.get("retrieved_policies") or []
    history        = result.get("customer_history") or []
    similar        = result.get("similar_cases") or []

    tokens = audit.get("total_tokens", 0)
    cost   = audit.get("total_cost_usd", 0.0)

    # -- 1. Decision panel ---------------------------------------------------
    esc_cell = (
        _badge("YES", "red") + f'&nbsp; <span style="color:#7f1d1d;font-size:0.87rem">{esc_reason}</span>'
        if escalated else _badge("NO", "green")
    )
    priority_color = {"urgent": "red", "high": "orange", "medium": "blue", "low": "gray"}.get(priority, "gray")

    rows = [
        ("Classification", f"<strong>{classification}</strong>"),
        ("Confidence",     _conf_bar(confidence)),
        ("Routing",        f"<strong>{routing}</strong>"),
        ("Escalated",      esc_cell),
        ("Priority",       _badge(priority, priority_color)),
        ("Channel",        f'<code style="background:#f1f5f9;padding:1px 6px;border-radius:4px">{channel}</code>'),
        ("Tokens Used",    str(tokens)),
        ("Est. Cost",      f"${cost:.5f}"),
        ("Ticket ID",      f'<code style="background:#f1f5f9;padding:1px 6px;border-radius:4px">{tid}</code>'),
        ("Customer ID",    f'<code style="background:#f1f5f9;padding:1px 6px;border-radius:4px">{cid}</code>'),
    ]
    decision_md = _kv_table(rows)

    if escalated and esc_payload:
        esc_rows = [(k, str(v)) for k, v in esc_payload.items()]
        decision_md += _section("Escalation Context", _kv_table(esc_rows))

    # -- 2. Response panel ---------------------------------------------------
    response_md = (
        f'<div style="background:#f8fafc;border-left:4px solid #2563eb;border-radius:0 8px 8px 0;'
        f'padding:1.25rem 1.5rem;line-height:1.7;font-size:0.93rem;color:#1e293b;white-space:pre-wrap">'
        f'{response_text}</div>'
    )

    # -- 3. Summary panel ----------------------------------------------------
    summary_md = (
        f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;'
        f'padding:1rem 1.25rem;font-size:0.93rem;color:#14532d;line-height:1.6">'
        f'{summary_text}</div>'
    )

    # -- 4. Retrieved policies panel -----------------------------------------
    if policies:
        parts = []
        for i, chunk in enumerate(policies):
            parts.append(
                f'<div style="border:1px solid #e2e8f0;border-radius:8px;padding:1rem;margin-bottom:0.75rem">'
                f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;'
                f'color:#94a3b8;margin:0 0 0.5rem 0">Chunk {i + 1}</p>'
                f'<p style="margin:0;font-size:0.9rem;line-height:1.6;color:#374151">{chunk}</p>'
                f'</div>'
            )
        policies_md = "\n".join(parts)
    else:
        policies_md = '<p style="color:#94a3b8;font-style:italic">No policy chunks were retrieved for this ticket.</p>'

    # -- 5. Customer memory panel --------------------------------------------
    if history:
        header = (
            f'<p style="font-size:0.85rem;font-weight:600;color:#374151;margin:0 0 0.75rem 0">'
            f'{len(history)} prior ticket(s) found</p>'
        )
        th_style = 'style="padding:0.55rem 0.85rem;text-align:left;font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;background:#f8fafc;border-bottom:2px solid #e2e8f0"'
        td_style = 'style="padding:0.55rem 0.85rem;border-bottom:1px solid #f1f5f9;font-size:0.88rem"'
        table = (
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr>'
            f'<th {th_style}>Ticket</th><th {th_style}>Subject</th>'
            f'<th {th_style}>Classification</th><th {th_style}>Resolution</th><th {th_style}>Date</th>'
            f'</tr></thead><tbody>'
        )
        for t in history:
            table += (
                f'<tr>'
                f'<td {td_style}><code>{t.get("ticket_id","?")}</code></td>'
                f'<td {td_style}>{t.get("subject","?")}</td>'
                f'<td {td_style}>{t.get("classification","?")}</td>'
                f'<td {td_style}>{t.get("resolution", t.get("status","?"))}</td>'
                f'<td {td_style}>{(t.get("created_at") or "")[:10]}</td>'
                f'</tr>'
            )
        table += "</tbody></table>"
        memory_md = header + table
    else:
        memory_md = '<p style="color:#94a3b8;font-style:italic">No prior tickets found for this customer.</p>'

    # -- 6. Similar cases panel ----------------------------------------------
    if similar:
        header = (
            f'<p style="font-size:0.85rem;font-weight:600;color:#374151;margin:0 0 0.75rem 0">'
            f'{len(similar)} similar case(s) retrieved</p>'
        )
        th_style = 'style="padding:0.55rem 0.85rem;text-align:left;font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;background:#f8fafc;border-bottom:2px solid #e2e8f0"'
        td_style = 'style="padding:0.55rem 0.85rem;border-bottom:1px solid #f1f5f9;font-size:0.88rem"'
        table = (
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr>'
            f'<th {th_style}>Ticket</th><th {th_style}>Subject</th>'
            f'<th {th_style}>Classification</th><th {th_style}>Similarity</th>'
            f'</tr></thead><tbody>'
        )
        for c in similar:
            score    = float(c.get("similarity", c.get("score", 0.0)))
            score_pct = int(score * 100)
            score_color = "#16a34a" if score >= 0.8 else "#d97706" if score >= 0.5 else "#dc2626"
            score_cell = (
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<div style="width:60px;height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden">'
                f'<div style="width:{score_pct}%;height:100%;background:{score_color};border-radius:3px"></div></div>'
                f'<span style="font-size:0.82rem;font-weight:600;color:{score_color}">{score:.2f}</span></div>'
            )
            table += (
                f'<tr>'
                f'<td {td_style}><code>{c.get("ticket_id","?")}</code></td>'
                f'<td {td_style}>{c.get("subject", c.get("document","?"))[:80]}</td>'
                f'<td {td_style}>{c.get("classification","?")}</td>'
                f'<td {td_style}>{score_cell}</td>'
                f'</tr>'
            )
        table += "</tbody></table>"
        similar_md = header + table
    else:
        similar_md = '<p style="color:#94a3b8;font-style:italic">No similar cases retrieved from semantic memory.</p>'

    # -- 7. Langfuse trace panel ---------------------------------------------
    host = (getattr(settings, "langfuse_host", "") or "").rstrip("/")
    if trace_id and host:
        trace_url = f"{host}/traces/{trace_id}"
        trace_md  = (
            f'<div style="border:1px solid #e0e7ff;border-radius:10px;padding:1.25rem 1.5rem;background:#f5f3ff">'
            f'<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;'
            f'color:#7c3aed;margin:0 0 0.6rem 0">Langfuse Observability Trace</p>'
            f'<p style="margin:0 0 0.75rem 0">'
            f'<a href="{trace_url}" target="_blank" style="color:#4f46e5;font-weight:600;text-decoration:none">'
            f'Open trace: {trace_id}</a></p>'
            f'<p style="margin:0;font-size:0.85rem;color:#6b7280">Includes LLM calls, tool invocations, '
            f'token counts, latency breakdown, and cost per node.</p>'
            f'</div>'
        )
    else:
        trace_md = (
            '<div style="background:#f8fafc;border:1px dashed #cbd5e1;border-radius:8px;'
            'padding:1rem 1.25rem;color:#94a3b8;font-style:italic;font-size:0.9rem">'
            'Langfuse tracing not configured or no trace ID was returned by the agent.'
            '</div>'
        )

    return decision_md, response_md, summary_md, policies_md, memory_md, similar_md, trace_md


# ---------------------------------------------------------------------------
# Gradio UI layout
# ---------------------------------------------------------------------------

CHANNELS   = ["email", "chat", "phone", "api"]
PRIORITIES = ["low", "medium", "high", "urgent"]

_EXAMPLES = [
    [
        "", "",
        "Charged twice this month",
        "I see two identical $49.99 charges on my January statement. Please investigate and refund the duplicate.",
        "email", "medium",
    ],
    [
        "", "",
        "Cannot log into my account",
        "My password reset email never arrives. I have tried three times over two days. I need access urgently.",
        "chat", "high",
    ],
    [
        "", "",
        "Cancel subscription and request refund",
        "Please cancel my Premium plan immediately and refund the unused portion of this month. Order #88234.",
        "email", "low",
    ],
    [
        "", "",
        "API integration broken after update",
        "Since yesterday our webhook endpoint returns 500. Our team is blocked. This is a production outage.",
        "api", "urgent",
    ],
]

with gr.Blocks(title="AI Customer Support Agent") as demo:

    gr.Markdown(
        "<h1>AI Customer Support Agent</h1>"
        "<p>Submit a support ticket and watch the LangGraph agent <strong>classify</strong>, "
        "<strong>retrieve context</strong>, <strong>draft a response</strong>, "
        "<strong>route</strong> it, and optionally <strong>escalate</strong> — "
        "with full Langfuse traceability.</p>",
        elem_id="app-header",
    )

    with gr.Row(equal_height=False):

        # Left: input form
        with gr.Column(scale=1, min_width=300, elem_id="submit-panel"):
            gr.Markdown("SUBMIT TICKET", elem_classes=["panel-label"])
            inp_ticket_id   = gr.Textbox(label="Ticket ID",   placeholder="Auto-generated if blank", container=True)
            inp_customer_id = gr.Textbox(label="Customer ID", placeholder="Auto-generated if blank", container=True)
            inp_subject     = gr.Textbox(label="Subject *",   placeholder="Brief description of the issue", container=True)
            inp_message     = gr.Textbox(label="Message *",   lines=5,
                                         placeholder="Describe the issue in detail...", container=True)
            with gr.Row():
                inp_channel  = gr.Dropdown(CHANNELS,   label="Channel",  value="email")
                inp_priority = gr.Dropdown(PRIORITIES, label="Priority", value="medium")
            btn_submit = gr.Button("Analyze Ticket", variant="primary", size="lg", elem_id="analyze-btn")

            gr.Examples(
                examples=_EXAMPLES,
                inputs=[inp_ticket_id, inp_customer_id, inp_subject, inp_message, inp_channel, inp_priority],
                label="Quick examples",
            )

        # Right: tabbed output
        with gr.Column(scale=2, elem_id="output-col"):
            with gr.Tabs(elem_id="output-tabs"):
                with gr.TabItem("Decision"):
                    out_decision = gr.HTML(
                        '<p style="color:#94a3b8;font-style:italic;padding:0.5rem 0">Submit a ticket to see the agent decision.</p>'
                    )

                with gr.TabItem("Response"):
                    out_response = gr.HTML(
                        '<p style="color:#94a3b8;font-style:italic;padding:0.5rem 0">Submit a ticket to see the drafted customer response.</p>'
                    )

                with gr.TabItem("Summary"):
                    out_summary = gr.HTML(
                        '<p style="color:#94a3b8;font-style:italic;padding:0.5rem 0">Submit a ticket to see the one-line summary.</p>'
                    )

                with gr.TabItem("Retrieved Policies"):
                    out_policies = gr.HTML(
                        '<p style="color:#94a3b8;font-style:italic;padding:0.5rem 0">Submit a ticket to see retrieved policy chunks.</p>'
                    )

                with gr.TabItem("Customer Memory"):
                    out_memory = gr.HTML(
                        '<p style="color:#94a3b8;font-style:italic;padding:0.5rem 0">Submit a ticket to see this customer\'s ticket history.</p>'
                    )

                with gr.TabItem("Similar Cases"):
                    out_similar = gr.HTML(
                        '<p style="color:#94a3b8;font-style:italic;padding:0.5rem 0">Submit a ticket to see semantically similar past cases.</p>'
                    )

                with gr.TabItem("Langfuse Trace"):
                    out_trace = gr.HTML(
                        '<p style="color:#94a3b8;font-style:italic;padding:0.5rem 0">Submit a ticket to see the observability trace link.</p>'
                    )

    _inputs  = [inp_ticket_id, inp_customer_id, inp_subject, inp_message, inp_channel, inp_priority]
    _outputs = [out_decision, out_response, out_summary, out_policies, out_memory, out_similar, out_trace]

    btn_submit.click(fn=analyze_ticket, inputs=_inputs, outputs=_outputs)

    gr.Markdown(
        "Powered by LangGraph &nbsp;·&nbsp; ChromaDB RAG &nbsp;·&nbsp; OpenAI GPT-4o-mini "
        "&nbsp;·&nbsp; SQLAlchemy &nbsp;·&nbsp; Langfuse",
        elem_id="app-footer",
    )


if __name__ == "__main__":
    demo.launch(server_port=7860, share=False, theme=gr.themes.Soft(), css=_CSS)
