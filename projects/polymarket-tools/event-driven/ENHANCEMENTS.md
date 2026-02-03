# Enhancement Tasks 🚀

## Priority Enhancements

### ENHANCE-001: Backtesting Framework
**Valor**: 🔥🔥🔥 Crítico - validar si el sistema funciona
**Objetivo**: Simular el sistema con datos históricos

**Implementar**:
- Recopilar eventos históricos (RSS archives, Twitter history)
- Recopilar precios históricos de Polymarket
- Simular: evento detectado → señal generada → precio se movió?
- Calcular métricas: win rate, average return, max drawdown
- Output: "Si hubiéramos corrido esto el último mes, habríamos ganado/perdido X"

**Archivos**:
- `src/backtesting/runner.py` - Motor de backtesting
- `src/backtesting/data_loader.py` - Carga datos históricos
- `src/backtesting/metrics.py` - Cálculo de métricas
- `data/historical/` - Datos históricos

### ENHANCE-002: Production Monitor Service
**Valor**: 🔥🔥 Alto - ver el sistema en acción
**Objetivo**: Servicio 24/7 que monitorea y alerta

**Implementar**:
- Launchd service (como el arb-bot)
- Logging estructurado a archivo
- Integración con Helmet para alertas Telegram
- Métricas de salud (uptime, eventos/hora, señales/día)
- Archivo de señales generadas para análisis

**Archivos**:
- `services/monitor.py` - Main monitor service
- `services/health.py` - Health checks
- `com.helmet.eventmonitor.plist` - Launchd config

### ENHANCE-003: Historical Data Collection
**Valor**: 🔥🔥 Necesario para backtesting
**Objetivo**: Recopilar datos históricos de Polymarket

**Implementar**:
- Scraper de precios históricos de Polymarket
- Almacenamiento en SQLite o JSON
- Datos de al menos 30 días atrás
- Incluir: precio, volumen, liquidez por hora

### ENHANCE-004: Signal Performance Tracker
**Valor**: 🔥🔥 Medir accuracy de señales
**Objetivo**: Trackear si las señales fueron correctas

**Implementar**:
- Guardar cada señal generada con timestamp
- Después de X tiempo, verificar si el precio se movió como predijimos
- Calcular accuracy rate en tiempo real
- Dashboard simple de performance

---

## Execution Plan

**Wave 1** (ahora):
- ENHANCE-001: Backtesting framework
- ENHANCE-002: Production monitor service

**Wave 2** (después de validar):
- ENHANCE-003: Historical data collection
- ENHANCE-004: Signal performance tracker

**Wave 3** (si funciona):
- Más fuentes de datos
- Semi-auto trading con confirmación manual
