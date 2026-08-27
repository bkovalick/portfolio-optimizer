from domain.strategies.base_strategy import BaseStrategy
from domain.optimizers.optimizer import PortfolioRebalancer
from domain.optimizers.optimizer import Optimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

import numpy as np
import pandas as pd

class SystematicStrategy(BaseStrategy):
    """ 
    Systematic strategy that is entirely driven by configuration files. 
    The strategy logic is determined by the signal source specified in the rebalance problem, 
    and the optimizer is applied to those signals to generate new weights.
    """
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer: Optimizer = None):
        super().__init__(rebalance_problem, optimizer)
    
    def rebalance(self, rebalance_context: RebalanceContext) -> RebalanceSolution:
        """Calculate rebalance weights"""
        signal_key = self.rebalance_problem.signal_source
        active_signal = rebalance_context.signals.get(signal_key)
        
        if active_signal is None:
            return RebalanceSolution(
                target_weights=rebalance_context.current_weights,
                sell_allocations={},
                realized_tax_cost=0.0,
                tracking_error=0.0
            )

        rebalance_solution = self.optimizer.optimize(
            rebalance_context, active_signal
        )

        return rebalance_solution
    
    def _convert_to_trades(self, 
                           target_weights: np.ndarray,
                           market_prices: pd.DataFrame) -> np.ndarray:
        available_cash = self.rebalance_problem.starting_portfolio_value + \
            self.rebalance_problem.cash_infusion
        
        rebalancer = PortfolioRebalancer(
            target_weights,
            available_cash,
            market_prices.iloc[-1].values
        )
        return rebalancer.generate_trades()
    
    def _get_prices(self, 
                    active_signal) -> pd.DataFrame:
        lookback_prices = getattr(active_signal, "lookback_prices")
        if not callable(lookback_prices):
            raise ValueError("Active signal must have a callable lookback_prices method")
        prices = lookback_prices()
        return prices


