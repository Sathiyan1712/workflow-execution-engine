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

if __name__ == "__main__":
    test_api_context_passing()
