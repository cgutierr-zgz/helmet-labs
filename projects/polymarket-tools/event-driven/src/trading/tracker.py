"""
Trading Data Persistence and Tracking
====================================

Handles saving and loading portfolio state and trade history.
Provides analytics and metrics tracking.
"""
import os
import json
import jsonlines
from typing import Dict, List, Optional
from datetime import datetime, date
from pathlib import Path

from .portfolio import PaperPortfolio, TradeRecord
from .decision_engine import TradingDecision


class TradingTracker:
    """
    Manages persistence of trading data and provides analytics.
    
    Data Storage:
    - Portfolio state: data/portfolio_state.json
    - Trade records: data/paper_trades.jsonl
    - Decision logs: data/decisions.jsonl
    - Daily summaries: data/daily_summaries.jsonl
    """
    
    def __init__(self, data_dir: str = "data"):
        """Initialize tracker with data directory."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # File paths
        self.portfolio_file = self.data_dir / "portfolio_state.json"
        self.trades_file = self.data_dir / "paper_trades.jsonl"
        self.decisions_file = self.data_dir / "decisions.jsonl"
        self.summaries_file = self.data_dir / "daily_summaries.jsonl"
        
        # Ensure files exist
        for file_path in [self.trades_file, self.decisions_file, self.summaries_file]:
            if not file_path.exists():
                file_path.touch()
    
    def save_portfolio_state(self, portfolio: PaperPortfolio) -> None:
        """Save current portfolio state to JSON file."""
        try:
            portfolio_data = portfolio.to_dict()
            portfolio_data['last_updated'] = datetime.now().isoformat()
            
            with open(self.portfolio_file, 'w') as f:
                json.dump(portfolio_data, f, indent=2)
        
        except Exception as e:
            print(f"Error saving portfolio state: {e}")
    
    def load_portfolio_state(self) -> Optional[PaperPortfolio]:
        """Load portfolio state from JSON file."""
        if not self.portfolio_file.exists():
            return None
        
        try:
            with open(self.portfolio_file, 'r') as f:
                data = json.load(f)
            
            # Remove tracking fields
            data.pop('last_updated', None)
            
            return PaperPortfolio.from_dict(data)
        
        except Exception as e:
            print(f"Error loading portfolio state: {e}")
            return None
    
    def get_or_create_portfolio(self, initial_balance: float = 1000.0) -> PaperPortfolio:
        """Get existing portfolio or create new one."""
        portfolio = self.load_portfolio_state()
        if portfolio is None:
            portfolio = PaperPortfolio(initial_balance)
            self.save_portfolio_state(portfolio)
        return portfolio
    
    def log_trade(self, trade: TradeRecord) -> None:
        """Log a completed trade to JSONL file."""
        try:
            with jsonlines.open(self.trades_file, mode='a') as writer:
                trade_data = trade.to_dict()
                trade_data['logged_at'] = datetime.now().isoformat()
                writer.write(trade_data)
        
        except Exception as e:
            print(f"Error logging trade: {e}")
    
    def log_decision(self, decision: TradingDecision) -> None:
        """Log a trading decision to JSONL file."""
        try:
            with jsonlines.open(self.decisions_file, mode='a') as writer:
                decision_data = decision.to_dict()
                decision_data['logged_at'] = datetime.now().isoformat()
                writer.write(decision_data)
        
        except Exception as e:
            print(f"Error logging decision: {e}")
    
    def get_trades_by_date(self, date_filter: date = None) -> List[Dict]:
        """Get trades filtered by date."""
        if not self.trades_file.exists():
            return []
        
        trades = []
        target_date = date_filter or date.today()
        
        try:
            with jsonlines.open(self.trades_file, mode='r') as reader:
                for trade in reader:
                    trade_date = datetime.fromisoformat(trade['exit_time']).date()
                    if trade_date == target_date:
                        trades.append(trade)
        
        except Exception as e:
            print(f"Error reading trades: {e}")
        
        return trades
    
    def get_decisions_by_date(self, date_filter: date = None) -> List[Dict]:
        """Get decisions filtered by date."""
        if not self.decisions_file.exists():
            return []
        
        decisions = []
        target_date = date_filter or date.today()
        
        try:
            with jsonlines.open(self.decisions_file, mode='r') as reader:
                for decision in reader:
                    decision_date = datetime.fromisoformat(decision['logged_at']).date()
                    if decision_date == target_date:
                        decisions.append(decision)
        
        except Exception as e:
            print(f"Error reading decisions: {e}")
        
        return decisions
    
    def calculate_daily_metrics(self, target_date: date = None) -> Dict:
        """Calculate trading metrics for a specific date."""
        if target_date is None:
            target_date = date.today()
        
        trades = self.get_trades_by_date(target_date)
        decisions = self.get_decisions_by_date(target_date)
        
        # Trade metrics
        total_trades = len(trades)
        profitable_trades = sum(1 for t in trades if t['pnl'] > 0)
        total_pnl = sum(t['pnl'] for t in trades)
        total_return = sum(t['return_pct'] for t in trades)
        
        # Decision metrics
        total_decisions = len(decisions)
        executed_decisions = sum(1 for d in decisions if d['should_trade'])
        
        # Best and worst trades
        best_trade = max(trades, key=lambda t: t['pnl']) if trades else None
        worst_trade = min(trades, key=lambda t: t['pnl']) if trades else None
        
        return {
            'date': target_date.isoformat(),
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': (profitable_trades / total_trades * 100) if total_trades > 0 else 0,
            'total_pnl': round(total_pnl, 2),
            'average_return': round(total_return / total_trades, 2) if total_trades > 0 else 0,
            'total_decisions': total_decisions,
            'executed_decisions': executed_decisions,
            'execution_rate': (executed_decisions / total_decisions * 100) if total_decisions > 0 else 0,
            'best_trade_pnl': round(best_trade['pnl'], 2) if best_trade else 0,
            'worst_trade_pnl': round(worst_trade['pnl'], 2) if worst_trade else 0,
            'calculated_at': datetime.now().isoformat()
        }
    
    def save_daily_summary(self, target_date: date = None) -> Dict:
        """Calculate and save daily summary."""
        metrics = self.calculate_daily_metrics(target_date)
        
        try:
            with jsonlines.open(self.summaries_file, mode='a') as writer:
                writer.write(metrics)
        
        except Exception as e:
            print(f"Error saving daily summary: {e}")
        
        return metrics
    
    def get_performance_history(self, days: int = 30) -> List[Dict]:
        """Get performance history for the last N days."""
        if not self.summaries_file.exists():
            return []
        
        summaries = []
        cutoff_date = date.today().replace(day=1)  # Start of current month for now
        
        try:
            with jsonlines.open(self.summaries_file, mode='r') as reader:
                for summary in reader:
                    summary_date = date.fromisoformat(summary['date'])
                    if summary_date >= cutoff_date:
                        summaries.append(summary)
        
        except Exception as e:
            print(f"Error reading summaries: {e}")
        
        return sorted(summaries, key=lambda s: s['date'])
    
    def get_all_trades(self) -> List[Dict]:
        """Get all trades from history."""
        if not self.trades_file.exists():
            return []
        
        trades = []
        try:
            with jsonlines.open(self.trades_file, mode='r') as reader:
                trades = list(reader)
        
        except Exception as e:
            print(f"Error reading all trades: {e}")
        
        return trades
    
    def get_trading_stats(self) -> Dict:
        """Get comprehensive trading statistics."""
        all_trades = self.get_all_trades()
        
        if not all_trades:
            return {
                'total_trades': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'average_return': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'average_duration_hours': 0,
                'total_volume': 0
            }
        
        # Calculate statistics
        total_trades = len(all_trades)
        total_pnl = sum(t['pnl'] for t in all_trades)
        profitable_trades = sum(1 for t in all_trades if t['pnl'] > 0)
        win_rate = profitable_trades / total_trades * 100
        
        returns = [t['return_pct'] for t in all_trades]
        average_return = sum(returns) / len(returns)
        
        best_trade = max(all_trades, key=lambda t: t['pnl'])
        worst_trade = min(all_trades, key=lambda t: t['pnl'])
        
        # Calculate average duration
        durations = [t['duration_hours'] for t in all_trades if 'duration_hours' in t]
        average_duration = sum(durations) / len(durations) if durations else 0
        
        # Calculate total volume (sum of all position costs)
        total_volume = sum(t['shares'] * t['entry_price'] for t in all_trades)
        
        return {
            'total_trades': total_trades,
            'total_pnl': round(total_pnl, 2),
            'win_rate': round(win_rate, 1),
            'average_return': round(average_return, 2),
            'best_trade': round(best_trade['pnl'], 2),
            'worst_trade': round(worst_trade['pnl'], 2),
            'average_duration_hours': round(average_duration, 1),
            'total_volume': round(total_volume, 2),
            'profitable_trades': profitable_trades,
            'losing_trades': total_trades - profitable_trades
        }
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> None:
        """Clean up old data files (keep last N days)."""
        # For now, just implement a simple version that doesn't delete anything
        # In a production environment, you might want to archive old data
        pass
    
    def backup_data(self, backup_dir: str = "backups") -> str:
        """Create a backup of all trading data."""
        import shutil
        from datetime import datetime
        
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = backup_path / f"trading_backup_{timestamp}"
        backup_subdir.mkdir(exist_ok=True)
        
        # Copy all data files
        for file_path in [self.portfolio_file, self.trades_file, self.decisions_file, self.summaries_file]:
            if file_path.exists():
                shutil.copy2(file_path, backup_subdir / file_path.name)
        
        return str(backup_subdir)
    
    def reset_portfolio(self, initial_balance: float = 1000.0) -> PaperPortfolio:
        """Reset portfolio to initial state (for testing)."""
        new_portfolio = PaperPortfolio(initial_balance)
        self.save_portfolio_state(new_portfolio)
        return new_portfolio