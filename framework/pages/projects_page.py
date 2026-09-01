from playwright.sync_api import expect

from core.base_page import BasePage
from pages.project_detail_page import ProjectDetailPage

PROJECTS_REQUEST = "/api/v1/projects"


class ProjectsPage(BasePage):
    path = "/projects"
    ready_test_id = "projects-list"

    @property
    def cards(self):
        return self.testid("project-card")

    @property
    def empty_state(self):
        return self.testid("projects-empty")

    # waiting on the response instead of a spinner handles the debounce too
    def search(self, term):
        with self.page.expect_response(
            lambda response: PROJECTS_REQUEST in response.url and response.status == 200,
            timeout=self.environment.expect_timeout_ms,
        ):
            self.testid("project-search").fill(term)
        return self

    def card(self, name):
        return self.cards.filter(has_text=name)

    # a write through the API can lag the UI read, so reload a bounded number of times
    def wait_for_project(self, name, attempts=3):
        for attempt in range(attempts):
            self.search(name)
            if self.card(name).count():
                break
            if attempt < attempts - 1:
                self.page.reload()
                self.wait_until_ready()
        card = self.card(name)
        expect(card).to_be_visible(timeout=self.environment.expect_timeout_ms)
        return card

    def open_project(self, name):
        self.wait_for_project(name).click()
        return ProjectDetailPage(self.page, self.environment, self.tenant).wait_until_ready()

    def visible_project_names(self):
        expect(self.testid("projects-skeleton")).to_have_count(0)
        self.cards.first.or_(self.empty_state).wait_for(
            state="visible", timeout=self.environment.expect_timeout_ms
        )
        if self.empty_state.is_visible():
            return []
        return [name.strip() for name in self.cards.get_by_test_id("project-name").all_inner_texts()]
