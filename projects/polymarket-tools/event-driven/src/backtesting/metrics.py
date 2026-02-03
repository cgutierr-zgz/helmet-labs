"""
Performance metrics calculation for backtesting results.
"""
import math
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from .simulator import TradingResult


@dataclass
class BacktestMetrics:
    """Comprehensive backtesting performance metrics."""
    
    # Basic metrics
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    
    # Return metrics
    avg_return: float
    total_return: float
    annualized_return: float
    best_trade: float
    worst_trade: float
    
    # Risk metrics
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_duration_days: float
    
    # Trading metrics
    avg_holding_period_hours: float
    profit_factor: float  # Total profits / Total losses
    avg_win: float
    avg_loss: float
    
    # Time-based metrics
    start_date: datetime
    end_date: datetime
    period_days: float
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            'total_trades': self.total_trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': round(self.win_rate, 4),
            'avg_return': round(self.avg_return, 4),
            'total_return': round(self.total_return, 4),
            'annualized_return': round(self.annualized_return, 4),
            'best_trade': round(self.best_trade, 4),
            'worst_trade': round(self.worst_trade, 4),
            'volatility': round(self.volatility, 4),
            'sharpe_ratio': round(self.sharpe_ratio, 4),
            'max_drawdown': round(self.max_drawdown, 4),
            'max_drawdown_duration_days': round(self.max_drawdown_duration_days, 2),
            'avg_holding_period_hours': round(self.avg_holding_period_hours, 2),
            'profit_factor': round(self.profit_factor, 4),
            'avg_win': round(self.avg_win, 4),
            'avg_loss': round(self.avg_loss, 4),
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'period_days': round(self.period_days, 1)
        }
    
    def print_summary(self):
        """Print formatted summary of metrics."""
        print("\n" + "="*50)
        print("           BACKTEST RESULTS")
        print("="*50)
        print(f"Period: {self.period_days:.1f} days")
        print(f"Total trades: {self.total_trades}")
        print(f"Wins: {self.wins} | Losses: {self.losses}")
        print(f"Win rate: {self.win_rate:.1%}")
        print(f"Average return per trade: {self.avg_return:+.1%}")
        print(f"Total return: {self.total_return:+.1%}")
        print(f"Annualized return: {self.annualized_return:+.1%}")
        print(f"Best trade: {self.best_trade:+.1%}")
        print(f"Worst trade: {self.worst_trade:+.1%}")
        print(f"Max drawdown: {self.max_drawdown:.1%}")
        print(f"Sharpe ratio: {self.sharpe_ratio:.2f}")
        print(f"Profit factor: {self.profit_factor:.2f}")
        print("="*50)


def calculate_metrics(results: List[TradingResult]) -> BacktestMetrics:
    """
    Calculate comprehensive performance metrics from trading results.
    
    Args:
        results: List of trading results from backtest
        
    Returns:
        BacktestMetrics object with all calculated metrics
    """
    if not results:
        # Return empty metrics if no results
        return BacktestMetrics(
            total_trades=0, wins=0, losses=0, win_rate=0.0,
            avg_return=0.0, total_return=0.0, annualized_return=0.0,
            best_trade=0.0, worst_trade=0.0, volatility=0.0,
            sharpe_ratio=0.0, max_drawdown=0.0, max_drawdown_duration_days=0.0,
            avg_holding_period_hours=0.0, profit_factor=0.0,
            avg_win=0.0, avg_loss=0.0, start_date=datetime.now(),
            end_date=datetime.now(), period_days=0.0
        )
    
    # Basic counts
    total_trades = len(results)
    wins = sum(1 for r in results if r.win)
    losses = total_trades - wins
    win_rate = wins / total_trades if total_trades > 0 else 0.0
    
    # Return calculations
    returns = [r.return_pct for r in results]
    avg_return = sum(returns) / len(returns) if returns else 0.0
    total_return = sum(returns)  # Simplified cumulative return
    
    best_trade = max(returns) if returns else 0.0
    worst_trade = min(returns) if returns else 0.0
    
    # Time period calculations
    start_date = min(r.entry_time for r in results)
    end_date = max(r.exit_time for r in results)
    period_days = (end_date - start_date).total_seconds() / (24 * 3600)
    
    # Annualized return
    if period_days > 0:
        annualized_return = (1 + total_return) ** (365 / period_days) - 1
    else:
        annualized_return = 0.0
    
    # Volatility (standard deviation of returns)
    if len(returns) > 1:
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        volatility = math.sqrt(variance)
        
        # Annualize volatility (assuming daily trading)
        volatility_annualized = volatility * math.sqrt(365)
    else:
        volatility = 0.0
        volatility_annualized = 0.0
    
    # Sharpe ratio (simplified, assuming 0% risk-free rate)
    if volatility_annualized > 0:
        sharpe_ratio = annualized_return / volatility_annualized
    else:
        sharpe_ratio = 0.0
    
    # Maximum drawdown calculation
    max_drawdown, max_dd_duration = _calculate_max_drawdown(results)
    
    # Holding period
    holding_periods = [(r.exit_time - r.entry_time).total_seconds() / 3600 for r in results]
    avg_holding_period_hours = sum(holding_periods) / len(holding_periods) if holding_periods else 0.0
    
    # Profit factor and win/loss averages
    winning_trades = [r.return_pct for r in results if r.win]
    losing_trades = [r.return_pct for r in results if not r.win]
    
    total_profits = sum(winning_trades) if winning_trades else 0.0
    total_losses = abs(sum(losing_trades)) if losing_trades else 0.0
    
    if total_losses > 0:
        profit_factor = total_profits / total_losses
    else:
        profit_factor = float('inf') if total_profits > 0 else 1.0
    
    avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0.0
    avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0.0
    
    return BacktestMetrics(
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        avg_return=avg_return,
        total_return=total_return,
        annualized_return=annualized_return,
        best_trade=best_trade,
        worst_trade=worst_trade,
        volatility=volatility_annualized,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        max_drawdown_duration_days=max_dd_duration,
        avg_holding_period_hours=avg_holding_period_hours,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        start_date=start_date,
        end_date=end_date,
        period_days=period_days
    )


