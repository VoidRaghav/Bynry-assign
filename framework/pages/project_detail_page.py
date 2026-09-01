from core.base_page import BasePage


class ProjectDetailPage(BasePage):
    ready_test_id = "project-header"

    def __init__(self, page, environment, tenant, project_id=None):
        super().__init__(page, environment, tenant)
        self.project_id = project_id

    @property
    def path(self):
        return f"/projects/{self.project_id}" if self.project_id else "/projects"

    @property
    def title(self):
        return self.testid("project-title")

    @property
    def description(self):
        return self.testid("project-description")

    @property
    def status(self):
        return self.testid("project-status")

    @property
    def members(self):
        return self.testid("project-member")

    @property
    def access_denied(self):
        return self.testid("access-denied")
