# Event-Driven Trading - Roadmap 🗺️

## Fase 1: Foundation ✅ (DONE)
- [x] Scanner básico de RSS feeds
- [x] Integración con Twitter via `bird` CLI
- [x] Keywords por categoría (politics, fed, crypto, etc.)
- [x] Sistema de logging de alertas
- [x] Estructura en repo con git

---

## Fase 2: Data Quality 🎯 (NEXT)
**Objetivo:** Reducir ruido, aumentar señal

### 2.1 Mejores fuentes
- [ ] Añadir feeds RSS de alta calidad:
  - Bloomberg Terminal leaks (Twitter accounts)
  - Fed Watch específicos
  - Polymarket Discord/Telegram
- [ ] Twitter lists curadas por categoría
- [ ] Webhooks de servicios de alertas (ej: unusual_whales API)

### 2.2 Filtrado inteligente
- [ ] NLP básico para clasificar relevancia (no solo keywords)
- [ ] Deduplicación de noticias (misma noticia, múltiples fuentes)
- [ ] Scoring de urgencia (1-10)
- [ ] Filtro de "ya es viejo" (noticia de hace >1h = probablemente priced in)

### 2.3 Contexto de mercado
- [ ] Conectar con API de Polymarket para ver precios actuales
- [ ] Calcular: ¿cuánto se ha movido el mercado desde la noticia?
- [ ] Historical data: ¿cómo reaccionaron mercados similares antes?

---

## Fase 3: Intelligence Layer 🧠
**Objetivo:** De alertas a recomendaciones accionables

### 3.1 Market mapping
- [ ] Base de datos de mercados activos en Polymarket
- [ ] Mapeo automático: evento → mercados afectados
- [ ] Tracking de liquidez y volumen por mercado

### 3.2 Signal generation
- [ ] Modelo de "expected move" basado en tipo de evento
- [ ] Comparar precio actual vs precio esperado post-evento
- [ ] Generar señal: BUY / SELL / HOLD con confidence score

### 3.3 Backtesting
- [ ] Histórico de eventos pasados
- [ ] Simular: si hubiéramos actuado, ¿cuánto habríamos ganado?
- [ ] Refinar thresholds basado en backtests

---

## Fase 4: Automation 🤖
**Objetivo:** Reducir latencia humana

### 4.1 Alertas en tiempo real
- [ ] Push notifications a Telegram (prioridad alta)
- [ ] Dashboard web con mercados + alertas
- [ ] Sonido/vibración para alertas urgentes

### 4.2 Semi-auto trading
- [ ] Botón "ejecutar trade" desde la alerta
- [ ] Pre-calcular tamaño de posición óptimo
- [ ] Confirmación con 1 click

### 4.3 Full auto (con límites)
- [ ] Auto-execute para señales de alta confianza
- [ ] Límites estrictos: max $ por trade, max $ diario
- [ ] Kill switch manual siempre disponible

---

## Fase 5: Edge Expansion 🌐
**Objetivo:** Más mercados, más edge

### 5.1 Multi-platform
- [ ] Kalshi (ya tenemos API key)
- [ ] PredictIt (si aplica)
- [ ] Metaculus (para calibración)

### 5.2 Nuevas categorías
- [ ] Sports (datos de lesiones, lineups)
- [ ] Weather (para mercados de clima)
- [ ] Earnings (para mercados de empresas)

### 5.3 Alpha sources
- [ ] Insider Telegram channels
- [ ] Discord servers de nichos específicos
- [ ] Scraping de fuentes no-mainstream

---

## Métricas de Éxito

| Métrica | Target Fase 2 | Target Fase 4 |
|---------|---------------|---------------|
| Alertas/día | 5-10 relevantes | 10-20 |
| Falsos positivos | <30% | <10% |
| Latencia (evento→alerta) | <5 min | <1 min |
| Win rate en trades | >55% | >60% |
| ROI mensual | Breakeven | >10% |

---

## Timeline Estimado

- **Fase 2**: 1-2 semanas
- **Fase 3**: 2-3 semanas  
- **Fase 4**: 2-4 semanas
- **Fase 5**: Ongoing

---

*Last updated: 2026-02-03*
