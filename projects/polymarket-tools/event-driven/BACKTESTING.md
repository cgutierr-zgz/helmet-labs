# 🧪 Backtesting Framework

Framework completo para validar el sistema de trading de Polymarket con datos históricos simulados.

## ✨ Características

- **Simulación completa**: Ejecuta eventos a través del pipeline completo (classify → score → map → signal)
- **Datos mock realistas**: Genera eventos y precios históricos para testing
- **Métricas avanzadas**: Win rate, Sharpe ratio, max drawdown, profit factor
- **Análisis detallado**: Performance por mercado, dirección y nivel de confianza

## 🚀 Uso Rápido

```bash
# Backtest básico con datos mock (30 días)
python3 run_backtest.py

# Backtest con análisis detallado
python3 run_backtest.py --days 30 --detailed

# Guardar resultados en JSON
python3 run_backtest.py --detailed --output results.json

# Solo generar datos mock
python3 run_backtest.py --generate-data --days 30

# Usar pipeline completo (más lento pero realista)
python3 run_backtest.py --full-pipeline
```

## 📊 Output Ejemplo

```
🧪 POLYMARKET BACKTESTING FRAMEWORK
============================================================
Configuration:
  📅 Period: 30 days
  🎲 Mock data: True
  🏭 Mock pipeline: True
  ⏰ Holding period: 24h

📊 Loaded 67 events and 5 markets

==================================================
           BACKTEST RESULTS
==================================================
Period: 20.8 days
Total trades: 19
Wins: 10 | Losses: 9
Win rate: 52.6%
Average return per trade: -0.1%
Total return: -2.6%
Best trade: +3.0%
Worst trade: -4.5%
Max drawdown: 7.4%
Sharpe ratio: -1.09
==================================================
```

## 🔧 Componentes

### 1. **data_loader.py**
- Carga eventos y precios históricos de JSON
- Genera datos mock realistas para testing
- Soporta 5 categorías: fed, crypto, politics, stocks, economy

### 2. **simulator.py**
- `BacktestSimulator`: Usa pipeline completo del sistema
- `MockPipelineSimulator`: Pipeline simplificado para testing rápido
- Simula compra/venta con períodos de holding configurables

### 3. **metrics.py**
- Métricas básicas: win rate, average return, best/worst trade
- Métricas de riesgo: Sharpe ratio, max drawdown, volatility
- Análisis por mercado, dirección y confianza

### 4. **runner.py**
- CLI completa para ejecutar backtests
- Opciones flexibles de configuración
- Export de resultados a JSON

## 📁 Datos Mock

El sistema genera datos realistas:

- **Eventos**: 50-100 eventos por período
- **Mercados**: 5 mercados activos con categorías diferentes
- **Precios**: Random walk con mean reversion y volatilidad realista

### Mercados Mock:
1. `mkt_fed_rate_dec_2024` - Política monetaria Fed
2. `mkt_bitcoin_100k_2024` - Bitcoin $100K predicción
3. `mkt_trump_president_2024` - Elección presidencial
4. `mkt_nvidia_split_2024` - Stock split NVIDIA
5. `mkt_recession_q1_2024` - Recesión económica

## 🎯 Parámetros Clave

- `--days`: Período de backtest (default: 30)
- `--holding-period`: Horas para mantener posiciones (default: 24)
- `--full-pipeline`: Usar pipeline completo vs mock
- `--detailed`: Análisis detallado por categorías
- `--output`: Guardar resultados JSON detallados

## 📈 Métricas Incluidas

### Básicas
- Total trades, wins, losses
- Win rate (%)
- Average return per trade
- Best/worst single trade

### Avanzadas
- Sharpe ratio (risk-adjusted returns)
- Maximum drawdown
- Profit factor (profits/losses)
- Volatility annualizada

### Análisis Segmentado
- Performance por mercado
- Performance por dirección (BUY_YES vs BUY_NO)
- Performance por nivel de confianza

## 🔄 Workflows

### Desarrollo de Estrategias
1. Modificar lógica de señales en `intelligence/signals.py`
2. Ejecutar backtest: `python3 run_backtest.py --detailed`
3. Analizar métricas y ajustar parámetros
4. Repetir hasta optimizar performance

### Validación de Modelos
1. Entrenar nuevo modelo de clasificación/scoring
2. Usar `--full-pipeline` para testing realista
3. Comparar métricas antes/después del cambio
4. Implementar si hay mejora significativa

### Testing Continuo
1. Configurar backtests automatizados
2. Monitorear métricas clave (win rate, Sharpe)
3. Alertas si performance degrada
4. Re-entrenar modelos periódicamente

## 🚨 Limitaciones

- **Datos mock**: No reflejan dinámicas reales del mercado
- **Slippage**: No considera costos de transacción
- **Liquidez**: Asume ejecución perfecta de trades
- **Look-ahead bias**: Eventos futuros no afectan precios pasados

## 🔮 Próximas Mejoras

- [ ] Integración con datos reales de Polymarket
- [ ] Modelado de slippage y fees
- [ ] Backtesting walk-forward
- [ ] Optimización de parámetros
- [ ] Análisis de correlaciones entre mercados
- [ ] Monte Carlo simulations

## 📖 Ejemplo de Uso Avanzado

```bash
# Generar datos para 60 días
python3 run_backtest.py --generate-data --days 60

# Backtest con holding period de 12h
python3 run_backtest.py --holding-period 12 --detailed

# Pipeline completo con análisis completo
python3 run_backtest.py --full-pipeline --detailed --output full_analysis.json

# Solo análisis rápido
python3 run_backtest.py --days 7
```

Esto permite validar rápidamente si las señales del sistema serían rentables antes de implementar trading real.