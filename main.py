import uuid
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from engine import run_workflow

app = FastAPI(title="Workflow Execution Engine")

# In-memory "database" — just a dict. Fine for a hackathon demo;
# a real system would use Postgres/Redis so data survives a restart.
workflows_db: Dict[str, dict] = {}


class Step(BaseModel):
    id: str
    type: str                          # "shell" or "rest"
    depends_on: Optional[List[str]] = []
    command: Optional[str] = None      # used when type == "shell"
    url: Optional[str] = None          # used when type == "rest"
    method: Optional[str] = "GET"      # used when type == "rest"
    body: Optional[Any] = None         # used when type == "rest"
    timeout: Optional[int] = 30


class WorkflowRequest(BaseModel):
    steps: List[Step]
    stop_on_failure: Optional[bool] = True


@app.post("/workflows")
def submit_workflow(request: WorkflowRequest):
    workflow_id = str(uuid.uuid4())
    steps_as_dicts = [s.dict() for s in request.steps]

    result = run_workflow(steps_as_dicts, stop_on_failure=request.stop_on_failure)
    workflows_db[workflow_id] = result

    return {"workflow_id": workflow_id, **result}


@app.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    if workflow_id not in workflows_db:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflows_db[workflow_id]


@app.get("/workflows")
def list_workflows():
    return {"workflow_ids": list(workflows_db.keys())}