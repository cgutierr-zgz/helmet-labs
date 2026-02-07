#!/usr/bin/env python3
"""
Learner Module v1.0 — Data-Driven Trading Insights

Analyzes trade history from auto_trader_v2 and generates recommendations.

Usage:
  python3 learner.py analyze    # Full analysis + recommendations
  python3 learner.py apply      # Write config_override.json
  python3 learner.py report     # Short summary for Telegram

Created: 2026-02-05
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent
STATE_FILES = {
    "bot_a": SCRIPT_DIR / "state_v2.json",
    "bot_b": SCRIPT_DIR / "state_bot_b.json",
    "bot_c": SCRIPT_DIR / "state_bot_c.json",
}
STATE_FILE = SCRIPT_DIR / "state_v2.json"  # Legacy compatibility
OVERRIDE_FILE = SCRIPT_DIR / "config_override.json"
ANALYSIS_FILE = SCRIPT_DIR / "analysis_log.json"

# Minimum trades required per category to draw conclusions
MIN_TRADES_FOR_CONCLUSION = 5
MIN_TRADES_FOR_WEAK_SIGNAL = 3


def load_state(bot: str = None) -> dict:
    """Load current trading state for one or all bots."""
    if bot:
        state_file = STATE_FILES.get(bot, STATE_FILE)
        if state_file.exists():
            try:
                return json.load(open(state_file))
            except:
                pass
        return {}
    
    # Load all bots
    all_states = {}
    for bot_name, state_file in STATE_FILES.items():
        if state_file.exists():
            try:
                all_states[bot_name] = json.load(open(state_file))
            except:
                all_states[bot_name] = {}
        else:
            all_states[bot_name] = {}
    return all_states


def load_analysis_log() -> list:
    """Load analysis history."""
    if ANALYSIS_FILE.exists():
        try:
            return json.load(open(ANALYSIS_FILE))
        except:
            pass
    return []


def classify_price(price: float) -> str:
    """Classify entry price into bucket."""
    if price <= 0.35:
        return "cheap"
    elif price <= 0.55:
        return "mid"
    else:
        return "expensive"


def classify_bias(bias: float) -> str:
    """Classify bias into ranges."""
    if bias >= 0.85:
        return "85%+"
    elif bias >= 0.75:
        return "75-85%"
    elif bias >= 0.65:
        return "65-75%"
    else:
        return "58-65%"


def get_hour(timestamp: str) -> int | None:
    """Extract hour from ISO timestamp."""
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.hour
    except:
        return None


def classify_time_of_day(hour: int | None) -> str:
    """Classify trading hour into time buckets."""
    if hour is None:
        return "unknown"
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 24:
        return "evening"
    else:
        return "night"


def get_confidence(count: int) -> str:
    """Determine confidence level based on sample size."""
    if count >= 10:
        return "high"
    elif count >= MIN_TRADES_FOR_CONCLUSION:
        return "medium"
    elif count >= MIN_TRADES_FOR_WEAK_SIGNAL:
        return "low"
    else:
        return "insufficient"


def analyze_trades(trades: list) -> dict:
    """Comprehensive trade analysis."""
    
    # Filter to closed trades only
    closed = [t for t in trades if t.get("status") == "closed" and t.get("result")]
    
    if not closed:
        return {"error": "No closed trades to analyze"}
    
    # Initialize analysis containers
    analysis = {
        "total_trades": len(closed),
        "overall": {"wins": 0, "losses": 0, "pnl": 0.0},
        "by_price_bucket": defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0, "avg_win": [], "avg_loss": []}),
        "by_bias_range": defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0}),
        "by_strategy": defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0}),
        "by_timeframe": defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0}),
        "by_close_reason": defaultdict(lambda: {"count": 0, "pnl": 0.0}),
        "by_time_of_day": defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0}),
        "pnl_distribution": {"wins": [], "losses": []},
    }
    
    for t in closed:
        result = t.get("result")
        pnl = t.get("pnl", 0)
        price = t.get("price", 0.5)
        bias = t.get("bias", 0) or t.get("market_state", {}).get(t.get("side", "").lower(), 0.5) or price
        strategy = t.get("strategy", "unknown")
        timeframe = t.get("timeframe", "unknown")
        close_reason = t.get("close_reason", "unknown")
        timestamp = t.get("timestamp", "")
        hour = get_hour(timestamp)
        time_bucket = classify_time_of_day(hour)
        
        # Price bucket
        price_bucket = t.get("price_bucket") or classify_price(price)
        
        # Bias range
        bias_range = classify_bias(bias)
        
        # Overall
        is_win = result == "WIN"
        analysis["overall"]["wins" if is_win else "losses"] += 1
        analysis["overall"]["pnl"] += pnl
        
        # By price bucket
        pb = analysis["by_price_bucket"][price_bucket]
        pb["wins" if is_win else "losses"] += 1
        pb["pnl"] += pnl
        if is_win:
            pb["avg_win"].append(pnl)
        else:
            pb["avg_loss"].append(pnl)
        
        # By bias range
        br = analysis["by_bias_range"][bias_range]
        br["wins" if is_win else "losses"] += 1
        br["pnl"] += pnl
        
        # By strategy
        st = analysis["by_strategy"][strategy]
        st["wins" if is_win else "losses"] += 1
        st["pnl"] += pnl
        
        # By timeframe
        tf = analysis["by_timeframe"][timeframe]
        tf["wins" if is_win else "losses"] += 1
        tf["pnl"] += pnl
        
        # By close reason
        cr = analysis["by_close_reason"][close_reason]
        cr["count"] += 1
        cr["pnl"] += pnl
        
        # By time of day
        tod = analysis["by_time_of_day"][time_bucket]
        tod["wins" if is_win else "losses"] += 1
        tod["pnl"] += pnl
        
        # P&L distribution
        if is_win:
            analysis["pnl_distribution"]["wins"].append(pnl)
        else:
            analysis["pnl_distribution"]["losses"].append(pnl)
    
    # Convert defaultdicts to regular dicts for JSON serialization
    analysis["by_price_bucket"] = dict(analysis["by_price_bucket"])
    analysis["by_bias_range"] = dict(analysis["by_bias_range"])
    analysis["by_strategy"] = dict(analysis["by_strategy"])
    analysis["by_timeframe"] = dict(analysis["by_timeframe"])
    analysis["by_close_reason"] = dict(analysis["by_close_reason"])
    analysis["by_time_of_day"] = dict(analysis["by_time_of_day"])
    
    return analysis


def calculate_win_rate(data: dict) -> float:
    """Calculate win rate from wins/losses dict."""
    total = data.get("wins", 0) + data.get("losses", 0)
    return data.get("wins", 0) / total if total > 0 else 0


def generate_learnings(analysis: dict) -> dict:
    """Generate actionable learnings from analysis."""
    
    if "error" in analysis:
        return {"error": analysis["error"]}
    
    learnings = {
        "timestamp": datetime.now().isoformat(),
        "total_trades_analyzed": analysis["total_trades"],
        "findings": [],
        "recommendations": {
            "15m": {},
            "1h": {},
        },
    }
    
    # --- Analyze price buckets ---
    bucket_results = []
    for bucket, data in analysis["by_price_bucket"].items():
        total = data["wins"] + data["losses"]
        if total >= MIN_TRADES_FOR_WEAK_SIGNAL:
            wr = calculate_win_rate(data)
            avg_win = sum(data["avg_win"]) / len(data["avg_win"]) if data["avg_win"] else 0
            avg_loss = sum(data["avg_loss"]) / len(data["avg_loss"]) if data["avg_loss"] else 0
            bucket_results.append({
                "bucket": bucket,
                "count": total,
                "win_rate": wr,
                "pnl": data["pnl"],
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "confidence": get_confidence(total),
            })
    
    # Find best price bucket
    if bucket_results:
        best_bucket = max(bucket_results, key=lambda x: (x["pnl"], x["win_rate"]))
        worst_bucket = min(bucket_results, key=lambda x: x["pnl"])
        
        learnings["findings"].append({
            "type": "price_bucket",
            "best": best_bucket["bucket"],
            "best_wr": f"{best_bucket['win_rate']:.0%}",
            "best_pnl": f"${best_bucket['pnl']:+.2f}",
            "worst": worst_bucket["bucket"],
            "worst_pnl": f"${worst_bucket['pnl']:+.2f}",
            "confidence": best_bucket["confidence"],
        })
        
        # Recommend which entries to prefer
        if best_bucket["confidence"] != "insufficient":
            learnings["recommendations"]["15m"]["prefer_bucket"] = best_bucket["bucket"]
            learnings["recommendations"]["1h"]["prefer_bucket"] = best_bucket["bucket"]
    
    # --- Analyze bias ranges ---
    bias_results = []
    for bias_range, data in analysis["by_bias_range"].items():
        total = data["wins"] + data["losses"]
        if total >= MIN_TRADES_FOR_WEAK_SIGNAL:
            wr = calculate_win_rate(data)
            bias_results.append({
                "range": bias_range,
                "count": total,
                "win_rate": wr,
                "pnl": data["pnl"],
                "confidence": get_confidence(total),
            })
    
    if bias_results:
        best_bias = max(bias_results, key=lambda x: (x["pnl"], x["win_rate"]))
        
        learnings["findings"].append({
            "type": "bias_range",
            "best": best_bias["range"],
            "best_wr": f"{best_bias['win_rate']:.0%}",
            "best_pnl": f"${best_bias['pnl']:+.2f}",
            "confidence": best_bias["confidence"],
        })
        
        # Extract minimum bias from best range
        if best_bias["confidence"] != "insufficient":
            # Parse range to get min bias
            range_str = best_bias["range"]
            if range_str == "85%+":
                min_bias = 0.85
            elif range_str == "75-85%":
                min_bias = 0.75
            elif range_str == "65-75%":
                min_bias = 0.65
            else:
                min_bias = 0.58
            
            # Only recommend tightening if WR is significantly better
            if best_bias["win_rate"] > 0.60 and min_bias > 0.58:
                learnings["recommendations"]["15m"]["min_bias"] = min_bias
                learnings["recommendations"]["1h"]["min_bias"] = min_bias
    
    # --- Analyze strategies ---
    strategy_results = []
    for strategy, data in analysis["by_strategy"].items():
        total = data["wins"] + data["losses"]
        if total >= MIN_TRADES_FOR_WEAK_SIGNAL:
            wr = calculate_win_rate(data)
            strategy_results.append({
                "strategy": strategy,
                "count": total,
                "win_rate": wr,
                "pnl": data["pnl"],
                "confidence": get_confidence(total),
            })
    
    if strategy_results:
        best_strategy = max(strategy_results, key=lambda x: (x["pnl"], x["win_rate"]))
        
        learnings["findings"].append({
            "type": "strategy",
            "best": best_strategy["strategy"],
            "best_wr": f"{best_strategy['win_rate']:.0%}",
            "best_pnl": f"${best_strategy['pnl']:+.2f}",
            "confidence": best_strategy["confidence"],
        })
        
        if best_strategy["confidence"] != "insufficient":
            learnings["recommendations"]["15m"]["active_strategy"] = best_strategy["strategy"]
            learnings["recommendations"]["1h"]["active_strategy"] = best_strategy["strategy"]
    
    # --- Analyze close reasons ---
    close_reasons = analysis["by_close_reason"]
    sl_data = close_reasons.get("stop_loss", {"count": 0, "pnl": 0})
    tp_data = close_reasons.get("take_profit", {"count": 0, "pnl": 0})
    resolved_data = close_reasons.get("resolved", {"count": 0, "pnl": 0})
    
    total_exits = sl_data["count"] + tp_data["count"] + resolved_data["count"]
    
    if total_exits > 0:
        sl_ratio = sl_data["count"] / total_exits
        tp_ratio = tp_data["count"] / total_exits
        resolved_ratio = resolved_data["count"] / total_exits
        
        learnings["findings"].append({
            "type": "exit_analysis",
            "stop_loss_ratio": f"{sl_ratio:.0%} ({sl_data['count']})",
            "stop_loss_pnl": f"${sl_data['pnl']:+.2f}",
            "take_profit_ratio": f"{tp_ratio:.0%} ({tp_data['count']})",
            "take_profit_pnl": f"${tp_data['pnl']:+.2f}",
            "resolved_ratio": f"{resolved_ratio:.0%} ({resolved_data['count']})",
            "resolved_pnl": f"${resolved_data['pnl']:+.2f}",
        })
        
        # If too many stop losses, recommend tighter SL or wider entry filter
        if sl_ratio > 0.30 and sl_data["count"] >= 3:
            learnings["findings"].append({
                "type": "warning",
                "message": f"High stop loss rate ({sl_ratio:.0%}). Consider tighter entry filters or wider SL.",
            })
    
    # --- Analyze P&L distribution for SL/TP adjustments ---
    wins = analysis["pnl_distribution"]["wins"]
    losses = analysis["pnl_distribution"]["losses"]
    
    if wins and losses:
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        learnings["findings"].append({
            "type": "pnl_analysis",
            "avg_win": f"${avg_win:+.2f}",
            "avg_loss": f"${avg_loss:+.2f}",
            "win_loss_ratio": f"{win_loss_ratio:.2f}:1",
        })
        
        # If avg loss > avg win, risk/reward is broken
        if win_loss_ratio < 1.0:
            learnings["findings"].append({
                "type": "warning",
                "message": f"Risk/reward broken (ratio {win_loss_ratio:.2f}:1). Avg loss ${avg_loss:.2f} > Avg win ${avg_win:.2f}. Need cheaper entries or tighter SL.",
            })
            # Recommend tighter SL
            learnings["recommendations"]["15m"]["stop_loss"] = 0.20
            learnings["recommendations"]["1h"]["stop_loss"] = 0.20
    
    # --- Analyze by timeframe ---
    tf_results = []
    for timeframe, data in analysis["by_timeframe"].items():
        total = data["wins"] + data["losses"]
        if total >= MIN_TRADES_FOR_WEAK_SIGNAL:
            wr = calculate_win_rate(data)
            tf_results.append({
                "timeframe": timeframe,
                "count": total,
                "win_rate": wr,
                "pnl": data["pnl"],
                "confidence": get_confidence(total),
            })
    
    if len(tf_results) > 1:
        best_tf = max(tf_results, key=lambda x: (x["pnl"], x["win_rate"]))
        learnings["findings"].append({
            "type": "timeframe_comparison",
            "results": tf_results,
            "best": best_tf["timeframe"],
        })
    
    # --- Analyze time of day (if enough data) ---
    tod_results = []
    for time_bucket, data in analysis["by_time_of_day"].items():
        total = data["wins"] + data["losses"]
        if total >= MIN_TRADES_FOR_WEAK_SIGNAL and time_bucket != "unknown":
            wr = calculate_win_rate(data)
            tod_results.append({
                "time": time_bucket,
                "count": total,
                "win_rate": wr,
                "pnl": data["pnl"],
            })
    
    if tod_results:
        best_time = max(tod_results, key=lambda x: (x["pnl"], x["win_rate"]))
        learnings["findings"].append({
            "type": "time_of_day",
            "best": best_time["time"],
            "best_wr": f"{best_time['win_rate']:.0%}",
            "best_pnl": f"${best_time['pnl']:+.2f}",
            "all_times": tod_results,
        })
    
    # Clean up empty recommendations
    for tf in ["15m", "1h"]:
        if not learnings["recommendations"][tf]:
            del learnings["recommendations"][tf]
    
    return learnings


def generate_config_override(learnings: dict) -> dict | None:
    """Convert learnings to config override format."""
    
    if "error" in learnings or not learnings.get("recommendations"):
        return None
    
    override = {
        "_generated": datetime.now().isoformat(),
        "_source": "learner.py",
        "_trades_analyzed": learnings.get("total_trades_analyzed", 0),
    }
    
    for tf in ["15m", "1h"]:
        if tf in learnings["recommendations"]:
            recs = learnings["recommendations"][tf]
            tf_override = {}
            
            if "min_bias" in recs:
                tf_override["min_bias"] = recs["min_bias"]
            
            if "stop_loss" in recs:
                tf_override["stop_loss"] = recs["stop_loss"]
            
            if "take_profit" in recs:
                tf_override["take_profit"] = recs["take_profit"]
            
            if "prefer_bucket" in recs:
                # Map bucket preference to max_price
                bucket = recs["prefer_bucket"]
                if bucket == "cheap":
                    tf_override["max_price"] = 0.35
                    tf_override["prefer_cheap"] = True
                elif bucket == "mid":
                    tf_override["max_price"] = 0.55
                    tf_override["prefer_cheap"] = True
                # expensive: don't change max_price
            
            if "active_strategy" in recs:
                # Store as string, trader will map to index
                tf_override["preferred_strategy"] = recs["active_strategy"]
            
            if tf_override:
                override[tf] = tf_override
    
    # Only return if we have actual overrides
    if len(override) > 3:  # More than just metadata
        return override
    return None


def format_analysis_report(analysis: dict, learnings: dict) -> str:
    """Format full analysis report."""
    
    if "error" in analysis:
        return f"❌ {analysis['error']}"
    
    lines = []
    lines.append("=" * 50)
    lines.append("📊 LEARNER ANALYSIS REPORT")
    lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)
    
    # Overall stats
    overall = analysis["overall"]
    total = overall["wins"] + overall["losses"]
    wr = overall["wins"] / total if total > 0 else 0
    lines.append(f"\n📈 OVERALL: {overall['wins']}W-{overall['losses']}L ({wr:.0%}) | P&L: ${overall['pnl']:+.2f}")
    
    # By price bucket
    lines.append("\n📊 BY PRICE BUCKET:")
    for bucket in ["cheap", "mid", "expensive"]:
        if bucket in analysis["by_price_bucket"]:
            data = analysis["by_price_bucket"][bucket]
            total = data["wins"] + data["losses"]
            if total > 0:
                wr = calculate_win_rate(data)
                conf = get_confidence(total)
                avg_win = sum(data["avg_win"]) / len(data["avg_win"]) if data["avg_win"] else 0
                avg_loss = sum(data["avg_loss"]) / len(data["avg_loss"]) if data["avg_loss"] else 0
                lines.append(f"  {bucket:>10}: {data['wins']}W-{data['losses']}L ({wr:.0%}) | P&L ${data['pnl']:+.2f} | AvgW ${avg_win:+.2f} AvgL ${avg_loss:+.2f} [{conf}]")
    
    # By bias range
    lines.append("\n📊 BY BIAS RANGE:")
    for bias_range in ["58-65%", "65-75%", "75-85%", "85%+"]:
        if bias_range in analysis["by_bias_range"]:
            data = analysis["by_bias_range"][bias_range]
            total = data["wins"] + data["losses"]
            if total > 0:
                wr = calculate_win_rate(data)
                conf = get_confidence(total)
                lines.append(f"  {bias_range:>10}: {data['wins']}W-{data['losses']}L ({wr:.0%}) | P&L ${data['pnl']:+.2f} [{conf}]")
    
    # By strategy
    lines.append("\n📊 BY STRATEGY:")
    for strategy, data in analysis["by_strategy"].items():
        total = data["wins"] + data["losses"]
        if total > 0:
            wr = calculate_win_rate(data)
            conf = get_confidence(total)
            lines.append(f"  {strategy:>12}: {data['wins']}W-{data['losses']}L ({wr:.0%}) | P&L ${data['pnl']:+.2f} [{conf}]")
    
    # By timeframe
    lines.append("\n📊 BY TIMEFRAME:")
    for timeframe, data in analysis["by_timeframe"].items():
        total = data["wins"] + data["losses"]
        if total > 0:
            wr = calculate_win_rate(data)
            lines.append(f"  {timeframe:>10}: {data['wins']}W-{data['losses']}L ({wr:.0%}) | P&L ${data['pnl']:+.2f}")
    
    # Exit analysis
    lines.append("\n📊 EXIT ANALYSIS:")
    for reason, data in analysis["by_close_reason"].items():
        if data["count"] > 0:
            lines.append(f"  {reason:>12}: {data['count']} exits | P&L ${data['pnl']:+.2f}")
    
    # Time of day (if data)
    tod_data = {k: v for k, v in analysis["by_time_of_day"].items() if k != "unknown" and (v["wins"] + v["losses"]) > 0}
    if tod_data:
        lines.append("\n📊 BY TIME OF DAY:")
        for time_bucket, data in tod_data.items():
            total = data["wins"] + data["losses"]
            wr = calculate_win_rate(data)
            lines.append(f"  {time_bucket:>10}: {data['wins']}W-{data['losses']}L ({wr:.0%}) | P&L ${data['pnl']:+.2f}")
    
    # P&L distribution
    wins = analysis["pnl_distribution"]["wins"]
    losses = analysis["pnl_distribution"]["losses"]
    if wins or losses:
        lines.append("\n📊 P&L DISTRIBUTION:")
        if wins:
            avg_win = sum(wins) / len(wins)
            max_win = max(wins)
            lines.append(f"  Wins:   Avg ${avg_win:+.2f} | Max ${max_win:+.2f} | Count {len(wins)}")
        if losses:
            avg_loss = sum(losses) / len(losses)
            max_loss = min(losses)
            lines.append(f"  Losses: Avg ${avg_loss:+.2f} | Max ${max_loss:+.2f} | Count {len(losses)}")
        if wins and losses:
            ratio = abs(sum(wins) / len(wins)) / abs(sum(losses) / len(losses)) if losses else 0
            lines.append(f"  Win/Loss Ratio: {ratio:.2f}:1")
    
    # Findings
    if learnings.get("findings"):
        lines.append("\n" + "=" * 50)
        lines.append("🔍 KEY FINDINGS:")
        for finding in learnings["findings"]:
            ftype = finding.get("type", "")
            if ftype == "price_bucket":
                lines.append(f"  ✅ Best bucket: {finding['best']} ({finding['best_wr']}, {finding['best_pnl']}) [{finding['confidence']}]")
                lines.append(f"  ⚠️ Worst bucket: {finding['worst']} ({finding['worst_pnl']})")
            elif ftype == "bias_range":
                lines.append(f"  ✅ Best bias: {finding['best']} ({finding['best_wr']}, {finding['best_pnl']}) [{finding['confidence']}]")
            elif ftype == "strategy":
                lines.append(f"  ✅ Best strategy: {finding['best']} ({finding['best_wr']}, {finding['best_pnl']}) [{finding['confidence']}]")
            elif ftype == "warning":
                lines.append(f"  ⚠️ {finding['message']}")
            elif ftype == "pnl_analysis":
                lines.append(f"  💡 Avg win: {finding['avg_win']} | Avg loss: {finding['avg_loss']} | Ratio: {finding['win_loss_ratio']}")
            elif ftype == "exit_analysis":
                lines.append(f"  📋 SL: {finding['stop_loss_ratio']} ({finding['stop_loss_pnl']}) | TP: {finding['take_profit_ratio']} ({finding['take_profit_pnl']}) | Resolved: {finding['resolved_ratio']} ({finding['resolved_pnl']})")
    
    # Recommendations
    if learnings.get("recommendations"):
        lines.append("\n" + "=" * 50)
        lines.append("🎯 RECOMMENDATIONS:")
        for tf, recs in learnings["recommendations"].items():
            if recs:
                rec_str = ", ".join([f"{k}={v}" for k, v in recs.items()])
                lines.append(f"  {tf}: {rec_str}")
    
    lines.append("\n" + "=" * 50)
    
    return "\n".join(lines)


def format_short_report(analysis: dict, learnings: dict) -> str:
    """Format short report for Telegram."""
    
    if "error" in analysis:
        return f"❌ {analysis['error']}"
    
    overall = analysis["overall"]
    total = overall["wins"] + overall["losses"]
    wr = overall["wins"] / total if total > 0 else 0
    
    lines = []
    lines.append(f"📊 LEARNER: {total} trades analyzed")
    lines.append(f"Record: {overall['wins']}W-{overall['losses']}L ({wr:.0%}) | P&L: ${overall['pnl']:+.2f}")
    
    # Key findings
    warnings = [f for f in learnings.get("findings", []) if f.get("type") == "warning"]
    if warnings:
        for w in warnings[:2]:
            lines.append(f"⚠️ {w['message']}")
    
    # Best performers
    bucket_finding = next((f for f in learnings.get("findings", []) if f.get("type") == "price_bucket"), None)
    if bucket_finding:
        lines.append(f"✅ Best bucket: {bucket_finding['best']} ({bucket_finding['best_wr']})")
    
    strategy_finding = next((f for f in learnings.get("findings", []) if f.get("type") == "strategy"), None)
    if strategy_finding:
        lines.append(f"✅ Best strategy: {strategy_finding['best']} ({strategy_finding['best_wr']})")
    
    # Recommendations
    if learnings.get("recommendations"):
        recs = []
        for tf, tf_recs in learnings["recommendations"].items():
            for k, v in tf_recs.items():
                recs.append(f"{k}={v}")
        if recs:
            lines.append(f"🎯 Recs: {', '.join(recs[:3])}")
    
    return "\n".join(lines)


def cmd_analyze(args):
    """Full analysis command — all 3 bots."""
    all_states = load_state()  # Returns dict of all bots
    
    if not all_states or not any(all_states.values()):
        print("❌ No state files found")
        return
    
    print("=" * 60)
    print("🧠 LEARNER ANALYSIS — 3-BOT COMPARISON")
    print("=" * 60)
    
    bot_results = {}
    
    for bot_name, state in all_states.items():
        if not state:
            continue
            
        # Collect all trades from both timeframes
        all_trades = []
        for tf in ["15m", "1h"]:
            if tf in state:
                all_trades.extend(state[tf].get("trades", []))
        
        if not all_trades:
            continue
        
        analysis = analyze_trades(all_trades)
        learnings = generate_learnings(analysis)
        bot_results[bot_name] = {"analysis": analysis, "learnings": learnings}
        
        print(f"\n{'='*40}")
        print(f"📊 {bot_name.upper()}")
        print(f"{'='*40}")
        print(format_analysis_report(analysis, learnings))
    
    # Comparison summary
    if len(bot_results) > 1:
        print("\n" + "=" * 60)
        print("🏆 BOT COMPARISON")
        print("=" * 60)
        for bot_name, data in sorted(bot_results.items(), 
                                      key=lambda x: x[1]["analysis"]["overall"]["pnl"], 
                                      reverse=True):
            a = data["analysis"]["overall"]
            wr = a["wins"] / (a["wins"] + a["losses"]) * 100 if (a["wins"] + a["losses"]) > 0 else 0
            print(f"  {bot_name}: {a['wins']}W-{a['losses']}L ({wr:.0f}%) | P&L: ${a['pnl']:.2f}")
    
    # Generate override from best performing or most data
    if bot_results.get("bot_a"):
        override = generate_config_override(bot_results["bot_a"]["learnings"])
        if override:
            print("\n📝 CONFIG OVERRIDE PREVIEW (Bot A):")
            print(json.dumps(override, indent=2))
            print("\nRun 'python3 learner.py apply' to write config_override.json")
        else:
            print("\n💡 No config changes recommended yet (need more data or clear patterns)")


def cmd_apply(args):
    """Apply learnings to config override."""
    state = load_state()
    
    if not state:
        print("❌ No state file found")
        return
    
    all_trades = []
    for tf in ["15m", "1h"]:
        if tf in state:
            all_trades.extend(state[tf].get("trades", []))
    
    if not all_trades:
        print("❌ No trades to analyze")
        return
    
    analysis = analyze_trades(all_trades)
    learnings = generate_learnings(analysis)
    override = generate_config_override(learnings)
    
    if not override:
        print("💡 No config changes recommended. Need more data or clearer patterns.")
        return
    
    # Write override file
    with open(OVERRIDE_FILE, "w") as f:
        json.dump(override, f, indent=2)
    
    print(f"✅ Wrote {OVERRIDE_FILE}")
    print("\nApplied overrides:")
    print(json.dumps(override, indent=2))
    print("\n⚠️ Auto trader will load these on next cycle.")


def cmd_report(args):
    """Short report for Telegram — all 3 bots."""
    all_states = load_state()
    
    if not all_states or not any(all_states.values()):
        print("❌ No state")
        return
    
    print("🧠 LEARNER REPORT\n")
    
    results = []
    for bot_name, state in all_states.items():
        if not state:
            continue
            
        all_trades = []
        for tf in ["15m", "1h"]:
            if tf in state:
                all_trades.extend(state[tf].get("trades", []))
        
        if not all_trades:
            continue
        
        analysis = analyze_trades(all_trades)
        learnings = generate_learnings(analysis)
        
        a = analysis["overall"]
        wr = a["wins"] / (a["wins"] + a["losses"]) * 100 if (a["wins"] + a["losses"]) > 0 else 0
        results.append((bot_name, a["pnl"], wr, a["wins"], a["losses"], learnings))
    
    # Sort by P&L
    results.sort(key=lambda x: x[1], reverse=True)
    
    for bot_name, pnl, wr, wins, losses, learnings in results:
        emoji = "👑" if results[0][0] == bot_name else "📊"
        print(f"{emoji} {bot_name.upper()}: {wins}W-{losses}L ({wr:.0f}%) | ${pnl:+.2f}")
        
        # Key insight per bot
        if learnings.get("key_insight"):
            print(f"   └─ {learnings['key_insight']}")
    
    # Overall recommendation
    if results:
        best = results[0]
        print(f"\n💡 Líder: {best[0]} — copiar su approach a los demás?")


def main():
    parser = argparse.ArgumentParser(description="Learner Module — Trade Analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("analyze", help="Full analysis + recommendations").set_defaults(func=cmd_analyze)
    subparsers.add_parser("apply", help="Write config_override.json").set_defaults(func=cmd_apply)
    subparsers.add_parser("report", help="Short summary for Telegram").set_defaults(func=cmd_report)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
