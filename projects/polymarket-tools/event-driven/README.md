# Event-Driven Trading System 🎯

Sistema de monitoreo de eventos para trading en Polymarket.
**v2.0 - Fase 2: Data Quality completada** ✅

## Quick Start

```bash
cd /Users/helmet/.openclaw/workspace/helmet-labs/projects/polymarket-tools/event-driven
pip3 install --user --break-system-packages -r requirements.txt
python3 scan.py
```

## Componentes

### 1. `scan.py` (v2.0)
Scanner inteligente con scoring de urgencia y deduplicación.

**Nuevas funciones v2.0:**
- ⚡ **Scoring de urgencia** (1-10): Prioriza alertas por importancia
- 🔄 **Deduplicación avanzada**: Evita la misma noticia de múltiples fuentes
- 📊 **Filtrado por calidad**: Solo muestra alertas con urgency ≥4
- 🎯 **15+ fuentes RSS** de alta calidad añadidas

### 2. `sources.json` (mejorado)
Configuración expandida con fuentes premium:
- **Bloomberg Terminal leaks** (Twitter)
- **Fed-specific** accounts 
- **Alta calidad RSS**: Fed official, Reuters breaking, etc.
- **Priority tiers**: High/medium priority sources

### 3. Otros archivos
- `ROADMAP.md` - Plan de desarrollo
- `STRATEGY.md` - Documentación de estrategia
- `alerts.jsonl` - Log de alertas detectadas
- `requirements.txt` - Dependencias Python

## Cómo funciona (v2.0)

1. **Scanner revisa** RSS feeds + Twitter accounts prioritarios
2. **Detecta eventos** usando keywords por categoría
3. **Calcula urgency score** basado en:
   - Importancia de categoría (Fed = máxima prioridad)
   - Keywords de urgencia ("breaking", "just in", etc.)
   - Calidad de la fuente
   - Frescura temporal
4. **Deduplica** usando similaridad de contenido + hash
5. **Filtra y loguea** solo alertas de calidad (score ≥4)

## Categorías monitoreadas

- 🏛️ **Trump/Politics**: deportaciones, tariffs, policy 
- 💰 **Fed/Economy**: rate decisions, FOMC, Powell (PRIORIDAD ALTA)
- 🌍 **Geopolitics**: Russia-Ukraine, China-Taiwan
- ₿ **Crypto**: BTC movements, ETF news
- 🎮 **Entertainment**: GTA VI, releases

## Ejemplo de Output v2.0

```
🔍 Event scan started at 2026-02-03T17:32:45
📰 Scanning RSS feeds...
   Found 9 potential alerts from RSS  
🐦 Scanning Twitter...
   Found 0 potential alerts from Twitter
🔥 ALERT [fed] Score:10.0/10 - Federal Reserve Board announces approval...
🔥 ALERT [tariffs] Score:9.5/10 - Pfizer's stock falls after mixed response...

✅ Scan complete. 2 new alerts logged (urgency ≥4).
   Average urgency score: 9.8/10
```

## Roadmap Status

- [x] **Fase 1: Foundation** - Scanner básico ✅
- [x] **Fase 2: Data Quality** - Scoring + deduplicación ✅
- [ ] **Fase 3: Intelligence Layer** - Market mapping + signals 
- [ ] **Fase 4: Automation** - Real-time alerts + trading
- [ ] **Fase 5: Edge Expansion** - Multi-platform + nuevas categorías

## Próximos pasos (Fase 3)

- [ ] Integrar con Polymarket API para precios actuales
- [ ] Mapeo automático: evento → mercados afectados
- [ ] Sistema de "expected move" basado en tipo de evento
- [ ] Backtesting de alertas históricas
