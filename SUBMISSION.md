# WorkFlow Pro, QA Automation Assessment

Author: Raghav
Scope: Part 1 (flaky test debugging), Part 2 (framework design), Part 3 (API + UI + mobile integration)

Everything in this repo is runnable code, not pseudocode. The framework in [framework/](framework/) is the design from Part 2, and the Part 3 test is written on top of it so the design has to hold up against a real test rather than a diagram.

The repo also ships a small mock of WorkFlow Pro, so the whole suite runs on any machine with `make demo`. The last run was **27 passed in 6.70s**, and the artifacts are in [reports/](reports/). Repo level documentation (test plan, case catalogue, data strategy) sits in [docs/](docs/).

## File map

| Part | What to look at | Why |
| --- | --- | --- |
| 1 | [part1_flaky_login/intern_original.py](part1_flaky_login/intern_original.py) | the original, kept so the fix can be diffed line by line |
| 1 | [part1_flaky_login/test_login_fixed.py](part1_flaky_login/test_login_fixed.py) | rewritten tests, short comments mark each fix |
| 1 | [part1_flaky_login/conftest.py](part1_flaky_login/conftest.py) | the fixtures that remove the leaks and pin the environment |
| 2 | [framework/](framework/) | full structure: config, core, pages, api, data, utils, tests |
| 2 | [framework/config/](framework/config/) | environments, tenants, device suites |
| 2 | [framework/conftest.py](framework/conftest.py) | fixture wiring, auth state reuse, BrowserStack session handling |
| 2 | [.github/workflows/tests.yml](.github/workflows/tests.yml) | pipeline shape: API gate, browser matrix, nightly device suite |
| 3 | [framework/tests/integration/test_project_creation_flow.py](framework/tests/integration/test_project_creation_flow.py) | the four step flow |
| 3 | [framework/tests/security/test_tenant_isolation.py](framework/tests/security/test_tenant_isolation.py) | isolation checks pulled out so they run on every build, not only inside the flow |
| all | [docs/TEST_PLAN.md](docs/TEST_PLAN.md), [docs/TEST_CASES.md](docs/TEST_CASES.md), [docs/TEST_DATA.md](docs/TEST_DATA.md), [docs/TESTING_APPROACH.md](docs/TESTING_APPROACH.md) | the plan, the case catalogue with ids, the data strategy and the approach |
| all | [reports/REPORT.md](reports/REPORT.md) | execution report from the run described above |
| all | [mock_app/server.py](mock_app/server.py) | the stand in product the demo run tests against |

## Running it

```bash
make install                    # dependencies and browsers
make demo                       # the whole suite against the bundled mock, writes reports/
cp .env.example .env            # passwords and BrowserStack keys live here, never in the repo
make smoke                      # pull request suite against a real environment
make web                        # chromium, firefox, webkit
make mobile                     # real devices through BrowserStack
make part1                      # the rewritten login tests on their own
```

---

# Part 1: Debugging the flaky login tests

## Approach

I read the two tests looking for three specific things: places where the test reads state that the app has not finished producing, places where a failure leaves the machine dirty for the next test, and places where the test can pass without proving anything. The second test has all three, and the third one is the dangerous one, because a test that passes green while checking nothing is worse than a flaky test. Nobody investigates a green build.

## 1. Everything that can cause an intermittent failure

