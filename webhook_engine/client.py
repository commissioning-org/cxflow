"""HTTP client for webhook delivery with connection pooling and auth support."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

import urllib.request
import urllib.error
import ssl

from .config import WebhookEndpoint

logger = logging.getLogger(__name__)


@dataclass
class WebhookResponse:
    """Response from a webhook call."""
    
    success: bool
    status_code: int
    headers: dict[str, str]
    body: str
    elapsed_ms: float
    request_id: str
    endpoint_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    retry_count: int = 0
    
    @property
    def is_retryable(self) -> bool:
        """Check if this response indicates a retryable error."""
        return self.status_code in (429, 500, 502, 503, 504)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "elapsed_ms": self.elapsed_ms,
            "request_id": self.request_id,
            "endpoint_name": self.endpoint_name,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "retry_count": self.retry_count,
        }
    
    def json(self) -> Any:
        """Parse response body as JSON."""
        return json.loads(self.body) if self.body else None


class AuthHandler:
    """Handles authentication for webhook requests."""
    
    @staticmethod
    def apply_auth(
        endpoint: WebhookEndpoint,
        headers: dict[str, str],
        url: str,
        body: bytes,
    ) -> tuple[dict[str, str], str]:
        """Apply authentication to a request. Returns (headers, url)."""
        auth_type = endpoint.auth_type
        auth_config = endpoint.auth_config
        
        if not auth_type:
            return headers, url
        
        headers = headers.copy()
        
        if auth_type == "bearer":
            token = auth_config.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        
        elif auth_type == "basic":
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        
        elif auth_type == "api_key":
            key_name = auth_config.get("header_name", "X-API-Key")
            key_value = auth_config.get("key", "")
            if auth_config.get("in_query", False):
                # Add to query string
                parsed = urlparse(url)
                query = parse_qs(parsed.query)
                query[key_name] = [key_value]
                new_query = urlencode(query, doseq=True)
                url = urlunparse(parsed._replace(query=new_query))
            else:
                headers[key_name] = key_value
        
        elif auth_type == "hmac":
            secret = auth_config.get("secret", "").encode()
            algorithm = auth_config.get("algorithm", "sha256")
            header_name = auth_config.get("header_name", "X-Signature")
            
            if algorithm == "sha256":
                signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
            elif algorithm == "sha512":
                signature = hmac.new(secret, body, hashlib.sha512).hexdigest()
            else:
                signature = hmac.new(secret, body, hashlib.sha1).hexdigest()
            
            prefix = auth_config.get("prefix", "")
            headers[header_name] = f"{prefix}{signature}"
        
        elif auth_type == "query_params":
            # Add all auth_config items as query parameters
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            for key, value in auth_config.items():
                query[key] = [value]
            new_query = urlencode(query, doseq=True)
            url = urlunparse(parsed._replace(query=new_query))
        
        elif auth_type == "custom_header":
            # Add custom headers from auth_config
            for key, value in auth_config.get("headers", {}).items():
                headers[key] = value
        
        return headers, url


class WebhookClient:
    """HTTP client for webhook delivery."""
    
    def __init__(
        self,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        connection_pool_size: int = 100,
        default_headers: Optional[dict[str, str]] = None,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.connection_pool_size = connection_pool_size
        self.default_headers = default_headers or {
            "Content-Type": "application/json",
            "User-Agent": "WebhookEngine/1.0",
        }
        self._session: Optional[Any] = None
        self._request_counter = 0
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        self._request_counter += 1
        timestamp = int(time.time() * 1000)
        return f"req_{timestamp}_{self._request_counter:06d}"
    
    async def _get_session(self) -> Any:
        """Get or create an aiohttp session."""
        if AIOHTTP_AVAILABLE and self._session is None:
            connector = aiohttp.TCPConnector(
                limit=self.connection_pool_size,
                ssl=self.verify_ssl,
            )
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
            )
        return self._session
    
    async def close(self) -> None:
        """Close the client session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
    
    async def send_async(
        self,
        endpoint: WebhookEndpoint,
        payload: dict[str, Any],
        extra_headers: Optional[dict[str, str]] = None,
    ) -> WebhookResponse:
        """Send a webhook request asynchronously."""
        request_id = self._generate_request_id()
        start_time = time.perf_counter()
        
        # Prepare headers
        headers = {**self.default_headers, **endpoint.headers}
        if extra_headers:
            headers.update(extra_headers)
        headers["X-Request-ID"] = request_id
        
        # Serialize payload
        body = json.dumps(payload).encode("utf-8")
        
        # Apply authentication
        headers, url = AuthHandler.apply_auth(endpoint, headers, endpoint.url, body)
        
        try:
            if AIOHTTP_AVAILABLE:
                return await self._send_aiohttp(
                    endpoint, url, headers, body, request_id, start_time
                )
            elif HTTPX_AVAILABLE:
                return await self._send_httpx(
                    endpoint, url, headers, body, request_id, start_time
                )
            else:
                # Fallback to sync urllib in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: self._send_urllib(
                        endpoint, url, headers, body, request_id, start_time
                    )
                )
        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(f"Webhook request failed: {e}", extra={
                "request_id": request_id,
                "endpoint": endpoint.name,
            })
            return WebhookResponse(
                success=False,
                status_code=0,
                headers={},
                body="",
                elapsed_ms=elapsed,
                request_id=request_id,
                endpoint_name=endpoint.name,
                error=str(e),
            )
    
    async def _send_aiohttp(
        self,
        endpoint: WebhookEndpoint,
        url: str,
        headers: dict[str, str],
        body: bytes,
        request_id: str,
        start_time: float,
    ) -> WebhookResponse:
        """Send request using aiohttp."""
        session = await self._get_session()
        
        async with session.request(
            method=endpoint.method,
            url=url,
            headers=headers,
            data=body,
            timeout=aiohttp.ClientTimeout(total=endpoint.timeout),
        ) as response:
            elapsed = (time.perf_counter() - start_time) * 1000
            response_body = await response.text()
            response_headers = dict(response.headers)
            
            return WebhookResponse(
                success=200 <= response.status < 300,
                status_code=response.status,
                headers=response_headers,
                body=response_body,
                elapsed_ms=elapsed,
                request_id=request_id,
                endpoint_name=endpoint.name,
            )
    
    async def _send_httpx(
        self,
        endpoint: WebhookEndpoint,
        url: str,
        headers: dict[str, str],
        body: bytes,
        request_id: str,
        start_time: float,
    ) -> WebhookResponse:
        """Send request using httpx."""
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.request(
                method=endpoint.method,
                url=url,
                headers=headers,
                content=body,
                timeout=endpoint.timeout,
            )
            elapsed = (time.perf_counter() - start_time) * 1000
            
            return WebhookResponse(
                success=200 <= response.status_code < 300,
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.text,
                elapsed_ms=elapsed,
                request_id=request_id,
                endpoint_name=endpoint.name,
            )
    
    def _send_urllib(
        self,
        endpoint: WebhookEndpoint,
        url: str,
        headers: dict[str, str],
        body: bytes,
        request_id: str,
        start_time: float,
    ) -> WebhookResponse:
        """Send request using urllib (sync fallback)."""
        request = urllib.request.Request(
            url=url,
            data=body,
            headers=headers,
            method=endpoint.method,
        )
        
        ctx = None
        if not self.verify_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(
                request,
                timeout=endpoint.timeout,
                context=ctx,
            ) as response:
                elapsed = (time.perf_counter() - start_time) * 1000
                response_body = response.read().decode("utf-8")
                response_headers = dict(response.headers)
                
                return WebhookResponse(
                    success=200 <= response.status < 300,
                    status_code=response.status,
                    headers=response_headers,
                    body=response_body,
                    elapsed_ms=elapsed,
                    request_id=request_id,
                    endpoint_name=endpoint.name,
                )
        except urllib.error.HTTPError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            return WebhookResponse(
                success=False,
                status_code=e.code,
                headers=dict(e.headers) if e.headers else {},
                body=e.read().decode("utf-8") if e.fp else "",
                elapsed_ms=elapsed,
                request_id=request_id,
                endpoint_name=endpoint.name,
                error=str(e),
            )
    
    def send_sync(
        self,
        endpoint: WebhookEndpoint,
        payload: dict[str, Any],
        extra_headers: Optional[dict[str, str]] = None,
    ) -> WebhookResponse:
        """Send a webhook request synchronously."""
        request_id = self._generate_request_id()
        start_time = time.perf_counter()
        
        # Prepare headers
        headers = {**self.default_headers, **endpoint.headers}
        if extra_headers:
            headers.update(extra_headers)
        headers["X-Request-ID"] = request_id
        
        # Serialize payload
        body = json.dumps(payload).encode("utf-8")
        
        # Apply authentication
        headers, url = AuthHandler.apply_auth(endpoint, headers, endpoint.url, body)
        
        return self._send_urllib(endpoint, url, headers, body, request_id, start_time)
    
    async def send_batch_async(
        self,
        endpoint: WebhookEndpoint,
        payloads: list[dict[str, Any]],
        concurrency: int = 10,
    ) -> list[WebhookResponse]:
        """Send multiple webhook requests concurrently."""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def send_with_semaphore(payload: dict[str, Any]) -> WebhookResponse:
            async with semaphore:
                return await self.send_async(endpoint, payload)
        
        tasks = [send_with_semaphore(p) for p in payloads]
        return await asyncio.gather(*tasks)


# Convenience function for quick sends
async def send_webhook(
    url: str,
    payload: dict[str, Any],
    method: str = "POST",
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> WebhookResponse:
    """Quick function to send a single webhook."""
    endpoint = WebhookEndpoint(
        name="adhoc",
        url=url,
        method=method,
        headers=headers or {},
        timeout=timeout,
    )
    client = WebhookClient(timeout=timeout)
    try:
        return await client.send_async(endpoint, payload)
    finally:
        await client.close()


def send_webhook_sync(
    url: str,
    payload: dict[str, Any],
    method: str = "POST",
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> WebhookResponse:
    """Quick function to send a single webhook synchronously."""
    endpoint = WebhookEndpoint(
        name="adhoc",
        url=url,
        method=method,
        headers=headers or {},
        timeout=timeout,
    )
    client = WebhookClient(timeout=timeout)
    return client.send_sync(endpoint, payload)
