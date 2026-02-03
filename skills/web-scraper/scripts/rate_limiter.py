"""
Rate limiter por dominio + retry con backoff exponencial.
"""
import asyncio
import time
from collections import defaultdict
from typing import Dict, Optional
from urllib.parse import urlparse
import random

class RateLimiter:
    def __init__(self):
        # Último request por dominio
        self._last_request: Dict[str, float] = defaultdict(float)
        # Delays por dominio (pueden aumentar si hay errores)
        self._domain_delays: Dict[str, float] = {}
        # Errores consecutivos por dominio
        self._consecutive_errors: Dict[str, int] = defaultdict(int)
        # Lock por dominio para evitar race conditions
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # Defaults
        self.default_delay = 2.0  # segundos entre requests al mismo dominio
        self.max_delay = 60.0  # máximo backoff
        self.jitter = 0.2  # ±20% random jitter
    
    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc
    
    def _get_delay(self, domain: str) -> float:
        base = self._domain_delays.get(domain, self.default_delay)
        # Añadir jitter
        jitter = base * self.jitter * (random.random() * 2 - 1)
        return max(0.5, base + jitter)
    
    async def acquire(self, url: str):
        """Wait until we can make a request to this domain."""
        domain = self._get_domain(url)
        async with self._locks[domain]:
            now = time.time()
            delay = self._get_delay(domain)
            wait_time = self._last_request[domain] + delay - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request[domain] = time.time()
    
    def report_success(self, url: str):
        """Reset error count on success."""
        domain = self._get_domain(url)
        self._consecutive_errors[domain] = 0
        # Gradually reduce delay back to default
        if domain in self._domain_delays:
            self._domain_delays[domain] = max(
                self.default_delay,
                self._domain_delays[domain] * 0.8
            )
    
    def report_error(self, url: str, status_code: Optional[int] = None):
        """Increase backoff on error."""
        domain = self._get_domain(url)
        self._consecutive_errors[domain] += 1
        
        # Exponential backoff
        current = self._domain_delays.get(domain, self.default_delay)
        if status_code == 429:  # Too Many Requests
            new_delay = min(self.max_delay, current * 3)
        else:
            new_delay = min(self.max_delay, current * 1.5)
        
        self._domain_delays[domain] = new_delay
        return self._consecutive_errors[domain]
    
    def should_skip(self, url: str, max_errors: int = 5) -> bool:
        """Check if we should skip this domain due to too many errors."""
        domain = self._get_domain(url)
        return self._consecutive_errors[domain] >= max_errors


class RetryHandler:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def execute(self, coro_func, *args, **kwargs):
        """Execute with retry and exponential backoff."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await coro_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt) + random.random()
                    await asyncio.sleep(delay)
        raise last_error
