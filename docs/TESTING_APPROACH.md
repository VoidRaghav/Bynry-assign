# Testing Approach

How this suite is built and why it is built that way. The assessment answers for the three exercises are in [../SUBMISSION.md](../SUBMISSION.md); this document is the standing reference for anyone working in the repo.

## Shape of the suite

The product is multi tenant, so the interesting failures are about who can see what, and those are cheapest to catch at the API. The shape follows from that.

```
   security and permissions   ████████████  fast, runs on every commit
   API behaviour              ████████████  fast, gates the browser jobs
   integration, API to UI     ██████        the critical path, per pull request
   UI journeys                █████         one per user visible behaviour
   real devices               ██            nightly, billed by the minute
```

Rules that follow from the shape:

1. If a rule can be proved at the API, it is not proved again through a browser.
2. Setup for a UI test always goes over the API. Only the behaviour under test goes through the interface.
3. Anything that is a security boundary gets a test at both layers, because they fail independently.

## Tool choices

| Choice | Why, and what I compared it with |
| --- | --- |
| Playwright | Auto waiting assertions remove the largest class of flake by construction, one API covers Chromium, Firefox and WebKit, and the trace viewer is the best failure evidence available. Selenium needs an explicit wait strategy that every author has to get right by hand. |
| pytest | Fixtures compose, parametrization turns a permission matrix into data, and the plugin ecosystem covers xdist, reruns and reporting. |
| requests plus pydantic | Plain HTTP for the API layer with the response contract declared once as a model, so a field rename fails in seconds with a clear message instead of surfacing later as a confusing UI failure. |
| BrowserStack | Real iOS and Android devices, and Safari on real hardware. Reserved for what emulation cannot answer honestly. |
| YAML config with typed loading | Adding a tenant, environment or device is a data edit. Config stores secret names, never secrets. |
| Allure and pytest-html | JUnit XML for the CI dashboard, a self contained HTML report for people, traces for the failures worth investigating. |

## Preventing flakes, not just fixing them

The rules the suite is written to, all of them present in the code:

- No `sleep`, ever. Every wait is tied to a condition: a URL pattern, a network response, an element state.
- Web first assertions (`expect`) rather than boolean snapshots (`is_visible`), because only the former retries.
- Locators come from `data-testid` and roles, never from styling classes.
- When several outcomes are legitimate, race them with `or_()` instead of guessing. Login is the example: 2FA, error, and success are all valid next states.
- Viewport, locale, timezone and reduced motion are pinned in the context, so CI and a laptop render the same layout.
- Analytics and support widgets are blocked at the network layer. They add latency and overlays and they test nothing.
- Auth state is cached and reused, which removes repeated logins as a source of rate limits and session interference.
- API to UI lag is handled with a bounded reload loop, not a longer timeout, so a slow read and a missing record fail differently.
- Failures keep a trace, a screenshot and a video. A failure nobody can diagnose gets rerun, and a rerun is how a real bug becomes invisible.

Reruns are enabled only on the wide regression suite, and a rerun is recorded rather than swallowed. A test that needs one is quarantined with an owner and a date.

## Waiting strategy in one line each

| Situation | What the code waits on |
| --- | --- |
| Navigation after a click | `wait_for_url` with a route regex, never a URL string |
| A widget that loads late | `expect(locator).to_be_visible()` with the environment's expect timeout |
| A list that streams in | The first card, plus the absence of the skeleton |
| A debounced search | The `/api/v1/projects` response, not the spinner |
| A record written over the API | A bounded search and reload loop, then a real assertion |
| A slow tenant | A per tenant timeout multiplier from config |

## Parallel execution

Session scoped browser, function scoped context, and one login per tenant and role reused through `storage_state`. API tests run at high concurrency, web tests moderate, device tests capped at the number of seats we pay for. Tests never assert on global counts, which is what makes a shared tenant safe under parallel load.

## CI gates

```
commit ────► API suite ────► browser matrix ────► merge
                              chromium │ firefox │ webkit
nightly ──► full matrix + real devices on BrowserStack
deploy ───► read only production smoke
```

The API suite gates the browser jobs so a backend break does not burn browser minutes, and pull requests run the smoke marker while the full suite runs after merge.

## Cost control

Local Playwright covers three engines for free, so BrowserStack is spent only on real device behaviour. Cached auth state keeps device sessions short, the idle timeout is capped so an abandoned session cannot bill for an hour, sessions close in teardown even on failure, and each one is stamped passed or failed so triage happens from the dashboard instead of by rerunning.

## Reporting and metrics

Every run publishes JUnit XML, an HTML report and traces. Three numbers are reported weekly: pass rate per test over the last thirty runs, the flake and quarantine list with owners, and mean time to diagnose. A suite nobody trusts is worse than no suite, and those numbers are how trust is measured rather than assumed.

## Maintenance

- One page object per screen, no assertions inside it.
- A new endpoint gets a client and a schema before it gets a test.
- A new tenant, environment or device is a config edit.
- Every fixed defect ships with a regression test in the same pull request.
- Anything the tests need from the frontend, mainly `data-testid` hooks, is raised as a normal engineering ticket rather than worked around with a fragile locator.
