# 3-Minute Live Presentation & Demonstration Script
**Nutanix Hackathon — Problem Statement 4: Workflow Execution Engine**  
**Team:** Sathiyan Anand Sinha & Pranav Shalya

---

## ⏱️ Presentation Timing Breakdown (3 Minutes Total)

| Section | Duration | Focus Area |
| :--- | :--- | :--- |
| **1. Executive Pitch** | 0:00 - 0:45 (45s) | Problem statement, infrastructure challenges, and our solution |
| **2. Architecture & DAG Core** | 0:45 - 1:15 (30s) | Kahn's algorithm, async parallel execution, and state engine |
| **3. Live UI Demonstration** | 1:15 - 2:30 (75s) | Walkthrough of 3 Live Presets on the Visual Graph Dashboard |
| **4. Judge Evaluation Mapping** | 2:30 - 3:00 (30s) | Innovation, completeness, impact, and code quality wrap-up |

---

## 1. Executive Pitch (The "Why") — *[0:00 - 0:45]*

> **Speaker Notes:**
>
> *"Good morning judges. Modern enterprise datacenters and hybrid clouds are distributed, high-velocity, and unpredictable. When an infrastructure alert fires at 2 AM, traditional automation relies on linear bash scripts or static cron jobs. These legacy approaches are brittle: they block event loops, break on the first error with no branch isolation, and fundamentally lack real-time reasoning.*
>
> *To solve this, we built the **Enterprise-Grade Agentic Workflow Orchestrator**.*
>
> *It is a lightweight, high-throughput asynchronous execution engine that ingests complex Directed Acyclic Graphs (DAGs) in pure JSON. It executes independent tasks in **true parallel concurrency**, features **non-blocking background ingestion**, provides **granular failure isolation**, and embeds a **native Gemini 3.6 Flash AI Reasoning Node** alongside **safe AST conditional routing** to achieve autonomous, self-healing infrastructure operations."*

---

## 2. Architecture & Key Innovations — *[0:45 - 1:15]*

> **Speaker Notes:**
>
> *"Let's take a quick look under the hood:*
>
> 1. * **Upfront Graph Validation:** Before a single task executes, we run **Kahn's Algorithm** to guarantee the graph is a valid DAG with zero circular dependencies.*
> 2. * **True Async Concurrency:** Ready nodes with in-degree zero launch concurrently via Python's `asyncio` engine. Heavy subprocesses are dispatched onto non-blocking worker threads via `asyncio.to_thread` to maintain event-loop responsiveness.*
> 3. * **Granular 5-State Lifecycle:** Every node transitions cleanly through `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, and `SKIPPED`.*
> 4. * **Inter-Step Context & AST Condition Evaluation:** Step outputs dynamically populate a global runtime context `${{ steps.ID.property }}`, which feed directly into our AST-based condition nodes without unsafe `eval()` calls.*
>
> *Let's now jump directly into the live visual dashboard to see it in action."*

---

## 3. Step-by-Step Live UI Walkthrough — *[1:15 - 2:30]*

*(Open browser at `http://127.0.0.1:8000/`)*

```
+-----------------------------------------------------------------------------------------------+
|  DAG Orchestrator  |  Workflow Execution Engine  [Nutanix Hackathon]             Status: IDLE |
+-------------------------------+-----------------------------------+---------------------------+
| PRESET SELECTOR & JSON EDITOR | INTERACTIVE LIVE DAG CANVAS       | NODE INSPECTOR & CONTEXT  |
|                               |                                   |                           |
| Preset 1: AI Incident Triage  |  [FetchCrashLog]                  | Node: AiTriage            |
|                               |         |                         | Type: AI (Gemini Flash)   |
| [⚡ Execute Workflow]         |         v                         | Status: SUCCESS           |
|                               |    [AiTriage]                     | Response: {               |
|                               |         |                         |   "severity": "CRITICAL", |
|                               |         v                         |   "requires_restart": true|
|                               |  [CheckCondition]                 | }                         |
|                               |    /         \                    |                           |
|                               | (True)     (False)                | Live stdout / stderr      |
|                               |   v           v                   | Runtime metrics           |
|                               |[Remediate] [SkippedAction]        |                           |
+-------------------------------+-----------------------------------+---------------------------+
```

---

### Demo 1: Autonomous AI Incident Triage & Remediation *(Preset 1)*
* **Action:** Select **"Preset 1: AI Triage + Condition + Remediation"** in the dropdown.
* **Click:** **[⚡ Execute Workflow]**
* **What Judges See:**
  1. Graph immediately renders on canvas in **Blue (`PENDING`)**.
  2. `FetchCrashLog` and `IndependentTelemetry` immediately turn **Amber (`RUNNING`) in parallel**.
  3. `FetchCrashLog` completes **Green (`SUCCESS`)** and feeds its crash log (`"Out of memory error in worker pool 3"`) into `AiTriage`.
  4. `AiTriage` invokes Gemini 3.6 Flash asynchronously, extracting structured JSON (`{"severity": "CRITICAL", "requires_restart": true, "action": "Restart worker pool 3"}`).
  5. `CheckRestartCondition` evaluates `${{ steps.AiTriage.response.requires_restart }} == true` via AST, evaluating to `True`.
  6. `RemediationAction` executes the remediation command and `NotifySlack` posts the alert to a webhook.