| # | Problem | What actually happens | Fix in the rewrite |
| --- | --- | --- | --- |
| 1 | `assert page.url == ...` right after `click` | the click returns as soon as the event is dispatched, the redirect chain is still running, so the assertion reads the login URL | `page.wait_for_url(DASHBOARD_ROUTE)` |
| 2 | Exact URL string comparison | a trailing slash, `?first_login=true`, or a redirect to `/dashboard/overview` fails a correct login | regex on the route, not string equality |
| 3 | `is_visible()` used as an assertion | it is a snapshot with no retry, it returns False if the widget is one paint away | `expect(locator).to_be_visible()` which polls until the expect timeout |
| 4 | `.all()` on `.project-card` | it snapshots the list before the cards stream in, returns `[]`, the for loop body never runs and the test passes without asserting anything | wait for the first card, assert the loaded state, then assert no foreign card exists |
| 5 | No 2FA branch | accounts with 2FA land on the challenge screen, never on `/dashboard`, so the test fails only for those users or only from CI IPs | race the OTP field, the error banner and the dashboard with `or_()`, then fill a TOTP code |
| 6 | Typing before hydration | the login form paints before React attaches handlers, so `fill` gets wiped by the first render or `click` hits a dead button | `expect(email_field).to_be_editable()` before typing |
| 7 | Hardcoded credentials | a password rotation breaks every run, and a real password sits in source control | read from environment, skip cleanly when absent |
| 8 | `browser.close()` after the asserts | on failure it never runs, so every failing test leaks a Chromium process and the runner slowly starves | browser and context fixtures with teardown |
| 9 | No trace, video or screenshot | a CI failure gives you one assert line, so the flake never gets diagnosed and gets a rerun instead of a fix | `--tracing=retain-on-failure`, video and screenshot on failure |
| 10 | CSS class and id selectors | `.welcome-message` and `#login-btn` break on any styling refactor or CSS module hash | `data-testid` locators, role based where the semantics are stable |
| 11 | No viewport pinned | the CI default width can cross the responsive breakpoint, the nav collapses into a drawer and elements are genuinely hidden | fixed 1440x900 context, mobile tested on purpose instead of by accident |
| 12 | Third party scripts left live | analytics and chat widgets are uncached in CI, a slow beacon eats the timeout budget and sometimes overlays the button | abort requests to analytics and support hosts |
| 13 | One shared account across parallel workers | concurrent logins hit rate limits or invalidate each other's sessions, giving 429s and random logouts | one account per role, session state reused instead of logging in repeatedly |
| 14 | One global timeout for every tenant | company2 is a cold start tenant, its first request after idle is much slower than company1 | per tenant timeout multiplier in config |
| 15 | Runs against production data | the assertion depends on whatever data exists that day | seeded environment, tests create the data they assert on |
| 16 | No cleanup | leftovers from earlier runs can satisfy or break the tenant assertion | every created record is tracked and deleted in teardown |

The tenant assertion is also weak on its own terms. `"Company2" in project.text_content()` passes if a Company1 project happens to mention Company2 in its description, and it never proves that a Company1 project is absent. The rewrite asserts the negative case, which is the thing that actually matters for a multi tenant product.

## 2. Why this breaks in CI and not on the laptop

Every issue above is a race that the developer's machine happens to win.

- **Speed and contention.** A laptop has warm caches, a warm browser profile and spare CPU. A 2 vCPU runner downloads every asset cold and runs four workers on the same cores, so a redirect that takes 150ms locally takes two seconds in CI. The test does not wait, it just gets lucky locally.
- **Network shape.** CI traffic goes through more hops, sometimes a proxy, with cold DNS and TLS. Login is the slowest call in the flow and it is the one the test does not wait for.
- **Headless rendering.** Paint and layout timing differ from headed mode, and animations are not GPU accelerated, so the moment when the welcome widget becomes visible moves.
- **The risk engine sees a strange IP.** Shared CI egress addresses look unfamiliar to the auth service, which is exactly when a product triggers 2FA, a captcha or a rate limit. This is why the same credentials behave differently from a desk.
- **Parallel workers share the account.** Locally you run one test at a time. In CI two workers log in as `admin@company1.com` at once, and depending on the session policy one of them gets logged out mid test.
- **Environment defaults differ.** Containers run UTC and a default locale, so dates and greeting strings differ from a machine set to IST. Window size defaults differ too, which moves the responsive breakpoint.
- **Failure leaks compound.** Locally you close the terminal. In CI, leaked browsers from earlier failures push the runner into memory pressure, and the tests that run last look flaky when the real cause was a test that failed twenty minutes earlier.
- **Human retry bias.** A developer who sees a local failure reruns it without thinking. CI writes it down. The tests were probably always this flaky, CI is just the first place that kept score.

## 3. The fix

