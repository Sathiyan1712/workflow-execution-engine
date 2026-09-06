import subprocess
import requests
from collections import deque


def topological_sort(steps):
    in_degree = {step["id"]: 0 for step in steps}
    graph = {step["id"]: [] for step in steps}

    for step in steps:
        for dep in step.get("depends_on", []):
            if dep not in graph:
                raise ValueError(f"Step '{step['id']}' depends on unknown step '{dep}'")
            graph[dep].append(step["id"])
            in_degree[step["id"]] += 1

    queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
    order = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(steps):
        raise ValueError("Cycle detected in workflow dependencies")

    return order


# Registry: maps step type name -> handler function
STEP_HANDLERS = {}


def register_step_type(name):
    """
    Decorator that registers a function as the handler for a given
    step type. This is the 'extensibility point': to add a new kind
    of step (e.g. 'database', 'email'), you just write a new function
    and decorate it — no need to touch execute_step or the engine core.
    """
    def decorator(func):
        STEP_HANDLERS[name] = func
        return func
    return decorator


@register_step_type("shell")
def handle_shell(step):
    proc = subprocess.run(
        step["command"],
        shell=True,
        capture_output=True,
        text=True,
        timeout=step.get("timeout", 30),
    )
    return {
        "success": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
    }


@register_step_type("rest")
def handle_rest(step):
    method = step.get("method", "GET").upper()
    resp = requests.request(
        method,
        step["url"],
        json=step.get("body"),
        timeout=step.get("timeout", 30),
    )
    out = {
        "success": resp.status_code < 400,
        "status_code": resp.status_code,
    }
    try:
        out["response"] = resp.json()
    except ValueError:
        out["response"] = resp.text
    return out


def execute_step(step):
    result = {"id": step["id"], "type": step["type"]}

    handler = STEP_HANDLERS.get(step["type"])
    if handler is None:
        result["success"] = False
        result["error"] = f"Unknown step type: '{step['type']}'"
        return result

    try:
        result.update(handler(step))
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result

def run_workflow(steps, stop_on_failure=True):
    order = topological_sort(steps)
    step_map = {step["id"]: step for step in steps}

    results = {}
    overall_success = True

    for step_id in order:
        step = step_map[step_id]
        res = execute_step(step)
        results[step_id] = res

        if not res.get("success", False):
            overall_success = False
            if stop_on_failure:
                break

    return {
        "success": overall_success,
        "execution_order": order,
        "results": results,
    }