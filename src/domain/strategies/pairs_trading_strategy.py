from domain.strategies.base_strategy import BaseStrategy
from models.rebalance_problem import RebalanceProblem

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

class PairsTradingStrategy(BaseStrategy):
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer=None):
        super().__init__(rebalance_problem, optimizer)

        # self.pairs_lookback_horizon = rebalance_problem.pairs_lookback_horizon
        self.pairs_lookback_horizon = 20
        self.pairs_zentry = 2
        self.pairs_zexit = 1

    def rebalance(self, 
                  signals: dict, 
                  current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        signal_key = self.rebalance_problem.signal_source
        active_signal = signals.get(signal_key)

        if active_signal is None:
            return current_weights
        
        optimized = self.optimizer.optimize(
            self.rebalance_problem,
            active_signal,
            current_weights 
        )

        # I think we can still have a signals class do most of the work but there might still be value in a separate strategy class
        
        self.run_pairs_strategy()
        return optimized

    # this becomes a signal, systematic strategy class is used instead this is just a mockup
    def _hedge_ratio(self, spread_a, spread_b):
        """Regress B to A"""
        return np.polyfit(spread_b, spread_a, 1)[0]
    
    def _compute_spread(self, spread_a, spread_b):
        """Calculate the relationship between the two assets to understand what a "normal" price gap looks like"""
        beta = self._hedge_ratio(spread_a, spread_b)
        return spread_a - beta * spread_b 

    def _compute_zscore(self, spread: pd.Series):
        """ 
        Transform the raw dollar spread into a standardized Z-score.
        """
        mean = spread.rolling(self.pairs_lookback_horizon).mean()
        std = spread.rolling(self.pairs_lookback_horizon).std()
        return (spread - mean) / std
    
    def _determine_pairs(self, active_signal):
        # group by sector first, must enrich data with gics sector
        prices = active_signal.lookback_prices()
        pairs = []
        sectors = []
        for sector in sectors:
            # look these up by sector
            log_ret = np.log(prices).diff()
            correlation_matrix = log_ret.corr()
            candidates = [ (i, j) for i, j in zip(*np.where(correlation_matrix > 0.70)) if i < j]
            for pair_a, pair_b in candidates:
                pvalue = coint(prices[pair_a], prices[pair_b])
                if pvalue < 0.05:
                    pairs.append((pair_a, pair_b, pvalue))        

    def run_pairs_strategy(self, active_signal):
        prices = active_signal.lookback_prices()
        pairs = self._determine_pairs(active_signal)

        for pair in pairs:
            spread = self._compute_spread(prices[pair[0]], prices[pair[1]])
            zscore = self._compute_zscore(spread)
            self._calculate_trading_decision(zscore)

    def _calculate_trading_decision(self, zscore):
        pass
        # if Z = -2 then we Long stock A and Short stock B (Stock A is unsustainably cheap relative to Stock B; the spread will likely rise.)
        # if Z = 2 then we Short Stock A and Long Stock B (Stock A is unsustainably expensive relative to Stock B; the spread will likely fall)
        # if Z = 0 then we close both positions to realize profit.
        # if abs(Z) > 3.5 then we exit as the spread has become unsustainable. We eat the loss essentially
        # if z < -self.entry: go long
        # elif z > self.entry: go short
        # elif abs(z) < self.exit: exit
        # else: hold


