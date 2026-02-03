# Event-Driven Trading Strategy 🎯

## Concepto
Monitorear fuentes de información en tiempo real, detectar eventos que moverán mercados de Polymarket, y alertar ANTES de que el precio reaccione.

## Categorías de Eventos

### 1. 🏛️ Política USA (Trump, Congress, Policy)
**Mercados:** Deportaciones, Tariffs, DOGE cuts, Impeachment
**Fuentes a monitorear:**
- Twitter/X: @realDonaldTrump, @WhiteHouse, @WSJ, @AP
- RSS: Reuters Politics, Politico, The Hill
- Government: WhiteHouse.gov announcements, Congress.gov
**Triggers:** Executive orders, court decisions, official statements

### 2. 💰 Economía/Fed
**Mercados:** Fed rate decisions, inflation, GDP, employment
**Fuentes:**
- Fed calendar (FOMC meetings)
- BLS releases (employment, CPI)
- Twitter: @federalreserve, @WSJ, @zaborsky
**Triggers:** Data releases (scheduled), Fed speeches

### 3. 🌍 Geopolítica
**Mercados:** Russia-Ukraine, China-Taiwan, conflicts
**Fuentes:**
- Twitter: @TheStudyofWar, @IntelCrab, @RALee85
- RSS: Reuters World, AP News
- Liveuamap, ISW reports
**Triggers:** Military movements, negotiations, official statements

### 4. ₿ Crypto
**Mercados:** BTC price targets, ETF approvals, regulations
**Fuentes:**
- Twitter: @whale_alert, @DocumentingBTC, @tier10k
- On-chain data: large movements
- SEC filings, regulatory news
**Triggers:** Whale moves, regulatory announcements, exchange news

### 5. 🎮 Tech/Entertainment
**Mercados:** Game releases (GTA VI), company earnings, product launches
**Fuentes:**
- Twitter: @RockstarGames, company accounts
- Press releases
- Insider leaks (careful with reliability)
**Triggers:** Official announcements, credible leaks

---

## Sistema de Alertas

### Prioridades
- 🔴 **URGENT**: Evento confirmado que moverá mercado >10%
- 🟡 **WATCH**: Evento probable o rumor creíble
- 🟢 **INFO**: Background relevante para contexto

### Flujo
1. Monitor detecta evento relevante
2. Evalúa impacto en mercados mapeados
3. Verifica si precio ya se movió (¿llegamos tarde?)
4. Si hay edge → alerta a Ichi con:
   - Qué pasó
   - Qué mercado afecta
   - Precio actual vs precio esperado
   - Recomendación (comprar/vender/esperar)

---

## Mercados Prioritarios (por liquidez)

| Mercado | Liquidez | Categoría | Eventos Clave |
|---------|----------|-----------|---------------|
| Trump deportations | ~$50K | Politics | ICE reports, court rulings |
| Tariffs revenue | ~$60K | Econ | Treasury data, trade deals |
| DOGE spending cuts | ~$30K | Politics | OMB reports, Musk tweets |
| Russia-Ukraine ceasefire | ~$57K | Geopolitics | Negotiations, military moves |
| BTC price milestones | ~$170K | Crypto | Whale moves, ETF flows |

---

## Ventaja Competitiva

1. **Velocidad**: Proceso info más rápido que traders manuales
2. **Coverage 24/7**: No duermo
3. **Multi-fuente**: Cruzo datos de múltiples fuentes
4. **Conocimiento local**: Ichi sabe de tech/gaming (edge en GTA VI etc)

---

## Siguiente Paso
Crear monitor de Twitter + RSS para las fuentes prioritarias.
