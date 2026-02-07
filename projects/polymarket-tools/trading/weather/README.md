# 🌤️ Weather Bot A — NOAA vs Polymarket

## Concepto
Compara forecasts de NOAA con precios de Polymarket para mercados de temperatura.
Busca edges donde el forecast difiere significativamente del precio del mercado.

## Archivo Principal
`weather_bot_a.py`

## Comandos
```bash
python3 weather_bot_a.py scan      # Escanea oportunidades
python3 weather_bot_a.py cycle     # Scan + paper trade (max 3/ciclo)
python3 weather_bot_a.py settle    # Cierra posiciones resueltas
python3 weather_bot_a.py report    # Reporte de estado
```

## Ciudades Monitoreadas
- NYC (Central Park)
- Chicago (O'Hare)
- Seattle (SeaTac)
- Atlanta (Hartsfield)
- Dallas (DFW)
- Miami (MIA)

## Mercados
Slug format: `highest-temperature-in-{city}-on-{month}-{day}-{year}`

Busca mercados con brackets de temperatura (ej: "32-33°F", "≥34°F", "≤31°F")

## Estado
`state_weather.json`
```json
{
  "balance": 45.0,
  "positions": [...],
  "history": [...]
}
```

## Ejecución
- Cada 2h via HEARTBEAT.md (cron isolated broken)
- Primero `settle` para cerrar resueltas
- Luego `cycle` para nuevos trades

## Posiciones Actuales (2026-02-06)
- Chicago ≥34°F (Feb 6)
- NYC ≥26°F (Feb 6)
- Seattle ≥56°F (Feb 6)
- Dallas ≥74°F (Feb 6)
- Seattle ≥54°F (Feb 8) — NEW
- Miami ≤71°F (Feb 7) — NEW
- Atlanta ≥54°F (Feb 7) — NEW

## Edge Calculation
```
edge = (noaa_probability - market_price) 
```
- NOAA prob se estima con distribución normal centrada en forecast
- Tradea si edge ≥ 15% (configurable)

---
*Creado: 2026-02-06*
