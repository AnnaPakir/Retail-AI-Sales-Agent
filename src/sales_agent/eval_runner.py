from __future__ import annotations

import json
from pathlib import Path

from .agent import SalesAgent
from .schemas import ChatRequest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def evaluate(cases_path: Path | None = None) -> tuple[int, int, list[str]]:
    path = cases_path or PROJECT_ROOT / "evals" / "cases.jsonl"
    agent = SalesAgent()
    passed = 0
    failures: list[str] = []
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    for index, case in enumerate(rows, start=1):
        session_id = f"eval-{index}"
        for setup_message in case.get("setup", []):
            agent.handle(ChatRequest(session_id=session_id, message=setup_message))
        response = agent.handle(ChatRequest(session_id=session_id, message=case["message"]))
        checks = [
            response.intent.value == case["expected_intent"],
            response.action.value == case["expected_action"],
        ]
        if "expected_tool" in case:
            checks.append(any(call.name == case["expected_tool"] for call in response.tool_calls))
        if "contains" in case:
            checks.append(case["contains"].casefold() in response.response.casefold())
        if all(checks):
            passed += 1
        else:
            failures.append(
                f"{case['id']}: got intent={response.intent.value}, "
                f"action={response.action.value}, "
                f"tools={[call.name for call in response.tool_calls]}, text={response.response!r}"
            )
    return passed, len(rows), failures


def main() -> None:
    passed, total, failures = evaluate()
    print(f"Policy evals: {passed}/{total} passed")
    for failure in failures:
        print(f"FAIL: {failure}")
    raise SystemExit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
