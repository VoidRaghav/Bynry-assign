import json
from functools import lru_cache
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@lru_cache(maxsize=None)
def load(name):
    with open(FIXTURE_DIR / f"{name}.json") as handle:
        return json.load(handle)


def payload_cases(kind):
    cases = []
    for entry in load("project_payloads")[kind]:
        payload = dict(entry["payload"])
        # a few cases need a long name, keeping the json readable
        if "repeat_name" in payload:
            payload["name"] = payload["name"] * payload.pop("repeat_name")
        cases.append((entry["case"], payload, entry.get("expected_status")))
    return cases
