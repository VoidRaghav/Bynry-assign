import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.errors import ApiError
from utils.retry import retry_call

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})
TRANSIENT_STATUSES = (429, 502, 503, 504)


class ApiClient:
    def __init__(self, environment, tenant, token):
        self.environment = environment
        self.tenant = tenant
        self.base_url = environment.api_base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant.id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        transient = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=TRANSIENT_STATUSES,
            allowed_methods=IDEMPOTENT_METHODS,
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=transient))
        self.session.mount("http://", HTTPAdapter(max_retries=transient))

    def request(self, method, path, expected=(200, 201), **kwargs):
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.environment.api_timeout_s)
        response = self.session.request(method, url, **kwargs)
        if expected and response.status_code not in expected:
            raise ApiError(method, url, response)
        return response

    def get(self, path, expected=(200,), **kwargs):
        return self.request("GET", path, expected, **kwargs)

    def delete(self, path, expected=(200, 204), **kwargs):
        return self.request("DELETE", path, expected, **kwargs)

    def post(self, path, json_body, expected=(200, 201), **kwargs):
        # retried on dropped connections only, the key stops a retry creating two records
        headers = {"Idempotency-Key": str(uuid.uuid4()), **kwargs.pop("headers", {})}
        return retry_call(
            lambda: self.request("POST", path, expected, json=json_body, headers=headers, **kwargs),
            attempts=3,
            retry_on=(requests.ConnectionError, requests.Timeout),
            label=f"POST {path}",
        )

    # same token, different tenant header, used to prove the header alone grants nothing
    def as_tenant(self, other_tenant):
        clone = ApiClient.__new__(ApiClient)
        clone.environment = self.environment
        clone.tenant = other_tenant
        clone.base_url = self.base_url
        clone.session = requests.Session()
        clone.session.headers.update({**self.session.headers, "X-Tenant-ID": other_tenant.id})
        clone.session.adapters = self.session.adapters
        return clone
