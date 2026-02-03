#!/usr/bin/env python3
"""
Test de rate limiter: simula errores 429 y verifica backoff exponencial.

Uso:
    python test_rate_limiter.py
"""

import asyncio
import time
from rate_limiter import RateLimiter, RetryHandler

# Colores para output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log(color, msg):
    print(f"{color}{msg}{RESET}")

async def test_basic_rate_limiting():
    """Test 1: Verificar que el delay por dominio funciona."""
    log(BLUE, "\n=== TEST 1: Basic Rate Limiting ===")
    
    limiter = RateLimiter()
    limiter.default_delay = 1.0  # 1 segundo entre requests
    limiter.jitter = 0  # Sin jitter para test predecible
    
    url = "https://example.com/test"
    
    # Primer request: debería ser instantáneo
    start = time.time()
    await limiter.acquire(url)
    elapsed1 = time.time() - start
    log(GREEN, f"✓ Primera request: {elapsed1:.2f}s (esperado: ~0s)")
    
    # Segundo request: debería esperar ~1s
    start = time.time()
    await limiter.acquire(url)
    elapsed2 = time.time() - start
    log(GREEN, f"✓ Segunda request: {elapsed2:.2f}s (esperado: ~1s)")
    
    assert elapsed1 < 0.1, "Primera request debería ser instantánea"
    assert 0.9 <= elapsed2 <= 1.2, f"Segunda request debería esperar ~1s, got {elapsed2:.2f}s"
    
    log(GREEN, "✅ TEST 1 PASSED\n")


async def test_backoff_on_errors():
    """Test 2: Verificar que el backoff aumenta con errores."""
    log(BLUE, "\n=== TEST 2: Backoff on Errors ===")
    
    limiter = RateLimiter()
    limiter.default_delay = 1.0
    limiter.jitter = 0
    
    url = "https://example.com/test2"
    domain = limiter._get_domain(url)
    
    # Reportar errores y verificar que el delay aumenta
    log(YELLOW, f"Delay inicial: {limiter._get_delay(domain):.2f}s")
    
    limiter.report_error(url, status_code=500)
    delay1 = limiter._get_delay(domain)
    log(YELLOW, f"Después de error 1 (500): {delay1:.2f}s")
    assert delay1 > 1.0, "Delay debería aumentar tras error"
    
    limiter.report_error(url, status_code=500)
    delay2 = limiter._get_delay(domain)
    log(YELLOW, f"Después de error 2 (500): {delay2:.2f}s")
    assert delay2 > delay1, "Delay debería seguir aumentando"
    
    # Error 429 debería aumentar mucho más
    limiter.report_error(url, status_code=429)
    delay3 = limiter._get_delay(domain)
    log(RED, f"Después de error 429: {delay3:.2f}s")
    assert delay3 > delay2 * 2, "Error 429 debería triplicar el delay"
    
    # Success debería reducir gradualmente
    limiter.report_success(url)
    delay4 = limiter._get_delay(domain)
    log(GREEN, f"Después de éxito: {delay4:.2f}s")
    assert delay4 < delay3, "Éxito debería reducir el delay"
    
    log(GREEN, "✅ TEST 2 PASSED\n")


async def test_should_skip():
    """Test 3: Verificar que should_skip() funciona correctamente."""
    log(BLUE, "\n=== TEST 3: Should Skip on Too Many Errors ===")
    
    limiter = RateLimiter()
    url = "https://badsite.com/broken"
    
    # Simular muchos errores consecutivos
    for i in range(5):
        limiter.report_error(url)
        should_skip = limiter.should_skip(url, max_errors=5)
        log(YELLOW, f"Error {i+1}: should_skip={should_skip}")
        
        if i < 4:
            assert not should_skip, f"No debería skipear en error {i+1}"
        else:
            assert should_skip, "Debería skipear después de 5 errores"
    
    # Éxito debería resetear
    limiter.report_success(url)
    assert not limiter.should_skip(url, max_errors=5), "Éxito debería resetear errores"
    log(GREEN, "✓ Éxito reseteó el contador de errores")
    
    log(GREEN, "✅ TEST 3 PASSED\n")


