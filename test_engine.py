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

    # 9. JQ Transformation Node Test
    jq_pipeline = [
        {
            "id": "GeneratePayload",
            "type": "shell",
            "config": {
                "command": 'echo {"users": [{"name": "alice", "active": true}, {"name": "bob", "active": false}, {"name": "charlie", "active": true}]}'
            }
        },
        {
            "id": "FilterActiveUsers",
            "type": "jq",
            "config": {
                "query": "[.users[] | select(.active == true) | .name]",
                "data": "${{ steps.GeneratePayload.stdout }}"
            },
            "depends_on": ["GeneratePayload"]
        },
        {
            "id": "ReshapeSummary",
            "type": "jq",
            "config": {
                "query": "{active_count: length, active_list: .}",
                "data": "${{ steps.FilterActiveUsers.response }}"
            },
            "depends_on": ["FilterActiveUsers"]
        },
        {
            "id": "OutputResult",
            "type": "shell",
            "config": {
                "command": "echo Found ${{ steps.ReshapeSummary.response.active_count }} active users"
            },
            "depends_on": ["ReshapeSummary"]
        }
    ]
    res_jq = show("JQ Transformation Node Pipeline", jq_pipeline)
    assert res_jq["status"] == WorkflowStatus.COMPLETED
    assert res_jq["results"]["FilterActiveUsers"]["status"] == StepStatus.SUCCESS
    assert res_jq["results"]["FilterActiveUsers"]["response"] == ["alice", "charlie"]
    assert res_jq["results"]["ReshapeSummary"]["status"] == StepStatus.SUCCESS
    assert res_jq["results"]["ReshapeSummary"]["response"]["active_count"] == 2
    assert "Found 2 active users" in res_jq["results"]["OutputResult"]["stdout"]

    # 10. JQ Invalid Query Error Handling
    bad_jq_pipeline = [
        {
            "id": "BadJqStep",
            "type": "jq",
            "config": {
                "query": ".[invalid_syntax",
                "data": {"a": 1}
            }
        }
    ]
    res_bad_jq = show("JQ Invalid Syntax Error Handling", bad_jq_pipeline)
    assert res_bad_jq["status"] == WorkflowStatus.FAILED
    assert res_bad_jq["results"]["BadJqStep"]["status"] == StepStatus.FAILED
    assert "JQ transformation error" in res_bad_jq["results"]["BadJqStep"]["error"]

    # 10b. JQ Handling Quoted Shell JSON String Output
    quoted_jq_pipeline = [
        {
            "id": "ShellQuotedJSON",
            "type": "shell",
            "config": {
                "command": "echo '{\"nodes\": [{\"id\": \"worker-1\", \"cpu\": 92}, {\"id\": \"worker-2\", \"cpu\": 45}]}'"
            }
        },
        {
            "id": "FilterNodes",
            "type": "jq",
            "config": {
                "query": "[.nodes[] | select(.cpu > 80) | .id]",
                "data": "${{ steps.ShellQuotedJSON.stdout }}"
            },
            "depends_on": ["ShellQuotedJSON"]
        }
    ]
    res_quoted_jq = show("JQ Single-Quoted Raw JSON Shell Parsing", quoted_jq_pipeline)
    assert res_quoted_jq["status"] == WorkflowStatus.COMPLETED
    assert res_quoted_jq["results"]["FilterNodes"]["status"] == StepStatus.SUCCESS
    assert res_quoted_jq["results"]["FilterNodes"]["response"] == ["worker-1"]


    # 11. Condition Node: True Evaluation & Downstream Execution
    condition_true_pipeline = [
        {
            "id": "GetMetrics",
            "type": "shell",
            "config": {
                "command": "echo 85"
            }
        },
        {
            "id": "CheckThreshold",
            "type": "condition",
            "config": {
                "expression": "${{ steps.GetMetrics.stdout }} >= 80"
            },
            "depends_on": ["GetMetrics"]
        },
        {
            "id": "TriggerAlert",
            "type": "shell",
            "config": {
                "command": "echo High CPU alert triggered"
            },
            "depends_on": ["CheckThreshold"]
        }
    ]
    res_cond_true = show("Condition Node: True Evaluation & Execution", condition_true_pipeline)
    assert res_cond_true["status"] == WorkflowStatus.COMPLETED
    assert res_cond_true["results"]["CheckThreshold"]["status"] == StepStatus.SUCCESS
    assert res_cond_true["results"]["CheckThreshold"]["condition_met"] is True
    assert res_cond_true["results"]["CheckThreshold"]["skip_downstream"] is False
    assert res_cond_true["results"]["TriggerAlert"]["status"] == StepStatus.SUCCESS
    assert "High CPU alert triggered" in res_cond_true["results"]["TriggerAlert"]["stdout"]

    # 12. Condition Node: False Evaluation, Selective Branch Skipping, & Workflow COMPLETED
    condition_false_pipeline = [
        {
            "id": "GetStatus",
            "type": "shell",
            "config": {
                "command": "echo healthy"
            }
        },
        {
            "id": "CheckUnhealthy",
            "type": "condition",
            "config": {
                "expression": "'${{ steps.GetStatus.stdout }}' == 'unhealthy'"
            },
            "depends_on": ["GetStatus"]
        },
        {
            "id": "RestartService",
            "type": "shell",
            "config": {
                "command": "echo Restarting service..."
            },
            "depends_on": ["CheckUnhealthy"]
        },
        {
            "id": "NotifyOnRestart",
            "type": "shell",
            "config": {
                "command": "echo Notification sent"
            },
            "depends_on": ["RestartService"]
        },
        {
            "id": "IndependentTelemetry",
            "type": "shell",
            "config": {
                "command": "echo Telemetry logging OK"
            }
        }
    ]
    res_cond_false = show("Condition Node: False Evaluation & Selective Branch Deactivation", condition_false_pipeline)
    assert res_cond_false["status"] == WorkflowStatus.COMPLETED
    assert res_cond_false["success"] is True
    assert res_cond_false["results"]["CheckUnhealthy"]["status"] == StepStatus.SUCCESS
    assert res_cond_false["results"]["CheckUnhealthy"]["condition_met"] is False
    assert res_cond_false["results"]["CheckUnhealthy"]["skip_downstream"] is True
    assert res_cond_false["results"]["RestartService"]["status"] == StepStatus.SKIPPED
    assert "Skipped because conditional step 'CheckUnhealthy' evaluated to False" in res_cond_false["results"]["RestartService"]["error"]
    assert res_cond_false["results"]["NotifyOnRestart"]["status"] == StepStatus.SKIPPED
    assert res_cond_false["results"]["IndependentTelemetry"]["status"] == StepStatus.SUCCESS

    # 13. Condition Node: Structured Comparison Syntax (left, operator, right)
    structured_cond_pipeline = [
        {
            "id": "InitData",
            "type": "shell",
            "config": {
                "command": "echo CRITICAL_ERROR"
            }
        },
        {
            "id": "CondStructured",
            "type": "condition",
            "config": {
                "left": "${{ steps.InitData.stdout }}",
                "operator": "contains",
                "right": "ERROR"
            },
            "depends_on": ["InitData"]
        },
        {
            "id": "EscalateIncident",
            "type": "shell",
            "config": {
                "command": "echo Incident escalated successfully"
            },
            "depends_on": ["CondStructured"]
        }
    ]
    res_struct_cond = show("Condition Node: Structured Operands Syntax", structured_cond_pipeline)
    assert res_struct_cond["status"] == WorkflowStatus.COMPLETED
    assert res_struct_cond["results"]["CondStructured"]["status"] == StepStatus.SUCCESS
    assert res_struct_cond["results"]["CondStructured"]["condition_met"] is True
    assert res_struct_cond["results"]["EscalateIncident"]["status"] == StepStatus.SUCCESS

    # 14. Condition Node: Invalid Syntax / Unsafe Evaluation Handling
    bad_cond_pipeline = [
        {
            "id": "BadCondition",
            "type": "condition",
            "config": {
                "expression": "1 + * 2"
            }
        }
    ]
    res_bad_cond = show("Condition Node: Malformed Syntax Handling", bad_cond_pipeline)
    assert res_bad_cond["status"] == WorkflowStatus.FAILED
    assert res_bad_cond["results"]["BadCondition"]["status"] == StepStatus.FAILED
    assert "Condition expression evaluation failed" in res_bad_cond["results"]["BadCondition"]["error"]

    # 15. End-to-End AI Triage -> Condition Branching -> Remediation
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        e2e_pipeline = [
            {
                "id": "AnalyzeAlert",
                "type": "ai",
                "config": {
                    "prompt": "Evaluate alert payload",
                    "response_format": "json"
                }
            },
            {
                "id": "CheckApproval",
                "type": "condition",
                "config": {
                    "expression": "'${{ steps.AnalyzeAlert.response.decision }}' == 'APPROVE' and ${{ steps.AnalyzeAlert.response.score }} > 90"
                },
                "depends_on": ["AnalyzeAlert"]
            },
            {
                "id": "DeployPatch",
                "type": "shell",
                "config": {
                    "command": "echo Patch auto-deployed for decision ${{ steps.AnalyzeAlert.response.decision }}"
                },
                "depends_on": ["CheckApproval"]
            }
        ]
        res_e2e = show("End-to-End AI + Condition + Action Pipeline", e2e_pipeline)
        assert res_e2e["status"] == WorkflowStatus.COMPLETED
        assert res_e2e["results"]["CheckApproval"]["condition_met"] is True
        assert res_e2e["results"]["DeployPatch"]["status"] == StepStatus.SUCCESS
        assert "Patch auto-deployed for decision APPROVE" in res_e2e["results"]["DeployPatch"]["stdout"]

    print("\nAll workflow tests including AI, JQ, and Condition nodes passed successfully!")


if __name__ == "__main__":
    main()