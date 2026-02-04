# Trading Config 🪖

## Modo: PAPER TRADING
*Validando estrategia dual antes de dinero real*

---

## Capital Split

| Pool | Capital | Uso |
|------|---------|-----|
| **Conservador** | $350 (70%) | Trades de alta convicción |
| **Activo** | $150 (30%) | Momentum, whale-following, aprendizaje |

---

## Estrategia Conservadora (70%)

### Criterios de entrada
- Edge estimado: **>15%**
- Confianza: **>70%**
- Fuente: Noticia confirmada, dato oficial, evento definitivo

### Gestión
- Max por posición: **$50**
- Stop loss: **-50%** (o antes si tesis invalida)
- Take profit: Evaluar caso a caso
- Max posiciones: **3**

### Cuándo tradear
- Evento que confirma outcome (ej: ley firmada, anuncio oficial)
- Mercado no ha reaccionado todavía
- Info asimétrica clara

---

## Estrategia Activa (30%)

### Criterios de entrada
- Edge estimado: **>5%** (más flexible)
- Señales válidas:
  - 🐋 Whale entra con >$10k en posición
  - 📈 Momentum: mercado mueve >10% en 1h
  - 📰 Noticia relevante aunque no definitiva
  - 🔄 Mean reversion: spike sin fundamento

### Gestión
- Max por posición: **$20**
- Stop loss: **-30%** (más agresivo)
- Take profit: **+20%** o trailing
- Max posiciones: **5**

### Reglas especiales
- Si whale que sigo entra, puedo copiar hasta $15
- Si pierdo 3 trades seguidos, pauso 2 horas
- Documentar SIEMPRE el razonamiento (para aprender)

---

## Whales a seguir

| Whale | Estilo | Wallet |
|-------|--------|--------|
| aenews2 | Político, alto volumen | `0x44c1dfe4...ebc1` |
| Theo5 | Diversificado | `0x8a4c788f...532b` |
| RememberAmalek | Agresivo | `0x6139c42e...6b7a` |
| ForesightOracle | Selectivo | `0x7072dd52...3413` |

---

## Prohibido (ambas estrategias)
- ❌ Deportes (sin edge)
- ❌ Doblar tras pérdida
- ❌ FOMO
- ❌ Trades sin documentar

---

## Métricas a trackear
- Win rate por estrategia
- P&L por estrategia
- Mejor/peor trade
- Correlación con whales

---

*Actualizado: 4 Feb 2026, 14:44*
