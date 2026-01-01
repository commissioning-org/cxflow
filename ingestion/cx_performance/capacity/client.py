"""
Power Automate HTTP Client for CX Performance Capacity Ingestion.
"""

import gzip
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .config import IngestionConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class IngestionResponse:
    """Response from Power Automate ingestion."""
    success: bool
    data: Any
    status_code: int
    timestamp: datetime
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
        }


class PowerAutomateClient:
    """
    Client for fetching CX Performance Capacity data from Power Automate workflows.
    
    Usage:
        client = PowerAutomateClient()
        
        # Fetch data from webhook
        response = client.fetch()
        
        if response.success:
            print(f"Received {len(response.data)} items")
        
        # Fetch with custom payload
        response = client.fetch(payload={"query": "search term"})
    """
    
    def __init__(self, config: Optional[IngestionConfig] = None):
        self.config = config or DEFAULT_CONFIG
    
    def fetch(
        self,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> IngestionResponse:
        """
        Fetch data from Power Automate webhook.
        
        Args:
            payload: Optional JSON payload to send with request
            headers: Optional additional headers
            
        Returns:
            IngestionResponse with the result
        """
        url = self.config.full_url
        
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CXPerformance-Capacity-Ingestor/1.0",
        }
        
        if headers:
            request_headers.update(headers)
        
        # Prepare request body
        body = None
        if payload:
            body = json.dumps(payload).encode("utf-8")
        
        # Retry logic
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Fetching from Power Automate (attempt {attempt + 1})")
                
                request = Request(
                    url,
                    data=body,
                    headers=request_headers,
                    method="GET" if body is None else "POST",
                )
                
                with urlopen(request, timeout=self.config.timeout) as response:
                    status_code = response.status
                    raw_data = response.read()
                    
                    # Get content type and encoding
                    content_type = response.headers.get("Content-Type", "")
                    charset = "utf-8"
                    
                    # Extract charset from content-type header
                    if "charset=" in content_type:
                        charset = content_type.split("charset=")[-1].split(";")[0].strip()
                    
                    # Try to decode response
                    response_data = None
                    for encoding in [charset, "utf-8", "latin-1", "cp1252"]:
                        try:
                            response_data = raw_data.decode(encoding)
                            break
                        except (UnicodeDecodeError, LookupError):
                            continue
                    
                    # If all decoding fails, use latin-1 as fallback (never fails)
                    if response_data is None:
                        response_data = raw_data.decode("latin-1", errors="replace")
                    
                    # Parse JSON response
                    try:
                        data = json.loads(response_data)
                    except json.JSONDecodeError:
                        # Check if it's binary/compressed data
                        if raw_data[:2] == b'\x1f\x8b':  # gzip magic bytes
                            try:
                                decompressed = gzip.decompress(raw_data)
                                data = json.loads(decompressed.decode("utf-8"))
                            except Exception:
                                data = {"raw_bytes": len(raw_data), "content_type": content_type}
                        else:
                            data = response_data
                    
                    logger.info(f"Successfully fetched data (status: {status_code}, type: {content_type})")
                    
                    return IngestionResponse(
                        success=True,
                        data=data,
                        status_code=status_code,
                        timestamp=datetime.now(),
                    )
                    
            except HTTPError as e:
                last_error = f"HTTP Error {e.code}: {e.reason}"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                
            except URLError as e:
                last_error = f"URL Error: {e.reason}"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
            
            # Wait before retry
            if attempt < self.config.max_retries - 1:
                time.sleep(self.config.retry_delay * (attempt + 1))
        
        logger.error(f"All {self.config.max_retries} attempts failed")
        
        return IngestionResponse(
            success=False,
            data=None,
            status_code=0,
            timestamp=datetime.now(),
            error_message=last_error,
        )
    
    def fetch_with_pagination(
        self,
        page_size: int = 100,
        max_pages: Optional[int] = None,
    ) -> List[IngestionResponse]:
        """
        Fetch data with pagination support.
        
        Args:
            page_size: Number of items per page
            max_pages: Maximum number of pages to fetch (None for all)
            
        Returns:
            List of IngestionResponse objects
        """
        responses = []
        page = 0
        
        while max_pages is None or page < max_pages:
            payload = {
                "page": page,
                "pageSize": page_size,
            }
            
            response = self.fetch(payload=payload)
            responses.append(response)
            
            if not response.success:
                break
            
            # Check if more pages available
            data = response.data
            if isinstance(data, dict):
                total = data.get("total", 0)
                items = data.get("items", data.get("value", []))
                
                if len(items) < page_size or (page + 1) * page_size >= total:
                    break
            elif isinstance(data, list):
                if len(data) < page_size:
                    break
            else:
                break
            
            page += 1
        
        return responses
    
    def health_check(self) -> bool:
        """Check if the Power Automate endpoint is accessible."""
        try:
            response = self.fetch(payload={"healthCheck": True})
            return response.success or response.status_code in (200, 202)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
