import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# Theme Colors (Dark Enterprise Palette matching web UI)
BG_COLOR = RGBColor(15, 23, 42)         # #0f172a (Slate 900)
CARD_BG = RGBColor(30, 41, 59)          # #1e293b (Slate 800)
ACCENT_CYAN = RGBColor(56, 189, 248)    # #38bdf8 (Cyan 400)
ACCENT_BLUE = RGBColor(59, 130, 246)    # #3b82f6 (Blue 500)
ACCENT_GREEN = RGBColor(52, 211, 153)   # #34d399 (Emerald 400)
ACCENT_AMBER = RGBColor(251, 191, 36)   # #fbbf24 (Amber 400)
ACCENT_ROSE = RGBColor(248, 113, 113)   # #f87171 (Rose 400)
TEXT_WHITE = RGBColor(248, 250, 252)    # #f8fafc
TEXT_MUTED = RGBColor(148, 163, 184)    # #94a3b8
CODE_TEXT = RGBColor(103, 232, 249)     # #67e8f9


def set_slide_background(slide):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = BG_COLOR


def add_header(slide, tag_text, title_text):
    set_slide_background(slide)
    
    # Tag
    tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = True
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = tag_text.upper()
    p_tag.font.size = Pt(10)
    p_tag.font.bold = True
    p_tag.font.color.rgb = ACCENT_CYAN
    
    # Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.8))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.size = Pt(24)
    p_title.font.bold = True
    p_title.font.color.rgb = TEXT_WHITE


def add_card(slide, left, top, width, height, title, content_bullets, border_color=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD_BG
    shape.line.color.rgb = border_color if border_color else RGBColor(51, 65, 85)
    shape.line.width = Pt(1.5)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.2)
    tf.margin_right = Inches(0.2)
    tf.margin_top = Inches(0.2)
    tf.margin_bottom = Inches(0.2)

    # Card Title
    p_title = tf.paragraphs[0]
    p_title.text = title
    p_title.font.size = Pt(14)
    p_title.font.bold = True
    p_title.font.color.rgb = border_color if border_color else ACCENT_CYAN

    # Bullets
    for item in content_bullets:
        p = tf.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_WHITE


