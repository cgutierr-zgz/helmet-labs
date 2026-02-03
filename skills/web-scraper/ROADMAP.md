# Web Scraper Roadmap - Trading Edition

## Fase 1: Fundamentos (Hoy)

### TASK-001: Playwright Setup
**Objetivo:** Instalar y configurar Playwright correctamente
- [ ] Instalar playwright en el venv del skill
- [ ] Instalar browsers (chromium)
- [ ] Crear `browser_pool.py` con context manager reutilizable
- [ ] Test básico que funcione

**Archivos:** `scripts/browser_pool.py`
**Test:** Scrape de polymarket.com con JS rendering

---

### TASK-002: Monitor Daemon
**Objetivo:** Daemon que monitorea múltiples URLs en paralelo
- [ ] Crear `monitor_daemon.py` con asyncio
- [ ] Cargar fuentes desde `sources.json`
- [ ] Loop de polling con intervals configurables
- [ ] Detección de cambios (hash del contenido)
- [ ] Guardar estado en `data/monitor_state.json`
- [ ] Output de eventos a `data/scraped_events.json`

**Archivos:** `scripts/monitor_daemon.py`, `sources.json`, `data/`
**Test:** Monitorear HN y detectar nuevos posts

---

### TASK-003: Trading Sources Config
**Objetivo:** Configurar fuentes iniciales relevantes para trading
- [ ] Crear `sources.json` con formato estándar
- [ ] Añadir SEC, FDA, White House (con selectores correctos)
- [ ] Probar que cada fuente se scrapea bien
- [ ] Documentar selectores en comentarios

**Archivos:** `sources.json`
**Test:** Cada fuente devuelve contenido válido

---

## Fase 2: Inteligencia (Esta semana)

### TASK-004: Diff Semántico
**Objetivo:** Detectar cambios significativos, ignorar ruido HTML
- [ ] Extraer texto limpio antes de comparar
- [ ] Ignorar timestamps, session IDs, ads
- [ ] Calcular diff a nivel de líneas de texto
- [ ] Threshold configurable de "cambio significativo"

**Archivos:** `scripts/diff_engine.py`
**Test:** No alertar si solo cambia un timestamp

---

### TASK-005: Templates Especializados
**Objetivo:** Parsers específicos para extraer datos estructurados
- [ ] `templates/sec.py` - Extraer filing type, company, date
- [ ] `templates/fda.py` - Extraer drug name, action type
- [ ] `templates/generic.py` - Fallback con heurísticas
- [ ] Auto-selección de template por URL

**Archivos:** `templates/*.py`
**Test:** SEC filing parseado a JSON estructurado

---

### TASK-006: Event-Driven Integration
**Objetivo:** Conectar output con el trading bot existente
- [ ] Formato de eventos compatible con classifier
- [ ] Escribir a `event-driven/data/scraped_events.json`
- [ ] Modificar orchestrator para leer de esta fuente
- [ ] Prioridad configurable (web events = high priority)

**Archivos:** Modificar `event-driven/src/orchestrator.py`
**Test:** Evento de web scraper procesado por el pipeline

---

## Fase 3: Producción (Próxima semana)

### TASK-007: Launchd Service
**Objetivo:** Monitor corriendo 24/7 como servicio
- [ ] Crear plist para launchd
- [ ] Health check endpoint
- [ ] Auto-restart en fallo
- [ ] Logging a archivo

**Archivos:** `com.helmet.webscraper.plist`
**Test:** Servicio sobrevive a restart

---

### TASK-008: Rate Limiting & Resilience
**Objetivo:** No nos baneen, recuperarse de errores
- [ ] Rate limiter por dominio
- [ ] Retry con backoff exponencial
- [ ] Rotación de User-Agents
- [ ] Alertar si una fuente falla repetidamente

**Archivos:** `scripts/rate_limiter.py`
**Test:** Recuperarse de 429/503

---

## Orden de Ejecución

```
TASK-001 (Playwright) ──┐
                        ├──► TASK-002 (Monitor) ──► TASK-004 (Diff)
TASK-003 (Sources) ─────┘                              │
                                                       ▼
                                              TASK-005 (Templates)
                                                       │
                                                       ▼
                                              TASK-006 (Integration)
                                                       │
                                                       ▼
                                              TASK-007 (Service)
                                                       │
                                                       ▼
                                              TASK-008 (Resilience)
```

## Agentes Sugeridos

| Task | Complejidad | Agente |
|------|-------------|--------|
| TASK-001 | Baja | Sonnet |
| TASK-002 | Media | Sonnet |
| TASK-003 | Baja | Sonnet |
| TASK-004 | Media | Sonnet |
| TASK-005 | Media | Sonnet |
| TASK-006 | Media | Sonnet |
| TASK-007 | Baja | Sonnet |
| TASK-008 | Media | Sonnet |

Todo Sonnet, yo superviso y hago QA.
