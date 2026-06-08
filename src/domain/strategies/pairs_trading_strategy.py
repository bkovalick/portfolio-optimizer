from domain.strategies.base_strategy import BaseStrategy
from domain.signals.pairs_trading_signal import PairsTradingSignal
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
        
        pair_weights = self._run_pairs_strategy(
            current_weights, active_signal
        )
        return pair_weights

    def _run_pairs_strategy(self, 
                            current_weights: np.ndarray,
                            active_signal: PairsTradingSignal) -> np.ndarray:
        if type(active_signal) is not PairsTradingSignal:
            raise ValueError("Active signal must be of type PairsTradingSignal")

        tickers = self.rebalance_problem.initial_weights.keys()
        current_weights_dict = dict(zip(tickers, current_weights))
        pairs = active_signal.compute_trading_pairs(current_weights_dict)
        if len(pairs) == 0:
            return current_weights

        # pairs should be weights ( if exiting then both are 0, if new then nonzero)
        # pair should be ({'JPM': 0.1}, {'BAC': 0.1})
        # spread_vol -> raw_weights = 1 / spread_vol (per pair)
        # final_weights -> raw_weights / raw_weights.sum()

        for pair in pairs:
            print("hi")
            # a_stock = pair[0][0]
            # a_stock_weight = pair[0][0]
            # b_stock = pair[1]
            # a_stock_weight = pair[0][1]

            # if current_weights_dict[a_stock] == 0 and current_weights_dict[b_stock] == 0:
            #     pass # new position

            # if current_weights_dict[a_stock] > 0 and current_weights_dict[b_stock] > 0:
            #     pass # position exists but the signal says we must exit

        return np.ndarray()


