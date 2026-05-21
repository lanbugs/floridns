from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PdnsError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class PdnsClient:
    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        ssl_verify: bool | None = None,
    ) -> None:
        base = (url or str(settings.PDNS_API_URL)).rstrip("/")
        key = api_key or settings.PDNS_API_KEY
        self._base = f"{base}/api/v1/servers/{settings.PDNS_SERVER_ID}"
        self._root = f"{base}/api/v1/servers/{settings.PDNS_SERVER_ID}"
        self._headers = {
            "X-API-Key": key,
            "Content-Type": "application/json",
        }
        self._base_url = base
        self._api_key = key
        self._ssl_verify = settings.PDNS_SSL_VERIFY if ssl_verify is None else ssl_verify

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._headers, timeout=10.0, verify=self._ssl_verify)

    def _raise(self, response: httpx.Response) -> None:
        if response.is_error:
            try:
                detail = response.json().get("error", response.text)
            except Exception:
                detail = response.text
            raise PdnsError(detail, response.status_code)

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def get_server_info(self) -> dict[str, Any]:
        async with self._client() as client:
            r = await client.get(f"{self._base_url}/api/v1/servers/{settings.PDNS_SERVER_ID}")
            self._raise(r)
            return r.json()  # type: ignore[no-any-return]

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def list_zones(self) -> list[dict[str, Any]]:
        async with self._client() as client:
            r = await client.get(f"{self._base}/zones")
            self._raise(r)
            return r.json()  # type: ignore[no-any-return]

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def get_zone(self, zone_id: str) -> dict[str, Any]:
        async with self._client() as client:
            r = await client.get(f"{self._base}/zones/{zone_id}")
            self._raise(r)
            return r.json()  # type: ignore[no-any-return]

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def create_zone(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as client:
            r = await client.post(f"{self._base}/zones", json=payload)
            self._raise(r)
            return r.json()  # type: ignore[no-any-return]

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def update_zone(self, zone_id: str, payload: dict[str, Any]) -> None:
        async with self._client() as client:
            r = await client.put(f"{self._base}/zones/{zone_id}", json=payload)
            self._raise(r)

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def delete_zone(self, zone_id: str) -> None:
        async with self._client() as client:
            r = await client.delete(f"{self._base}/zones/{zone_id}")
            self._raise(r)

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def patch_rrsets(self, zone_id: str, payload: dict[str, Any]) -> None:
        async with self._client() as client:
            r = await client.patch(f"{self._base}/zones/{zone_id}", json=payload)
            self._raise(r)

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def get_dnssec(self, zone_id: str) -> dict[str, Any]:
        async with self._client() as client:
            r = await client.get(f"{self._base}/zones/{zone_id}/cryptokeys")
            self._raise(r)
            return {"cryptokeys": r.json()}  # type: ignore[no-any-return]

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def enable_dnssec(self, zone_id: str) -> None:
        async with self._client() as client:
            r = await client.put(
                f"{self._base}/zones/{zone_id}", json={"dnssec": True}
            )
            self._raise(r)

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def disable_dnssec(self, zone_id: str) -> None:
        async with self._client() as client:
            r = await client.put(
                f"{self._base}/zones/{zone_id}", json={"dnssec": False}
            )
            self._raise(r)

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def get_statistics(
        self,
        server_url: str | None = None,
        api_key: str | None = None,
        ssl_verify: bool = True,
    ) -> list[dict[str, Any]]:
        if server_url is not None:
            base_url = server_url.rstrip("/")
            headers = {
                "X-API-Key": api_key or self._api_key,
                "Content-Type": "application/json",
            }
            url = f"{base_url}/api/v1/servers/{settings.PDNS_SERVER_ID}/statistics"
            async with httpx.AsyncClient(headers=headers, timeout=10.0, verify=ssl_verify) as client:
                r = await client.get(url)
                self._raise(r)
                return r.json()  # type: ignore[no-any-return]
        else:
            async with self._client() as client:
                r = await client.get(f"{self._base}/statistics")
                self._raise(r)
                return r.json()  # type: ignore[no-any-return]

    @retry(retry=retry_if_exception_type(httpx.TransportError), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def search(self, query: str, max_results: int = 100) -> list[dict[str, Any]]:
        async with self._client() as client:
            r = await client.get(
                f"{self._base}/search-data",
                params={"q": query, "max": max_results, "object_type": "all"},
            )
            self._raise(r)
            return r.json()  # type: ignore[no-any-return]
