from models.rebalance_problem import RebalanceProblem
from utils.lookback_windows import LOOKBACK_WINDOWS

import pandas as pd

class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""

    def __init__(self, 
                 config: dict, 
                 universe_meta: dict, 
                 market_frequency: str = "d"):
        """Initialize with configuration dictionary."""
        self.config = config
        self.universe_meta = universe_meta
        self.market_frequency = market_frequency

    def _resolve_window(self, value):
        """Resolve a duration string (e.g. '1m') or raw int to a period count. Returns None if value is None."""
        if value is None:
            return None
        if isinstance(value, str):
            freq_map = LOOKBACK_WINDOWS.get(self.market_frequency, LOOKBACK_WINDOWS["d"])
            if value not in freq_map:
                valid = sorted(freq_map.keys())
                raise ValueError(
                    f"Invalid duration key {value!r} for market_frequency={self.market_frequency!r}. "
                    f"Valid keys: {valid}"
                )
            return freq_map[value]
        return int(value)
    
    def _build_init_weights_from_mkt_caps(self, market_caps: pd.Series) -> dict:
        return (market_caps / market_caps.sum()).to_dict()

    def _setup_initial_weights(self, 
                               cash_allocation: float, 
                               tickers: list, 
                               n_assets: int) -> dict: 
        apply_market_caps = self.config.get("apply_market_caps", False)
        market_caps = self.universe_meta.get("market_caps", None)
        if apply_market_caps and market_caps is not None:
            return self._build_init_weights_from_mkt_caps(market_caps)
        
        explicit_weights = self.config.get("initial_weights", None)
        if explicit_weights:
            weights = explicit_weights
        elif cash_allocation > 0:
            weights = [(1 - cash_allocation) / (n_assets - 1)] * (n_assets - 1) + [cash_allocation]
        else:
            weights = [1 / n_assets] * n_assets

        if isinstance(weights, list):
            initial_weights = dict(zip(tickers, weights))
        elif isinstance(weights, dict):
            initial_weights = weights
        return initial_weights      

    def build(self) -> RebalanceProblem:
        """Build and return a RebalanceProblem instance."""
        n_assets = len(investment_universe)
        cash_allocation = self.universe_meta.get("cash_allocation", 0.0)
        investment_universe = self.universe_meta.get("investment_universe", ["AAPL"])
        signal_universe = self.universe_meta.get("signal_universe", investment_universe)
        security_to_etf_map = {}
        initial_weights = self._setup_initial_weights(cash_allocation, investment_universe, n_assets)
        constraints = self.config.get("constraints", {})
        strategy_rules = self.config.get("strategy_rules", {}) 
        prepared_data = {
            "n_assets": n_assets,
            "optimizer_type": self.config.get("optimizer_type"),
            "strategy_type": self.config.get("strategy_type"),
            "apply_max_return_objective": self.config.get("apply_max_return_objective", False),
            "apply_sharpe_objective": self.config.get("apply_sharpe_objective", False),
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "rebalance_frequency": self.config.get("rebalance_frequency", None),
            "risk_aversion": constraints.get("risk_aversion", 1),
            "turnover_limit": constraints.get("turnover_limit", None),
            "min_position_size": constraints.get("min_position_size", None),
            "max_position_size": constraints.get("max_position_size", None),
            "max_number_of_positions": constraints.get("max_number_of_positions", None),
            "asset_class_constraints": constraints.get("asset_class_constraints", None),
            "sector_constraints": constraints.get("sector_constraints", None),
            "max_return": constraints.get("max_return", 0.05),
            "concentration_strength": constraints.get("concentration_strength", 1),
            "asset_class_map": self.universe_meta.get("asset_class_map", {}),
            "sector_map": self.universe_meta.get("sector_map", {}),
            "investment_universe": investment_universe,
            "signal_universe": signal_universe,
            "security_to_etf_map": security_to_etf_map,
            "optimizer_vol_constraint": constraints.get("optimizer_vol_constraint", None),
            "vol_target": strategy_rules.get("vol_target", None),
            "vol_lookback_days": self._resolve_window(strategy_rules.get("vol_lookback_days", None)),
            "vol_max_leverage": strategy_rules.get("vol_max_leverage", None),
            "signal_source": self.config.get("signal_source", "risk_return"),
            "transaction_cost": self.universe_meta.get("transaction_cost", 0.0),
            "starting_portfolio_value": self.config.get("starting_portfolio_value", 10000),
            "cash_infusion": self.config.get("cash_infusion", 1000)
        }

        return RebalanceProblem(prepared_data)