import re

import pyotp
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.web

DASHBOARD_ROUTE = re.compile(r"/dashboard(/|\?|$)")


def sign_in(page, user):
    page.goto(f"{user.base_url}/login", wait_until="domcontentloaded")

    email_field = page.get_by_test_id("email")
    # form paints before it hydrates, so wait for a field that can actually take input
    expect(email_field).to_be_editable()
    email_field.fill(user.email)
    page.get_by_test_id("password").fill(user.password)
    page.get_by_test_id("login-btn").click()

    otp_field = page.get_by_test_id("verification-code")
    error_banner = page.get_by_test_id("login-error")
    welcome = page.get_by_test_id("welcome-message")
    # three outcomes are possible after submit, so race them instead of assuming the happy path
    otp_field.or_(error_banner).or_(welcome).first.wait_for(state="visible")

    if error_banner.is_visible():
        pytest.fail(f"login was rejected for {user.email}: {error_banner.inner_text()}")

    if otp_field.is_visible():
        if not user.totp_secret:
            pytest.fail(f"{user.email} was challenged for 2FA but no TOTP secret is configured")
        otp_field.fill(pyotp.TOTP(user.totp_secret).now())
        page.get_by_test_id("verify-btn").click()

    # never compare page.url straight after a click, the redirect chain is still running
    page.wait_for_url(DASHBOARD_ROUTE)


def test_admin_lands_on_dashboard(stable_page, user_for):
    user = user_for("admin", "company1")

    sign_in(stable_page, user)

    expect(stable_page).to_have_url(DASHBOARD_ROUTE)
    # is_visible() is a snapshot with no retry, expect() polls until the widget renders
    expect(stable_page.get_by_test_id("welcome-message")).to_be_visible()
    expect(stable_page.get_by_test_id("tenant-badge")).to_have_text(user.company_label)


def test_tenant_only_sees_its_own_projects(stable_page, user_for):
    user = user_for("employee", "company2")

    sign_in(stable_page, user)
    stable_page.get_by_test_id("nav-projects").click()

    cards = stable_page.get_by_test_id("project-card")
    # cards stream in after the dashboard renders, so anchor on the loaded state first
    expect(stable_page.get_by_test_id("projects-skeleton")).to_have_count(0)
    # an empty list used to make this test pass without checking anything
    expect(cards.first).to_be_visible()

    foreign_cards = cards.filter(has_not_text=user.company_label)
    expect(foreign_cards).to_have_count(0)