Full file: [part1_flaky_login/test_login_fixed.py](part1_flaky_login/test_login_fixed.py). The core of it:

```python
def sign_in(page, base_url, user):
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")

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
        otp_field.fill(pyotp.TOTP(user.totp_secret).now())
        page.get_by_test_id("verify-btn").click()

    # never compare page.url straight after a click, the redirect chain is still running
    page.wait_for_url(DASHBOARD_ROUTE)
```

Three decisions worth calling out:

- **Racing the three outcomes with `or_()` instead of a try/except or a sleep.** A 2FA challenge, a rejected login and a successful login are all legitimate states after submit. Waiting on whichever appears first turns a guess into a decision, and a wrong password now fails in five seconds with the banner text instead of timing out after thirty with nothing useful.
- **No `wait_for_timeout` anywhere.** A sleep is either too short (flaky) or too long (slow), and in CI it is usually both across the suite. Every wait in the rewrite is tied to a condition.
- **`pytest.fail` with the banner text, not a bare assert.** The point of the rewrite is that the next CI failure should be readable without reproducing it locally.

I did not add `--reruns` to the login tests. Reruns belong on the full regression suite as a safety net with the flake recorded, not on a test I just fixed, because a rerun hides exactly the class of bug this exercise is about.

## 4. What I would ask before calling this done

The brief hints at four things and each one changes the code:

1. **Which users get 2FA, and is it per user or risk based?** If it is risk based, CI needs allow listed egress IPs or a test only bypass, otherwise the challenge appears at random and no amount of waiting fixes it. If it is per user, I need a TOTP secret in the secret store for each account that has it enabled.
2. **What does "dynamic loading" mean on the dashboard?** Websocket push, polling, or plain lazy fetch. If projects arrive over a socket the correct wait is on the payload, not on a DOM node, and I would wait for the `/api/v1/projects` response rather than a card.
3. **How slow is the slowest tenant, and why?** If company2 is slow because of a cold container, the fix is a warm up call in the pipeline rather than a longer timeout. Config carries `cold_start` per tenant so this stays data, not a magic number in a test.
4. **Which browsers and viewports are actually supported?** Testing Safari at 1024px when the product only supports 1280px and up creates fake failures. I want the supported matrix from the product side before I build the CI matrix.
5. **Are there `data-testid` attributes in the app?** The rewrite assumes them. If not, adding them is a one afternoon change on the frontend and it removes an entire category of flake permanently. Until then the locators fall back to roles and text, which is second best.
6. **Is there a seeded staging environment, or do tests share production style data?** Every stability strategy below depends on this answer.

---

# Part 2: Framework design

## Principles I designed against

1. **A test should read like the business rule it protects.** All waiting, tenant switching and device plumbing lives below the test, never inside it.
2. **Configuration is data, code is behaviour.** Adding a tenant, an environment or a device is a YAML edit, not a new class.
3. **The API is the fastest way to set up a UI test.** Anything the test is not asserting gets created over HTTP, not clicked through the interface.
4. **Every layer can run alone.** API tests do not need a browser, web tests do not need BrowserStack, and the mobile suite can be skipped without breaking collection.
5. **Cheap and fast on every pull request, broad and expensive on a schedule.** That single rule drives most of the CI and BrowserStack decisions below.

## Structure

