# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Your Turn Extensions

### Extension 3 - Cache economics

- Estimated average cache reads per prefix: 150.0
- Measured cache savings: $35/month

| Model tier | Break-even reads | Worth it? |
|---|---:|---|
| small | 0.28 | True |
| large | 0.28 | True |

### Extension 4 - Reasoning budget

- Reasoning is 8.4% of requests, 16.5% of optimized inference cost, and 94.0% of inference energy.
- Cap to 10.0% served tokens saves $16/month and 11,708 Wh/day.
- Routing rule: Use reasoning only for eval or high-complexity requests; cap reasoning to 10% of served tokens.

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

_Figures are June-2026 as-of snapshots; re-baseline before acting._