def generate_presentation_bytes() -> bytes:
    prs = Presentation()
    # 16:9 Widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_slide_layout = prs.slide_layouts[6]

    # ==================== SLIDE 1: Title & Executive Overview ====================
    s1 = prs.slides.add_slide(blank_slide_layout)
    set_slide_background(s1)
    
    tag = s1.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(11.7), Inches(0.4))
    p = tag.text_frame.paragraphs[0]
    p.text = "NUTANIX HACKATHON • PROBLEM STATEMENT 4"
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN

    title = s1.shapes.add_textbox(Inches(0.8), Inches(1.7), Inches(11.7), Inches(1.5))
    p = title.text_frame.paragraphs[0]
    p.text = "Enterprise-Grade Agentic Workflow Orchestrator"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = TEXT_WHITE

    sub = s1.shapes.add_textbox(Inches(0.8), Inches(3.2), Inches(11.7), Inches(1.0))
    p = sub.text_frame.paragraphs[0]
    p.text = "An Asynchronous, Parallel DAG Execution Engine with Native Gemini 3.6 Flash AI Reasoning, Safe AST Conditional Routing, and Real-Time Visual Telemetry."
    p.font.size = Pt(16)
    p.font.color.rgb = TEXT_MUTED

    add_card(s1, Inches(0.8), Inches(4.5), Inches(2.7), Inches(1.8), "Async Parallel DAG", ["Kahn's upfront validation", "True asyncio concurrency", "Non-blocking subprocesses"], ACCENT_CYAN)
    add_card(s1, Inches(3.8), Inches(4.5), Inches(2.7), Inches(1.8), "Gemini 3.6 Flash AI", ["Native log analysis", "Structured JSON mode", "Autonomous triage"], ACCENT_BLUE)
    add_card(s1, Inches(6.8), Inches(4.5), Inches(2.7), Inches(1.8), "Safe AST Routing", ["Python AST evaluation", "Zero unsafe eval()", "Selective branch skips"], ACCENT_GREEN)
    add_card(s1, Inches(9.8), Inches(4.5), Inches(2.7), Inches(1.8), "Live Web Dashboard", ["vis-network canvas", "Live node polling", "Interactive Inspector"], ACCENT_AMBER)

    footer = s1.shapes.add_textbox(Inches(0.8), Inches(6.6), Inches(11.7), Inches(0.4))
    p = footer.text_frame.paragraphs[0]
    p.text = "Authors: Sathiyan Anand Sinha & Pranav Shalya  |  Python 3.10+ • FastAPI • asyncio • vis-network"
    p.font.size = Pt(11)
    p.font.color.rgb = TEXT_MUTED

    # ==================== SLIDE 2: Real-world Problem & Industry Need ====================
    s2 = prs.slides.add_slide(blank_slide_layout)
    add_header(s2, "The Challenge", "Why Traditional Infrastructure Automation Fails")
    add_card(s2, Inches(0.8), Inches(1.8), Inches(5.6), Inches(2.2), "Brittle Linear Execution", [
        "Sequential bash scripts execute line-by-line",
        "Independent tasks wait unnecessarily, blocking event loops",
        "High incident resolution time during cloud outages"
    ], ACCENT_ROSE)
    add_card(s2, Inches(6.8), Inches(1.8), Inches(5.6), Inches(2.2), "Cascading Total Failures", [
        "Failure in one non-critical task crashes the entire runbook",
        "No concept of dependency subgraphs or selective skipping",
        "Lack of isolated survival for independent parallel branches"
    ], ACCENT_ROSE)
    add_card(s2, Inches(0.8), Inches(4.3), Inches(5.6), Inches(2.2), "Zero Real-Time Intelligence", [
        "Static regex cannot parse unstructured logs or stack traces",
        "Rigid hard-coded if/else rules fail on unseen crash patterns",
        "Requires manual human intervention at 2 AM for basic triage"
    ], ACCENT_ROSE)
    add_card(s2, Inches(6.8), Inches(4.3), Inches(5.6), Inches(2.2), "Fragile Glue Code & Temp Files", [
        "Inter-step data passing relies on temporary disk files",
        "Fragile sed, awk, and grep scripts break across OS environments",
        "No structured runtime context store or variable interpolation"
    ], ACCENT_ROSE)

    # ==================== SLIDE 3: System Architecture ====================
    s3 = prs.slides.add_slide(blank_slide_layout)
    add_header(s3, "System Architecture", "End-to-End Orchestrator Pipeline")
    add_card(s3, Inches(0.8), Inches(1.8), Inches(3.6), Inches(4.8), "1. Ingestion & Validation", [
        "POST /workflows accepts JSON DAG",
        "Kahn's Algorithm runs upfront",
        "Validates zero cycles & duplicate IDs",
        "Immediate 202 Accepted response",
        "Dispatches UUID to BackgroundTasks"
    ], ACCENT_CYAN)
    add_card(s3, Inches(4.8), Inches(1.8), Inches(3.6), Inches(4.8), "2. Async Parallel Engine", [
        "Reactive in-degree resolution loop",
        "Ready nodes launch via asyncio.create_task",
        "Threaded subprocesses (asyncio.to_thread)",
        "Global runtime context (${{ steps }})",
        "AST evaluation & failure propagation"
    ], ACCENT_BLUE)
    add_card(s3, Inches(8.8), Inches(1.8), Inches(3.6), Inches(4.8), "3. Telemetry & Web UI", [
        "Non-blocking polling GET /workflows/{id}",
        "Real-time vis-network DAG canvas",
        "Live node state color transitions",
        "Interactive node inspector",
        "Live runtime context viewer"
    ], ACCENT_GREEN)

    # ==================== SLIDE 4: Async Parallel DAG Execution ====================
    s4 = prs.slides.add_slide(blank_slide_layout)
    add_header(s4, "Concurrency Core", "Asynchronous Parallel DAG Scheduling")
    add_card(s4, Inches(0.8), Inches(1.8), Inches(5.6), Inches(2.2), "Kahn's Algorithm Graph Validation", [
        "Computes in-degree for every step in O(V + E) time",
        "Deterministically catches cycles and missing dependencies",
        "Guarantees graph validity before any step execution"
    ], ACCENT_CYAN)
    add_card(s4, Inches(6.8), Inches(1.8), Inches(5.6), Inches(2.2), "Dynamic Parallel Fork-Join", [
        "Zero in-degree nodes launch concurrently via asyncio",
        "Multiple branches execute in parallel simultaneously",
        "Join nodes automatically wait for all dependencies"
    ], ACCENT_CYAN)
    add_card(s4, Inches(0.8), Inches(4.3), Inches(5.6), Inches(2.4), "Non-Blocking Subprocess Dispatch", [
        "Wrapped via asyncio.to_thread(subprocess.run, ...)",
        "Sidesteps Windows Uvicorn loop limitations",
        "Server event loop remains completely responsive during heavy shell jobs"
    ], ACCENT_CYAN)
    add_card(s4, Inches(6.8), Inches(4.3), Inches(5.6), Inches(2.4), "Reactive Task Completion", [
        "asyncio.wait(return_when=FIRST_COMPLETED)",
        "Instantly unlocks downstream dependents on task completion",
        "Eliminates polling delays inside the execution loop"
    ], ACCENT_CYAN)

    # ==================== SLIDE 5: State Machine & Failure Isolation ====================
    s5 = prs.slides.add_slide(blank_slide_layout)
    add_header(s5, "Fault Tolerance", "Granular 5-State Lifecycle & Failure Isolation")
    add_card(s5, Inches(0.8), Inches(1.8), Inches(2.1), Inches(1.8), "PENDING", ["Blue color", "Awaiting upstream dependencies"], ACCENT_BLUE)
    add_card(s5, Inches(3.2), Inches(1.8), Inches(2.1), Inches(1.8), "RUNNING", ["Amber pulsing", "Active async execution"], ACCENT_AMBER)
    add_card(s5, Inches(5.6), Inches(1.8), Inches(2.1), Inches(1.8), "SUCCESS", ["Green color", "Outputs placed in context"], ACCENT_GREEN)
    add_card(s5, Inches(8.0), Inches(1.8), Inches(2.1), Inches(1.8), "FAILED", ["Red color", "Error captured & logged"], ACCENT_ROSE)
    add_card(s5, Inches(10.4), Inches(1.8), Inches(2.1), Inches(1.8), "SKIPPED", ["Slate dashed", "Branch deactivated"], TEXT_MUTED)

    add_card(s5, Inches(0.8), Inches(4.0), Inches(5.6), Inches(2.8), "Recursive Subgraph Deactivation", [
        "BFS traversal (_mark_descendants_skipped) cascades skips only to dependent children",
        "Every skipped step receives a clear diagnostic skip reason",
        "Prevents unexecutable downstream steps from hanging"
    ], ACCENT_ROSE)
    add_card(s5, Inches(6.8), Inches(4.0), Inches(5.6), Inches(2.8), "Independent Branch Survival", [
        "Isolated parallel branches continue executing to SUCCESS",
        "A broken database step will not kill an independent telemetry service",
        "Workflow reaches COMPLETED if all active branches succeed"
    ], ACCENT_GREEN)

    # ==================== SLIDE 6: Dynamic Context Engine ====================
    s6 = prs.slides.add_slide(blank_slide_layout)
    add_header(s6, "Data Flow", "Dynamic Context Engine & Variable Passing")
    add_card(s6, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8), "Inter-Step Context Store", [
        "Global runtime dictionary context['steps'][step_id]",
        "Captures stdout, stderr, exit codes, status_code, JSON responses",
        "Eliminates disk I/O and temporary environment variables",
        "Deep dot/bracket property traversal: resolve_path()",
        "Clean KeyError diagnostics if upstream property is missing"
    ], ACCENT_CYAN)
    add_card(s6, Inches(6.8), Inches(1.8), Inches(5.6), Inches(4.8), "Template Interpolation Syntax", [
        "${{ steps.FetchLog.stdout }} -> String output from shell",
        "${{ steps.FetchUser.response.args.token }} -> Nested REST JSON",
        "${{ steps.AiTriage.response.severity }} -> AI extracted property",
        "${{ steps.JQFilter.response[0].id }} -> Array index from JQ",
        "Safe string substitution + full object preservation"
    ], ACCENT_BLUE)

    # ==================== SLIDE 7: Core Innovation - AI Reasoning Node ====================
    s7 = prs.slides.add_slide(blank_slide_layout)
    add_header(s7, "Core Innovation", "Native AI Reasoning Node (type: 'ai')")
    add_card(s7, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8), "Gemini 3.6 Flash Integration", [
        "Asynchronous HTTP POST via httpx.AsyncClient",
        "Direct connection to Google Gemini 3.6 Flash endpoint",
        "Analyzes unstructured incident logs in real time",
        "Produces structured root cause analysis & action plans",
        "Fallback model parameter support in step configuration"
    ], ACCENT_BLUE)
    add_card(s7, Inches(6.8), Inches(1.8), Inches(5.6), Inches(4.8), "Strict JSON Mode & Schema Enforcement", [
        "response_format: 'json' sets application/json MIME type",
        "Automatic markdown fence stripping (```json ... ```)",
        "Validates JSON decoding before injecting into context",
        "Allows downstream condition nodes to route decisions cleanly",
        "Autonomous bridging from unstructured logs to structured actions"
    ], ACCENT_GREEN)

    # ==================== SLIDE 8: Data Transformation - JQ Node ====================
    s8 = prs.slides.add_slide(blank_slide_layout)
    add_header(s8, "Data Reshaping", "JQ Transformation Node (type: 'jq')")
    add_card(s8, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8), "In-Memory C-Speed Processing", [
        "Powered by native Python jq compiler",
        "Filters, slices, maps, and reshapes JSON payloads",
        "No need to spawn external Python/bash glue scripts",
        "Handles complex array selections: [.nodes[] | select(.cpu >= 85)]",
        "Aggregates metrics: {high_load_count: length, targets: [.[].id]}"
    ], ACCENT_CYAN)
    add_card(s8, Inches(6.8), Inches(1.8), Inches(5.6), Inches(4.8), "Robust Shell String & Object Decoding", [
        "Automatically unwraps raw JSON shell strings with outer quotes",
        "Supports pre-parsed Python dictionaries and raw JSON text",
        "Non-blocking execution via asyncio.to_thread",
        "Standardizes microservice payloads between REST stages",
        "Graceful syntax and runtime error diagnostics"
    ], ACCENT_CYAN)

    # ==================== SLIDE 9: Dynamic Routing - Safe AST Condition Node ====================
    s9 = prs.slides.add_slide(blank_slide_layout)
    add_header(s9, "Dynamic Branching", "Safe AST Conditional Node (type: 'condition')")
    add_card(s9, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8), "Safe AST-Based Evaluation", [
        "Zero unsafe eval() calls - strictly uses Python ast module",
        "Parses literals, comparisons, and boolean logic (and/or/not)",
        "Function calls and malicious code injections are blocked",
        "Automatic type coercion ('200' == 200, 'true' == True)",
        "Supports structured operands: left, operator, right"
    ], ACCENT_GREEN)
    add_card(s9, Inches(6.8), Inches(1.8), Inches(5.6), Inches(4.8), "Selective Branch Deactivation", [
        "Condition True -> Downstream dependents proceed normally",
        "Condition False -> Downstream branch marked SKIPPED",
        "Independent parallel branches continue unaffected",
        "Workflow reaches COMPLETED without being treated as an error",
        "Output: {condition_met: bool, skip_downstream: bool}"
    ], ACCENT_GREEN)

    # ==================== SLIDE 10: Complete Node Ecosystem ====================
    s10 = prs.slides.add_slide(blank_slide_layout)
    add_header(s10, "Node Registry", "Complete Step Handler Ecosystem")
    add_card(s10, Inches(0.8), Inches(1.8), Inches(2.1), Inches(4.8), "shell", [
        "Handler: handle_shell",
        "Core: subprocess.run in thread",
        "Keys: command, timeout",
        "Output: stdout, stderr, exit_code",
        "OS command execution"
    ], ACCENT_CYAN)
    add_card(s10, Inches(3.2), Inches(1.8), Inches(2.1), Inches(4.8), "rest", [
        "Handler: handle_rest",
        "Core: httpx.AsyncClient",
        "Keys: url, method, body, headers",
        "Output: response, status_code",
        "Microservice integration"
    ], ACCENT_BLUE)
    add_card(s10, Inches(5.6), Inches(1.8), Inches(2.1), Inches(4.8), "ai", [
        "Handler: handle_ai",
        "Core: Gemini 3.6 Flash",
        "Keys: prompt, response_format",
        "Output: response (JSON)",
        "Log triage & reasoning"
    ], ACCENT_GREEN)
    add_card(s10, Inches(8.0), Inches(1.8), Inches(2.1), Inches(4.8), "jq", [
        "Handler: handle_jq",
        "Core: jq.compile()",
        "Keys: query, data",
        "Output: response (transformed)",
        "In-memory JSON slicing"
    ], ACCENT_AMBER)
    add_card(s10, Inches(10.4), Inches(1.8), Inches(2.1), Inches(4.8), "condition", [
        "Handler: handle_condition",
        "Core: ast.parse() eval",
        "Keys: expression, left, op, right",
        "Output: condition_met, skip",
        "Path deactivation"
    ], ACCENT_ROSE)

    # ==================== SLIDE 11: Real-Time Visual Dashboard ====================
    s11 = prs.slides.add_slide(blank_slide_layout)
    add_header(s11, "User Interface", "Real-Time Visual Graph Dashboard")
    add_card(s11, Inches(0.8), Inches(1.8), Inches(3.6), Inches(4.8), "Interactive DAG Canvas", [
        "vis-network hierarchical layout",
        "Real-time color transitions",
        "Pulsing amber running indicators",
        "Zoom, pan, and layout orientation (LR/UD)",
        "Clear status legend"
    ], ACCENT_AMBER)
    add_card(s11, Inches(4.8), Inches(1.8), Inches(3.6), Inches(4.8), "JSON Editor & Presets", [
        "Syntax-validated JSON editor",
        "3 pre-loaded operational presets",
        "One-click JSON formatting",
        "Live node and edge counters",
        "Single-click Execute trigger"
    ], ACCENT_CYAN)
    add_card(s11, Inches(8.8), Inches(1.8), Inches(3.6), Inches(4.8), "Inspector & Telemetry", [
        "Click node to view stdout/stderr",
        "View structured AI JSON outputs",
        "Inspect exact skip/failure reasons",
        "Global runtime context explorer",
        "Download PPTX deck button"
    ], ACCENT_GREEN)

    # ==================== SLIDE 12: Live Demo Scenarios ====================
    s12 = prs.slides.add_slide(blank_slide_layout)
    add_header(s12, "Live Walkthrough", "Three Live Demonstration Scenarios")
    add_card(s12, Inches(0.8), Inches(1.8), Inches(3.6), Inches(4.8), "Preset 1: AI Remediation", [
        "1. Fetch crash log (Shell)",
        "2. Gemini 3.6 Flash triage (AI)",
        "3. Evaluate restart needed (Condition)",
        "4. Restart worker pool (Shell)",
        "5. Notify incident resolved (REST)",
        "Autonomous self-healing in <2s"
    ], ACCENT_BLUE)
    add_card(s12, Inches(4.8), Inches(1.8), Inches(3.6), Inches(4.8), "Preset 2: JQ Auto-Scale", [
        "1. Ingest cluster CPU metrics",
        "2. Filter nodes cpu >= 85% (JQ)",
        "3. Reshape alert count & targets (JQ)",
        "4. Validate threshold > 0 (Condition)",
        "5. Trigger capacity scale-up (Shell)",
        "Zero glue scripts required"
    ], ACCENT_CYAN)
    add_card(s12, Inches(8.8), Inches(1.8), Inches(3.6), Inches(4.8), "Preset 3: Failure Isolation", [
        "1. Auth token generation (Shell)",
        "2. Deliberate DB sync failure (Shell)",
        "3. Backup steps marked SKIPPED",
        "4. Independent telemetry runs to SUCCESS",
        "5. Broken branch isolated completely",
        "Zero cascading crashes"
    ], ACCENT_ROSE)

    # ==================== SLIDE 13: Judging Criteria Mapping ====================
    s13 = prs.slides.add_slide(blank_slide_layout)
    add_header(s13, "Evaluation Alignment", "Direct Mapping to Judging Criteria")
    add_card(s13, Inches(0.8), Inches(1.8), Inches(5.6), Inches(2.2), "1. Innovation", [
        "Native Gemini 3.6 Flash LLM node for unstructured log triage",
        "Safe AST-based conditional routing without insecure eval()"
    ], ACCENT_CYAN)
    add_card(s13, Inches(6.8), Inches(1.8), Inches(5.6), Inches(2.2), "2. Completeness", [
        "Full async parallel scheduler, Kahn validation, 202 background ingestion",
        "Live vis-network dashboard, inspector, and 14-slide presentation deck"
    ], ACCENT_BLUE)
    add_card(s13, Inches(0.8), Inches(4.3), Inches(5.6), Inches(2.4), "3. Practical Impact", [
        "Solves Day-2 IT infrastructure operations by automating incident triage",
        "Converts static runbooks into self-healing, agentic pipelines"
    ], ACCENT_GREEN)
    add_card(s13, Inches(6.8), Inches(4.3), Inches(5.6), Inches(2.4), "4. Technical Depth & Reliability", [
        "Thread-safe subprocess execution via asyncio.to_thread",
        "100% automated test suite passing across all 16 unit & API test cases"
    ], ACCENT_AMBER)

    # ==================== SLIDE 14: Roadmap & Conclusion ====================
    s14 = prs.slides.add_slide(blank_slide_layout)
    add_header(s14, "Looking Forward", "Production Roadmap & Conclusion")
    add_card(s14, Inches(0.8), Inches(1.8), Inches(2.7), Inches(2.2), "Persistent Storage", [
        "PostgreSQL / SQLite storage",
        "Workflow history replay",
        "Audit logs & execution metrics"
    ], ACCENT_CYAN)
    add_card(s14, Inches(3.8), Inches(1.8), Inches(2.7), Inches(2.2), "MCP Integration", [
        "Model Context Protocol",
        "Dynamic tool discovery",
        "Agentic multi-step tool calls"
    ], ACCENT_BLUE)
    add_card(s14, Inches(6.8), Inches(1.8), Inches(2.7), Inches(2.2), "Human-in-the-Loop", [
        "Interactive approval gates",
        "Slack / Teams interactive cards",
        "Manual override controls"
    ], ACCENT_AMBER)
    add_card(s14, Inches(9.8), Inches(1.8), Inches(2.7), Inches(2.2), "Distributed Scale", [
        "Celery / Redis worker queues",
        "Multi-datacenter distribution",
        "High-throughput DAG scaling"
    ], ACCENT_GREEN)

    summary_box = s14.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(4.4), Inches(11.7), Inches(2.2))
    summary_box.fill.solid()
    summary_box.fill.fore_color.rgb = CARD_BG
    summary_box.line.color.rgb = ACCENT_CYAN
    tf = summary_box.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = "Autonomous. Resilient. Intelligent."
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_WHITE
    p1.alignment = PP_ALIGN.CENTER

    p2 = tf.add_paragraph()
    p2.text = "Built for Nutanix Problem Statement 4 by Sathiyan Anand Sinha & Pranav Shalya\nThank you! Ready for Judge Q&A."
    p2.font.size = Pt(14)
    p2.font.color.rgb = ACCENT_CYAN
    p2.alignment = PP_ALIGN.CENTER

    # Output to in-memory buffer
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()


if __name__ == "__main__":
    data = generate_presentation_bytes()
    with open("Workflow_Engine_Nutanix_PS4.pptx", "wb") as f:
        f.write(data)
    print(f"Generated Workflow_Engine_Nutanix_PS4.pptx ({len(data)} bytes)")
