"""
backtester.py
Event-Driven Strategy Backtesting Simulator & Performance Evaluation Framework.
Tracks holding window alpha vectors, evaluates market regimes, and delivers
active rule injections to change live behavior.
"""

import os
import json
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
PREDICTIONS_FILE    = "reports/predictions.csv"
BACKTEST_REPORT     = "reports/backtest_results_summary.json"
RULES_OVERRIDE_FILE = "reports/scoring_rules_override.json"


def evaluate_market_regime(ticker: str, target_date: datetime.date) -> str:
    """Classifies the index background regime during strategy trigger setups."""
    try:
        nifty = yf.Ticker("^NSEI")
        start_dt = target_date - timedelta(days=40)
        hist = nifty.history(start=start_dt, end=target_date + timedelta(days=2))
        if len(hist) < 20:
            return "UNKNOWN_REGIME"
            
        sma_20 = hist["Close"].rolling(window=20).mean().iloc[-1]
        sma_50 = hist["Close"].rolling(window=50).mean().iloc[-1]
        
        if sma_20 > sma_50:
            return "BULL_MARKET"
        else:
            return "BEAR_MARKET"
    except Exception:
        return "CONSOLIDATION"


def run_historical_event_backtest():
    """Simulates multi-horizon tracking windows and delivers actionable rule updates."""
    if not os.path.exists(PREDICTIONS_FILE):
        logger.info("No logs found to backtest.")
        return

    try:
        df = pd.read_csv(PREDICTIONS_FILE)
    except Exception as e:
        logger.error(f"Failed to read dataset: {e}")
        return

    if df.empty or "date_predicted" not in df.columns:
        return

    df["date_predicted"] = pd.to_datetime(df["date_predicted"]).dt.date
    results = []

    logger.info("Executing algorithmic backtest matrix evaluations...")
    for idx, row in df.iterrows():
        ticker = row["symbol"]
        entry_pr = float(row["entry_price"])
        evt_date = row["date_predicted"]
        
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(start=evt_date, end=evt_date + timedelta(days=45))
            if hist.empty:
                continue

            p3 = close_series = hist["Close"].iloc[min(3, len(hist)-1)]
            p7 = hist["Close"].iloc[min(7, len(hist)-1)]
            p30 = hist["Close"].iloc[min(30, len(hist)-1)]
            
            mfe_peak = hist["High"].max()
            max_potential_gain = ((mfe_peak - entry_pr) / entry_pr) * 100
            
            regime = evaluate_market_regime(ticker, evt_date)
            
            results.append({
                "ticker": ticker,
                "event_date": str(evt_date),
                "regime": regime,
                "gain_t3": round(((p3 - entry_pr)/entry_pr)*100, 2),
                "gain_t7": round(((p7 - entry_pr)/entry_pr)*100, 2),
                "gain_t30": round(((p30 - entry_pr)/entry_pr)*100, 2),
                "max_upside_excursion": round(max_potential_gain, 2)
            })
        except Exception:
            continue

    if not results:
        return

    res_df = pd.DataFrame(results)
    
    # Calculate performance metrics
    bull_avg = res_df[res_df["regime"] == "BULL_MARKET"]["max_upside_excursion"].mean() if not res_df[res_df["regime"] == "BULL_MARKET"].empty else 0.0
    bear_avg = res_df[res_df["regime"] == "BEAR_MARKET"]["max_upside_excursion"].mean() if not res_df[res_df["regime"] == "BEAR_MARKET"].empty else 0.0
    optimal_exit = "T+7 Days" if res_df["gain_t7"].mean() > res_df["gain_t30"].mean() else "T+30 Days"

    summary_metrics = {
        "total_events_backtested": len(res_df),
        "bull_market_avg_upside": round(bull_avg, 2),
        "bear_market_avg_upside": round(bear_avg, 2),
        "optimal_exit_horizon": optimal_exit
    }

    # Save summary stats
    os.makedirs("reports", exist_ok=True)
    with open(BACKTEST_REPORT, "w") as f:
        json.dump(summary_metrics, f, indent=2)

    # 🔄 DELIVER WHAT IS LEARNED: Generate programmatic rule injection
    intelligence_injection = ""
    
    if bear_avg < 3.0 and summary_metrics["total_events_backtested"] >= 5:
        intelligence_injection += "CRITICAL OVERRIDE NOTICE: Backtest shows heavy failure rates under current BEAR_MARKET metrics. Automatically penalize high-beta SME momentum targets by 3 points. "
    
    if optimal_exit == "T+7 Days":
        intelligence_injection += "HOLDING CONSTRAINT: Historical data reveals sharp performance decay beyond T+7 windows. Prioritize immediate SWING profiles over long-term holdings."

    # Pack and deliver directly to the override file used by stock_analyzer.py
    if intelligence_injection:
        override_payload = {
            "identified_fault_pattern": "Backtest revealed performance optimization rules.",
            "prompt_injection": intelligence_injection.strip()
        }
        try:
            with open(RULES_OVERRIDE_FILE, "w") as f:
                json.dump(override_payload, f, indent=2)
            logger.info("Backtest engine successfully delivered learned rules to the live prompt system!")
        except Exception as e:
            logger.error(f"Failed to deliver rules to system: {e}")


if __name__ == "__main__":
    run_historical_event_backtest()
