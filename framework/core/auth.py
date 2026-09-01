import os
import time
from pathlib import Path

import requests

from core.errors import ApiError
from utils.totp import code_for

STATE_DIR = Path(os.environ.get("AUTH_STATE_DIR", ".auth"))
STATE_TTL_SECONDS = 30 * 60
_tokens = {}


def api_token(environment, tenant, user):
    key = (environment.name, tenant.key, user.role)
    if key in _tokens:
        return _tokens[key]

    url = f"{environment.api_base_url}/api/v1/auth/token"
    payload = {"email": user.email, "password": user.password}
    if user.totp_secret:
        payload["otp"] = code_for(user.totp_secret)

    response = requests.post(
        url,
        json=payload,
        headers={"X-Tenant-ID": tenant.id},
        timeout=environment.api_timeout_s,
    )
    if response.status_code != 200:
        raise ApiError("POST", url, response)

    _tokens[key] = response.json()["access_token"]
    return _tokens[key]


def state_path(environment, tenant, user):
    return STATE_DIR / f"{environment.name}-{tenant.key}-{user.role}.json"


# reusing a signed in state keeps the auth service from rate limiting CI
def state_is_fresh(path):
    return path.exists() and (time.time() - path.stat().st_mtime) < STATE_TTL_SECONDS


def forget_state(environment, tenant, user):
    path = state_path(environment, tenant, user)
    if path.exists():
        path.unlink()
    _tokens.pop((environment.name, tenant.key, user.role), None)
