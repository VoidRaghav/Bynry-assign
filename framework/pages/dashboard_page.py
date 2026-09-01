from core.base_page import BasePage
from pages.projects_page import ProjectsPage


class DashboardPage(BasePage):
    path = "/dashboard"
    ready_test_id = "welcome-message"

    @property
    def welcome_message(self):
        return self.testid("welcome-message")

    @property
    def tenant_badge(self):
        return self.testid("tenant-badge")

    def open_projects(self):
        self.go_to("projects")
        return ProjectsPage(self.page, self.environment, self.tenant).wait_until_ready()
