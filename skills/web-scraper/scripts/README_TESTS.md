# Rate Limiter Tests

Tests para verificar el sistema de rate limiting del web scraper.

## 🚀 Quick Start

```bash
# Activar entorno virtual
cd /Users/helmet/.openclaw/workspace/skills/web-scraper
source venv/bin/activate

# Tests unitarios (rápido, ~5s)
python scripts/test_rate_limiter.py

# Test de integración (más lento, ~10s)
python scripts/test_rate_limiter_integration.py
```

## 📋 Tests Disponibles

### 1. **test_rate_limiter.py** (Unitario)

Tests aislados del RateLimiter y RetryHandler:

- ✅ **TEST 1:** Basic rate limiting
  - Verifica delays entre requests al mismo dominio
  
- ✅ **TEST 2:** Backoff on errors
  - Verifica que el delay aumenta exponencialmente
  - Error 429 causa backoff x3
  - Éxito reduce delay gradualmente
  
- ✅ **TEST 3:** Should skip
  - Verifica que dominios con muchos errores se skipean
  - Éxito resetea el contador
  
- ✅ **TEST 4:** Retry handler
  - Verifica reintentos con exponential backoff
  - Función que falla N veces y luego tiene éxito
  - Función que siempre falla (lanza excepción tras max_retries)
  
- ✅ **TEST 5:** Parallel requests (same domain)
  - Requests paralelas al mismo dominio se serializan
  
- ✅ **TEST 6:** Different domains don't block each other
  - Requests a diferentes dominios no se bloquean entre sí

**Output esperado:**
```
🧪 Rate Limiter Tests
✅ ALL TESTS PASSED (6/6)
```

### 2. **test_rate_limiter_integration.py** (Integración)

Test end-to-end con servidor HTTP real:

**Qué hace:**
1. Levanta servidor HTTP local en puerto 8765
2. Servidor devuelve 429 en primeras 2 requests
3. Servidor devuelve 200 OK en 3ª request
4. Ejecuta `monitor_daemon.py` contra el servidor
5. Verifica comportamiento completo

**Verifica:**
- ✅ Detecta errores 429
- ✅ Aumenta backoff automáticamente
- ✅ Reintentos con delay exponencial
- ✅ Eventualmente recupera (200 OK)
- ✅ Estado se guarda correctamente
- ✅ Errores consecutivos se resetean tras éxito

**Output esperado:**
```
📨 Request #1 → 429 (Too Many Requests)
📨 Request #2 → 429 (Too Many Requests)
📨 Request #3 → 200 OK
✅ INTEGRATION TEST PASSED
```

## 🔍 Detalles de Verificación

### Test Unitario verifica:
- Timing preciso de delays
- Cálculo correcto de backoff exponencial
- Comportamiento de locks por dominio
- Retry logic con delays correctos
- Paralelización correcta

### Test de Integración verifica:
- Integración real con aiohttp
- Manejo correcto de HTTP status codes
- Persistencia de estado
- Parsing de RSS
- User-agent rotation
- Config loading desde sources.json

## 🐛 Troubleshooting

### ModuleNotFoundError: No module named 'X'

**Solución:** Activar entorno virtual:
```bash
source venv/bin/activate
```

### Port 8765 already in use

**Causa:** Test de integración anterior no se cerró correctamente.

**Solución:**
```bash
# Matar proceso que ocupa el puerto
lsof -ti:8765 | xargs kill -9
```

### Tests fallan con timing issues

**Causa:** Sistema bajo carga, delays no precisos.

**Solución:** Los tests tienen tolerancia (±10%), pero en sistemas muy lentos pueden fallar. Es normal en CI.

## 📊 CI/CD Integration

Los tests están diseñados para CI:

```bash
# Run all tests
cd /Users/helmet/.openclaw/workspace/skills/web-scraper
source venv/bin/activate

python scripts/test_rate_limiter.py || exit 1
python scripts/test_rate_limiter_integration.py || exit 1

echo "✅ All rate limiter tests passed"
```

## 📚 Ver También

- [RATE_LIMITING.md](../docs/RATE_LIMITING.md) - Documentación completa
- [sources.json](../sources.json) - Configuración del rate limiter
- [monitor_daemon.py](./monitor_daemon.py) - Implementación
- [rate_limiter.py](./rate_limiter.py) - Rate limiter core
