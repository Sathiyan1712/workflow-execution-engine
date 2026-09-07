import time
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_context_passing():
    payload = {
        "steps": [
            {
                "id": "Auth",
                "type": "shell",
                "config": {
                    "command": "echo admin_token_999"
                }
            },
            {
                "id": "Fetch",
                "type": "rest",
                "config": {
                    "url": "https://httpbin.org/get?auth=${{ steps.Auth.stdout }}",
                    "method": "GET"
                },
                "depends_on": ["Auth"]
            },
            {
                "id": "Report",
                "type": "shell",
                "config": {
                    "command": "echo Token was ${{ steps.Fetch.response.args.auth }}"
                },
                "depends_on": ["Fetch"]
            }
        ]
    }

    res = client.post("/workflows", json=payload)
    assert res.status_code == 202
    wid = res.json()["workflow_id"]

    time.sleep(1)

    get_res = client.get(f"/workflows/{wid}")
    data = get_res.json()
    print("Workflow Status:", data["status"])
    print("Report stdout:", data["results"]["Report"]["stdout"])
    assert data["status"] == "COMPLETED"
    assert "admin_token_999" in data["results"]["Report"]["stdout"]
    print("FastAPI Context Variable Passing with Nested Config Passed!")


def test_api_condition_routing():
    payload = {
        "steps": [
            {
                "id": "GetCode",
                "type": "shell",
                "config": {
                    "command": "echo 200"
                }
            },
            {
                "id": "CheckOK",
                "type": "condition",
                "config": {
                    "expression": "${{ steps.GetCode.stdout }} == 200"
                },
                "depends_on": ["GetCode"]
            },
            {
                "id": "SuccessPath",
                "type": "shell",
                "config": {
                    "command": "echo All systems operational"
                },
                "depends_on": ["CheckOK"]
            },
            {
                "id": "CheckFailed",
                "type": "condition",
                "config": {
                    "expression": "${{ steps.GetCode.stdout }} != 200"
                },
                "depends_on": ["GetCode"]
            },
            {
                "id": "RemediationPath",
                "type": "shell",
                "config": {
                    "command": "echo Triggering recovery"
                },
                "depends_on": ["CheckFailed"]
            }
        ]
    }

    res = client.post("/workflows", json=payload)
    assert res.status_code == 202
    wid = res.json()["workflow_id"]

    time.sleep(1)

    get_res = client.get(f"/workflows/{wid}")
    data = get_res.json()
    print("\nConditional API Workflow Status:", data["status"])
    assert data["status"] == "COMPLETED"
    assert data["results"]["CheckOK"]["condition_met"] is True
    assert data["results"]["SuccessPath"]["status"] == "SUCCESS"
    assert data["results"]["CheckFailed"]["condition_met"] is False
    assert data["results"]["RemediationPath"]["status"] == "SKIPPED"
    print("FastAPI Condition Branch Routing Passed!")


def test_api_dashboard_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    assert "Workflow Execution Engine | Visual DAG Dashboard" in res.text
    assert "vis-network" in res.text
    print("Dashboard GET / endpoint returned 200 OK with UI HTML!")


def test_api_presentation_endpoint():
    res = client.get("/presentation")
    assert res.status_code == 200
    assert "Enterprise Agentic Workflow Orchestrator | Presentation" in res.text
    assert "Nutanix PS-4" in res.text
    print("Presentation GET /presentation endpoint returned 200 OK with slide deck!")


if __name__ == "__main__":
    test_api_dashboard_endpoint()
    test_api_presentation_endpoint()
    test_api_context_passing()
    test_api_condition_routing()

