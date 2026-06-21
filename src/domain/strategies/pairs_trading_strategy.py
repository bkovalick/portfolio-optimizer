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
        if not isinstance(active_signal, PairsTradingSignal):
            raise ValueError("Active signal must be of type PairsTradingSignal")

        tickers = self.rebalance_problem.initial_weights.keys()
        current_weights_dict = dict(zip(tickers, current_weights))

        active_pairs = active_signal.compute_trading_pairs(current_weights_dict)
        if active_pairs.empty:
            return current_weights

        new_weights = {ticker: 0.0 for ticker in tickers}
        active = active_pairs[active_pairs["State"].isin({"EnterShort", "HoldShort", "EnterLong", "HoldLong"})].copy()

        sign = np.where(active["State"].isin({"EnterShort", "HoldShort"}), -1.0, 1.0)
        active["WeightA"] = sign * active["FinalWeight"]
        active["WeightB"] = -sign * active["FinalWeight"] * active["HedgeRatio"]

        weight_a = active.groupby("AssetA")["WeightA"].sum()
        weight_b = active.groupby("AssetB")["WeightB"].sum()
        for ticker, w in weight_a.add(weight_b, fill_value=0).items():
            if ticker in new_weights:
                new_weights[ticker] = w

        self.pairs_cache.extend(active.itertuples())

        if sum(new_weights.values()) == 0:
            return current_weights
        return np.array(list(new_weights.values())) 