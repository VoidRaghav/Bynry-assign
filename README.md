# WorkFlow Pro, Test Automation

Test automation for a multi tenant B2B project management SaaS: API, web, mobile and tenant isolation, built with pytest and Playwright, with BrowserStack for real devices.

The repo ships with a small mock of the product, so the entire suite runs on any machine with one command and no credentials.

```bash
make install
make demo
```

```
27 passed in 6.70s
```

That run produced [reports/report.html](reports/report.html) and [reports/REPORT.md](reports/REPORT.md).

## What is here

```
docs/                 test plan, test cases, test data, testing approach
framework/            the framework: config, core, pages, api, data, tests
part1_flaky_login/    a flaky login test taken apart and rebuilt
mock_app/             a small stand in for WorkFlow Pro so the suite is runnable
reports/              the last execution report, html, junit and console output
scripts/run_demo.sh   starts the mock app, runs everything, writes the reports
.github/workflows/    the pipeline: API gate, browser matrix, nightly devices
```

## Documentation

| Document | What it covers |
| --- | --- |
| [docs/TEST_PLAN.md](docs/TEST_PLAN.md) | Scope, environments, entry and exit criteria, risks, defect handling |
| [docs/TEST_CASES.md](docs/TEST_CASES.md) | Every case with an id, priority and the file that automates it |
| [docs/TEST_DATA.md](docs/TEST_DATA.md) | The three data tiers, uniqueness, cleanup, secrets |
| [docs/TESTING_APPROACH.md](docs/TESTING_APPROACH.md) | Tool choices, waiting strategy, flake prevention, CI gates, cost |
| [SUBMISSION.md](SUBMISSION.md) | The assessment write up: flaky test analysis, framework design, the integration flow |

## Setup

```bash
pip install -r requirements.txt -r requirements-dev.txt
playwright install --with-deps
cp .env.example .env
```

Credentials come from the environment. `framework/config/tenants.yaml` holds only the variable names, so nothing secret is committed, and a suite whose credentials are missing skips with the missing variable named instead of failing in a confusing way.

## Running

| Command | What it runs |
| --- | --- |
| `make demo` | Everything against the bundled mock app, writes the reports |
| `make smoke` | The pull request suite, four workers |
| `make api` | Backend only, no browser |
| `make web` | Chromium, Firefox and WebKit |
| `make mobile` | Real devices through BrowserStack |
| `make regression` | The full suite with one rerun and Allure results |
| `make part1` | Just the rewritten login tests |

Useful flags: `--env staging`, `--tenant company2`, `--device-suite nightly`, `--browser firefox`, `--headed`.

Failures keep a trace, a screenshot and a video under `artifacts/`. Open a trace with `playwright show-trace artifacts/<test>/trace.zip` for a frame by frame replay with the DOM and the network attached.

## Coverage at a glance

| Area | Cases | Where |
| --- | --- | --- |
| Project API behaviour and validation | 13 | `framework/tests/api/` |
| Tenant isolation and permissions | 5 plus 4 more inside the flow | `framework/tests/security/` |
| Login, roles, responsive dashboard | 5 | `framework/tests/web/` |
| API to UI to handset, end to end | 2 | `framework/tests/integration/` |
| The rewritten flaky tests | 2 | `part1_flaky_login/` |

## The mock app

`mock_app/server.py` is a small Flask stand in for WorkFlow Pro: login with an optional 2FA step, a dashboard, a projects list that loads asynchronously, project detail pages, and a REST API with tenant scoped data and a role matrix. It reads the same `tenants.yaml` the framework reads, so both sides always agree on who exists.

It is there so a reviewer can run the suite without a backend, and so the reports in this repo are reproducible. Pointing the suite at the real product is a matter of `TEST_ENV=staging`.

## Notes

- BrowserStack is used for real iOS and Android devices. Without credentials the mobile steps fall back to an emulated handset and warn in the report that emulation is not real device coverage.
- The framework assumes the app exposes `data-testid` attributes. Where it does not, the same locators fall back to roles and text, less stably.
- Assumptions about auth, mobile, and the permission matrix are listed at the end of [SUBMISSION.md](SUBMISSION.md), each with the one place that changes if the assumption is wrong.