def _calculate_max_drawdown(results: List[TradingResult]) -> tuple[float, float]:
    """Calculate maximum drawdown and its duration."""
    if not results:
        return 0.0, 0.0
    
    # Sort results by time
    sorted_results = sorted(results, key=lambda r: r.entry_time)
    
    # Calculate cumulative returns
    cumulative_returns = []
    cum_return = 0.0
    
    for result in sorted_results:
        cum_return += result.return_pct
        cumulative_returns.append(cum_return)
    
    # Find maximum drawdown
    peak = cumulative_returns[0]
    max_drawdown = 0.0
    max_dd_duration = 0.0
    
    drawdown_start = None
    
    for i, current_return in enumerate(cumulative_returns):
        if current_return > peak:
            # New peak
            peak = current_return
            
            # End of drawdown period
            if drawdown_start is not None:
                dd_duration = (sorted_results[i].entry_time - drawdown_start).total_seconds() / (24 * 3600)
                max_dd_duration = max(max_dd_duration, dd_duration)
                drawdown_start = None
        else:
            # Drawdown
            current_drawdown = (peak - current_return) / (1 + peak) if peak != 0 else 0
            max_drawdown = max(max_drawdown, current_drawdown)
            
            # Start tracking drawdown duration
            if drawdown_start is None:
                drawdown_start = sorted_results[i].entry_time
    
    return max_drawdown, max_dd_duration


def analyze_by_market(results: List[TradingResult]) -> Dict[str, Dict]:
    """Analyze performance by market."""
    market_results = {}
    
    for result in results:
        market_id = result.signal.market_id
        if market_id not in market_results:
            market_results[market_id] = []
        market_results[market_id].append(result)
    
    market_metrics = {}
    for market_id, market_trades in market_results.items():
        if market_trades:
            metrics = calculate_metrics(market_trades)
            market_metrics[market_id] = {
                'trades': len(market_trades),
                'win_rate': metrics.win_rate,
                'avg_return': metrics.avg_return,
                'total_return': metrics.total_return
            }
    
    return market_metrics


def analyze_by_direction(results: List[TradingResult]) -> Dict[str, Dict]:
    """Analyze performance by trade direction."""
    direction_results = {'BUY_YES': [], 'BUY_NO': []}
    
    for result in results:
        direction = result.signal.direction
        if direction in direction_results:
            direction_results[direction].append(result)
    
    direction_metrics = {}
    for direction, direction_trades in direction_results.items():
        if direction_trades:
            metrics = calculate_metrics(direction_trades)
            direction_metrics[direction] = {
                'trades': len(direction_trades),
                'win_rate': metrics.win_rate,
                'avg_return': metrics.avg_return,
                'total_return': metrics.total_return
            }
    
    return direction_metrics


def analyze_by_confidence(results: List[TradingResult], bins: int = 3) -> Dict[str, Dict]:
    """Analyze performance by confidence level."""
    if not results:
        return {}
    
    # Create confidence bins
    confidences = [r.signal.confidence for r in results]
    min_conf, max_conf = min(confidences), max(confidences)
    bin_size = (max_conf - min_conf) / bins
    
    confidence_results = {}
    
    for result in results:
        conf = result.signal.confidence
        bin_idx = min(bins - 1, int((conf - min_conf) / bin_size))
        bin_label = f"{min_conf + bin_idx * bin_size:.2f}-{min_conf + (bin_idx + 1) * bin_size:.2f}"
        
        if bin_label not in confidence_results:
            confidence_results[bin_label] = []
        confidence_results[bin_label].append(result)
    
    confidence_metrics = {}
    for bin_label, bin_trades in confidence_results.items():
        if bin_trades:
            metrics = calculate_metrics(bin_trades)
            confidence_metrics[bin_label] = {
                'trades': len(bin_trades),
                'win_rate': metrics.win_rate,
                'avg_return': metrics.avg_return,
                'total_return': metrics.total_return
            }
    
    return confidence_metrics