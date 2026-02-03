# Polymarket Tools 🎯

Herramientas para trading en Polymarket.

## Componentes

### 1. `arb-bot/` - Arbitrage Monitor
Monitor de arbitraje entre Polymarket y Kalshi para mercados de BTC.

- Detecta oportunidades de arbitraje cross-platform
- Dashboard web para visualización
- Logs oportunidades para análisis

### 2. `event-driven/` - Event Scanner
Sistema de monitoreo de eventos para trading direccional.

- Escanea RSS feeds y Twitter
- Detecta eventos que moverán mercados
- Categorías: Politics, Fed, Geopolitics, Crypto, Entertainment

## Setup

```bash
# Arb monitor
cd arb-bot/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 ../monitor.py

# Event scanner
cd event-driven
python3 -m venv venv
source venv/bin/activate
pip install feedparser requests
python3 scan.py
```

## Roadmap

- [x] Arb monitor básico (Polymarket ↔ Kalshi)
- [x] Event scanner v0.1 (RSS + Twitter keywords)
- [ ] Conectar scanner con precios en tiempo real
- [ ] Sistema de scoring de alertas
- [ ] Más fuentes (Telegram, Discord)
- [ ] Backtesting framework
- [ ] Ejecución automática de trades

## Disclaimer

Esto es experimental. No es consejo financiero. Úsalo bajo tu propio riesgo.
