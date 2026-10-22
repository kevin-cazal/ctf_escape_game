"""Thin client for the CTFd REST API (stock CTFd 3.8), admin token auth.

CTFd only honours an `Authorization: Token ...` header on JSON requests (and on
multipart uploads to /api/v1/files), so every call sends Content-Type: application/json,
GETs included.
"""

import requests


class CTFdError(Exception):
    pass


class CTFd:
    def __init__(self, url, token, timeout=10):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Token {token}"

    def _call(self, method, path, json=None, params=None, files=None, data=None):
        headers = {} if files else {"Content-Type": "application/json"}
        try:
            r = self.session.request(
                method,
                f"{self.url}/api/v1{path}",
                json=json,
                params=params,
                files=files,
                data=data,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as e:
            raise CTFdError(f"{method} {path}: unreachable ({e.__class__.__name__})")
        if r.status_code >= 300:
            raise CTFdError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}")
        body = r.json() if r.content else {}
        if body.get("success") is False:
            raise CTFdError(f"{method} {path}: {body.get('errors') or body}")
        return body

    def get(self, path, **params):
        return self._call("GET", path, params=params)["data"]

    def get_all(self, path, **params):
        """Follow CTFd's pagination (max 100 per page)."""
        items, page = [], 1
        while page:
            body = self._call("GET", path, params={**params, "page": page, "per_page": 100})
            items += body["data"]
            page = body.get("meta", {}).get("pagination", {}).get("next")
        return items

    def post(self, path, payload):
        return self._call("POST", path, json=payload)["data"]

    def patch(self, path, payload):
        return self._call("PATCH", path, json=payload).get("data")

    def delete(self, path):
        self._call("DELETE", path)

    def upload(self, challenge_id, filename, content):
        return self._call(
            "POST",
            "/files",
            files={"file": (filename, content)},
            data={"challenge_id": challenge_id, "type": "challenge"},
        )["data"]

    # --- helpers --------------------------------------------------------

    def check_admin(self):
        """/configs is admin-only: it fails for a wrong or non-admin token."""
        self._call("GET", "/configs")

    def users(self):
        return self.get_all("/users", view="admin")

    def challenges(self):
        return self.get_all("/challenges", view="admin")

    def solves(self):
        return self.get_all("/submissions", type="correct")

    def fails(self):
        return self.get_all("/submissions", type="incorrect")