```
workflowpro-automation/
├── pytest.ini                  markers, default browser, artifact policy, pythonpath
├── requirements.txt
├── Makefile                    the five commands anyone on the team actually runs
├── .env.example                every secret the suite needs, by name only
├── .github/workflows/tests.yml API gate, browser matrix, nightly device suite
└── framework/
    ├── conftest.py             fixture wiring, auth state reuse, device sessions, cleanup
    ├── config/
    │   ├── settings.py         typed loader, env vars override YAML, cached
    │   ├── environments.yaml   local, staging, production: urls and timeout budgets
    │   ├── tenants.yaml        tenant ids, subdomains, users per role, secret names
    │   └── devices.yaml        smoke and nightly device suites for BrowserStack
    ├── core/
    │   ├── base_page.py        open, ready check, testid helper, responsive navigation
    │   ├── api_client.py       auth and tenant headers, retries, idempotency keys
    │   ├── auth.py             token cache, storage state files, TTL
    │   ├── browser_factory.py  local launch, BrowserStack connect, session verdicts
    │   └── errors.py           ApiError with request id, TenantLeakError
    ├── pages/
    │   ├── login_page.py       the only place that knows about 2FA
    │   ├── dashboard_page.py
    │   ├── projects_page.py    search, eventual consistency handling, card lookup
    │   └── project_detail_page.py
    ├── api/
    │   ├── projects.py         one client per resource
    │   └── schemas.py          pydantic models, the response contract in one place
    ├── data/
    │   ├── factories.py        unique payloads stamped with the run id
    │   └── ledger.py           what was created, deleted in reverse on teardown
    ├── utils/
    │   ├── retry.py            retry_call and poll_until for non DOM waits
    │   └── totp.py
    └── tests/
        ├── api/                fast, runs first, gates the rest
        ├── web/                desktop browsers
        ├── integration/        API plus UI plus device, Part 3 lives here
        └── security/           tenant isolation and the permission matrix
```

Tests are split by layer rather than by feature because that is how they get scheduled: API tests are seconds and run on every commit, web tests are minutes and run per pull request, device tests cost money and run nightly. Feature grouping would force every schedule to cut across folders.

## Base classes and what each one owns

| Class | Owns | Deliberately does not own |
| --- | --- | --- |
| `BasePage` | url building per tenant, the ready check, `data-testid` access, opening the nav drawer when the layout is compact | assertions, test data |
| `LoginPage` | credentials, the 2FA branch, the rejected login error | where the user goes next beyond returning the dashboard page |
| `ApiClient` | auth header, tenant header, timeouts, retries on transient failures, idempotency key on POST | response shape |
| `ProjectsApi` | endpoints and response parsing into models | HTTP mechanics |
| `ResourceLedger` | what this test created and how to remove it | when cleanup runs, that is the fixture's job |
| `settings` | environments, tenants, users, device suites, secret resolution | anything test specific |

`BasePage.go_to()` is the small piece that makes one page object work on desktop and on a handset: below 768px it opens the drawer first, above it clicks the link directly. Without that, mobile needs a parallel set of page objects and the suite doubles in size for no new coverage.

## Configuration management

Four layers, each one overriding the one before:

```
config/*.yaml  (committed defaults, no secrets)
      ↓
TEST_ENV / API_BASE_URL / *_PASSWORD / BROWSERSTACK_*  (environment, per machine and per CI job)
      ↓
CLI flags: --env, --tenant, --device-suite, --browser, --headed
      ↓
per test marks and parametrization
```

`tenants.yaml` stores the secret **name**, never the secret:

```yaml
company1:
  id: "1001"
  subdomain: company1
  cold_start: false
  users:
    admin:
      email: admin@company1.com
      password_env: COMPANY1_ADMIN_PASSWORD
      totp_secret_env: COMPANY1_ADMIN_TOTP
```

That gives three things at once: the repo is safe to open source internally, CI injects real values from the secret store, and a developer without credentials gets a clean skip instead of a mysterious auth failure. URLs are templated (`https://{subdomain}.{domain}`) so one tenant entry works across local, staging and production, and `cold_start` lets a slow tenant get a longer navigation budget without slowing every other test down.

## Test data strategy

Three tiers, because they have different lifetimes:

| Tier | Examples | Owner | Lifecycle |
| --- | --- | --- | --- |
| Reference | tenants, role users, plans, feature flags | environment provisioning script | created with the environment, refreshed on demand, never touched by tests |
| Transactional | projects, tasks, comments the test asserts on | the test itself, over the API | created in a fixture, deleted in teardown through the ledger |
| Golden | reporting and analytics fixtures that need history | nightly restore job | read only for tests |

Rules that keep it stable under parallel execution:

