# Workflow Execution Engine

A lightweight, extensible workflow execution engine that runs a set of
steps (shell commands or REST API calls) in dependency order, defined
entirely via a JSON payload.

Built for the Nutanix Hackathon — Project Area 4: Workflow Execution Engine.

## Features
- Define workflows as JSON: a list of steps with an `id`, `type`, and
  `depends_on` list.
- Dependency-aware execution using topological sort (Kahn's algorithm) —
  steps only run after everything they depend on has completed.
- Supports two step types out of the box: `shell` (runs a shell command)
  and `rest` (makes an HTTP request).
- **Extensible by design**: new step types can be added via a registry
  pattern (`@register_step_type("name")`) without modifying the core
  engine or execution logic.
- Exposed as a REST API via FastAPI for easy integration and demoing.

## Architecture


- `engine.py` — core logic: dependency sorting, step execution, registry
- `main.py` — FastAPI wrapper exposing the engine over HTTP
- `test_engine.py` — standalone tests for the engine logic

## Running it

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000/docs` for an interactive API UI, or POST
a workflow JSON to `http://127.0.0.1:8000/workflows`.

## Example: a workflow with branching and failure handling

```json
{
  "steps": [
    {"id": "A", "type": "shell", "command": "echo Fetching data"},
    {"id": "B", "type": "shell", "command": "echo Processing data", "depends_on": ["A"]},
    {"id": "C", "type": "shell", "command": "exit /b 1", "depends_on": ["A"]},
    {"id": "D", "type": "shell", "command": "echo Notify user", "depends_on": ["B", "C"]}
  ]
}
```

Here, step `D` depends on both `B` and `C`. Since `C` fails, `D` is
correctly never executed — demonstrating dependency-aware failure
handling.

## What we'd add with more time
- Retry logic with configurable backoff for failed steps
- Persistent storage (Postgres/Redis) instead of in-memory state
- Additional step types (database queries, email/notifications)
- A minimal web UI for building/monitoring workflows visually

## Team
Sathiyan Anand Sinha & Pranav Shalya