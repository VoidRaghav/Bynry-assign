# Test Execution Report

| | |
| --- | --- |
| Run date | 1 September 2026, 19:20 IST |
| Environment | demo, the bundled mock app on `http://127.0.0.1:8123` |
| Command | `make demo` |
| Browser | Chromium 148, headless |
| Result | **27 passed, 0 failed, 0 skipped, 6.70s** |

## Summary

| Suite | Tests | Time | Result |
| --- | --- | --- | --- |
| API, projects and validation | 13 | 0.03s | passed |
| Security, tenant isolation | 5 | 0.02s | passed |
| Web UI, login and roles | 5 | 1.55s | passed |
| Integration, API to UI to handset | 2 | 3.45s | passed |
| Part 1, the rewritten login tests | 2 | 1.57s | passed |
| **Total** | **27** | **6.70s** | **passed** |

## Artifacts in this folder

| File | What it is |
| --- | --- |
| `report.html` | Self contained HTML report, open it in a browser |
| `junit.xml` | JUnit XML for a CI dashboard |
| `last-run.txt` | Full console output of the run above |
| `mock_app.log` | Request log from the demo app, useful when a UI test fails |

Failures also write a Playwright trace to `artifacts/`. Open one with `playwright show-trace artifacts/<test>/trace.zip` and you get the DOM, the network and a frame by frame timeline of the failure.

## What this run proves

- The API layer enforces the role matrix, the validation rules and the tenant header rule.
- Tenant isolation holds under four different attempts, including a valid token with a swapped tenant header.
- The critical path works end to end: a project created over the API appears in the web UI, opens correctly, is readable on a handset layout, and stays invisible to the other tenant in both the API and the UI.
- The rewritten Part 1 login tests pass, including the 2FA branch, which the demo environment enables for the company1 admin.
- Every test cleans up after itself. The demo app starts from the same seeded state on every run, so this report is reproducible.

## Two bugs the suite found while it was being written

Both were caught by the tests before any manual check, which is a fair demonstration of what the coverage is for.

| Finding | How it surfaced |
| --- | --- |
| The projects page had no viewport meta tag, so the responsive breakpoint never applied and the mobile nav stayed hidden | `MOB-01` failed with the drawer toggle resolved but hidden at 390px |
| The tenant badge label did not match the value the test derived from configuration | `AUTH-01` failed on an exact text assertion, which is the assertion that should be exact |

## Environment notes for this particular run

- The suite ran with `--browser-channel=chromium` because the Playwright headless shell download is blocked on this machine. On a normal machine `make demo` needs no extra flags.
- Video recording was off for the same reason, the ffmpeg download is blocked here. Traces and screenshots were unaffected.
- BrowserStack was not exercised, since this run has no credentials. The mobile steps ran on an emulated iPhone 15 profile and each one warns in the report that real device coverage needs BrowserStack. Emulation is not equivalent to a real device, which is exactly why the nightly job exists.

## Reproducing it

```bash
pip install -r requirements.txt -r requirements-dev.txt
playwright install chromium
make demo
```

The script starts the mock app, waits for it, runs the whole suite, writes these artifacts, and stops the app again. To run against a real environment instead:

```bash
TEST_ENV=staging pytest -m smoke
```
