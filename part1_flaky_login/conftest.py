import os
import re

import pytest

DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
NOISY_HOSTS = re.compile(r"(segment|googletagmanager|google-analytics|hotjar|intercom|fullstory)\.(com|io)")
ACTION_TIMEOUT_MS = 15_000
NAVIGATION_TIMEOUT_MS = 45_000


class TestUser:
    def __init__(self, role, email, password, totp_secret, company_label, base_url):
        self.role = role
        self.email = email
        self.password = password
        self.totp_secret = totp_secret
        self.company_label = company_label
        self.base_url = base_url


@pytest.fixture(scope="session")
def base_url_template():
    return os.environ.get("WORKFLOWPRO_BASE_URL", "https://app.workflowpro.com").rstrip("/")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": DESKTOP_VIEWPORT,
        "locale": "en-US",
        "timezone_id": "UTC",
        "reduced_motion": "reduce",
    }


@pytest.fixture(autouse=True)
def stable_page(page):
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    page.context.route(NOISY_HOSTS, lambda route: route.abort())
    return page


@pytest.fixture
def user_for(base_url_template):
    def _user_for(role, company):
        prefix = f"{company.upper()}_{role.upper()}"
        email = os.environ.get(f"{prefix}_EMAIL")
        password = os.environ.get(f"{prefix}_PASSWORD")
        if not email or not password:
            pytest.skip(f"credentials for {prefix} are not present in the environment")
        return TestUser(
            role=role,
            email=email,
            password=password,
            totp_secret=os.environ.get(f"{prefix}_TOTP"),
            company_label=company.capitalize(),
            base_url=base_url_template.format(tenant=company),
        )

    return _user_for
