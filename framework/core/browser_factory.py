import json
import os
import urllib.parse

from playwright.sync_api import Error as PlaywrightError

CDP_ENDPOINT = "wss://cdp.browserstack.com/playwright?caps="
DESKTOP_VIEWPORT = {"width": 1440, "height": 900}


def browserstack_ready():
    return bool(os.environ.get("BROWSERSTACK_USERNAME") and os.environ.get("BROWSERSTACK_ACCESS_KEY"))


def build_name():
    return os.environ.get("BUILD_NAME") or f"workflowpro-local-{os.environ.get('USER', 'dev')}"


def launch_local(playwright, browser_name="chromium", headed=False, slow_mo=0):
    engine = getattr(playwright, browser_name)
    return engine.launch(headless=not headed, slow_mo=slow_mo, args=["--disable-dev-shm-usage"])


def connect_browserstack(playwright, device, test_name):
    capabilities = {
        "browser": device.get("browser", "playwright-chromium"),
        "browser_version": device.get("browser_version", "latest"),
        "os": device.get("os"),
        "os_version": device.get("os_version"),
        "deviceName": device.get("device"),
        "realMobile": "true" if device.get("real_mobile") else None,
        "build": build_name(),
        "name": test_name,
        "browserstack.username": os.environ["BROWSERSTACK_USERNAME"],
        "browserstack.accessKey": os.environ["BROWSERSTACK_ACCESS_KEY"],
        "browserstack.networkLogs": "true",
        "browserstack.debug": "true",
        "browserstack.idleTimeout": "60",
        "client.playwrightVersion": os.environ.get("PLAYWRIGHT_VERSION", "1.47.0"),
    }
    payload = {key: value for key, value in capabilities.items() if value is not None}
    endpoint = CDP_ENDPOINT + urllib.parse.quote(json.dumps(payload))
    return playwright.chromium.connect(endpoint, timeout=120_000)


# stamps the verdict on the session so triage happens in the dashboard
def report_status(page, passed, reason):
    if not browserstack_ready():
        return
    verdict = {"action": "setSessionStatus", "arguments": {"status": "passed" if passed else "failed", "reason": reason[:255]}}
    try:
        page.evaluate("_ => {}", f"browserstack_executor: {json.dumps(verdict)}")
    except PlaywrightError:
        pass
