"""
Paper Trading Portfolio Management
=================================

Manages a virtual portfolio for paper trading, tracking positions,
balance, and P&L without real money involved.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Literal
from decimal import Decimal, ROUND_HALF_UP


@dataclass
class Position:
    """Represents an open trading position."""
    id: str
    market_id: str
    direction: Literal["BUY_YES", "BUY_NO"]
    shares: float
    entry_price: float
    entry_time: datetime
    signal_id: str
    confidence: float
    
    def __post_init__(self):
        """Validate position data."""
        if self.shares <= 0:
            raise ValueError("Position shares must be positive")
        if not (0 <= self.entry_price <= 1):
            raise ValueError("Entry price must be between 0 and 1")
        if not (0 <= self.confidence <= 1):
            raise ValueError("Confidence must be between 0 and 1")
    
    @property
    def cost_basis(self) -> float:
        """Total amount invested in this position."""
        return self.shares * self.entry_price
    
    @property
    def age_hours(self) -> float:
        """Age of position in hours."""
        return (datetime.now() - self.entry_time).total_seconds() / 3600
    
    @property
    def should_auto_close(self) -> bool:
        """Whether position should be auto-closed (24h rule)."""
        return self.age_hours >= 24.0
    
    def current_value(self, current_price: float) -> float:
        """Calculate current value of position given current price."""
        return self.shares * current_price
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L."""
        return self.current_value(current_price) - self.cost_basis
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'market_id': self.market_id,
            'direction': self.direction,
            'shares': self.shares,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat(),
            'signal_id': self.signal_id,
            'confidence': self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        """Create position from dictionary."""
        data = data.copy()
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        return cls(**data)


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    id: str
    market_id: str
    direction: Literal["BUY_YES", "BUY_NO"]
    shares: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    signal_id: str
    confidence: float
    pnl: float
    return_pct: float
    reason: str  # "manual", "auto_close", "market_resolved"
    
    @property
    def duration_hours(self) -> float:
        """Trade duration in hours."""
        return (self.exit_time - self.entry_time).total_seconds() / 3600
    
    @property
    def was_profitable(self) -> bool:
        """Whether trade was profitable."""
        return self.pnl > 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'market_id': self.market_id,
            'direction': self.direction,
            'shares': self.shares,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'signal_id': self.signal_id,
            'confidence': self.confidence,
            'pnl': self.pnl,
            'return_pct': self.return_pct,
            'reason': self.reason
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeRecord':
        """Create trade record from dictionary."""
        data = data.copy()
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)


