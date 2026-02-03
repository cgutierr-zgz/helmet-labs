# Rate Limiting System

Sistema completo de rate limiting para web scraper, diseñado para evitar baneos y recuperarse de errores.

## 📋 Componentes

### 1. **RateLimiter** (`scripts/rate_limiter.py`)

Controla la frecuencia de requests **por dominio**.

**Features:**
- ⏱️ Delay configurable entre requests al mismo dominio
- 🔄 Backoff exponencial cuando hay errores
- ⚠️ Backoff agresivo (x3) para errores 429 (Too Many Requests)
- 🎲 Jitter aleatorio (±20%) para evitar patrones predecibles
- 🚫 Skip automático de dominios con demasiados errores consecutivos
- 🔒 Thread-safe con asyncio locks por dominio

**Configuración:**
```json
{
  "config": {
    "rate_limit_per_domain_ms": 2000,    // 2s entre requests al mismo dominio
    "max_consecutive_errors": 5          // Skip dominio tras 5 errores
  }
}
```

**Uso:**
```python
limiter = RateLimiter()

# Esperar turno antes de hacer request
await limiter.acquire(url)

# Reportar resultado
limiter.report_success(url)  # Resetea errores, reduce delay gradualmente
limiter.report_error(url, status_code=429)  # Aumenta backoff

# Check si debería skipear
if limiter.should_skip(url, max_errors=5):
    print("Too many errors, skipping")
```

**Comportamiento:**
- **Primer error:** delay × 1.5
- **Segundo error:** delay × 1.5 de nuevo (exponencial)
- **Error 429:** delay × 3 (backoff agresivo)
- **Éxito:** delay × 0.8 (gradualmente vuelve a normal)
- **Max delay:** 60s (configurable)

### 2. **RetryHandler** (`scripts/rate_limiter.py`)

Maneja reintentos con exponential backoff.

**Features:**
- 🔁 Reintentos automáticos con backoff exponencial
- 🎲 Jitter aleatorio para evitar thundering herd
- ⚙️ Configurable: max_retries y base_delay

**Configuración:**
```json
{
  "config": {
    "max_retries": 3,
    "retry_base_delay_ms": 1000  // 1s base, luego 2s, 4s, 8s...
  }
}
```

**Uso:**
```python
handler = RetryHandler(max_retries=3, base_delay=1.0)

async def fetch():
    # Tu código que puede fallar
    return await session.get(url)

# Ejecutar con retry
result = await handler.execute(fetch)
```

**Delays de retry:**
- Intento 1: sin delay
- Intento 2: base_delay × 2^0 + random = ~1s
- Intento 3: base_delay × 2^1 + random = ~2s
- Intento 4: base_delay × 2^2 + random = ~4s

### 3. **User-Agent Rotation** (`monitor_daemon.py`)

Rota user-agents para evitar fingerprinting.

**Pool de user-agents:**
- Chrome (Mac/Windows/Linux)
- Safari (Mac)
- Firefox (Windows)

**Configuración:**
```json
{
  "config": {
    "user_agent_rotation": true  // Activar rotación
  }
}
```

Por defecto: **activado**.

## 🔧 Integración en monitor_daemon.py

El rate limiter está completamente integrado:

### Flujo de una request:

```python
# 1. Check si debería skipear el dominio
if limiter.should_skip(url, max_errors):
    raise RuntimeError("Domain skipped")

# 2. Esperar turno (rate limiting)
await limiter.acquire(url)

# 3. Hacer request con retry
async def _fetch():
    async with session.get(url) as resp:
        if resp.status == 429:
            limiter.report_error(url, 429)  # Backoff agresivo
        resp.raise_for_status()
        return await resp.text()

result = await retry_handler.execute(_fetch)

# 4. Reportar éxito
limiter.report_success(url)
```

### Estado persistente:

El estado de errores **NO se persiste** entre ejecuciones del daemon. Cada ejecución empieza fresco, pero durante la ejecución mantiene el contador de errores por dominio.

## 🧪 Testing

### Test unitario: `scripts/test_rate_limiter.py`

Tests completos del rate limiter:

```bash
cd /Users/helmet/.openclaw/workspace/skills/web-scraper
source venv/bin/activate
python scripts/test_rate_limiter.py
```

