import asyncio
from collections import deque
import copy
from enum import Enum
import ast
import operator as op
import json
import os
import re
import subprocess
from typing import Any
import httpx
import jq


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
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""
        is_success = (proc.returncode == 0)

        res = {
            "success": is_success,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
        }

        if not is_success:
            res["error"] = stderr if stderr else f"Command failed with exit code {proc.returncode}"

        return res

    except subprocess.TimeoutExpired:
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


@register_step_type("ai")
async def handle_ai(step: dict) -> dict:
    config = step.get("config")
    if config is None or not isinstance(config, dict) or not config:
        if isinstance(step, dict) and step.get("prompt"):
            config = step
        else:
            raise ValueError("AI step requires a 'prompt' string in config.")

    prompt = config.get("prompt") or step.get("prompt")
    if not prompt or not isinstance(prompt, str):
        raise ValueError("AI step requires a 'prompt' string in config.")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing 'GEMINI_API_KEY' environment variable for AI step.")

    is_json = (config.get("response_format") == "json" or step.get("response_format") == "json")
    if is_json:
        prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Return ONLY raw, valid JSON. Do not include markdown formatting, backticks, or explanatory text."
        )

    model = config.get("model") or step.get("model") or "gemini-3.6-flash"
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload: dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    if is_json:
        payload["generationConfig"] = {
            "responseMimeType": "application/json"
        }

    timeout = config.get("timeout") or step.get("timeout", 60)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        if resp.status_code >= 400:
            return {
                "success": False,
                "status_code": resp.status_code,
                "error": f"Gemini API error ({resp.status_code}): {resp.text}",
            }

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return {
                "success": False,
                "error": f"Gemini API returned no candidates in response: {data}",
            }

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return {
                "success": False,
                "error": f"Gemini API returned empty content parts: {data}",
            }

        raw_text = parts[0].get("text", "")

        if is_json:
            clean_text = raw_text.strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                clean_text = re.sub(r"\s*```$", "", clean_text)
            try:
                parsed_response = json.loads(clean_text)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Failed to parse AI response as JSON: {e}",
                    "raw_response": raw_text,
                }
        else:
            parsed_response = raw_text

        return {
            "success": True,
            "response": parsed_response,
            "raw_response": raw_text,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"AI step execution failed: {str(e)}",
        }


@register_step_type("jq")
async def handle_jq(step: dict) -> dict:
    config = step.get("config")
    if config is None or not isinstance(config, dict) or not config:
        if isinstance(step, dict) and step.get("query"):
            config = step
        else:
            raise ValueError("JQ step requires a 'query' string in config.")

    query = config.get("query") or step.get("query")
    if not query or not isinstance(query, str):
        raise ValueError("JQ step requires a 'query' string in config.")

    if "data" not in config and "data" not in step:
        raise ValueError("JQ step requires a 'data' source in config.")

    raw_data = config.get("data") if "data" in config else step.get("data")

    # If data is a JSON string, attempt to parse it to a Python object
    data = raw_data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass

    def _run_jq(q: str, d: Any):
        compiled = jq.compile(q)
        results = compiled.input_value(d).all()
        if len(results) == 1:
            return results[0]
        elif len(results) == 0:
            return None
        return results

    try:
        transformed = await asyncio.to_thread(_run_jq, query, data)
        return {
            "success": True,
            "response": transformed,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"JQ transformation error: {str(e)}",
        }


# --- Safe Expression Evaluation for Condition Nodes ---
AST_OPERATORS = {
    ast.Eq: op.eq,
    ast.NotEq: op.ne,
    ast.Lt: op.lt,
    ast.LtE: op.le,
    ast.Gt: op.gt,
    ast.GtE: op.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: op.is_,
    ast.IsNot: op.is_not,
}

AST_BOOL_OPS = {
    ast.And: all,
    ast.Or: any,
}

