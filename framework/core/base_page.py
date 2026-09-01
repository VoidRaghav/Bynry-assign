from playwright.sync_api import expect

COMPACT_BREAKPOINT = 768


class BasePage:
    path = "/"
    ready_test_id = None

    def __init__(self, page, environment, tenant):
        self.page = page
        self.environment = environment
        self.tenant = tenant

    @property
    def url(self):
        return self.environment.web_url(self.tenant, self.path)

    def open(self):
        self.page.goto(self.url, wait_until="domcontentloaded", timeout=self.environment.timeout_for(self.tenant))
        return self.wait_until_ready()

    def wait_until_ready(self):
        if self.ready_test_id:
            expect(self.testid(self.ready_test_id)).to_be_visible(timeout=self.environment.expect_timeout_ms)
        return self

    def testid(self, name):
        return self.page.get_by_test_id(name)

    def is_compact_layout(self):
        viewport = self.page.viewport_size or {"width": COMPACT_BREAKPOINT}
        return viewport["width"] < COMPACT_BREAKPOINT

    # below the breakpoint the links live behind the drawer
    def go_to(self, section):
        if self.is_compact_layout():
            toggle = self.testid("nav-toggle")
            expect(toggle).to_be_visible()
            toggle.click()
        self.testid(f"nav-{section}").click()
        return self

    def toast_text(self):
        toast = self.testid("toast")
        expect(toast).to_be_visible()
        return toast.inner_text()
