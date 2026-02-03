"""
Trading Performance Reporter
============================

Generates formatted reports for trading performance analysis.
Supports multiple output formats including Telegram-friendly reports.
"""
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from .portfolio import PaperPortfolio
from .tracker import TradingTracker
from .decision_engine import TradingDecisionEngine


class ReportGenerator:
    """
    Generates various trading performance reports.
    
    Report Types:
    - Daily summary (Telegram format)
    - Weekly performance
    - Portfolio health check
    - Trade analysis
    """
    
    def __init__(self, tracker: TradingTracker):
        """Initialize reporter with data tracker."""
        self.tracker = tracker
    
    def generate_telegram_report(
        self, 
        portfolio: PaperPortfolio, 
        current_prices: Dict[str, float] = None
    ) -> str:
        """
        Generate Telegram-formatted daily performance report.
        
        Args:
            portfolio: Current portfolio state
            current_prices: Current market prices for position valuation
        
        Returns:
            Formatted report string for Telegram
        """
        if current_prices is None:
            current_prices = {}
        
        # Get portfolio summary
        summary = portfolio.get_pnl_summary(current_prices)
        
        # Get today's trades
        today_trades = self.tracker.get_trades_by_date(date.today())
        today_pnl = sum(t['pnl'] for t in today_trades)
        
        # Calculate performance indicators
        return_pct = summary['return_pct']
        performance_emoji = "📈" if return_pct > 0 else "📉" if return_pct < 0 else "➡️"
        
        # Header
        report = "📊 **PAPER TRADING REPORT**\n\n"
        
        # Portfolio overview
        report += f"💰 **Portfolio:** ${summary['total_value']:,.2f} ({return_pct:+.1f}%)\n"
        report += f"📈 **Today:** {'+' if today_pnl >= 0 else ''}${today_pnl:.2f} ({len(today_trades)} trades)\n\n"
        
        # Open Positions
        if portfolio.positions:
            report += "**📋 Open Positions:**\n"
            for market_id, position in portfolio.positions.items():
                current_price = current_prices.get(market_id, position.entry_price)
                unrealized_pnl = position.unrealized_pnl(current_price)
                pnl_emoji = "🟢" if unrealized_pnl > 0 else "🔴" if unrealized_pnl < 0 else "🟡"
                
                direction_emoji = "📈" if position.direction == "BUY_YES" else "📉"
                
                # Truncate market ID for display
                market_display = market_id[:30] + "..." if len(market_id) > 30 else market_id
                
                report += f"• {direction_emoji} {market_display}\n"
                report += f"  Entry: {position.entry_price:.3f} → Now: {current_price:.3f} "
                report += f"{pnl_emoji} ${unrealized_pnl:+.2f}\n"
            
            report += "\n"
        else:
            report += "📋 **No Open Positions**\n\n"
        
        # Recent Trades (last 3)
        if today_trades:
            report += "**🔄 Recent Trades:**\n"
            recent_trades = sorted(today_trades, key=lambda t: t['exit_time'], reverse=True)[:3]
            
            for trade in recent_trades:
                result_emoji = "✅" if trade['pnl'] > 0 else "❌"
                direction_emoji = "📈" if trade['direction'] == "BUY_YES" else "📉"
                
                # Truncate market ID
                market_display = trade['market_id'][:25] + "..." if len(trade['market_id']) > 25 else trade['market_id']
                
                report += f"{result_emoji} {direction_emoji} {market_display}: ${trade['pnl']:+.2f}\n"
            
            report += "\n"
        
        # Key Stats
        report += "**📊 Performance Stats:**\n"
        report += f"• Total Trades: {summary['total_trades']}\n"
        report += f"• Win Rate: {summary['win_rate']:.1f}%\n"
        report += f"• Best Trade: ${summary['best_trade_pnl']:.2f}\n"
        report += f"• Worst Trade: ${summary['worst_trade_pnl']:.2f}\n"
        
        # Add timestamp
        report += f"\n🕒 *Updated: {datetime.now().strftime('%H:%M')} GMT+1*"
        
        return report
    
    def generate_daily_summary(self, target_date: date = None) -> Dict:
        """Generate comprehensive daily summary."""
        if target_date is None:
            target_date = date.today()
        
        # Get daily metrics
        metrics = self.tracker.calculate_daily_metrics(target_date)
        
        # Get portfolio state
        portfolio = self.tracker.load_portfolio_state()
        if portfolio is None:
            return metrics
        
        # Add portfolio information
        portfolio_summary = portfolio.get_pnl_summary()
        metrics.update({
            'portfolio_value': portfolio_summary['total_value'],
            'portfolio_return_pct': portfolio_summary['return_pct'],
            'open_positions': portfolio_summary['open_positions'],
            'available_balance': portfolio_summary['balance']
        })
        
        return metrics
    
    def generate_weekly_report(self) -> str:
        """Generate weekly performance report."""
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        # Collect trades from the week
        weekly_trades = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_trades = self.tracker.get_trades_by_date(current_date)
            weekly_trades.extend(daily_trades)
            current_date += timedelta(days=1)
        
        if not weekly_trades:
            return "📅 **Weekly Report**\n\nNo trades this week."
        
        # Calculate weekly stats
        total_pnl = sum(t['pnl'] for t in weekly_trades)
        profitable_trades = sum(1 for t in weekly_trades if t['pnl'] > 0)
        win_rate = profitable_trades / len(weekly_trades) * 100
        
        best_trade = max(weekly_trades, key=lambda t: t['pnl'])
        worst_trade = min(weekly_trades, key=lambda t: t['pnl'])
        
        report = "📅 **WEEKLY PERFORMANCE REPORT**\n\n"
        report += f"📊 **Summary ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})**\n"
        report += f"• Total Trades: {len(weekly_trades)}\n"
        report += f"• Total P&L: ${total_pnl:+.2f}\n"
        report += f"• Win Rate: {win_rate:.1f}%\n"
        report += f"• Best Trade: ${best_trade['pnl']:+.2f}\n"
        report += f"• Worst Trade: ${worst_trade['pnl']:+.2f}\n\n"
        
        # Daily breakdown
        report += "**📈 Daily Breakdown:**\n"
        daily_summary = {}
        
        for trade in weekly_trades:
            trade_date = datetime.fromisoformat(trade['exit_time']).date()
            if trade_date not in daily_summary:
                daily_summary[trade_date] = {'trades': 0, 'pnl': 0}
            daily_summary[trade_date]['trades'] += 1
            daily_summary[trade_date]['pnl'] += trade['pnl']
        
        for trade_date in sorted(daily_summary.keys()):
            data = daily_summary[trade_date]
            emoji = "📈" if data['pnl'] > 0 else "📉" if data['pnl'] < 0 else "➡️"
            report += f"{emoji} {trade_date.strftime('%a %b %d')}: {data['trades']} trades, ${data['pnl']:+.2f}\n"
        
        return report
    
    def generate_portfolio_health_report(
        self, 
        portfolio: PaperPortfolio, 
        current_prices: Dict[str, float] = None
    ) -> str:
        """Generate portfolio health assessment."""
        if current_prices is None:
            current_prices = {}
        
        # Calculate health metrics
        decision_engine = TradingDecisionEngine()
        health_score = decision_engine.get_portfolio_health_score(portfolio, current_prices)
        summary = portfolio.get_pnl_summary(current_prices)
        
        # Health assessment
        if health_score >= 0.8:
            health_status = "🟢 Excellent"
        elif health_score >= 0.6:
            health_status = "🟡 Good"
        elif health_score >= 0.4:
            health_status = "🟠 Fair"
        else:
            health_status = "🔴 Poor"
        
        report = "🏥 **PORTFOLIO HEALTH CHECK**\n\n"
        report += f"**Overall Health:** {health_status} ({health_score:.1%})\n\n"
        
        # Detailed metrics
        report += "**📊 Key Metrics:**\n"
        report += f"• Portfolio Value: ${summary['total_value']:,.2f}\n"
        report += f"• Total Return: {summary['return_pct']:+.1f}%\n"
        report += f"• Available Cash: ${summary['balance']:,.2f} ({summary['balance']/summary['total_value']*100:.1f}%)\n"
        report += f"• Open Positions: {summary['open_positions']}/5\n"
        report += f"• Win Rate: {summary['win_rate']:.1f}%\n\n"
        
        # Risk assessment
        report += "**⚠️ Risk Assessment:**\n"
        
        # Cash ratio check
        cash_ratio = summary['balance'] / summary['total_value']
        if cash_ratio < 0.1:
            report += "• 🔴 Low cash reserves (<10%)\n"
        elif cash_ratio > 0.5:
            report += "• 🟡 High cash reserves (>50%) - consider more positions\n"
        else:
            report += "• 🟢 Healthy cash allocation\n"
        
        # Position concentration
        if summary['open_positions'] >= 5:
            report += "• 🟡 Maximum positions reached\n"
        elif summary['open_positions'] == 0:
            report += "• 🟡 No active positions\n"
        else:
            report += "• 🟢 Good position diversification\n"
        
        # Performance trend
        if summary['total_trades'] < 5:
            report += "• 🟡 Limited trading history\n"
        elif summary['win_rate'] < 40:
            report += "• 🔴 Low win rate - review strategy\n"
        elif summary['win_rate'] > 70:
            report += "• 🟢 Strong win rate\n"
        else:
            report += "• 🟢 Healthy win rate\n"
        
        # Recommendations
        report += "\n**💡 Recommendations:**\n"
        
        if cash_ratio < 0.2 and summary['open_positions'] >= 3:
            report += "• Consider taking profits on some positions\n"
        
        if summary['win_rate'] < 50 and summary['total_trades'] > 10:
            report += "• Review decision criteria - consider higher confidence threshold\n"
        
        if summary['open_positions'] == 0 and cash_ratio > 0.8:
            report += "• Look for high-confidence trading opportunities\n"
        
        if summary['return_pct'] < -10:
            report += "• Consider reducing position sizes until performance improves\n"
        
        return report
    
    def generate_trade_analysis(self, limit: int = 10) -> str:
        """Generate analysis of recent trades."""
        all_trades = self.tracker.get_all_trades()
        if not all_trades:
            return "No trades to analyze."
        
        # Sort by exit time, most recent first
        recent_trades = sorted(all_trades, key=lambda t: t['exit_time'], reverse=True)[:limit]
        
        report = f"📈 **TRADE ANALYSIS** (Last {len(recent_trades)} trades)\n\n"
        
        # Performance metrics
        total_pnl = sum(t['pnl'] for t in recent_trades)
        profitable = sum(1 for t in recent_trades if t['pnl'] > 0)
        win_rate = profitable / len(recent_trades) * 100
        
        report += f"**📊 Performance:**\n"
        report += f"• Total P&L: ${total_pnl:+.2f}\n"
        report += f"• Win Rate: {win_rate:.1f}% ({profitable}/{len(recent_trades)})\n"
        report += f"• Avg P&L: ${total_pnl/len(recent_trades):+.2f}\n\n"
        
        # Best and worst trades
        best = max(recent_trades, key=lambda t: t['pnl'])
        worst = min(recent_trades, key=lambda t: t['pnl'])
        
        report += f"**🏆 Best Trade:** +${best['pnl']:.2f}\n"
        report += f"**💸 Worst Trade:** ${worst['pnl']:.2f}\n\n"
        
        # Trade details
        report += "**📋 Recent Trades:**\n"
        for i, trade in enumerate(recent_trades[:5], 1):
            result_emoji = "✅" if trade['pnl'] > 0 else "❌"
            direction_emoji = "📈" if trade['direction'] == "BUY_YES" else "📉"
            
            # Format trade time
            exit_time = datetime.fromisoformat(trade['exit_time'])
            time_str = exit_time.strftime('%m/%d %H:%M')
            
            market_short = trade['market_id'][:20] + "..." if len(trade['market_id']) > 20 else trade['market_id']
            
            report += f"{i}. {result_emoji} {direction_emoji} {market_short}\n"
            report += f"   ${trade['pnl']:+.2f} ({trade['return_pct']:+.1f}%) - {time_str}\n"
        
        return report
    
    def export_csv_report(self, output_path: str = "trading_report.csv") -> str:
        """Export all trades to CSV format."""
        import csv
        
        all_trades = self.tracker.get_all_trades()
        if not all_trades:
            return "No trades to export."
        
        output_file = Path(output_path)
        
        try:
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = [
                    'exit_time', 'market_id', 'direction', 'shares', 
                    'entry_price', 'exit_price', 'pnl', 'return_pct', 
                    'duration_hours', 'confidence', 'reason'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in all_trades:
                    # Clean data for CSV
                    row = {k: v for k, v in trade.items() if k in fieldnames}
                    writer.writerow(row)
            
            return f"Exported {len(all_trades)} trades to {output_file}"
        
        except Exception as e:
            return f"Error exporting CSV: {e}"