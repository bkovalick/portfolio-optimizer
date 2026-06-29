from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from utils.lookback_windows import LOOKBACK_WINDOWS

@dataclass(frozen=True)
class MarketStateConfig:
    lookback_window_key: str
    market_frequency: str
    lookback_window: int
    cash_allocation: float
    investment_universe: List[str]
    signal_universe: List[str]
    security_to_etf_map: Optional[Dict[str, str]]
    exogenous_tickers: List[str]
    annual_trading_days: int

    @classmethod
    def from_dict(cls, d: dict):
        lookback_window_key = d.get("lookback_window_key", "1y")
        market_frequency = d.get("market_frequency", "w")
        lookback_window = LOOKBACK_WINDOWS[market_frequency][lookback_window_key]
        annual_trading_days = LOOKBACK_WINDOWS[market_frequency]["1y"]
        cash_allocation = d.get("cash_allocation", 0.0)
        investment_universe = list(d.get("investment_universe", ["AAPL"]))
        signal_universe = list(d.get("signal_universe", investment_universe))
        security_to_etf_map = d.get("security_to_etf_map", None)
        exogenous_tickers = list(d.get("exogenous_tickers", []))
        
        if cash_allocation > 0:
            investment_universe = investment_universe + ["CASH"] 

        return cls(
            lookback_window_key = lookback_window_key,
            market_frequency = market_frequency,
            lookback_window = lookback_window,
            cash_allocation = cash_allocation,
            investment_universe = investment_universe,
            signal_universe = signal_universe,
            security_to_etf_map = security_to_etf_map,
            exogenous_tickers = exogenous_tickers,
            annual_trading_days = annual_trading_days
        )

@dataclass(frozen=True)
class MarketStoreConfig:
    tickers: List[Any]
    start_date: str
    end_date: str
    data_source: Dict
    benchmark: Optional[str]
    risk_free_rate: float
    transaction_cost: float
    apply_market_caps: bool

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            tickers = d.get("tickers", ["AAPL"]),
            start_date = d.get("start_date", "2005-01-01"),
            end_date = d.get("end_date", "2026-02-19"),
            data_source = d.get("data_source", { "yfinance": None }),
            benchmark = d.get("benchmark", "SPY"),
            risk_free_rate = d.get("risk_free_rate", 0.0),
            transaction_cost = d.get("transaction_cost", 0.0),
            apply_market_caps = d.get("apply_market_caps", False)
        )
    
    def to_dict(self):
        return {
            "tickers": self.tickers,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "data_source": self.data_source,
            "benchmark": self.benchmark,
            "risk_free_rate": self.risk_free_rate,
            "transaction_cost": self.transaction_cost,
            "apply_market_caps": self.apply_market_caps
        }
    
