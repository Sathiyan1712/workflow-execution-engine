import asyncio
from collections import deque
import copy
from enum import Enum
import re
from typing import Any
import httpx


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def validate_dag(steps: list[dict]) -> None:
    step_ids = {step["id"] for step in steps}
    if len(step_ids) != len(steps):
        raise ValueError("Duplicate step IDs detected in workflow")

    in_degree = {step["id"]: 0 for step in steps}
    graph = {step["id"]: [] for step in steps}

    for step in steps:
        for dep in step.get("depends_on", []):
            if dep not in graph:
                raise ValueError(f"Step '{step['id']}' depends on unknown step '{dep}'")
            graph[dep].append(step["id"])
            in_degree[step["id"]] += 1

    queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
    visited_count = 0

    while queue:
        current = queue.popleft()
        visited_count += 1
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count != len(steps):
        raise ValueError("Cycle detected in workflow dependencies")


# --- Templating & Variable Substitution ---
TEMPLATE_PATTERN = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")


def resolve_path(context: dict, path: str) -> Any:
    tokens = re.findall(r'[^.\[\]"\']+', path.strip())
    if not tokens:
        raise KeyError(f"Empty variable path: '{path}'")

    current = context
    for token in tokens:
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(f"Key '{token}' not found in context while resolving '${{{{ {path.strip()} }}}}'")
            current = current[token]
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(token)
                current = current[idx]
            except (ValueError, IndexError):
                raise KeyError(f"Index '{token}' invalid or out of bounds while resolving '${{{{ {path.strip()} }}}}'")
        else:
            raise KeyError(f"Cannot access property '{token}' on non-container type '{type(current).__name__}' while resolving '${{{{ {path.strip()} }}}}'")
    return current


def interpolate_value(value: Any, context: dict) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        if "${{" not in value:
            return value

        trimmed = value.strip()
        full_match = TEMPLATE_PATTERN.fullmatch(trimmed)
        if full_match:
            var_path = full_match.group(1).strip()
            return resolve_path(context, var_path)

        def replacer(match):
            var_path = match.group(1).strip()
            val = resolve_path(context, var_path)
            return str(val)

        return TEMPLATE_PATTERN.sub(replacer, value)

    elif isinstance(value, dict):
        return {k: interpolate_value(v, context) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [interpolate_value(v, context) for v in value]

    return value


def interpolate_step_config(step: dict, context: dict) -> dict:
    step_copy = copy.deepcopy(step)
    for key, val in step_copy.items():
        if key not in ("id", "type", "depends_on") and val is not None:
            step_copy[key] = interpolate_value(val, context)
    return step_copy


# Registry: maps step type name -> async handler function
STEP_HANDLERS = {}


def register_step_type(name: str):
    def decorator(func):
        STEP_HANDLERS[name] = func
        return func
    return decorator


@register_step_type("shell")
async def handle_shell(step: dict) -> dict:
    config = step.get("config")
    if config is None or not isinstance(config, dict) or not config:
        if isinstance(step, dict) and (step.get("command") or step.get("cmd")):
            config = step
        else:
            raise ValueError("Shell step requires a 'command' string in config.")

    cmd = config.get("command") or config.get("cmd") or step.get("command") or step.get("cmd")
    if not cmd or not isinstance(cmd, str):
        raise ValueError("Shell step requires a 'command' string in config.")

    timeout = config.get("timeout") or step.get("timeout", 30)
    proc = None
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip() if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip() if stderr_bytes else ""

        returncode = proc.returncode
        if returncode is None:
            return {
                "success": False,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": -1,
                "error": "Process terminated without returning an exit code",
            }

        is_success = (returncode == 0)
        res = {
            "success": is_success,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": returncode,
        }

        if not is_success:
            res["error"] = stderr if stderr else f"Command failed with exit code {returncode}"

        return res

    except asyncio.TimeoutError:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "exit_code": -1,
        }
    except Exception as e:
        err_msg = str(e).strip()
        error_detail = f"{type(e).__name__}: {err_msg}" if err_msg else f"Shell execution failed ({type(e).__name__})"
        return {
            "success": False,
            "error": error_detail,
            "exit_code": -1,
        }