**Tests incluidos:**
1. ✅ Basic rate limiting (delays por dominio)
2. ✅ Backoff on errors (exponencial)
3. ✅ Should skip (tras muchos errores)
4. ✅ Retry handler (con exponential backoff)
5. ✅ Parallel requests (mismo dominio)
6. ✅ Different domains (no se bloquean entre sí)

### Test de integración: `scripts/test_rate_limiter_integration.py`

Test end-to-end con servidor HTTP real:

```bash
cd /Users/helmet/.openclaw/workspace/skills/web-scraper
source venv/bin/activate
python scripts/test_rate_limiter_integration.py
```

**Qué testea:**
- Levanta servidor HTTP local que devuelve 429
- Ejecuta monitor_daemon.py contra ese servidor
- Verifica que:
  - Se detectan los errores 429
  - Se aumenta el backoff
  - Se reintentan las requests
  - Eventualmente se recupera
  - El estado se guarda correctamente

**Output esperado:**
```
📨 Request #1 recibida → 429
📨 Request #2 recibida → 429
📨 Request #3 recibida → 200 OK
✅ ALL CHECKS PASSED
```

## 📊 Métricas y Monitoring

El estado del rate limiter se refleja en el state file (`data/monitor_state.json`):

```json
{
  "source-id": {
    "last_check": "2026-02-03T22:36:23Z",
    "consecutive_errors": 0,
    "last_error": "HTTP 429...",
    "items_count": 10
  }
}
```

**Campos relevantes:**
- `consecutive_errors`: Número de errores seguidos
- `last_error`: Último error encontrado
- Si `consecutive_errors >= max_consecutive_errors`, el dominio se skipeará

## 🚨 Troubleshooting

### "Domain skipped due to too many consecutive errors"

**Causa:** El dominio ha fallado muchas veces seguidas.

**Solución:**
1. Verificar que la URL es correcta
2. Verificar que el sitio está online
3. Aumentar `max_consecutive_errors` en config
4. Revisar logs para ver el error específico

### "HTTP 429 (Too Many Requests)"

**Causa:** El sitio detectó demasiadas requests.

**Solución automática:** El rate limiter aumenta el backoff x3 automáticamente.

**Solución manual:**
1. Aumentar `rate_limit_per_domain_ms` en config
2. Reducir `max_concurrent_requests` en config
3. Considerar usar proxy rotativo

### Requests muy lentas

**Causa:** Backoff demasiado agresivo tras errores.

**Para resetear:** Reiniciar el daemon (el estado de errores se pierde).

**Para prevenir:**
1. Asegurar que las URLs son correctas
2. Verificar que los sitios están online
3. Ajustar `retry_base_delay_ms` más bajo

## ⚙️ Configuración Recomendada

### Para sitios **tolerantes** (blogs, feeds RSS):
```json
{
  "config": {
    "rate_limit_per_domain_ms": 1000,
    "max_retries": 3,
    "retry_base_delay_ms": 500,
    "max_consecutive_errors": 5,
    "max_concurrent_requests": 5,
    "user_agent_rotation": true
  }
}
```

### Para sitios **estrictos** (news sites, APIs):
```json
{
  "config": {
    "rate_limit_per_domain_ms": 5000,
    "max_retries": 2,
    "retry_base_delay_ms": 2000,
    "max_consecutive_errors": 3,
    "max_concurrent_requests": 2,
    "user_agent_rotation": true
  }
}
```

### Para **desarrollo/testing**:
```json
{
  "config": {
    "rate_limit_per_domain_ms": 500,
    "max_retries": 1,
    "retry_base_delay_ms": 100,
    "max_consecutive_errors": 10,
    "max_concurrent_requests": 3,
    "user_agent_rotation": false
  }
}
```

## 📚 Referencias

- **Rate limiter:** `scripts/rate_limiter.py`
- **Integración:** `scripts/monitor_daemon.py`
- **Tests:** `scripts/test_rate_limiter.py`, `scripts/test_rate_limiter_integration.py`
- **Config:** `sources.json` (sección `config`)

## 🎯 Próximos pasos potenciales

- [ ] Proxy rotativo para distribución de IP
- [ ] Rate limiting basado en tokens (token bucket algorithm)
- [ ] Persistencia del estado de errores entre ejecuciones
- [ ] Dashboard para monitoring de rate limits
- [ ] Integración con Prometheus/Grafana
