from domain.strategies.istrategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem
from domain.optimizers.optimizer import PortfolioRebalancer

import numpy as np
import pandas as pd

class SystematicStrategy(StrategyInterface):
    """ 
    Systematic strategy that is entirely driven by configuration files. 
    The strategy logic is determined by the signal source specified in the rebalance problem, 
    and the optimizer is applied to those signals to generate new weights.
    """
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, 
                  signals: dict, 
                  current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        signal_key = self.rebalance_problem.signal_source
        active_signals = signals.get(signal_key)
        
        if active_signals is None:
            return current_weights
        
        optimized = self.optimizer.optimize(
            self.rebalance_problem, active_signals, current_weights
        )
        
        # live = False
        # if live:
        #     trades = self._convert_to_trades(
        #         optimized,
        #         market_prices=self._get_prices(active_signals)
        #     )
        return optimized
    
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
                    active_signals) -> pd.DataFrame:
        lookback_prices = getattr(active_signals, "lookback_prices")
        if not callable(lookback_prices):
            raise ValueError("Active signals must have a callable lookback_prices method")
        prices = lookback_prices()
        return prices