- Every generated name carries the run id and a random token (`qa-20260831-142130-x4k9p`), so two workers, two branches and two environments never collide.
- Cleanup is registered at creation time, not written at the end of the test, so it still runs when the test fails halfway.
- Cleanup failures produce a warning with the resource id rather than a test failure, because a leaked project should not turn a real pass into a red build. The warning is what feeds a weekly leftover sweep.
- No test asserts on a global count, only on records it created. That is the single rule that makes parallel runs on a shared tenant possible.

## Parallel execution

- Session scoped browser, function scoped context. Contexts are cheap, browsers are not.
- Login happens once per tenant and role, then `storage_state` is reused for 30 minutes. That cuts a login from every test down to a handful per run, which speeds the suite up and, more importantly, stops the auth service from rate limiting CI.
- API tests run at high concurrency (`-n 8`), web at `-n 4`, device tests at the number of BrowserStack seats we pay for, never more.
- Distinct accounts per role mean workers do not fight over sessions. If the platform enforces single active session per user, the next step is a small account pool keyed by `PYTEST_XDIST_WORKER`.

## BrowserStack strategy and cost

Coverage is a budget, so I spend it where local browsers cannot reach:

| Trigger | What runs | Where |
| --- | --- | --- |
| every commit | API suite | local runner |
| pull request | smoke, chromium plus webkit | local Playwright, free |
| merge to main | full web suite on chromium, firefox, webkit | local Playwright, free |
| nightly | full matrix plus real iOS and Android devices | BrowserStack |
| release candidate | nightly matrix plus the oldest supported OS versions | BrowserStack |

Cost controls that are already in the code: `storage_state` reuse keeps device sessions short because login is skipped, `browserstack.idleTimeout` is capped so an abandoned session does not bill for an hour, every session is closed in fixture teardown even on failure, and each session is marked passed or failed through the executor so triage happens from the dashboard instead of by rerunning. Playwright covers WebKit locally for Safari rendering, so BrowserStack is reserved for real device behaviour that a desktop engine genuinely cannot reproduce: touch, on screen keyboards, real iOS Safari and device pixel ratios.

## Reporting

Allure report per run, plus the raw Playwright trace for every failure, which is the artifact that actually ends debates about whether a failure was the app or the test. Beyond a single run I would track pass rate per test over the last 30 runs and alert on tests below 95 percent, because a test that fails one run in twenty is invisible in any single report but is the main reason people stop trusting the suite. Flaky tests get a quarantine marker with an owner and a date, they keep running and reporting but do not block the pipeline, and the quarantine list is reviewed weekly so it does not become a graveyard.

## Missing requirements, the questions I would ask

**Environments and data**
1. Is there a dedicated test environment, or do we test against staging shared with manual QA? Shared environments are the most common cause of "flaky" tests that are actually data collisions.
2. Can automation create and destroy tenants on demand, or are the test tenants fixed? Disposable tenants would remove most of the cleanup complexity.
3. Is there a data reset or restore point, and how long does it take?
4. Does production data ever get cloned into staging, and if so how is PII handled?

**Auth and permissions**
5. What is the exact permission matrix for Admin, Manager and Employee? I need it as a table to turn into a parametrized test, and it is the kind of requirement that lives in someone's head until an incident.
6. Is 2FA per user, per tenant, or triggered by risk signals?
7. Can CI get a service account with 2FA disabled, or should we automate TOTP?
8. What is the session policy, single active session per user or many?

**Mobile**
9. Is mobile a native iOS and Android app, or responsive web? The brief says both platforms but never says which, and the answer decides between Playwright on real devices and Appium with App Automate. The current code covers responsive web on real devices, which is the assumption I noted.
10. If native, do we get signed test builds per commit, and where are they uploaded?
11. Which OS versions are supported, and what is the minimum screen size?

**Scope and priority**
12. Which flows lose money when they break? That list is the smoke suite, everything else is regression.
13. What are the top five support tickets from the last quarter? They tell me where coverage is missing better than a feature list does.
14. Is there a release cadence to attach the suites to, and who is allowed to override a red build?

