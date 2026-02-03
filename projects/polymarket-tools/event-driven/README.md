# Event-Driven Trading System 🎯

Sistema de monitoreo de eventos para trading en Polymarket.

## Componentes

### 1. `scan.py`
Scanner que revisa RSS feeds y Twitter buscando eventos relevantes.

```bash
cd /Users/helmet/.openclaw/workspace/event-driven
source venv/bin/activate
python3 scan.py
```

### 2. `sources.json`
Configuración de fuentes (Twitter accounts, RSS feeds) y mappings a mercados.

### 3. `STRATEGY.md`
Documentación de la estrategia y categorías de eventos.

### 4. `alerts.jsonl`
Log de todas las alertas detectadas.

## Cómo funciona

1. El scanner revisa fuentes cada X minutos
2. Busca keywords específicos por categoría
3. Si encuentra algo, loguea una alerta
4. Helmet revisa las alertas y notifica a Ichi si hay oportunidad

## Categorías monitoreadas

- 🏛️ **Trump/Politics**: deportaciones, tariffs, policy
- 💰 **Fed/Economy**: rate decisions, inflation data
- 🌍 **Geopolitics**: Russia-Ukraine, China-Taiwan
- ₿ **Crypto**: BTC movements, ETF news
- 🎮 **Entertainment**: GTA VI, releases

## Próximos pasos

- [ ] Integrar con Polymarket API para ver precios actuales
- [ ] Crear servicio launchd para monitoreo 24/7
- [ ] Añadir más fuentes (Discord leaks, Telegram channels)
- [ ] Sistema de scoring para priorizar alertas
