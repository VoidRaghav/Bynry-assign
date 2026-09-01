import re
from dataclasses import replace

import pytest
from playwright.sync_api import expect

from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage

pytestmark = pytest.mark.web


@pytest.mark.smoke
@pytest.mark.parametrize("role", ["admin", "manager", "employee"])
def test_every_role_lands_on_its_dashboard(signed_in_page, environment, tenant, role):
    dashboard = DashboardPage(signed_in_page(tenant, role), environment, tenant).open()

    expect(dashboard.welcome_message).to_contain_text(tenant.user(role).display_name)
    expect(dashboard.tenant_badge).to_have_text(tenant.label)


def test_wrong_password_keeps_the_user_on_login(fresh_page, environment, tenant):
    user = replace(tenant.user("admin"), password="not-the-real-one")

    with pytest.raises(AssertionError, match="login rejected"):
        LoginPage(fresh_page, environment, tenant).login_as(user)

    expect(fresh_page).to_have_url(re.compile(r"/login"))


@pytest.mark.mobile
def test_dashboard_is_usable_on_a_handset(signed_in_page, environment, tenant):
    page = signed_in_page(tenant, "employee", viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    dashboard = DashboardPage(page, environment, tenant).open()

    expect(dashboard.welcome_message).to_be_visible()
    board = dashboard.open_projects()
    expect(board.testid("projects-list")).to_be_visible()