**Execution and reporting**
15. What is the acceptable pull request feedback time? Ten minutes changes the design of the smoke suite significantly compared to thirty.
16. What is the BrowserStack plan, specifically the parallel session count? That number is a hard input to the CI design, not a detail.
17. Who reads the report, and does anyone need it in a dashboard rather than a CI artifact?
18. Do we have feature flags, and can tests set them per tenant? Flags silently change what the UI renders and are a top source of unexplained failures.
19. Are there rate limits on the API that automation will hit?
20. What is the definition of done for a bug fix, does it require a regression test before merge?

---

# Part 3: API and UI integration flow

## Approach

The valuable thing about this scenario is not that it touches three layers, it is that each layer can fail in a way the others hide. The API can accept a project that the UI never renders because of a stale cache. The UI can render it while the mobile layout drops the card below the fold. And all three can look perfect while the record leaks to another tenant, which is the only failure in this list that is a security incident rather than a bug.

So the test runs in that order and fails at the earliest layer that is wrong:

```
   API create (POST /api/v1/projects)
        │  contract, status, id
        ▼
   API read back .......................... backend agrees with itself
        │
        ▼
   Web UI as a Manager of the owning tenant
        │  list card, then detail page
        ▼
   Real device (BrowserStack, iOS or Android)
        │  compact layout, drawer nav, same record
        ▼
   Isolation as the other tenant
        ├─ API by id                 must be 403 or 404
        ├─ API with a swapped tenant header   must be refused
        ├─ UI search                 must not list it
        └─ direct URL to /projects/{id}       must show access denied
```

Failing early matters for triage. If the API step fails, nobody spends an hour in a Playwright trace looking for a UI bug that does not exist.

## The test

Full file: [framework/tests/integration/test_project_creation_flow.py](framework/tests/integration/test_project_creation_flow.py).

```python
@pytest.fixture
def seeded_project(api_for, ledger, tenants):
    owner = tenants["company1"]
    projects = ProjectsApi(api_for(owner, "admin"))
    payload = project_payload(members=[owner.user("manager").email, owner.user("employee").email])
    project = projects.create(payload)
    ledger.track(f"project {project.id} on {owner.key}", lambda: projects.delete(project.id))
    return owner, project, payload


def test_project_creation_flow(seeded_project, tenants, environment, api_for, signed_in_page, mobile_page):
    owner, project, payload = seeded_project
    outsider = tenants["company2"]

    # 1. API first, so a broken contract never gets misread as a UI bug
    assert project.status == "active"
    assert project.name == payload["name"]
    assert ProjectsApi(api_for(owner, "admin")).fetch(project.id).name == payload["name"]

    # 2. Web UI, read back through the product the way a manager would
    desktop = signed_in_page(owner, "manager")
    board = ProjectsPage(desktop, environment, owner).open()
    expect(board.wait_for_project(project.name)).to_contain_text("Active")

    detail = board.open_project(project.name)
    expect(detail.title).to_have_text(project.name)
    expect(detail.description).to_have_text(payload["description"])
    expect(detail.members).to_have_count(len(payload["team_members"]))

    # 3. Mobile on a real device, where the nav sits behind the drawer
    handset = mobile_page(owner, "manager")
    mobile_board = ProjectsPage(handset, environment, owner).open()
    assert mobile_board.is_compact_layout()
    expect(mobile_board.wait_for_project(project.name)).to_be_visible()

    # 4. Isolation, checked at the API and again in the UI because they can fail apart
    stranger = api_for(outsider, "admin")
    assert ProjectsApi(stranger).get(project.id, expected=(403, 404)).status_code in (403, 404)

    spoofed = stranger.as_tenant(owner)
    assert ProjectsApi(spoofed).get(project.id, expected=(401, 403, 404)).status_code in (401, 403, 404)

    intruder_page = signed_in_page(outsider, "admin")
    intruder_board = ProjectsPage(intruder_page, environment, outsider).open()
    intruder_board.search(project.name)
    if project.name in intruder_board.visible_project_names():
        raise TenantLeakError(f"{outsider.key} can list project {project.id} owned by {owner.key}")

    forced = ProjectDetailPage(intruder_page, environment, outsider, project.id)
    intruder_page.goto(forced.url, wait_until="domcontentloaded")
    expect(forced.access_denied).to_be_visible()
    expect(forced.title).to_have_count(0)
```

