# The Arbitrage Thesis

This document explains the theoretical foundation behind the **Polymarket-Kalshi BTC Arbitrage Bot**. It details how we can mathematically guarantee a risk-free profit (arbitrage) by exploiting price discrepancies in the **Bitcoin 1-Hour Price** markets on **Polymarket** and **Kalshi**.

## 1. The Markets: Binary Options

Both Polymarket and Kalshi trade **binary options**. These are contracts that pay out exactly **$1.00** if an event happens ("Yes" or "Up") and **$0.00** if it does not ("No" or "Down").

Because the payout is fixed at $1.00, the price of a contract (e.g., $0.60) represents the market's implied probability of the event occurring (60%).

### Polymarket Structure
-   **Up**: Pays $1 if Price $\ge$ Strike.
-   **Down**: Pays $1 if Price $<$ Strike.
-   **Relation**: Cost(Up) + Cost(Down) $\approx$ $1.00 (ignoring fees/spread).

### Kalshi Structure
-   **Yes**: Pays $1 if Price $\ge$ Strike.
-   **No**: Pays $1 if Price $<$ Strike.
-   **Relation**: Cost(Yes) + Cost(No) $\approx$ $1.00.

## 2. The Arbitrage Opportunity

Arbitrage exists when we can construct a portfolio of positions across both markets such that:
1.  **Minimum Payout**: We are guaranteed to receive at least **$1.00** regardless of the outcome.
2.  **Total Cost**: The cost to buy this portfolio is **less than $1.00**.

If both conditions are met, we have a risk-free profit:
$$ \text{Profit} = \$1.00 - \text{Total Cost} $$

## 3. The Strategies

We compare the **Strike Prices** of the two markets to find overlapping coverage.

### Scenario A: Polymarket Strike > Kalshi Strike
*Example: Poly Strike = \$90,000 | Kalshi Strike = \$89,000*

We buy:
1.  **Polymarket DOWN** (Wins if Price < \$90,000)
2.  **Kalshi YES** (Wins if Price $\ge$ \$89,000)

**Outcome Analysis:**
-   **Price < \$89,000**:
    -   Poly Down: **WINS** ($1.00)
    -   Kalshi Yes: LOSES ($0.00)
    -   **Total Payout: $1.00**
-   **Price $\ge$ \$90,000**:
    -   Poly Down: LOSES ($0.00)
    -   Kalshi Yes: **WINS** ($1.00)
    -   **Total Payout: $1.00**
-   **Price between \$89,000 and \$90,000** (The "Middle"):
    -   Poly Down: **WINS** ($1.00)
    -   Kalshi Yes: **WINS** ($1.00)
    -   **Total Payout: $2.00**

**Conclusion**: The *minimum* payout is $1.00. If we can buy (Poly Down + Kalshi Yes) for **less than $1.00**, we make a guaranteed profit. If the price lands in the middle, we double our money.

---

### Scenario B: Polymarket Strike < Kalshi Strike
*Example: Poly Strike = \$89,000 | Kalshi Strike = \$90,000*

We buy:
1.  **Polymarket UP** (Wins if Price $\ge$ \$89,000)
2.  **Kalshi NO** (Wins if Price < \$90,000)

**Outcome Analysis:**
-   **Price < \$89,000**:
    -   Poly Up: LOSES ($0.00)
    -   Kalshi No: **WINS** ($1.00)
    -   **Total Payout: $1.00**
-   **Price $\ge$ \$90,000**:
    -   Poly Up: **WINS** ($1.00)
    -   Kalshi No: LOSES ($0.00)
    -   **Total Payout: $1.00**
-   **Price between \$89,000 and \$90,000**:
    -   Poly Up: **WINS** ($1.00)
    -   Kalshi No: **WINS** ($1.00)
    -   **Total Payout: $2.00**

**Conclusion**: Similar to Scenario A, the minimum payout is $1.00. If Cost(Poly Up + Kalshi No) < $1.00, it is a risk-free trade.

## 4. Execution

The bot automates this process:
1.  Fetches live prices for the current hourly market on both platforms.
2.  Identifies the relevant strike prices.
3.  Checks the cost of the "Middle" strategies described above.
4.  Alerts if `Total Cost < $1.00`.

## 5. Risks (The "Risk-Free" Caveats)
While mathematically sound, practical risks exist:
-   **Execution Risk**: Prices might change between buying leg 1 and leg 2.
-   **Liquidity Risk**: Not enough depth to fill the order at the displayed price.
-   **Platform Risk**: One exchange goes down or halts trading.
-   **Fees**: Trading fees (if any) must be accounted for in the cost calculation.
