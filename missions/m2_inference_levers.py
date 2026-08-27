"""M2 - Inference Cost Levers: $/1M-token, batch x cache x cascade.

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations

from collections import defaultdict
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from finops import pricing, sustainability
from missions._common import load_csv, num

# $/1M tokens (input, output) - illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
CACHE_WRITE_FRAC = 0.25
REASONING_CAP_FRAC = 0.10


def _cache_policy(rows: list[dict]) -> dict:
    """Estimate cache-read reuse from repeated team/project/model prompt families."""
    cache_groups = defaultdict(int)
    for row in rows:
        if int(num(row["cached_input_tokens"])) > 0:
            cache_groups[(row["team"], row["project"], row["route_tier"])] += 1

    avg_reads = sum(cache_groups.values()) / len(cache_groups) if cache_groups else 0.0
    policy = {}
    for tier, (input_price, _) in MODEL_PRICES.items():
        write_cost = input_price * CACHE_WRITE_FRAC
        break_even = pricing.cache_break_even_reads(
            write_cost_per_m=write_cost,
            read_price_per_m=input_price,
        )
        policy[tier] = {
            "avg_reads": round(avg_reads, 1),
            "break_even_reads": round(break_even, 2),
            "write_cost_per_m": round(write_cost, 4),
            "worth_it": pricing.cache_is_worth_it(
                avg_cache_reads=avg_reads,
                write_cost_per_m=write_cost,
                read_price_per_m=input_price,
            ),
        }
    return {"avg_reads": avg_reads, "policy_by_tier": policy}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    cache = _cache_policy(rows)
    policy_by_tier = cache["policy_by_tier"]

    base_cost = opt_cost = opt_no_cache_cost = 0.0
    total_tokens = 0
    reasoning = {
        "requests": 0,
        "tokens": 0,
        "cost": 0.0,
        "wh": 0.0,
        "non_reasoning_requests": 0,
        "non_reasoning_tokens": 0,
        "non_reasoning_cost": 0.0,
        "non_reasoning_wh": 0.0,
    }

    for row in rows:
        inp = int(num(row["input_tokens"]))
        out = int(num(row["output_tokens"]))
        requested_cached = int(num(row["cached_input_tokens"]))
        is_batch = bool(int(num(row["is_batch"])))
        is_reasoning = bool(int(num(row["is_reasoning"])))
        total = inp + out
        total_tokens += total

        large_in, large_out = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, large_in, large_out)

        price_in, price_out = MODEL_PRICES[row["route_tier"]]
        cached = requested_cached if policy_by_tier[row["route_tier"]]["worth_it"] else 0
        row_cost = pricing.request_cost(
            inp, out, price_in, price_out, cached_in=cached, batch=is_batch
        )
        row_no_cache = pricing.request_cost(
            inp, out, price_in, price_out, cached_in=0, batch=is_batch
        )
        opt_cost += row_cost
        opt_no_cache_cost += row_no_cache

        wh = sustainability.wh_per_query(total, is_reasoning=is_reasoning)
        if is_reasoning:
            reasoning["requests"] += 1
            reasoning["tokens"] += total
            reasoning["cost"] += row_cost
            reasoning["wh"] += wh
        else:
            reasoning["non_reasoning_requests"] += 1
            reasoning["non_reasoning_tokens"] += total
            reasoning["non_reasoning_cost"] += row_cost
            reasoning["non_reasoning_wh"] += wh

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    cache_savings = opt_no_cache_cost - opt_cost

    request_count = len(rows)
    current_reasoning_frac = reasoning["requests"] / request_count if request_count else 0.0
    current_reasoning_token_frac = reasoning["tokens"] / total_tokens if total_tokens else 0.0
    cap_keep_frac = (
        min(1.0, REASONING_CAP_FRAC / current_reasoning_token_frac)
        if current_reasoning_token_frac > 0 else 1.0
    )
    cap_cost_savings = reasoning["cost"] * (1.0 - cap_keep_frac)
    cap_wh_savings = reasoning["wh"] * (1.0 - cap_keep_frac)
    total_wh = reasoning["wh"] + reasoning["non_reasoning_wh"]
    reasoning_summary = {
        "requests": reasoning["requests"],
        "request_pct": round(current_reasoning_frac * 100.0, 1),
        "tokens": reasoning["tokens"],
        "token_pct": round(reasoning["tokens"] / total_tokens * 100.0, 1)
        if total_tokens else 0.0,
        "cost_daily": round(reasoning["cost"], 2),
        "cost_pct": round(reasoning["cost"] / opt_cost * 100.0, 1) if opt_cost else 0.0,
        "wh_daily": round(reasoning["wh"], 2),
        "wh_pct": round(reasoning["wh"] / total_wh * 100.0, 1) if total_wh else 0.0,
        "non_reasoning_cost_daily": round(reasoning["non_reasoning_cost"], 2),
        "non_reasoning_wh_daily": round(reasoning["non_reasoning_wh"], 2),
        "cap_request_pct": round(REASONING_CAP_FRAC * 100.0, 1),
        "cap_token_pct": round(REASONING_CAP_FRAC * 100.0, 1),
        "cap_cost_savings_daily": round(cap_cost_savings, 2),
        "cap_wh_savings_daily": round(cap_wh_savings, 2),
        "routing_rule": (
            "Use reasoning only for eval or high-complexity requests; "
            "cap reasoning to 10% of served tokens."
        ),
    }

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(
            "discount stack (batch + 100% cache): "
            f"{pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive"
        )
        print(
            f"cache avg reads/prefix: {cache['avg_reads']:.1f}; "
            f"cache savings: ${cache_savings:,.2f}/day"
        )
        for tier, tier_policy in policy_by_tier.items():
            print(
                f"  {tier:5} break-even reads={tier_policy['break_even_reads']:.2f} "
                f"-> worth it? {tier_policy['worth_it']}"
            )
        print(
            f"reasoning: {reasoning_summary['request_pct']}% requests, "
            f"{reasoning_summary['cost_pct']}% cost, {reasoning_summary['wh_pct']}% Wh"
        )
        print(
            "cap reasoning to 10% served tokens -> save "
            f"${cap_cost_savings:,.2f}/day and {cap_wh_savings:,.0f} Wh/day"
        )

    return {
        "baseline_daily": round(base_cost, 2),
        "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3),
        "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1),
        "total_tokens": total_tokens,
        "cache": {
            "avg_reads": round(cache["avg_reads"], 1),
            "savings_daily": round(cache_savings, 2),
            "policy_by_tier": policy_by_tier,
        },
        "reasoning": reasoning_summary,
    }


if __name__ == "__main__":
    run()
