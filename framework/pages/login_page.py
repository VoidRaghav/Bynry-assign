import re

from playwright.sync_api import expect

from core.base_page import BasePage
from pages.dashboard_page import DashboardPage
from utils.totp import code_for

DASHBOARD_ROUTE = re.compile(r"/dashboard(/|\?|$)")


class LoginPage(BasePage):
    path = "/login"
    ready_test_id = "login-form"

    def login_as(self, user):
        if not user.has_credentials:
            raise AssertionError(f"no password is configured for {user.email}")

        self.open()
        email_field = self.testid("email")
        expect(email_field).to_be_editable()
        email_field.fill(user.email)
        self.testid("password").fill(user.password)
        self.testid("login-btn").click()
        self.resolve_challenge(user)

        self.page.wait_for_url(DASHBOARD_ROUTE, timeout=self.environment.timeout_for(self.tenant))
        return DashboardPage(self.page, self.environment, self.tenant).wait_until_ready()

    def resolve_challenge(self, user):
        otp_field = self.testid("verification-code")
        error_banner = self.testid("login-error")
        welcome = self.testid("welcome-message")

        otp_field.or_(error_banner).or_(welcome).first.wait_for(
            state="visible", timeout=self.environment.expect_timeout_ms
        )

        if error_banner.is_visible():
            raise AssertionError(f"login rejected for {user.email}: {error_banner.inner_text()}")

        if otp_field.is_visible():
            otp_field.fill(code_for(user.totp_secret))
            self.testid("verify-btn").click()