async def test_retry_handler():
    """Test 4: Verificar RetryHandler con exponential backoff."""
    log(BLUE, "\n=== TEST 4: Retry Handler ===")
    
    handler = RetryHandler(max_retries=3, base_delay=0.5)
    
    # Función que falla 2 veces y luego tiene éxito
    attempts = 0
    async def flaky_func():
        nonlocal attempts
        attempts += 1
        log(YELLOW, f"  Intento {attempts}...")
        if attempts < 3:
            raise RuntimeError(f"Fallo simulado {attempts}")
        return "¡Éxito!"
    
    start = time.time()
    result = await handler.execute(flaky_func)
    elapsed = time.time() - start
    
    log(GREEN, f"✓ Resultado: {result}")
    log(GREEN, f"✓ Total intentos: {attempts}, tiempo: {elapsed:.2f}s")
    assert attempts == 3, "Debería haber intentado 3 veces"
    assert result == "¡Éxito!", "Debería haber tenido éxito"
    assert elapsed >= 1.5, "Debería haber esperado por backoff (0.5s + 1s)"
    
    # Función que siempre falla
    attempts = 0
    async def always_fails():
        nonlocal attempts
        attempts += 1
        log(RED, f"  Intento {attempts}...")
        raise RuntimeError("Siempre falla")
    
    try:
        await handler.execute(always_fails)
        assert False, "Debería haber lanzado excepción"
    except RuntimeError as e:
        log(GREEN, f"✓ Excepción esperada: {e}")
        assert attempts == 3, "Debería haber intentado max_retries veces"
    
    log(GREEN, "✅ TEST 4 PASSED\n")


async def test_parallel_requests():
    """Test 5: Verificar rate limiting con requests paralelas."""
    log(BLUE, "\n=== TEST 5: Parallel Requests (Same Domain) ===")
    
    limiter = RateLimiter()
    limiter.default_delay = 1.0
    limiter.jitter = 0
    
    url = "https://example.com/test5"
    
    # Lanzar 3 requests en paralelo
    start = time.time()
    tasks = [limiter.acquire(url) for _ in range(3)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    log(GREEN, f"✓ 3 requests paralelas tardaron: {elapsed:.2f}s")
    # Deberían ser: 0s + 1s + 1s = ~2s
    assert 1.8 <= elapsed <= 2.3, f"Deberían tardar ~2s, got {elapsed:.2f}s"
    
    log(GREEN, "✅ TEST 5 PASSED\n")


async def test_different_domains():
    """Test 6: Verificar que dominios diferentes no se bloquean entre sí."""
    log(BLUE, "\n=== TEST 6: Different Domains Don't Block Each Other ===")
    
    limiter = RateLimiter()
    limiter.default_delay = 1.0
    limiter.jitter = 0
    
    url1 = "https://site1.com/test"
    url2 = "https://site2.com/test"
    
    # Primera request a cada dominio
    await limiter.acquire(url1)
    await limiter.acquire(url2)
    
    # Requests en paralelo a dominios diferentes deberían ser instantáneas
    start = time.time()
    await asyncio.gather(
        limiter.acquire(url1),
        limiter.acquire(url2)
    )
    elapsed = time.time() - start
    
    log(GREEN, f"✓ 2 requests a dominios diferentes tardaron: {elapsed:.2f}s")
    # Deberían esperar ~1s cada una pero en paralelo
    assert 0.9 <= elapsed <= 1.2, f"Deberían tardar ~1s (en paralelo), got {elapsed:.2f}s"
    
    log(GREEN, "✅ TEST 6 PASSED\n")


async def main():
    """Ejecutar todos los tests."""
    print(f"\n{BLUE}{'='*60}")
    print(f"🧪 Rate Limiter Tests")
    print(f"{'='*60}{RESET}\n")
    
    tests = [
        test_basic_rate_limiting,
        test_backoff_on_errors,
        test_should_skip,
        test_retry_handler,
        test_parallel_requests,
        test_different_domains,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except AssertionError as e:
            failed += 1
            log(RED, f"❌ {test.__name__} FAILED: {e}\n")
        except Exception as e:
            failed += 1
            log(RED, f"💥 {test.__name__} ERROR: {e}\n")
    
    # Resumen
    print(f"\n{BLUE}{'='*60}")
    if failed == 0:
        log(GREEN, f"✅ ALL TESTS PASSED ({passed}/{passed})")
    else:
        log(RED, f"❌ SOME TESTS FAILED ({passed}/{passed+failed} passed)")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    return failed == 0


if __name__ == '__main__':
    success = asyncio.run(main())
    exit(0 if success else 1)
