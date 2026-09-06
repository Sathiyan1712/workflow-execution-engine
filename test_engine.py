from engine import run_workflow
import json

def show(title, steps):
    print(f"\n=== {title} ===")
    result = run_workflow(steps)
    print(json.dumps(result, indent=2))


# 1. Linear: A -> B -> C
linear = [
    {"id": "A", "type": "shell", "command": "echo Step A running"},
    {"id": "B", "type": "shell", "command": "echo Step B running", "depends_on": ["A"]},
    {"id": "C", "type": "shell", "command": "echo Step C running", "depends_on": ["B"]},
]
show("Linear workflow", linear)

# 2. Branching: A -> B and A -> C
branching = [
    {"id": "A", "type": "shell", "command": "echo Setup done"},
    {"id": "B", "type": "shell", "command": "echo Branch B", "depends_on": ["A"]},
    {"id": "C", "type": "shell", "command": "echo Branch C", "depends_on": ["A"]},
]
show("Branching workflow", branching)

# 3. Deliberate failure: B fails, C should never run
failing = [
    {"id": "A", "type": "shell", "command": "echo Step A ok"},
    {"id": "B", "type": "shell", "command": "exit 1", "depends_on": ["A"]},
    {"id": "C", "type": "shell", "command": "echo Should not print", "depends_on": ["B"]},
]
show("Failing workflow", failing)

# 4. REST step
rest_example = [
    {"id": "A", "type": "rest", "url": "https://httpbin.org/get", "method": "GET"},
]
show("REST workflow", rest_example)