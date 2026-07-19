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
        self.existing_pairs = None

    def get_diagnostics(self) -> dict:
        return {"pairs_cache": self.pairs_cache}

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

        tickers = list(self.rebalance_problem.initial_weights.keys())
        active_pairs = active_signal.compute_trading_pairs(dict(zip(tickers, current_weights)), self.existing_pairs)
        if active_pairs.empty:
            return current_weights

        active = active_pairs[active_pairs["State"].isin({"EnterShort", "HoldShort", "EnterLong", "HoldLong"})].copy()
        sign = np.where(active["State"].isin({"EnterShort", "HoldShort"}), -1.0, 1.0)
        denom = 1.0 + active["HedgeRatio"].abs()
        active["WeightA"] = (sign * active["FinalWeight"]) / denom
        active["WeightB"] = (-sign * active["FinalWeight"] * active["HedgeRatio"]) / denom

        combined = active.groupby("AssetA")["WeightA"].sum().add(
            active.groupby("AssetB")["WeightB"].sum(), fill_value=0
        )
        new_weights = {t: combined.get(t, 0.0) for t in tickers}

        self.pairs_cache.extend(active.itertuples())
        self.existing_pairs = list(zip(active_pairs["AssetA"], active_pairs["AssetB"]))
        updated_weights = current_weights if sum(new_weights.values()) == 0 else np.array(list(new_weights.values())) 
        return updated_weights