# Short Write-up - GPU FinOps Lab 25

## Summary

NimbusAI should manage GPU cost by measuring unit economics in `$/1M-token`, not
only by looking at `$/GPU-hour` or `GPU-Util`. The optimized plan reduces monthly
spend from `$27,133` to `$14,626`, saving `$12,507/month` or about `46%`.

The biggest lever is purchasing strategy: moving interruptible workloads to spot
with checkpointing and steady workloads to reserved capacity saves about
`$10,040/month`. Inference optimization also matters: cascade routing, prompt
caching, and batch processing reduce inference unit cost from `$6.488/1M-token`
to `$1.126/1M-token`, an `82.6%` drop.

## Key Findings

Mission 1 shows why `GPU-Util` can be misleading. `gpu-h100-4` reports very high
utilization, but its MFU is low, meaning the team is paying for H100 hours while
receiving only a fraction of the expected compute. Idle waste also costs about
`$600/month`, so shutting down unused GPUs is a simple governance win.

Mission 4 shows tag coverage is `92%`, which is high enough to move from
showback toward chargeback. The generated FOCUS export makes the cost data easier
to reuse across billing and reporting tools.

## Your Turn Extensions

### Extension 3 - Cache Economics

I added `cache_is_worth_it()` and `cache_break_even_reads()` to check whether
prompt caching is economically justified before counting cache savings.

In this dataset, average cache reads per prefix are `150.0`, while the break-even
point is only `0.28` reads for both small and large model tiers. That means cache
reuse is far above the threshold. Measured cache savings are about `$35/month`.

### Extension 4 - Reasoning Budget

I separated reasoning traffic from normal inference traffic and measured both
cost and energy impact. Reasoning is only `8.4%` of requests, but it accounts for
`16.5%` of optimized inference cost and `94.0%` of inference energy.

The recommended rule is to use reasoning only for evaluation or high-complexity
requests, then cap reasoning to `10%` of served tokens for routine traffic. Under
that cap, the simulation saves about `$16/month` and `11,708 Wh/day`.

## Recommendation

For Milestone 2, NimbusAI should adopt the optimized baseline, enforce tagging
before chargeback, keep prompt caching enabled for repeated prompt families, and
add a reasoning budget policy. These changes are measurable, low-risk, and keep
the platform focused on cost per useful token served.
