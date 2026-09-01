# Test Data

## The rule

A test owns the data it asserts on. Anything else it needs, it creates over the API and removes on the way out. Nothing depends on a record another test left behind.

## Three tiers

| Tier | What it is | Where it lives | Lifecycle |
| --- | --- | --- | --- |
| Reference | Tenants, role users, plans | `framework/config/tenants.yaml` plus environment provisioning | Created with the environment, never mutated by a test |
| Transactional | Projects a test creates to assert on | Built by `framework/data/factories.py` | Created in a fixture, deleted in teardown |
| Case data | Valid and invalid payload variants | `framework/data/fixtures/project_payloads.json` | Committed, read at collection time |
| Seed | Baseline projects for the demo app | `framework/data/fixtures/seed.json` | Loaded when the mock app starts |

## Files

```
framework/
├── config/tenants.yaml                  two tenants, five role users, secret names only
├── data/
│   ├── factories.py                     unique payloads stamped with the run id
│   ├── fixtures.py                      loader, expands the long name case
│   ├── ledger.py                        what was created, removed in reverse
│   └── fixtures/
│       ├── project_payloads.json        3 valid and 5 invalid cases, each with expected status
│       └── seed.json                    baseline projects per tenant for the demo app
```

`project_payloads.json` is the test data for PROJ-02 to PROJ-09. Adding a validation case is a JSON edit, not a new test:

```json
{"case": "name over 200 chars", "payload": {"name": "x", "repeat_name": 260, "description": "too long", "team_members": []}, "expected_status": 422}
```

## Uniqueness

Every generated name carries the run id and a random token:

```
qa-20260831-190350-x4k9p
```

The run id comes from `TEST_RUN_ID`, which CI sets to the pipeline run number. Two workers, two branches and two environments can therefore share a tenant without colliding, and a leftover record is traceable to the exact run that made it.

## Cleanup

Cleanup is registered at the moment of creation, never written at the end of a test:

```python
project = projects.create(payload)
ledger.track(f"project {project.id} on {owner.key}", lambda: projects.delete(project.id))
```

The ledger releases in reverse order so a child record never outlives its parent, and delete accepts 404 as success so teardown is idempotent. A cleanup failure raises a warning naming the resource, not a test failure, because a leaked project should never turn a real pass into a red build. Those warnings are what a weekly sweep works from.

## Secrets

Configuration stores the variable name, never the value:

```yaml
admin:
  email: admin@company1.com
  password_env: COMPANY1_ADMIN_PASSWORD
  totp_secret_env: COMPANY1_ADMIN_TOTP
```

CI injects the values from the secret store. A developer without them gets a clean skip naming the missing variable. `.env.demo` is the only file with passwords in it, and they belong to the throwaway mock app, not to any real system.

## Adding a tenant or a user

1. Add the entry to `framework/config/tenants.yaml` with the secret variable names.
2. Add the values to the secret store and to `.env.example`.
3. Nothing else. Tests take tenants as fixtures, so a new tenant is available to every parametrized suite immediately.

## Data in the demo environment

The bundled mock app loads `seed.json` on start and keeps everything in memory, so every `make demo` run begins from the same known state. That is deliberate: the reports in `reports/` are reproducible, and a reviewer can run the whole suite without credentials or a backend.

## Policy notes

- No production data is copied into a test environment. If that ever changes, PII has to be masked at export, and the plan needs a data privacy section.
- No customer names, real emails or real tokens in fixtures. The two tenants are fictional and their users are role accounts.
- Test accounts are not shared with manual QA, so a suite run cannot be disturbed by someone else's session.
