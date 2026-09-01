import os
import random
import string
from datetime import datetime, timezone

RUN_ID = os.environ.get("TEST_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def unique_token(size=5):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=size))


def project_payload(name=None, members=(), description=None):
    return {
        "name": name or f"qa-{RUN_ID}-{unique_token()}",
        "description": description or f"automated check from run {RUN_ID}",
        "team_members": list(members),
    }
