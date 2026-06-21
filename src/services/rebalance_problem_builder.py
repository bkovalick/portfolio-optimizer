from models.rebalance_problem import RebalanceProblem
from models.rebalance_config import RebalanceProblemConfig
from simulation.market_state import MarketState
from utils.lookback_windows import LOOKBACK_WINDOWS

import pandas as pd

class RebalanceProblemBuilder:
    """Orchestrates the pipeline to build a RebalanceProblem from input configuration."""

    def __init__(self, 
                 rebalance_config: RebalanceProblemConfig, 
                 market_state: MarketState):
        self.rebalance_config = rebalance_config
        self.market_state = market_state

    def _resolve_window(self, value):
        """Resolve a duration string (e.g. '1m') or raw int to a period count. Returns None if value is None."""
        if value is None:
            return None
        if isinstance(value, str):
            freq_map = LOOKBACK_WINDOWS.get(self.market_state.market_frequency, LOOKBACK_WINDOWS["d"])
            if value not in freq_map:
                valid = sorted(freq_map.keys())
                raise ValueError(
                    f"Invalid duration key {value!r} for market_frequency={self.market_state.market_frequency!r}. "
                    f"Valid keys: {valid}"
                )
            return freq_map[value]
        return int(value)
    
    def _build_init_weights_from_mkt_caps(self) -> dict:
        """Builds the initial weight vector based on market capitalization weights."""
        market_caps = self.market_state.market_caps
        return (market_caps / market_caps.sum()).to_dict()   

    def _setup_initial_weights(self, 
                               cash_allocation: float, 
                               tickers: list, 
                               n_assets: int) -> dict: 
        """ Determines the initial weight vector based on the rebalance configuration."""
        if self.rebalance_config.apply_market_caps:
            return self._build_init_weights_from_mkt_caps()

        explicit_weights = self.rebalance_config.initial_weights
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
        n_assets = len(self.market_state.investment_universe)
        cash_allocation = self.market_state.cash_allocation
        investment_universe = self.market_state.investment_universe
        initial_weights = self._setup_initial_weights(cash_allocation, investment_universe, n_assets)
        prepared_data = {
            "n_assets": n_assets,
            "optimizer_type": self.rebalance_config.optimizer_type,
            "strategy_type": self.rebalance_config.strategy_type,
            "apply_max_return_objective": self.rebalance_config.apply_max_return_objective,
            "apply_sharpe_objective": self.rebalance_config.apply_sharpe_objective,
            "initial_weights": initial_weights,
            "cash_allocation": cash_allocation,
            "rebalance_frequency": self.rebalance_config.rebalance_frequency,
            "risk_aversion": self.rebalance_config.constraints.risk_aversion,
            "turnover_limit": self.rebalance_config.constraints.turnover_limit,
            "min_position_size": self.rebalance_config.constraints.min_position_size,
            "max_position_size": self.rebalance_config.constraints.max_position_size,
            "max_number_of_positions": self.rebalance_config.constraints.max_number_of_positions,
            "asset_class_constraints": self.rebalance_config.constraints.asset_class_constraints,
            "sector_constraints": self.rebalance_config.constraints.sector_constraints,
            "max_return": self.rebalance_config.constraints.max_return,
            "concentration_strength": self.rebalance_config.constraints.concentration_strength,
            "asset_class_map": self.market_state.asset_class_map,
            "sector_map": self.market_state.sector_map,
            "investment_universe": investment_universe,
            "signal_universe": self.market_state.signal_universe,
            "security_to_etf_map": self.market_state.security_to_etf_map,
            "optimizer_vol_constraint": self.rebalance_config.constraints.optimizer_vol_constraint,
            "vol_target": self.rebalance_config.strategy_rules.vol_target,
            "vol_lookback_days": self._resolve_window(self.rebalance_config.strategy_rules.vol_lookback_days),
            "vol_max_leverage": self.rebalance_config.strategy_rules.vol_max_leverage,
            "signal_source": self.rebalance_config.signal_source,
            "transaction_cost": self.market_state.transaction_cost,
            "starting_portfolio_value": self.rebalance_config.starting_portfolio_value,
            "cash_infusion": self.rebalance_config.cash_infusion,
            "monitoring_type": self.rebalance_config.monitoring_type
        }

        return RebalanceProblem(prepared_data)