@register_step_type("rest")
async def handle_rest(step: dict) -> dict:
    config = step.get("config")
    if config is None or not isinstance(config, dict) or not config:
        if isinstance(step, dict) and step.get("url"):
            config = step
        else:
            raise ValueError("REST step requires a 'url' string in config.")

    url = config.get("url") or step.get("url")
    if not url or not isinstance(url, str):
        raise ValueError("REST step requires a 'url' string in config.")

    method = str(config.get("method") or step.get("method") or "GET").upper()
    body = config.get("body") if "body" in config else step.get("body")
    headers = config.get("headers") if "headers" in config else step.get("headers")
    timeout = config.get("timeout") or step.get("timeout", 30)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=method,
                url=url,
                json=body,
                headers=headers,
            )

        try:
            response_data = resp.json()
        except Exception:
            response_data = resp.text

        return {
            "success": resp.is_success,
            "status_code": resp.status_code,
            "response": response_data,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def execute_step(step: dict, context: dict = None) -> dict:
    result = {"id": step["id"], "type": step["type"]}

    if context:
        try:
            step = interpolate_step_config(step, context)
        except Exception as e:
            result.update({
                "status": StepStatus.FAILED,
                "success": False,
                "error": f"Variable substitution error in step '{step['id']}': {e}",
            })
            return result

    handler = STEP_HANDLERS.get(step["type"])
    if handler is None:
        result.update({
            "status": StepStatus.FAILED,
            "success": False,
            "error": f"Unknown step type: '{step['type']}'",
        })
        return result

    try:
        if asyncio.iscoroutinefunction(handler):
            res = await handler(step)
        else:
            res = handler(step)
    except Exception as e:
        res = {"success": False, "error": str(e)}

    status = StepStatus.SUCCESS if res.get("success", False) else StepStatus.FAILED
    result.update({
        "status": status,
        **res,
    })
    return result


def _mark_descendants_skipped(failed_id: str, downstream: dict, results: dict) -> None:
    visited = set()
    queue = list(downstream.get(failed_id, []))
    while queue:
        child_id = queue.pop(0)
        if child_id not in visited:
            visited.add(child_id)
            if results[child_id]["status"] == StepStatus.PENDING:
                results[child_id].update({
                    "status": StepStatus.SKIPPED,
                    "success": False,
                    "error": f"Skipped due to failure in upstream step '{failed_id}'",
                })
            queue.extend(downstream.get(child_id, []))


async def run_workflow(steps: list[dict], workflow_state: dict = None) -> dict:
    validate_dag(steps)

    step_map = {s["id"]: s for s in steps}
    upstream = {s["id"]: set(s.get("depends_on", [])) for s in steps}
    downstream = {s["id"]: [] for s in steps}
    for s in steps:
        for dep in s.get("depends_on", []):
            downstream[dep].append(s["id"])

    results = {
        s["id"]: {
            "id": s["id"],
            "type": s["type"],
            "status": StepStatus.PENDING,
        }
        for s in steps
    }

    # Global context for inter-step data passing
    context = {"steps": {}}

    if workflow_state is not None:
        workflow_state["status"] = WorkflowStatus.RUNNING
        workflow_state["results"] = results
        workflow_state["context"] = context

    running_tasks: dict[str, asyncio.Task] = {}

    while True:
        # Launch any PENDING step whose upstream dependencies have all reached SUCCESS
        for step_id, step in step_map.items():
            if results[step_id]["status"] == StepStatus.PENDING and step_id not in running_tasks:
                deps = upstream[step_id]
                if all(results[dep]["status"] == StepStatus.SUCCESS for dep in deps):
                    results[step_id]["status"] = StepStatus.RUNNING
                    task = asyncio.create_task(execute_step(step, context), name=step_id)
                    running_tasks[step_id] = task

        if not running_tasks:
            # Mark any remaining unrunnable PENDING steps as SKIPPED
            for step_id in step_map:
                if results[step_id]["status"] == StepStatus.PENDING:
                    results[step_id].update({
                        "status": StepStatus.SKIPPED,
                        "success": False,
                        "error": "Skipped because upstream dependencies could not be satisfied",
                    })
            break

        # Await completion of the next task(s)
        done, _ = await asyncio.wait(
            running_tasks.values(),
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            step_id = task.get_name()
            running_tasks.pop(step_id, None)

            try:
                res = task.result()
            except Exception as e:
                res = {
                    "id": step_id,
                    "type": step_map[step_id]["type"],
                    "status": StepStatus.FAILED,
                    "success": False,
                    "error": str(e),
                }

            results[step_id].update(res)

            if results[step_id]["status"] == StepStatus.SUCCESS:
                # Add successful step output to context for downstream steps
                context["steps"][step_id] = {**results[step_id]}
            elif results[step_id]["status"] == StepStatus.FAILED:
                _mark_descendants_skipped(step_id, downstream, results)

    overall_success = all(
        res.get("status") == StepStatus.SUCCESS
        for res in results.values()
    )
    workflow_status = WorkflowStatus.COMPLETED if overall_success else WorkflowStatus.FAILED

    output = {
        "status": workflow_status,
        "success": overall_success,
        "results": results,
        "context": context,
    }

    if workflow_state is not None:
        workflow_state.update(output)

    return output