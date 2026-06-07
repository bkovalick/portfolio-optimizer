from domain.strategies.base_strategy import BaseStrategy
from models.rebalance_problem import RebalanceProblem

import numpy as np

class PairsTradingStrategy(BaseStrategy):
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, 
                  signals: dict, 
                  current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        signal_key = self.rebalance_problem.signal_source
        active_signal = signals.get(signal_key)

        if active_signal is None:
            return current_weights 
        
        # I think we can still have a signals class do most of the work but there might still be value in a separate strategy class
        # current_weights = self._run_pairs_strategy()
        
        optimized = self.optimizer.optimize(
            self.rebalance_problem,
            active_signal,
            current_weights 
        )

        return optimized

    def _run_pairs_strategy(self):
        pass


