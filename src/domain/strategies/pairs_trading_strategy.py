from domain.strategies.base_strategy import BaseStrategy
from domain.signals.pairs_trading_signal import PairsTradingSignal
from models.rebalance_problem import RebalanceProblem

import numpy as np

class PairsTradingStrategy(BaseStrategy):
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        super().__init__(rebalance_problem, optimizer)
        self.pairs_cache = []

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

        active_pairs = active_signal.compute_trading_pairs(current_weights_dict)
        if active_pairs.empty:
            return current_weights


        new_weights = {ticker: 0.0 for ticker in tickers}
        for pair in active_pairs.itertuples():
            hedge_ratio = pair.HedgeRatio
            if pair.State in {"EnterShort", "HoldShort"}:
                asset_a_wght = -pair.FinalWeight
                asset_b_wght = pair.FinalWeight * hedge_ratio
            elif pair.State in {"EnterLong", "HoldLong"}:
                asset_a_wght = pair.FinalWeight
                asset_b_wght = -pair.FinalWeight * hedge_ratio
            else:
                continue

            new_weights[pair.AssetA] += asset_a_wght
            new_weights[pair.AssetB] += asset_b_wght

            self.pairs_cache.append(pair)

        if sum(new_weights.values()) == 0:
            return current_weights
        return np.array(list(new_weights.values())) 