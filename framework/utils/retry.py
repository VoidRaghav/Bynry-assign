import time


def retry_call(action, attempts=3, delay=1.0, backoff=2.0, retry_on=(Exception,), label="call"):
    failure = None
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except retry_on as error:
            failure = error
            if attempt == attempts:
                break
            time.sleep(delay)
            delay *= backoff
    raise AssertionError(f"{label} failed after {attempts} attempts: {failure}") from failure


def poll_until(condition, timeout=30.0, interval=1.0, label="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError(f"{label} was still false after {timeout}s")
