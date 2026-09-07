# Workflow Execution Engine

An asynchronous, parallel workflow execution engine that runs a directed acyclic graph (DAG) of steps (Shell commands, REST APIs, AI Reasoning, and JQ JSON transformations) with dependency resolution, variable substitution/context passing, granular failure cascading, and non-blocking background processing.

Built for the Nutanix Hackathon — Project Area 4: Workflow Execution Engine.

## Features
- **JSON-defined DAGs**: Define workflows with step IDs, types, and `depends_on` dependencies.
- **Asynchronous Parallel Execution**: Nodes whose dependencies have succeeded execute concurrently via standard Python `asyncio`.
- **AI Reasoning Node (`type: "ai"`)**: Integrated with Gemini 3.6 Flash API for prompt evaluation, structured JSON extraction (`response_format: "json"`), and intelligent decision routing.
- **JQ Transformation Node (`type: "jq"`)**: Filter, reshape, map, and slice JSON payloads between steps using standard JQ query expressions.
- **Conditional Routing Node (`type: "condition"`)**: Evaluate boolean/pythonic expressions or structured operands (`left`, `operator`, `right`) to dynamically activate or skip downstream branches without aborting the workflow.
- **Variable Substitution & Context Passing**: Pass outputs dynamically between steps using `${{ steps.STEP_ID.stdout }}` or nested JSON `${{ steps.STEP_ID.response.json_key }}`.
- **Background Processing**: `POST /workflows` accepts the DAG payload immediately with `202 Accepted` and executes the pipeline in the background.
- **Explicit Lifecycle States**: Granular status tracking (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `SKIPPED`) at both step and workflow levels.
- **Granular Failure Propagation**: If a step fails or a variable is missing, downstream dependents are recursively marked as `SKIPPED`, while independent parallel branches continue executing to completion.
- **Extensible Registry**: Register new step types via `@register_step_type("name")` with non-blocking `async def` handlers.
- **REST API**: Exposed via FastAPI with interactive OpenAPI documentation.

## Architecture

- `engine.py` — Core async execution engine: DAG validation, templating & context variable resolution, dynamic step scheduler, failure propagation, and step registry (`shell`, `rest`, `ai`, `jq`, `condition`).
- `main.py` — FastAPI service providing non-blocking background job submission and polling endpoints.
- `test_engine.py` — Comprehensive test suite covering linear, parallel branching, context passing, AI reasoning, JQ transformations, conditional routing, and failure cascading.
- `test_api.py` — End-to-end integration test verifying FastAPI background tasks, conditional path selection, and variable substitution over HTTP.

## Running it

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

- **Interactive Visual DAG Dashboard**: Open `http://127.0.0.1:8000/` in your browser to visually compose, execute, and monitor workflows in real time.
- **API Documentation**: Open `http://127.0.0.1:8000/docs` for the interactive OpenAPI UI.
- **REST Ingestion**: POST JSON workflows directly to `http://127.0.0.1:8000/workflows`.

## Example: AI and JQ Transformation Workflow

```json
{
  "steps": [
    {
      "id": "FetchLog",
      "type": "shell",
      "config": {
        "command": "echo ERROR: Database connection timed out on port 5432"
      }
    },
    {
      "id": "AnalyzeLog",
      "type": "ai",
      "config": {
        "prompt": "Classify this error log and suggest severity: ${{ steps.FetchLog.stdout }}",
        "response_format": "json"
      },
      "depends_on": ["FetchLog"]
    },
    {
      "id": "FormatAlert",
      "type": "jq",
      "config": {
        "query": "{alert_title: \"Critical Incident\", level: .severity, details: .}",
        "data": "${{ steps.AnalyzeLog.response }}"
      },
      "depends_on": ["AnalyzeLog"]
    },
    {
      "id": "DispatchAlert",
      "type": "shell",
      "config": {
        "command": "echo Alert Level: ${{ steps.FormatAlert.response.level }}"
      },
      "depends_on": ["FormatAlert"]
    }
  ]
}
```

## Team
Sathiyan Anand Sinha & Pranav Shalya