from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MeiliError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass(frozen=True)
class MeiliTask:
    task_uid: int | None = None
    index_uid: str | None = None
    status: str | None = None
    raw: dict[str, Any] | None = None


class MeiliClient:
    """Tiny Meilisearch REST client using stdlib only.

    We intentionally avoid adding new deps (httpx/requests) to keep the ML image slim.
    """

    def __init__(self, *, base_url: str, api_key: str | None = None, timeout_sec: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_sec = float(timeout_sec)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["X-Meili-API-Key"] = self.api_key
        return headers

    def _request(self, method: str, path: str, *, query: dict[str, Any] | None = None, body: Any | None = None) -> Any:
        if not path.startswith("/"):
            path = "/" + path

        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode({k: v for k, v in query.items() if v is not None}, doseq=True)}"

        data: bytes | None
        if body is None:
            data = None
        else:
            data = json.dumps(body).encode("utf-8")

        req = Request(url=url, data=data, method=method.upper(), headers=self._headers())

        try:
            with urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                try:
                    return json.loads(raw)
                except Exception:
                    return raw
        except HTTPError as e:
            body_text = None
            try:
                body_text = e.read().decode("utf-8")
            except Exception:
                body_text = None
            raise MeiliError(
                f"Meilisearch HTTP error: {e.code} {e.reason}",
                status_code=int(e.code),
                body=body_text,
            )
        except URLError as e:
            raise MeiliError(f"Meilisearch connection error: {e}")

    # ---------------------------------------------------------------------
    # Core API
    # ---------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        out = self._request("GET", "/health")
        return out if isinstance(out, dict) else {"raw": out}

    def get_index(self, uid: str) -> dict[str, Any]:
        out = self._request("GET", f"/indexes/{uid}")
        return out if isinstance(out, dict) else {"raw": out}

    def create_index(self, uid: str, *, primary_key: str | None = None) -> MeiliTask:
        payload: dict[str, Any] = {"uid": uid}
        if primary_key:
            payload["primaryKey"] = primary_key
        out = self._request("POST", "/indexes", body=payload)
        return _parse_task(out)

    def update_settings(self, uid: str, settings_payload: dict[str, Any]) -> MeiliTask:
        out = self._request("PATCH", f"/indexes/{uid}/settings", body=settings_payload)
        return _parse_task(out)

    def ensure_index(
        self,
        uid: str,
        *,
        primary_key: str | None = None,
        settings_payload: dict[str, Any] | None = None,
        configure: bool = True,
    ) -> dict[str, Any]:
        try:
            idx = self.get_index(uid)
        except MeiliError as e:
            if e.status_code == 404:
                self.create_index(uid, primary_key=primary_key)
                idx = self.get_index(uid)
            else:
                raise

        if configure and settings_payload:
            # Settings updates are async in Meilisearch; we don't await task completion here.
            self.update_settings(uid, settings_payload)

        return idx

    def add_documents(self, uid: str, docs: list[dict[str, Any]], *, primary_key: str | None = None) -> MeiliTask:
        query = {"primaryKey": primary_key} if primary_key else None
        out = self._request("POST", f"/indexes/{uid}/documents", query=query, body=docs)
        return _parse_task(out)

    def search(
        self,
        uid: str,
        *,
        q: str,
        limit: int = 20,
        offset: int = 0,
        filter: str | list[str] | None = None,
        sort: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"q": q, "limit": limit, "offset": offset}
        if filter is not None:
            payload["filter"] = filter
        if sort is not None:
            payload["sort"] = sort
        out = self._request("POST", f"/indexes/{uid}/search", body=payload)
        return out if isinstance(out, dict) else {"raw": out}


def _parse_task(out: Any) -> MeiliTask:
    if not isinstance(out, dict):
        return MeiliTask(raw={"raw": out})

    # Meilisearch v1 returns taskUid; older versions may return updateId.
    task_uid = out.get("taskUid")
    if task_uid is None:
        task_uid = out.get("updateId")

    return MeiliTask(
        task_uid=int(task_uid) if task_uid is not None else None,
        index_uid=out.get("indexUid"),
        status=out.get("status"),
        raw=out,
    )
