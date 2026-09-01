class ApiError(AssertionError):
    def __init__(self, method, url, response):
        self.status_code = response.status_code
        self.body = response.text[:2000]
        self.request_id = response.headers.get("X-Request-Id", "unknown")
        super().__init__(
            f"{method.upper()} {url} returned {self.status_code} (request id {self.request_id})\n{self.body}"
        )


class TenantLeakError(AssertionError):
    pass