AST_UNARY_OPS = {
    ast.Not: op.not_,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

SAFE_NAMES = {
    "true": True,
    "True": True,
    "false": False,
    "False": False,
    "null": None,
    "none": None,
    "None": None,
}


def _coerce_pair(a: Any, b: Any) -> tuple[Any, Any]:
    if isinstance(a, (int, float)) and isinstance(b, str):
        try:
            return a, type(a)(b)
        except (ValueError, TypeError):
            pass
    elif isinstance(b, (int, float)) and isinstance(a, str):
        try:
            return type(b)(a), b
        except (ValueError, TypeError):
            pass
    elif isinstance(a, bool) and isinstance(b, str):
        if b.lower() in ("true", "false"):
            return a, b.lower() == "true"
    elif isinstance(b, bool) and isinstance(a, str):
        if a.lower() in ("true", "false"):
            return a.lower() == "true", b
    return a, b


def _safe_compare(op_func, a: Any, b: Any) -> bool:
    try:
        if op_func(a, b):
            return True
    except TypeError:
        pass

    coerced_a, coerced_b = _coerce_pair(a, b)
    if (coerced_a, coerced_b) != (a, b):
        try:
            return op_func(coerced_a, coerced_b)
        except TypeError:
            pass
    return False


def safe_eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return safe_eval_node(node.body)
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Name):
        if node.id in SAFE_NAMES:
            return SAFE_NAMES[node.id]
        raise ValueError(f"Disallowed name in expression: '{node.id}'")
    elif isinstance(node, ast.UnaryOp):
        operand = safe_eval_node(node.operand)
        op_func = AST_UNARY_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(operand)
    elif isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for val in node.values:
                if not safe_eval_node(val):
                    return False
            return True
        elif isinstance(node.op, ast.Or):
            for val in node.values:
                if safe_eval_node(val):
                    return True
            return False
        else:
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")
    elif isinstance(node, ast.Compare):
        left = safe_eval_node(node.left)
        for cmp_op, comparator in zip(node.ops, node.comparators):
            right = safe_eval_node(comparator)
            op_func = AST_OPERATORS.get(type(cmp_op))
            if op_func is None:
                raise ValueError(f"Unsupported comparison operator: {type(cmp_op).__name__}")
            if not _safe_compare(op_func, left, right):
                return False
            left = right
        return True
    elif isinstance(node, (ast.List, ast.Tuple)):
        return [safe_eval_node(elt) for elt in node.elts]
    elif isinstance(node, ast.Dict):
        return {safe_eval_node(k): safe_eval_node(v) for k, v in zip(node.keys, node.values)}
    else:
        raise ValueError(f"Unsupported expression construct: {type(node).__name__}")


def evaluate_structured(left: Any, operator_str: str, right: Any) -> bool:
    op_str = str(operator_str).strip().lower()
    left_coerced, right_coerced = _coerce_pair(left, right)

    if op_str in ("==", "="):
        return left_coerced == right_coerced
    elif op_str == "!=":
        return left_coerced != right_coerced
    elif op_str == ">":
        return left_coerced > right_coerced
    elif op_str == "<":
        return left_coerced < right_coerced
    elif op_str == ">=":
        return left_coerced >= right_coerced
    elif op_str == "<=":
        return left_coerced <= right_coerced
    elif op_str == "in":
        return left in right
    elif op_str == "not in":
        return left not in right
    elif op_str == "contains":
        return right in left
    elif op_str == "is":
        return left is right
    elif op_str == "is not":
        return left is not right
    else:
        raise ValueError(f"Unsupported operator '{operator_str}' in condition step.")


@register_step_type("condition")
async def handle_condition(step: dict) -> dict:
    config = step.get("config")
    if config is None or not isinstance(config, dict) or not config:
        if isinstance(step, dict) and (step.get("expression") is not None or step.get("operator") is not None):
            config = step
        else:
            raise ValueError("Condition step requires 'expression' or structured ('operator', 'left', 'right') config.")

    expression = config.get("expression") if "expression" in config else step.get("expression")
    operator_val = config.get("operator") if "operator" in config else step.get("operator")

    if expression is not None:
        if isinstance(expression, bool):
            met = expression
        elif isinstance(expression, str) and expression.strip() != "":
            expr_str = expression.strip()
            try:
                tree = ast.parse(expr_str, mode="eval")
                met = bool(safe_eval_node(tree))
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Condition expression evaluation failed: {str(e)}",
                }
        else:
            raise ValueError("Condition step 'expression' must be a non-empty string or boolean.")
    elif operator_val is not None:
        left = config.get("left") if "left" in config else step.get("left")
        right = config.get("right") if "right" in config else step.get("right")
        try:
            met = bool(evaluate_structured(left, operator_val, right))
        except Exception as e:
            return {
                "success": False,
                "error": f"Condition structured evaluation failed: {str(e)}",
            }
    else:
        raise ValueError("Condition step requires 'expression' or 'operator'/'left'/'right' in config.")

    skip_downstream = not met
    return {
        "success": True,
        "result": met,
        "condition_met": met,
        "response": met,
        "skip_downstream": skip_downstream,
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


def _mark_descendants_skipped(failed_id: str, downstream: dict, results: dict, reason: str = None) -> None:
    if reason is None:
        reason = f"Skipped due to failure in upstream step '{failed_id}'"
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
                    "error": reason,
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
                if res.get("skip_downstream"):
                    _mark_descendants_skipped(
                        step_id,
                        downstream,
                        results,
                        reason=f"Skipped because conditional step '{step_id}' evaluated to False",
                    )
            elif results[step_id]["status"] == StepStatus.FAILED:
                _mark_descendants_skipped(step_id, downstream, results)

    has_failed = any(
        res.get("status") == StepStatus.FAILED
        for res in results.values()
    )
    overall_success = not has_failed
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