The pieces that make it reliable sit in the framework rather than in the test:

```python
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
```

That loop is the honest answer to a real problem: a write through the API and a read through the UI are usually separated by a cache or a read replica, so a card that is not there yet is not the same as a card that will never be there. A bounded reload loop distinguishes the two, and it still fails with a proper Playwright error message and a trace if the record never appears. A plain sleep would paper over both cases.

`search()` waits on the `/api/v1/projects` response rather than on a spinner, so the debounce and the network are handled by one deterministic wait.

## Test data across API and UI

- The project is created over the API in a fixture, never through the UI form, because this test is about a project existing in three places, not about the create dialog. The create dialog has its own UI test.
- The payload is generated by `project_payload()` with the run id baked into the name, so the UI search is guaranteed to match exactly one record even when three branches run at once.
- The same payload object is asserted against in every layer. There is no second copy of "Test Project" in a UI test that can drift from the API fixture.
- Cleanup is registered the moment the project exists, so an assertion failure in step 4 still removes the record. Delete accepts 404 as success, which makes teardown idempotent when a test already removed the record.
- Nothing depends on data that this test did not create, and nothing is left behind for the next test to trip over.

## Cross platform validation

| Layer | Where it runs | Why there |
| --- | --- | --- |
| API | any runner, no browser | it is HTTP, a browser adds cost and nothing else |
| Web | chromium, firefox and webkit locally through the pytest matrix | free, fast, catches engine differences including Safari rendering through WebKit |
| Mobile | real iOS and Android devices on BrowserStack | touch, on screen keyboard, real Safari on iOS and device pixel ratio cannot be emulated honestly |

The main flow uses one representative handset so it stays affordable on every nightly run. Broader device coverage is a separate parametrized test over `devices.yaml`, which means widening the matrix is a YAML edit and the expensive suite is scheduled independently of the flow test.

```python
HANDSETS = [pytest.param(item, id=item["name"]) for item in device_suite("smoke") if item.get("real_mobile")]

@pytest.mark.mobile
@pytest.mark.parametrize("device", HANDSETS)
def test_project_reads_on_each_handset(seeded_project, environment, mobile_page, device):
    ...
```

Mobile responsiveness is asserted, not assumed: `assert mobile_board.is_compact_layout()` fails loudly if a device somehow serves the desktop layout, which is exactly the bug a desktop only suite misses.

## Tenant isolation

Four checks, because they fail independently:

| Check | Attack it models | Expected |
| --- | --- | --- |
| Company2 token reads the project by id | a leaked or guessed id | 403 or 404 |
| Company2 token with `X-Tenant-ID: company1` | the tenant header is trusted instead of the token | 401, 403 or 404 |
| Company2 UI search for the exact name | a broken query filter or a shared cache | not listed |
| Company2 browser opens `/projects/{id}` directly | the frontend hides the link but the route still renders | access denied, no title |

The header swap is the one I would insist on. Plenty of platforms scope the query by the header for convenience, and that turns a header into an authorization decision. The same checks live in [framework/tests/security/test_tenant_isolation.py](framework/tests/security/test_tenant_isolation.py) as fast API only tests so they run on every commit, not only inside the slow flow.

A leak raises `TenantLeakError` rather than a plain assertion. It is a small thing, but it means a data leak is greppable in the report and can be routed differently from an ordinary failure.

## Edge cases handled

