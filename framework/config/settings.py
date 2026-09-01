import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent
DEFAULT_ENVIRONMENT = "staging"


@dataclass(frozen=True)
class User:
    role: str
    email: str
    password: str
    totp_secret: str
    display_name: str

    @property
    def has_credentials(self):
        return bool(self.password)


@dataclass(frozen=True)
class Tenant:
    key: str
    id: str
    subdomain: str
    label: str
    plan: str
    cold_start: bool
    users: dict

    def user(self, role):
        if role not in self.users:
            raise KeyError(f"tenant {self.key} has no {role} user configured")
        return self.users[role]


@dataclass(frozen=True)
class Environment:
    name: str
    domain: str
    api_base_url: str
    web_url_template: str
    action_timeout_ms: int
    navigation_timeout_ms: int
    expect_timeout_ms: int
    api_timeout_s: int
    block_third_party: bool

    def web_url(self, tenant, path=""):
        root = self.web_url_template.format(subdomain=tenant.subdomain, domain=self.domain)
        return f"{root}/{path.lstrip('/')}" if path else root

    def timeout_for(self, tenant):
        return self.navigation_timeout_ms * 2 if tenant.cold_start else self.navigation_timeout_ms


def _read(name):
    with open(CONFIG_DIR / name) as handle:
        return yaml.safe_load(handle)


@lru_cache(maxsize=None)
def environment(name=None):
    name = name or os.environ.get("TEST_ENV", DEFAULT_ENVIRONMENT)
    raw = _read("environments.yaml")
    if name not in raw or name == "defaults":
        raise KeyError(f"unknown environment {name}, choose from {sorted(k for k in raw if k != 'defaults')}")
    values = dict(raw[name])
    values["api_base_url"] = os.environ.get("API_BASE_URL", values["api_base_url"])
    values["domain"] = os.environ.get("WEB_DOMAIN", values["domain"])
    return Environment(name=name, **values)


@lru_cache(maxsize=None)
def tenants():
    loaded = {}
    for key, raw in _read("tenants.yaml").items():
        users = {
            role: User(
                role=role,
                email=spec["email"],
                password=os.environ.get(spec.get("password_env", ""), ""),
                totp_secret=os.environ.get(spec.get("totp_secret_env", ""), ""),
                display_name=spec["display_name"],
            )
            for role, spec in raw["users"].items()
        }
        loaded[key] = Tenant(
            key=key,
            id=raw["id"],
            subdomain=raw["subdomain"],
            label=raw["label"],
            plan=raw.get("plan", "growth"),
            cold_start=raw.get("cold_start", False),
            users=users,
        )
    return loaded


def tenant(key):
    registry = tenants()
    if key not in registry:
        raise KeyError(f"unknown tenant {key}, choose from {sorted(registry)}")
    return registry[key]


@lru_cache(maxsize=None)
def device_suite(name="smoke"):
    suites = _read("devices.yaml")
    if name not in suites:
        raise KeyError(f"unknown device suite {name}, choose from {sorted(suites)}")
    return suites[name]