class PaperPortfolio:
    """
    Manages a virtual trading portfolio for paper trading.
    
    Features:
    - Tracks cash balance and positions
    - Enforces risk management rules
    - Calculates P&L and portfolio value
    - Maintains trade history
    """
    
    def __init__(self, initial_balance: float = 1000.0):
        """Initialize portfolio with starting balance."""
        self.balance = float(initial_balance)
        self.initial_balance = float(initial_balance)
        self.positions: Dict[str, Position] = {}  # market_id -> Position
        self.history: List[TradeRecord] = []
        self.created_at = datetime.now()
    
    @property
    def open_position_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)
    
    @property
    def max_position_size(self) -> float:
        """Maximum position size (10% of total value)."""
        return self.get_total_value({}) * 0.10
    
    def can_open_position(self, amount: float) -> bool:
        """Check if we can open a new position."""
        # Check position count limit
        if self.open_position_count >= 5:
            return False
        
        # Check available balance
        if amount > self.balance:
            return False
        
        # Check position size limit
        if amount > self.max_position_size:
            return False
        
        return True
    
    def has_position_in_market(self, market_id: str) -> bool:
        """Check if we already have a position in this market."""
        return market_id in self.positions
    
    def open_position(
        self, 
        market_id: str, 
        direction: Literal["BUY_YES", "BUY_NO"], 
        amount: float, 
        price: float,
        signal_id: str,
        confidence: float
    ) -> Position:
        """
        Open a new position.
        
        Args:
            market_id: Market identifier
            direction: BUY_YES or BUY_NO
            amount: USD amount to invest
            price: Entry price (0-1)
            signal_id: ID of the signal that triggered this trade
            confidence: Signal confidence (0-1)
        
        Returns:
            Created Position object
        
        Raises:
            ValueError: If position cannot be opened
        """
        # Validate inputs
        if not self.can_open_position(amount):
            raise ValueError(f"Cannot open position: insufficient balance or limits exceeded")
        
        if self.has_position_in_market(market_id):
            raise ValueError(f"Already have position in market {market_id}")
        
        if not (0 <= price <= 1):
            raise ValueError("Price must be between 0 and 1")
        
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Calculate shares
        shares = amount / price if price > 0 else 0
        if shares <= 0:
            raise ValueError("Invalid shares calculation")
        
        # Create position
        position = Position(
            id=str(uuid.uuid4()),
            market_id=market_id,
            direction=direction,
            shares=shares,
            entry_price=price,
            entry_time=datetime.now(),
            signal_id=signal_id,
            confidence=confidence
        )
        
        # Update portfolio
        self.positions[market_id] = position
        self.balance -= amount
        
        return position
    
    def close_position(
        self, 
        market_id: str, 
        exit_price: float,
        reason: str = "manual"
    ) -> Optional[TradeRecord]:
        """
        Close an open position.
        
        Args:
            market_id: Market identifier
            exit_price: Exit price (0-1)
            reason: Reason for closing
        
        Returns:
            TradeRecord if position was closed, None if no position found
        """
        if market_id not in self.positions:
            return None
        
        position = self.positions.pop(market_id)
        
        # Calculate proceeds and P&L
        proceeds = position.shares * exit_price
        pnl = proceeds - position.cost_basis
        return_pct = pnl / position.cost_basis if position.cost_basis > 0 else 0
        
        # Update balance
        self.balance += proceeds
        
        # Create trade record
        trade = TradeRecord(
            id=str(uuid.uuid4()),
            market_id=market_id,
            direction=position.direction,
            shares=position.shares,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            signal_id=position.signal_id,
            confidence=position.confidence,
            pnl=pnl,
            return_pct=return_pct,
            reason=reason
        )
        
        # Add to history
        self.history.append(trade)
        
        return trade
    
    def close_stale_positions(self, current_prices: Dict[str, float]) -> List[TradeRecord]:
        """
        Close positions that should be auto-closed (24h rule).
        
        Args:
            current_prices: Dict of market_id -> current_price
        
        Returns:
            List of TradeRecord objects for closed positions
        """
        closed_trades = []
        stale_markets = []
        
        for market_id, position in self.positions.items():
            if position.should_auto_close:
                stale_markets.append(market_id)
        
        for market_id in stale_markets:
            # Use last known price or entry price
            exit_price = current_prices.get(market_id, self.positions[market_id].entry_price)
            trade = self.close_position(market_id, exit_price, "auto_close")
            if trade:
                closed_trades.append(trade)
        
        return closed_trades
    
    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value (balance + position values).
        
        Args:
            current_prices: Dict of market_id -> current_price
        
        Returns:
            Total portfolio value
        """
        total_value = self.balance
        
        for market_id, position in self.positions.items():
            current_price = current_prices.get(market_id, position.entry_price)
            total_value += position.current_value(current_price)
        
        return total_value
    
    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate total unrealized P&L from open positions."""
        total_pnl = 0.0
        
        for market_id, position in self.positions.items():
            current_price = current_prices.get(market_id, position.entry_price)
            total_pnl += position.unrealized_pnl(current_price)
        
        return total_pnl
    
    def get_realized_pnl(self) -> float:
        """Calculate total realized P&L from closed trades."""
        return sum(trade.pnl for trade in self.history)
    
    def get_total_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate total P&L (realized + unrealized)."""
        return self.get_realized_pnl() + self.get_unrealized_pnl(current_prices)
    
    def get_return_pct(self, current_prices: Dict[str, float]) -> float:
        """Calculate total return percentage."""
        current_value = self.get_total_value(current_prices)
        return (current_value - self.initial_balance) / self.initial_balance * 100
    
    def get_pnl_summary(self, current_prices: Dict[str, float] = None) -> Dict:
        """Get comprehensive P&L summary."""
        if current_prices is None:
            current_prices = {}
        
        total_value = self.get_total_value(current_prices)
        realized_pnl = self.get_realized_pnl()
        unrealized_pnl = self.get_unrealized_pnl(current_prices)
        total_pnl = realized_pnl + unrealized_pnl
        
        # Trade statistics
        total_trades = len(self.history)
        winning_trades = sum(1 for trade in self.history if trade.was_profitable)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        best_trade = max(self.history, key=lambda t: t.pnl) if self.history else None
        worst_trade = min(self.history, key=lambda t: t.pnl) if self.history else None
        
        return {
            'balance': round(self.balance, 2),
            'total_value': round(total_value, 2),
            'initial_balance': round(self.initial_balance, 2),
            'total_pnl': round(total_pnl, 2),
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'return_pct': round(self.get_return_pct(current_prices), 2),
            'open_positions': self.open_position_count,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': round(win_rate, 1),
            'best_trade_pnl': round(best_trade.pnl, 2) if best_trade else 0,
            'worst_trade_pnl': round(worst_trade.pnl, 2) if worst_trade else 0,
            'created_at': self.created_at.isoformat()
        }
    
    def to_dict(self) -> Dict:
        """Convert portfolio to dictionary for serialization."""
        return {
            'balance': self.balance,
            'initial_balance': self.initial_balance,
            'positions': {k: v.to_dict() for k, v in self.positions.items()},
            'history': [trade.to_dict() for trade in self.history],
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PaperPortfolio':
        """Create portfolio from dictionary."""
        portfolio = cls(data.get('initial_balance', 1000.0))
        portfolio.balance = data.get('balance', portfolio.initial_balance)
        
        # Load positions
        portfolio.positions = {
            k: Position.from_dict(v) 
            for k, v in data.get('positions', {}).items()
        }
        
        # Load history
        portfolio.history = [
            TradeRecord.from_dict(trade) 
            for trade in data.get('history', [])
        ]
        
        # Set creation time
        if 'created_at' in data:
            portfolio.created_at = datetime.fromisoformat(data['created_at'])
        
        return portfolio