* **Speaker Highlight:**
  > *"Notice how the AI node seamlessly extracted root cause diagnostics in raw JSON, dynamic context substitution routed the decision to our condition node, and the engine remediated the crash autonomously in under 2 seconds."*

---

### Demo 2: High-Speed JQ Data Reshaping & Auto-Scaling *(Preset 2)*
* **Action:** Select **"Preset 2: JQ Metrics Filter + Auto-Scale"** in the dropdown.
* **Click:** **[⚡ Execute Workflow]**
* **What Judges See:**
  1. `CollectClusterMetrics` dumps raw multi-node cluster CPU metrics.
  2. `FilterOverloadedNodes` (JQ Node) applies `[.nodes[] | select(.cpu >= 85)]` entirely in-memory without spawning external scripts.
  3. `ReshapeAlertData` aggregates the results into a clean dictionary `{high_load_count: 2, target_nodes: ["worker-1", "worker-3"]}`.
  4. `CheckCriticalThreshold` validates `high_load_count > 0` $\to$ triggers `TriggerAutoScale` for the exact target nodes.
* **Speaker Highlight:**
  > *"Instead of writing custom Python glue scripts, workflows can filter, slice, and reshape high-volume infrastructure metrics in-memory using native JQ transformations."*

---

### Demo 3: Granular Failure Isolation & Independent Branching *(Preset 3)*
* **Action:** Select **"Preset 3: Failure Isolation & Independent Branch"** in the dropdown.
* **Click:** **[⚡ Execute Workflow]**
* **What Judges See:**
  1. `FailDatabaseSync` exits with code `1` and turns **Red (`FAILED`)**.
  2. `SkippedDownstreamTask` and `SkippedNotification` turn **Slate (`SKIPPED`)** with dashed borders.
  3. Clicking `SkippedDownstreamTask` in the Inspector reveals the exact reason: `"Skipped due to failure in upstream step 'FailDatabaseSync'"`.
  4. **Crucial:** `IndependentTelemetryA` and `IndependentTelemetryB` continue executing concurrently to **Green (`SUCCESS`)**.
* **Speaker Highlight:**
  > *"In a monolithic script, one failure crashes the entire run. In our engine, failures are strictly isolated: broken dependency subgraphs are cleanly skipped, while independent operational branches run to full completion."*

---

## 4. Judge Evaluation Mapping & Wrap-Up — *[2:30 - 3:00]*

| Hackathon Criteria | How Our Engine Delivers |
| :--- | :--- |
| 🚀 **Innovation** | Native integration of **Gemini 3.6 Flash** for agentic reasoning + safe **AST-based conditional execution** without unsafe `eval()`. |
| 🧩 **Completeness** | Full async DAG scheduling, Kahn's validation, non-blocking background ingestion (`202 Accepted`), context data passing, REST API, and interactive visual dashboard. |
| 💼 **Practical Impact** | Solves real-world Day-2 cloud infrastructure operations by transforming static runbooks into self-healing, intelligent automation pipelines. |
| 🛡️ **Code Quality & Reliability** | Thread-safe subprocess execution (`asyncio.to_thread`), comprehensive error fallbacks, 100% automated test suite passing across all 15 unit and API scenarios. |

> **Closing Statement:**
>
> *"Our Workflow Execution Engine brings true parallelism, failure resilience, and AI intelligence to modern infrastructure operations. Thank you, and we're ready for your questions!"*

---

## 5. Potential Judge Q&A Cheatsheet

### Q1: How do you prevent event loop blocking when running heavy shell commands or REST requests?
> **Answer:** We offload synchronous subprocess execution to worker threads via `asyncio.to_thread(subprocess.run, ...)` and use `httpx.AsyncClient` for all HTTP and AI communications. The FastAPI event loop remains completely unblocked.

### Q2: How do you ensure safety in the Condition Node? Could someone inject malicious Python code?
> **Answer:** We do **not** use `eval()`. Instead, we parse the expression using Python's `ast` (Abstract Syntax Tree) module, strictly whitelisting constants, boolean operations (`and`, `or`, `not`), comparisons, and literals. Any function calls or unauthorized AST nodes are rejected immediately.

### Q3: How does the engine scale for large DAGs?
> **Answer:** Graph validation is $O(V + E)$ via Kahn's algorithm. Task scheduling is purely reactive using async task completions (`asyncio.FIRST_COMPLETED`), and FastAPI handles requests in background tasks returning immediate `202 Accepted` receipts.
