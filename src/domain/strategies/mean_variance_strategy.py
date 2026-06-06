from domain.strategies.base_strategy import BaseStrategy
from models.rebalance_problem import RebalanceProblem

import numpy as np

class MeanVarianceStrategy(BaseStrategy):
    """Mean-variance optimized strategy.

    Maximizes risk-adjusted return using the portfolio optimizer subject to
    constraints (vol cap, turnover, asset class limits). Optionally applies
    post-optimization vol targeting to scale weights toward a target volatility.
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
        
        optimized_weights = self.optimizer.optimize(
            self.rebalance_problem, active_signals, current_weights
        )

        if getattr(self.rebalance_problem, 'vol_target', None):
            return self._apply_vol_targeting(active_signals, optimized_weights)
        return optimized_weights
    
