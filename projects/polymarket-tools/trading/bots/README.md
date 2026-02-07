# 🤖 Trading Bots - BTC 15min/1h Markets

## 3-Bot Comparison Experiment
Experimento activo desde 2026-02-05 comparando 3 estrategias en los mismos mercados.

### Bot A — Rules-Based (`auto_trader_v2.py`)
- **Estrategia:** Reglas fijas + BTC feed + momentum/contrarian/volatility rotation
- **Estado:** `state_v2.json`
- **Config:** `config_override.json` (generado por learner)
- **Cron:** Cada 5 min via HEARTBEAT.md (cron isolated broken)

### Bot B — Technical Indicators (`bot_b_technical.py`)
- **Estrategia:** RSI + MACD + EMA + Bollinger Bands + BTC feed
- **Indicadores:** RSI<30 oversold, RSI>70 overbought, EMA crossovers
- **Estado:** `state_bot_b.json`

### Bot C — AI Decision Maker (`bot_c_ai.py`)
- **Estrategia:** Toda la data → GPT-4o-mini decide (Anthropic sin créditos)
- **Ventaja:** Puede abstenerse cuando señales conflictivas
- **Estado:** `state_bot_c.json`

## Otros Bots

### Multi-Market Trader (`multi_market_trader.py`)
- Tradea múltiples mercados (no solo BTC)
- Report: `multi-market-report.md`

### Learner (`learner.py`)
- Analiza histórico de trades
- Genera `config_override.json` con ajustes de SL/TP/estrategia
- Corre cada 6h

### Legacy
- `auto_trader.py` — v1, deprecated (18W-27L, -$37.59)
- `short_term_trader.py` — experimento anterior

## Estado Actual (2026-02-06)
| Bot | Record | P&L | Notas |
|-----|--------|-----|-------|
| A | 12W-7L | -$8.71 | Solo mañanas (8-14h) |
| B | 2W-4L | -$11.82 | Technical veto frecuente |
| C | 4W-5L | -$7.45 | Mejor take profit timing |

## Archivos de Estado
- `state_v2.json` — Bot A positions + history
- `state_bot_b.json` — Bot B positions + history  
- `state_bot_c.json` — Bot C positions + history
- `analysis_log.json` — Historial de análisis
- `btc_feed.json` — BTC price feed (actualizado por launchd)
- `config_override.json` — Overrides generados por learner

## Lecciones Aprendidas
1. **No tradear bias <60%** — v1 mostró 33% WR en bias débil
2. **Morning >> Afternoon** — 83% WR mañanas vs 25% tarde
3. **15m >> 1h** — 15m tiene 80% WR, 1h 44%
4. **AI sabe abstenerse** — Bot C reconoce señales conflictivas

---
*Actualizado: 2026-02-06*
