from models.signals_config import SignalsConfig
from models.pairs_trading_config import PairsTradingConfig
from simulation.market_state import MarketState
from domain.signals.risk_return_signals import RiskReturnSignals

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

class PairsTradingSignal(RiskReturnSignals):
    def __init__(self,
                 market_state: MarketState, 
                 signals_config: SignalsConfig,
                 pairs_trading_config: PairsTradingConfig):
        super().__init__(market_state, signals_config)
        self.pairs_trading_config = pairs_trading_config
        self.pairs_lookback_horizon = pairs_trading_config.pairs_lookback_horizon
        self.cointegration_threshold = pairs_trading_config.cointegration_threshold
        self.pairs_entry = pairs_trading_config.pairs_entry
        self.pairs_exit = pairs_trading_config.pairs_exit

    def mean_returns(self)-> np.ndarray:
        if self.pairs_trading_config is None:
            return super().mean_returns()
        
        return self._compute_pairs_signals()

    def _compute_pairs_signals(self) -> np.ndarray:
        prices = self.lookback_prices()
        pairs = self._determine_pairs(prices)

        for pair in pairs:
            spread = self._compute_spread(prices[pair[0]], prices[pair[1]])
            zscore = self._compute_zscore(spread)
            self._calculate_trading_decision(zscore)
        
        return np.ndarray()
    
    def _hedge_ratio(self, spread_a, spread_b):
        """Regress B to A"""
        return np.polyfit(spread_b, spread_a, 1)[0]
    
    def _compute_spread(self, spread_a, spread_b):
        """
        Calculate the relationship between the two assets to understand 
        what a "normal" price gap looks like
        """
        beta = self._hedge_ratio(spread_a, spread_b)
        return spread_a - beta * spread_b 

    def _compute_zscore(self, spread: pd.Series):
        """ 
        Transform the raw dollar spread into a standardized Z-score.
        """
        mean = spread.rolling(self.pairs_lookback_horizon).mean()
        std = spread.rolling(self.pairs_lookback_horizon).std()
        return (spread - mean) / std
    
    def _determine_pairs(self, prices: pd.DataFrame) -> list:
        """
        Identify pairs of assets that are historically correlated and cointegrated, 
        ideally within the same sector.
        """
        sectors_to_tickers = self.market_state.sectors_to_tickers

        pairs = []
        for sector, tickers in sectors_to_tickers.items():
            if len(tickers) < 2:
                continue
            px_with_sector = prices[tickers]
            log_ret = np.log(px_with_sector).diff()
            correlation_matrix = log_ret.corr()
            candidates = [(tickers[i], tickers[j]) for i, j in \
                          zip(*np.where(correlation_matrix > self.cointegration_threshold)) if i < j]
            for pair_a, pair_b in candidates:
                pvalue = coint(prices[pair_a], prices[pair_b])[1]
                if pvalue < 0.05:
                    pairs.append((pair_a, pair_b, pvalue))
        return pairs

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