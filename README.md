# Workflow Execution Engine

An asynchronous, parallel workflow execution engine that runs a directed acyclic graph (DAG) of steps (Shell commands, REST APIs, and AI Reasoning nodes) with dependency resolution, variable substitution/context passing, granular failure cascading, and non-blocking background processing.

Built for the Nutanix Hackathon — Project Area 4: Workflow Execution Engine.

## Features
- **JSON-defined DAGs**: Define workflows with step IDs, types, and `depends_on` dependencies.
- **Asynchronous Parallel Execution**: Nodes whose dependencies have succeeded execute concurrently via standard Python `asyncio`.
- **AI Reasoning Node (`type: "ai"`)**: Integrated with Gemini 2.5 Flash API for prompt evaluation, structured JSON extraction (`response_format: "json"`), and intelligent decision routing.
- **Variable Substitution & Context Passing**: Pass outputs dynamically between steps using `${{ steps.STEP_ID.stdout }}` or nested JSON `${{ steps.STEP_ID.response.json_key }}`.
- **Background Processing**: `POST /workflows` accepts the DAG payload immediately with `202 Accepted` and executes the pipeline in the background.
- **Explicit Lifecycle States**: Granular status tracking (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `SKIPPED`) at both step and workflow levels.
- **Granular Failure Propagation**: If a step fails or a variable is missing, downstream dependents are recursively marked as `SKIPPED`, while independent parallel branches continue executing to completion.
- **Extensible Registry**: Register new step types via `@register_step_type("name")` with non-blocking `async def` handlers.
- **REST API**: Exposed via FastAPI with interactive OpenAPI documentation.

## Architecture

- `engine.py` — Core async execution engine: DAG validation, templating & context variable resolution, dynamic step scheduler, failure propagation, and step registry (`shell`, `rest`, `ai`).
- `main.py` — FastAPI service providing non-blocking background job submission and polling endpoints.
- `test_engine.py` — Test suite covering linear, parallel branching, context passing/interpolation, AI node integration, and failure cascading.
- `test_api.py` — End-to-end integration test verifying FastAPI background tasks and variable substitution over HTTP.

## Running it

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000/docs` for the interactive API UI, or POST a workflow JSON to `http://127.0.0.1:8000/workflows`.

## Example: AI-Powered Context Workflow

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
      "id": "DispatchAlert",
      "type": "shell",
      "config": {
        "command": "echo Alert severity: ${{ steps.AnalyzeLog.response.severity }}"
      },
      "depends_on": ["AnalyzeLog"]
    }
  ]
}
```

## Team
Sathiyan Anand Sinha & Pranav Shalya