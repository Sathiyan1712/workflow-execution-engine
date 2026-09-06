import asyncio
import json
import os
from unittest.mock import patch
import httpx
from engine import (
    run_workflow,
    StepStatus,
    WorkflowStatus,
    interpolate_value,
    interpolate_step_config,
    handle_ai,
)


def show(title, steps):
    print(f"\n=== {title} ===")
    result = asyncio.run(run_workflow(steps))
    print(json.dumps(result, indent=2))
    return result


def main():
    # 0. Unit verification of interpolate_value and interpolate_step_config with non-templated inputs
    ctx = {"steps": {}}
    assert interpolate_value("https://example.com/api/v1", ctx) == "https://example.com/api/v1"
    assert interpolate_value("echo normal command", ctx) == "echo normal command"
    assert interpolate_value({"key": "val", "nested": [1, "two", {"three": "3"}]}, ctx) == {
        "key": "val", "nested": [1, "two", {"three": "3"}]
    }
    assert interpolate_value(None, ctx) is None

    test_step = {
        "id": "step_non_templated",
        "type": "shell",
        "config": {
            "command": "echo plain_command",
            "timeout": 45,
        }
    }
    interpolated_test_step = interpolate_step_config(test_step, ctx)
    assert interpolated_test_step["config"]["command"] == "echo plain_command"
    assert interpolated_test_step["config"]["timeout"] == 45

    # 1. Linear: A -> B -> C
    linear = [
        {"id": "A", "type": "shell", "config": {"command": "echo Step A running"}},
        {"id": "B", "type": "shell", "config": {"command": "echo Step B running"}, "depends_on": ["A"]},
        {"id": "C", "type": "shell", "config": {"command": "echo Step C running"}, "depends_on": ["B"]},
    ]
    res_linear = show("Linear workflow (Nested config syntax)", linear)
    assert res_linear["status"] == WorkflowStatus.COMPLETED
    assert res_linear["results"]["A"]["status"] == StepStatus.SUCCESS
    assert res_linear["results"]["A"]["success"] is True
    assert res_linear["results"]["A"]["stdout"] == "Step A running"
    assert res_linear["results"]["C"]["status"] == StepStatus.SUCCESS

    # 2. Parallel Branching: A -> (B, C) -> D
    branching = [
        {"id": "A", "type": "shell", "config": {"command": "echo Step A initialized"}},
        {"id": "B", "type": "shell", "config": {"cmd": "echo Branch B running with cmd key"}, "depends_on": ["A"]},
        {"id": "C", "type": "shell", "config": {"command": "echo Branch C running"}, "depends_on": ["A"]},
        {"id": "D", "type": "shell", "config": {"command": "echo Step D joined"}, "depends_on": ["B", "C"]},
    ]
    res_branching = show("Parallel Branching workflow (with 'cmd' fallback)", branching)
    assert res_branching["status"] == WorkflowStatus.COMPLETED
    assert res_branching["results"]["B"]["status"] == StepStatus.SUCCESS
    assert "Branch B running with cmd key" in res_branching["results"]["B"]["stdout"]
    assert res_branching["results"]["C"]["status"] == StepStatus.SUCCESS
    assert res_branching["results"]["D"]["status"] == StepStatus.SUCCESS

    # 3. Granular Failure & Non-Empty Error Fallback
    failing_with_independent = [
        {"id": "FailStep", "type": "shell", "config": {"command": "exit /b 1"}},
        {"id": "SkippedStep", "type": "shell", "config": {"command": "echo Should not run"}, "depends_on": ["FailStep"]},
        {"id": "IndepA", "type": "shell", "config": {"command": "echo Independent branch A"}},
        {"id": "IndepB", "type": "shell", "config": {"command": "echo Independent branch B"}, "depends_on": ["IndepA"]},
    ]
    res_failing = show("Granular Failure & Independent Branch workflow", failing_with_independent)
    assert res_failing["status"] == WorkflowStatus.FAILED
    assert res_failing["results"]["FailStep"]["status"] == StepStatus.FAILED
    assert res_failing["results"]["FailStep"]["success"] is False
    assert res_failing["results"]["FailStep"]["error"] == "Command failed with exit code 1"
    assert res_failing["results"]["SkippedStep"]["status"] == StepStatus.SKIPPED
    assert res_failing["results"]["IndepA"]["status"] == StepStatus.SUCCESS
    assert res_failing["results"]["IndepB"]["status"] == StepStatus.SUCCESS

    # 4. Strict Input Validation (Shell, REST, AI)
    validation_failures = [
        {"id": "InvalidShell", "type": "shell", "config": {}},
        {"id": "InvalidRest", "type": "rest", "config": {"url": None}},
        {"id": "InvalidAI", "type": "ai", "config": {}},
    ]
    res_validation = show("Strict Input Validation Failures", validation_failures)
    assert res_validation["status"] == WorkflowStatus.FAILED
    assert res_validation["results"]["InvalidShell"]["status"] == StepStatus.FAILED
    assert res_validation["results"]["InvalidShell"]["error"] == "Shell step requires a 'command' string in config."
    assert res_validation["results"]["InvalidRest"]["status"] == StepStatus.FAILED
    assert res_validation["results"]["InvalidRest"]["error"] == "REST step requires a 'url' string in config."
    assert res_validation["results"]["InvalidAI"]["status"] == StepStatus.FAILED
    assert res_validation["results"]["InvalidAI"]["error"] == "AI step requires a 'prompt' string in config."

    # 5. Standard Non-Templated REST Step
    rest_standard = [
        {
            "id": "GetStaticURL",
            "type": "rest",
            "config": {
                "url": "https://httpbin.org/get",
                "method": "GET",
            }
        }
    ]
    res_rest = show("Standard Non-Templated REST step", rest_standard)
    assert res_rest["status"] == WorkflowStatus.COMPLETED
    assert res_rest["results"]["GetStaticURL"]["status"] == StepStatus.SUCCESS

    # 6. Context Passing & Variable Interpolation across Nested config blocks
    context_pipeline = [
        {
            "id": "GenerateUser",
            "type": "shell",
            "config": {
                "command": "echo alice"
            }
        },
        {
            "id": "FetchUserData",
            "type": "rest",
            "config": {
                "url": "https://httpbin.org/get?username=${{ steps.GenerateUser.stdout }}",
                "method": "GET",
            },
            "depends_on": ["GenerateUser"],
        },
        {
            "id": "ConsumeUserData",
            "type": "shell",
            "config": {
                "command": "echo Processed user ${{ steps.FetchUserData.response.args.username }} with status ${{ steps.FetchUserData.status_code }}",
            },
            "depends_on": ["FetchUserData"],
        },
    ]
    res_context = show("Context Data Passing & Variable Interpolation (Nested config)", context_pipeline)
    assert res_context["status"] == WorkflowStatus.COMPLETED
    assert res_context["results"]["GenerateUser"]["status"] == StepStatus.SUCCESS
    assert res_context["results"]["FetchUserData"]["status"] == StepStatus.SUCCESS
    assert res_context["results"]["ConsumeUserData"]["status"] == StepStatus.SUCCESS
    assert "alice" in res_context["results"]["ConsumeUserData"]["stdout"]
    assert "200" in res_context["results"]["ConsumeUserData"]["stdout"]

    # 7. Missing Template Variable Error Handling & Cascading Skip
    missing_var_pipeline = [
        {
            "id": "Step1",
            "type": "shell",
            "config": {
                "command": "echo Step 1 OK"
            }
        },
        {
            "id": "Step2_BadVar",
            "type": "shell",
            "config": {
                "command": "echo ${{ steps.Step1.non_existent_key }}"
            },
            "depends_on": ["Step1"],
        },
        {
            "id": "Step3_Skipped",
            "type": "shell",
            "config": {
                "command": "echo Should never run"
            },
            "depends_on": ["Step2_BadVar"],
        },
    ]
    res_missing = show("Missing Variable Template Error Handling", missing_var_pipeline)
    assert res_missing["status"] == WorkflowStatus.FAILED
    assert res_missing["results"]["Step1"]["status"] == StepStatus.SUCCESS
    assert res_missing["results"]["Step2_BadVar"]["status"] == StepStatus.FAILED
    assert "Variable substitution error" in res_missing["results"]["Step2_BadVar"]["error"]
    assert res_missing["results"]["Step3_Skipped"]["status"] == StepStatus.SKIPPED

    # 8. AI Node Integration & Structured JSON Parsing Test
    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": json.dumps({"decision": "APPROVE", "score": 98, "reason": "Low risk"})}
                    ]
                }
            }
        ]
    }

    class MockResponse:
        status_code = 200
        text = json.dumps(mock_gemini_response)

        def json(self):
            return mock_gemini_response

    async def mock_post(*args, **kwargs):
        return MockResponse()

    os.environ["GEMINI_API_KEY"] = "mock_gemini_key_123"
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        ai_pipeline = [
            {
                "id": "DataPrep",
                "type": "shell",
                "config": {
                    "command": "echo user_transaction_42"
                }
            },
            {
                "id": "AiEval",
                "type": "ai",
                "config": {
                    "prompt": "Evaluate transaction ${{ steps.DataPrep.stdout }}",
                    "response_format": "json"
                },
                "depends_on": ["DataPrep"]
            },
            {
                "id": "RouteAction",
                "type": "shell",
                "config": {
                    "command": "echo Decision: ${{ steps.AiEval.response.decision }} with score ${{ steps.AiEval.response.score }}"
                },
                "depends_on": ["AiEval"]
            }
        ]
        res_ai = show("AI Node Integration & Context Routing", ai_pipeline)
        assert res_ai["status"] == WorkflowStatus.COMPLETED
        assert res_ai["results"]["AiEval"]["status"] == StepStatus.SUCCESS
        assert res_ai["results"]["AiEval"]["response"]["decision"] == "APPROVE"
        assert res_ai["results"]["AiEval"]["response"]["score"] == 98
        assert "Decision: APPROVE with score 98" in res_ai["results"]["RouteAction"]["stdout"]

    print("\nAll workflow tests including AI node integration passed successfully!")


if __name__ == "__main__":
    main()