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


def execute_step(step):
    result = {"id": step["id"], "type": step["type"]}

    try:
        if step["type"] == "shell":
            proc = subprocess.run(
                step["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=step.get("timeout", 30),
            )
            result["success"] = (proc.returncode == 0)
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["exit_code"] = proc.returncode

        elif step["type"] == "rest":
            method = step.get("method", "GET").upper()
            resp = requests.request(
                method,
                step["url"],
                json=step.get("body"),
                timeout=step.get("timeout", 30),
            )
            result["success"] = resp.status_code < 400
            result["status_code"] = resp.status_code
            try:
                result["response"] = resp.json()
            except ValueError:
                result["response"] = resp.text

        else:
            result["success"] = False
            result["error"] = f"Unknown step type: '{step['type']}'"

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