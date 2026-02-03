# Polymarket Tools 🎯

Sistema completo de trading para mercados de predicción.

## Componentes

### 1. `arb-bot/` - Arbitrage Monitor
Monitor de arbitraje entre Polymarket y Kalshi.
- Detecta oportunidades de arbitraje cross-platform
- Corre como servicio launchd 24/7
- Gap actual típico: $0.04-0.08

### 2. `event-driven/` - Event-Driven Trading System ⭐
Sistema completo de trading basado en eventos. **6,000+ líneas de código.**

#### Arquitectura:
```
📥 RSS + Twitter → 🏷️ Classify → 📊 Score → 🔄 Dedupe → 🎯 Map Markets → 💰 Prices → 🔮 Signals → 📱 Alerts
```

#### Módulos:
- **Fetchers**: RSS (17 feeds, 3 tiers), Twitter (4 tiers + rate limiting), Polymarket prices
- **Processors**: Classifier (5 categorías), Scorer (6 factores), Deduplicator (4 estrategias)
- **Intelligence**: Market Mapper (87 keywords), Signal Generator (confidence scoring)
- **Outputs**: Telegram alerts con priorización

#### Features:
- ✅ Pipeline completo end-to-end
- ✅ Clasificación inteligente de eventos
- ✅ Scoring multi-factor (source, recency, confirmation)
- ✅ Mapeo a 50+ mercados de Polymarket
- ✅ Generación de señales con confidence
- ✅ Rate limiting y deduplicación
- ✅ Monitor service 24/7 (launchd)
- ✅ Paper trading autónomo
- ✅ Backtesting framework

## Quick Start

```bash
cd event-driven
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Single scan
python3 main.py --once --verbose

# Continuous monitoring
python3 run_monitor.py --interval 300

# Install as service
cp com.helmet.eventmonitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.helmet.eventmonitor.plist
```

## Roadmap

- [x] ~~Arb monitor básico~~
- [x] ~~Event scanner v0.1~~
- [x] ~~Sistema de scoring~~
- [x] ~~Conectar con precios tiempo real~~
- [x] ~~Signal generation~~
- [x] ~~Monitor service 24/7~~
- [x] ~~Paper trading system~~
- [x] ~~Backtesting framework~~
- [ ] Más fuentes (Discord, Telegram insiders)
- [ ] ML-based classifier
- [ ] Dashboard web
- [ ] Semi-auto trading con confirmación

## Performance

- **Events procesados**: 60+ por scan
- **Latencia**: <30s evento→alerta
- **Uptime**: 24/7 via launchd

## Disclaimer

Esto es experimental. No es consejo financiero. Paper trading primero.

---
*Built by Helmet 🪖 | 2026-02-03*
