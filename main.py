import asyncio
import sys
import uuid
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from engine import run_workflow, validate_dag, StepStatus, WorkflowStatus

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="Workflow Execution Engine")

workflows_db: Dict[str, dict] = {}


class Step(BaseModel):
    id: str
    type: str
    depends_on: Optional[List[str]] = []
    config: Optional[Dict[str, Any]] = None
    command: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = "GET"
    body: Optional[Any] = None
    headers: Optional[Dict[str, str]] = None
    prompt: Optional[str] = None
    response_format: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[int] = 30


class WorkflowRequest(BaseModel):
    steps: List[Step]


@app.post("/workflows", status_code=status.HTTP_202_ACCEPTED)
async def submit_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    steps_as_dicts = [s.dict() for s in request.steps]

    try:
        validate_dag(steps_as_dicts)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    workflow_id = str(uuid.uuid4())

    workflows_db[workflow_id] = {
        "workflow_id": workflow_id,
        "status": WorkflowStatus.PENDING,
        "results": {
            s["id"]: {
                "id": s["id"],
                "type": s["type"],
                "status": StepStatus.PENDING,
            }
            for s in steps_as_dicts
        },
    }

    background_tasks.add_task(run_workflow, steps_as_dicts, workflows_db[workflow_id])

    return {
        "workflow_id": workflow_id,
        "status": WorkflowStatus.PENDING,
        "message": "Workflow accepted for background execution",
    }


@app.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    if workflow_id not in workflows_db:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflows_db[workflow_id]


@app.get("/workflows")
def list_workflows():
    return {
        "workflow_ids": list(workflows_db.keys()),
        "workflows": workflows_db,
    }