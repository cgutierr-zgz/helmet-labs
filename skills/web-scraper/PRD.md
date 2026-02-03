# Web Scraper PRD - Trading Intelligence

## Objetivo
Extender el web scraper para alimentar el sistema de trading con fuentes que no tienen RSS/API: comunicados oficiales, páginas gubernamentales, earnings, sitios de empresas, etc.

## Problema
El trading bot actual depende de RSS y Twitter. Pero muchas señales valiosas están en:
- Páginas de gobiernos (FDA, SEC, White House)
- Comunicados de empresas (earnings, productos)
- Sitios de reguladores
- Páginas que cambian segundos antes de que salga la noticia en RSS

## Requisitos

### Must Have (v1)
1. **Playwright integrado** - JS rendering real, no el subprocess chapucero
2. **Monitor de cambios rápido** - Detectar cambios en <30 segundos
3. **Integración con event-driven** - Output compatible con el classifier existente
4. **Fuentes de trading** - Templates para sitios clave:
   - SEC (filings)
   - FDA (approvals, warnings)
   - White House (statements)
   - FED (announcements)
   - Earnings calendars

### Should Have (v2)
5. **Diff semántico** - Detectar cambios significativos vs ruido HTML
6. **Rate limiting inteligente** - No nos baneen
7. **Caché con ETags** - Eficiencia en polling
8. **Alertas prioritarias** - Webhook directo cuando hay cambio crítico

### Nice to Have (v3)
9. **Proxy rotation** - Para sitios quisquillosos
10. **Login/cookies** - Para fuentes con auth
11. **Screenshot diff** - Detección visual de cambios

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Web Scraper v2                        │
├─────────────────────────────────────────────────────────┤
│  sources.json          Lista de URLs + selectores        │
│  ├─ url                Página a monitorear              │
│  ├─ selector           CSS selector del contenido       │
│  ├─ interval           Frecuencia de check (segundos)   │
│  ├─ category           Tipo (government, corporate...)  │
│  └─ priority           1-5 (afecta orden de proceso)    │
├─────────────────────────────────────────────────────────┤
│  monitor_daemon.py     Loop principal de monitoreo      │
│  ├─ Playwright pool    Browsers reutilizables           │
│  ├─ Change detector    Compara con última versión       │
│  ├─ Event emitter      Genera eventos para classifier   │
│  └─ Health check       Reporta estado                   │
├─────────────────────────────────────────────────────────┤
│  templates/            Extractores por sitio            │
│  ├─ sec.py            SEC filings parser                │
│  ├─ fda.py            FDA announcements parser          │
│  ├─ whitehouse.py     White House statements            │
│  └─ generic.py        Fallback genérico                 │
├─────────────────────────────────────────────────────────┤
│  Output → event-driven/data/scraped_events.json         │
│  (mismo formato que RSS events, el classifier lo pilla) │
└─────────────────────────────────────────────────────────┘
```

## Fuentes Iniciales (Trading-relevant)

| Fuente | URL | Selector | Intervalo | Por qué |
|--------|-----|----------|-----------|---------|
| SEC Filings | sec.gov/cgi-bin/browse-edgar | .tableFile2 | 60s | Insider trading, 8-K filings |
| FDA News | fda.gov/news-events | .view-content | 120s | Drug approvals mueven mercados |
| White House | whitehouse.gov/briefing-room | .news-item | 60s | Policy announcements |
| FED | federalreserve.gov/newsevents | .ng-scope | 120s | Rate decisions |
| Treasury | home.treasury.gov/news | .views-row | 120s | Sanctions, policy |

## Integración con Trading Bot

```python
# El monitor genera eventos con este formato:
{
    "source": "web_scraper",
    "source_url": "https://sec.gov/...",
    "title": "8-K Filing: NVIDIA Corp",
    "content": "...",
    "detected_at": "2026-02-03T20:00:00Z",
    "category": "corporate",  # pre-clasificado
    "priority": 1,
    "raw_diff": "..."  # qué cambió exactamente
}

# El classifier del event-driven lo procesa igual que RSS
```

## Métricas de Éxito
- Detectar cambios en <30s desde que ocurren
- 0 falsos positivos por cambios de HTML irrelevantes
- Uptime >99% del monitor
- Al menos 1 señal útil por semana de fuentes web-only

## Riesgos
- Rate limiting / IP bans → mitigar con intervals conservadores
- Cambios de estructura HTML → templates actualizables
- Recursos (Playwright es pesado) → pool limitado de browsers

## Timeline
- **Fase 1** (hoy): Playwright + monitor básico + 2-3 fuentes
- **Fase 2** (esta semana): Templates especializados + diff semántico
- **Fase 3** (próxima semana): Integración completa con trading bot
