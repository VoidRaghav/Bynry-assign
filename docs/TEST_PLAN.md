# Test Plan, WorkFlow Pro

| | |
| --- | --- |
| Product | WorkFlow Pro, multi tenant B2B project management SaaS |
| Author | Raghav |
| Version | 1.0, 31 August 2026 |
| Applies to | web app, mobile web, public REST API v1 |
| Related docs | [TESTING_APPROACH.md](TESTING_APPROACH.md), [TEST_CASES.md](TEST_CASES.md), [TEST_DATA.md](TEST_DATA.md), [../reports/REPORT.md](../reports/REPORT.md) |

## 1. Purpose

Define what gets tested, how, in which environment, and what has to be true before a release ships. The plan covers automated coverage owned by QA and names the gaps that are deliberately left to manual or exploratory testing.

## 2. Quality objectives

1. A tenant can never read, change or delete another tenant's data, through the UI or the API.
2. The critical path (sign in, see projects, create a project, open a project) works on every supported browser and on real iOS and Android devices.
3. A pull request gets a trustworthy pass or fail in under ten minutes.
4. A failing test explains itself well enough to triage without reproducing it locally.
5. Suite pass rate stays above 95 percent per test over a rolling 30 runs, so nobody learns to ignore red.

## 3. Scope

**In scope**

| Area | Covered by |
| --- | --- |
| Authentication, including 2FA and rejected logins | API and UI tests |
| Role permissions for Admin, Manager, Employee | parametrized API tests |
| Project CRUD and validation rules | data driven API tests |
| Project visibility in the web UI, list and detail | UI tests |
| Tenant isolation across API and UI | dedicated security suite |
| Responsive behaviour and real device rendering | mobile suite, emulated locally, real devices nightly |
| Cross browser rendering on Chromium, Firefox, WebKit | CI matrix |
| Contract shape of API responses | pydantic models in `framework/api/schemas.py` |

**Out of scope for this plan**

Unit tests (owned by the engineering teams), load and performance testing, penetration testing beyond tenant boundary checks, billing and invoicing flows, email and push notification delivery, accessibility audit, and third party integrations. Each of these is a known gap, not an oversight, and the ones worth adding first are listed in section 12.

## 4. Test approach

Layered, cheapest layer first, because each layer answers a different question.

| Layer | Question it answers | Tooling | Runtime |
| --- | --- | --- | --- |
| API | Does the backend behave and enforce permissions? | pytest, requests, pydantic | seconds |
| UI, web | Does the product show the truth to the right person? | Playwright, page objects | minutes |
| Integration | Do the layers agree with each other? | pytest driving both | minutes |
| Security | Do tenant boundaries hold under a deliberate attempt? | pytest, cross tenant clients | seconds |
| Mobile | Does it work on a real device, not just a narrow window? | Playwright on BrowserStack | minutes, billed |

Setup for a UI test is always performed over the API. Only the behaviour under test goes through the interface.

## 5. Environments

| Environment | Purpose | Data | Who uses it |
| --- | --- | --- | --- |
| demo (bundled mock) | Run and review the whole suite with no backend access, used for the reports in this repo | seeded from `framework/data/fixtures/seed.json` on start | anyone, no credentials needed |
| local | A developer running the real app on their machine | developer owned | engineers |
| staging | The default target for CI | seeded reference data, tests create their own transactional data | QA and CI |
| production | Read only smoke after deploy, no data creation | live | release manager |

Environment specifics, including per tenant timeout budgets, live in `framework/config/environments.yaml`. Nothing environment specific is hardcoded in a test.

## 6. Test data

Summarised here, detailed in [TEST_DATA.md](TEST_DATA.md). Reference data (tenants, role users) is owned by environment provisioning. Transactional data is created by the test over the API, carries the run id in its name, and is deleted in teardown by the resource ledger. No test asserts on a global count.

## 7. Entry criteria

- The build deploys to the target environment and the health endpoint answers.
- Reference data for both test tenants exists and role credentials are present in the secret store.
- API contract changes have been communicated, or the API suite runs first and reports them.

## 8. Exit criteria

- Every smoke test passes on Chromium and WebKit, no exceptions.
- No open Critical or High defect on the critical path.
- The security suite passes with zero failures. A tenant isolation failure blocks the release outright.
- Any quarantined test has an owner and a date, and the quarantine list did not grow this release.
- Test data cleanup warnings reviewed, so leftovers are not accumulating.

## 9. Suites, triggers and budget

| Suite | Trigger | Contents | Target runtime |
| --- | --- | --- | --- |
| API | every commit | markers `api` | under 2 minutes |
| Smoke | every pull request | marker `smoke`, Chromium and WebKit | under 10 minutes |
| Regression | merge to main | all web and integration, three engines | under 30 minutes |
| Device | nightly and release candidate | marker `mobile` on BrowserStack real devices | under 45 minutes |
| Production smoke | after deploy | read only critical path | under 5 minutes |

## 10. Roles

| Role | Responsibility |
| --- | --- |
| QA automation | Framework, suites, triage of failures, flake budget |
| Engineering | Fix product defects, add `data-testid` hooks, keep the API contract documented |
| Release manager | Decides on exit criteria exceptions, owns the production smoke result |
| DevOps | Environment provisioning, secret store, runner capacity |

## 11. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| A tenant isolation bug reaches production | Critical, a data breach and a contractual problem | Isolation suite runs on every commit at API level, four attack shapes, a leak fails the build with a distinct error type |
| Shared staging data changes under a running suite | Failures that look like product bugs | Tests create their own data with unique names, never assert on global counts |
| Flaky suite erodes trust | Teams start ignoring red builds | Web first assertions, no sleeps, trace on failure, per test pass rate tracked, quarantine with an owner |
| BrowserStack spend grows with the matrix | Budget overrun | Local Playwright covers three engines free, devices run nightly, sessions kept short by cached auth state |
| CI IP triggers 2FA or rate limits | Random authentication failures | TOTP automated, auth state cached and reused, allow listed egress requested from the platform team |
| Test accounts locked or rotated | Suite wide outage | Credentials in the secret store, one account per role, clear skip messages naming the missing variable |
| API contract drifts silently | UI tests fail for backend reasons | Response models validated in the API layer, API suite gates the browser jobs |

## 12. Defect management

Severity is decided by blast radius, not by which screen it appeared on.

| Severity | Definition | Response |
| --- | --- | --- |
| Critical | Data leak across tenants, auth bypass, critical path broken for all users | Block the release, fix now |
| High | Critical path broken for one role, browser or device | Block the release unless a workaround is documented |
| Medium | Non critical feature broken, or broken only in an edge case | Fix in the current cycle |
| Low | Cosmetic, copy, minor layout | Backlog |

Every reproducible defect gets a regression test in the same pull request as the fix. A test that fails intermittently is a defect against QA, not an inconvenience: it is quarantined with an owner and a date, and quarantine is reviewed weekly.

## 13. Reporting

Every run publishes a JUnit XML for the CI dashboard, a self contained HTML report for humans, and Playwright traces for failures. Weekly, three numbers are reported: pass rate trend per test, the current flake and quarantine list, and mean time to diagnose a failure.

## 14. Deliverables

This repository: the framework, the automated suites, the test data, the execution reports in [../reports/](../reports/), this plan, the case catalogue and the approach document.

## 15. Open questions

The plan assumes answers to twenty questions that the requirements do not settle, from whether mobile means native apps to what the BrowserStack parallel session count is. They are listed in [../SUBMISSION.md](../SUBMISSION.md) under "The requirements that are missing" and each one has a stated assumption in the meantime.