| Edge case | Handling | Where |
| --- | --- | --- |
| Transient 5xx or 429 from the API | urllib3 retry with backoff for idempotent methods | `core/api_client.py` |
| Connection drop during create | `retry_call` around POST with an `Idempotency-Key`, so a retry cannot create two projects | `core/api_client.py` |
| Write to read lag between API and UI | bounded search and reload loop, then a real expect | `pages/projects_page.py` |
| Slow tenant, cold start | per tenant navigation timeout multiplier | `config/settings.py` |
| Search debounce | wait on the projects response instead of the spinner | `pages/projects_page.py` |
| Compact layout hides the nav | drawer opened automatically below 768px | `core/base_page.py` |
| BrowserStack unavailable or no credentials | the mobile step falls back to an emulated handset and warns that this is not real device coverage | `conftest.py` |
| Device session left open on failure | fixture teardown always closes it and stamps the verdict | `conftest.py` |
| Test data left behind after a failure | ledger cleanup in reverse order, warning instead of a false failure | `data/ledger.py` |
| 2FA challenge during login | raced against success and error, TOTP filled from the secret store | `pages/login_page.py` |
| Missing credentials locally | clean skip with the variable name in the message | `conftest.py` |

## Assumptions

1. **Auth.** `POST /api/v1/auth/token` returns `{"access_token": ...}` and accepts an optional `otp`. Tokens are cached per tenant and role for the session.
2. **Mobile means responsive web on real devices.** If WorkFlow Pro ships native apps, the mobile fixture is the only piece that changes, swapped for Appium against App Automate, and the page objects would gain a mobile locator strategy. The rest of the design holds. Without BrowserStack credentials the same step runs on an emulated handset and says so in the report, because a green mobile test that silently ran on a desktop engine would be worse than no test.
3. **The app exposes `data-testid` attributes.** Without them the same locators work through roles and text, less stably.
4. **A create returns 201 with the full record**, and list responses are `{"items": [...]}` or a bare array. `api/schemas.py` is the one place to correct that.
5. **Admin and Manager can create projects, Employee cannot.** This is encoded as a parametrized table so it is easy to correct once someone confirms the real matrix.
6. **Deleting a project is allowed for the tenant admin** and is the cleanup path. If deletes are soft or restricted, cleanup becomes an archive call, one line in the ledger registration.
7. **Tests run against a seeded staging environment**, never production.

---

# What the suite caught while it was being written

Two real bugs, both found by the tests before any manual check, which is a fair sample of what this coverage is for.

| Finding | How it surfaced |
| --- | --- |
| The projects page shipped without a viewport meta tag, so the responsive breakpoint never applied and the mobile nav stayed hidden behind a drawer toggle that could not be seen | `MOB-01` failed with the toggle resolved but hidden at 390px |
| The tenant badge did not match the label the test derived from configuration | `AUTH-01` failed on an exact text assertion, which is the assertion that should be exact |

# Live session notes

Short answers to the topics listed for the call, in case they are useful ahead of it.

- **Preventing flakes, not just fixing them.** Ban `sleep` in review, require `data-testid` for anything a test touches, put trace on failure in CI from day one, and track per test pass rate so a one in twenty failure is visible before people start ignoring the suite.
- **Scaling the framework.** The three things that break first at scale are shared test data, login rate limits and device minutes. Disposable tenants, cached auth state and a scheduled device matrix are the answers to those three, and all three are in this design.
- **Test data in a multi tenant product.** Reference data owned by provisioning, transactional data owned by the test, run id in every name, cleanup registered at creation. Never assert on global counts.
- **BrowserStack cost.** Local Playwright covers three engines for free, so real devices only get used for what devices actually do differently. Short sessions through cached login, idle timeout capped, nightly rather than per pull request.
- **CI and parallel execution.** API gates the browser matrix so a backend break does not burn browser minutes, browsers run in parallel jobs, tests inside a job run under xdist, one rerun on the regression suite with the flake recorded.
- **Monitoring.** A suite nobody trusts is worse than no suite. Pass rate trend, flake list with owners, and mean time to diagnose a failure are the three numbers I would report weekly.

# What I would build next

1. A permission matrix suite covering all three roles across every resource, generated from one table.
2. Disposable tenant provisioning so tests stop sharing state entirely.
3. Contract tests against the OpenAPI spec, so a backend field rename fails in seconds rather than in a browser five minutes later.
4. Visual checks on the three highest traffic screens across the device matrix, since layout breakage is the failure mode functional assertions miss.
5. A flake dashboard fed by the Allure history, with a weekly quarantine review.
