import re
import warnings

import pytest
from playwright.sync_api import expect

from config import settings
from core import auth
from core.api_client import ApiClient
from core.browser_factory import browserstack_ready, connect_browserstack, report_status
from data.ledger import ResourceLedger
from pages.login_page import LoginPage

NOISY_HOSTS = re.compile(r"(segment|googletagmanager|google-analytics|hotjar|intercom|fullstory)\.(com|io)")
EMULATION_KEYS = ("viewport", "user_agent", "device_scale_factor", "is_mobile", "has_touch")


def pytest_addoption(parser):
    group = parser.getgroup("workflowpro")
    group.addoption("--env", default=None, help="environment key from config/environments.yaml")
    group.addoption("--device-suite", default="smoke", help="device suite from config/devices.yaml")
    group.addoption("--tenant", default="company1", help="default tenant key for single tenant tests")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, f"report_{call.when}", outcome.get_result())


@pytest.fixture(scope="session")
def environment(pytestconfig):
    active = settings.environment(pytestconfig.getoption("--env"))
    expect.set_options(timeout=active.expect_timeout_ms)
    return active


@pytest.fixture(scope="session")
def tenants():
    return settings.tenants()


@pytest.fixture
def tenant(tenants, pytestconfig):
    return tenants[pytestconfig.getoption("--tenant")]


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, environment):
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-US",
        "timezone_id": "UTC",
        "reduced_motion": "reduce",
    }


def emulation(playwright, device):
    descriptor = playwright.devices[device["emulate"]]
    return {key: descriptor[key] for key in EMULATION_KEYS if key in descriptor}


def prepare(page, environment):
    page.set_default_timeout(environment.action_timeout_ms)
    page.set_default_navigation_timeout(environment.navigation_timeout_ms)
    if environment.block_third_party:
        page.context.route(NOISY_HOSTS, lambda route: route.abort())
    return page


@pytest.fixture
def api_for(environment):
    def _api_for(tenant, role="admin"):
        user = tenant.user(role)
        if not user.has_credentials:
            pytest.skip(f"no password configured for {tenant.key}/{role}")
        return ApiClient(environment, tenant, auth.api_token(environment, tenant, user))

    return _api_for


@pytest.fixture
def ledger():
    tracker = ResourceLedger()
    yield tracker
    failures = tracker.release()
    if failures:
        warnings.warn(f"test data was left behind: {'; '.join(failures)}")


@pytest.fixture
def signed_in_page(browser, environment, browser_context_args):
    contexts = []

    def _signed_in_page(tenant, role="admin", **context_overrides):
        user = tenant.user(role)
        if not user.has_credentials:
            pytest.skip(f"no password configured for {tenant.key}/{role}")

        # log in once per tenant and role, then hand every test a ready context
        state_file = auth.state_path(environment, tenant, user)
        if not auth.state_is_fresh(state_file):
            state_file.parent.mkdir(parents=True, exist_ok=True)
            bootstrap = browser.new_context(**browser_context_args)
            LoginPage(prepare(bootstrap.new_page(), environment), environment, tenant).login_as(user)
            bootstrap.storage_state(path=str(state_file))
            bootstrap.close()

        context = browser.new_context(
            storage_state=str(state_file), **{**browser_context_args, **context_overrides}
        )
        contexts.append(context)
        return prepare(context.new_page(), environment)

    yield _signed_in_page
    for context in contexts:
        context.close()


@pytest.fixture
def mobile_page(playwright, browser, environment, pytestconfig, request):
    remote_sessions = []
    local_contexts = []

    def _mobile_page(tenant, role="admin", device=None):
        user = tenant.user(role)
        if not user.has_credentials:
            pytest.skip(f"no password configured for {tenant.key}/{role}")

        suite = settings.device_suite(pytestconfig.getoption("--device-suite"))
        target = device or next(item for item in suite if item.get("real_mobile"))

        if browserstack_ready():
            remote = connect_browserstack(playwright, target, request.node.name)
            context = remote.new_context()
            page = prepare(context.new_page(), environment)
            remote_sessions.append((remote, page))
        else:
            # no BrowserStack keys, so the step still runs on an emulated handset locally
            warnings.warn(f"{target['name']} is emulated, real device coverage needs BrowserStack credentials")
            context = browser.new_context(**emulation(playwright, target))
            local_contexts.append(context)
            page = prepare(context.new_page(), environment)

        LoginPage(page, environment, tenant).login_as(user)
        return page

    yield _mobile_page

    report = getattr(request.node, "report_call", None)
    passed = report is not None and report.passed
    for remote, page in remote_sessions:
        report_status(page, passed, "assertions passed" if passed else f"{request.node.name} failed")
        remote.close()
    for context in local_contexts:
        context.close()


@pytest.fixture
def fresh_page(page, environment):
    return prepare(page, environment)
