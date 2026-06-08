from models.pairs_trading_config import PairsTradingConfig
from simulation.market_state import MarketState

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

class PairsTradingSignal:
    def __init__(self,
                 market_state: MarketState,
                 pairs_trading_config: PairsTradingConfig):
        self.market_state = market_state
        self.prices = self.market_state.lookback_prices()
        self.sectors_to_tickers = self.market_state.sectors_to_tickers        
        self.pairs_trading_config = pairs_trading_config
        self.pairs_lookback_horizon = pairs_trading_config.pairs_lookback_horizon
        self.cointegration_threshold = pairs_trading_config.cointegration_threshold
        self.correlation_filter = pairs_trading_config.correlation_filter
        self.pairs_entry = pairs_trading_config.pairs_entry
        self.pairs_exit = pairs_trading_config.pairs_exit
        self.pairs_stop_loss = pairs_trading_config.pairs_stop_loss

    def compute_trading_pairs(self, current_weights_dict: dict) -> pd.DataFrame:
        """
           Identify pairs of assets that are historically correlated and cointegrated, 
           build portfolio weights based on the signal and return those weights 
        """
        pairs = self._determine_pairs(self.prices)
        active_pairs = []
        for pair in pairs:
            hedge_ratio = self._hedge_ratio(self.prices[pair[0]], self.prices[pair[1]])
            spread = self._compute_spread(self.prices[pair[0]], self.prices[pair[1]], hedge_ratio)
            spread_vol = spread.diff().rolling(self.pairs_lookback_horizon).std()
            zscores = self._compute_zscores(spread)
            state = self._determine_state(pair, zscores.iloc[-1], current_weights_dict)
            active_pairs.append(
                {
                    "pair": pair,
                    "hedge_ratio": hedge_ratio,
                    "spread": spread,
                    "spread_vol": spread_vol,
                    "zscore": zscores.iloc[-1],
                    "state": state
                }
            )
    
        return pd.DataFrame(active_pairs)

    def _hedge_ratio(self, spread_a: pd.Series, spread_b: pd.Series) -> float:
        """Regress B to A"""
        return np.polyfit(spread_b, spread_a, 1)[0]
    
    def _compute_spread(self, 
                        spread_a: pd.Series, 
                        spread_b: pd.Series,
                        beta: float) -> pd.Series:
        """
        Calculate the relationship between the two assets to understand 
        what a "normal" price gap looks like
        """
        return spread_a - beta * spread_b 

    def _compute_zscores(self, spread: pd.Series) -> pd.Series:
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
        pairs = []
        for sector, tickers in self.sectors_to_tickers.items():
            if len(tickers) < 2:
                continue
            px_with_sector = prices[tickers]
            log_ret = np.log(px_with_sector).diff().dropna(how="all")
            correlation_matrix = log_ret.corr()
            candidates = [(tickers[i], tickers[j]) for i, j in \
                          zip(*np.where(correlation_matrix > self.correlation_filter)) if i < j]
            for pair_a, pair_b in candidates:
                pvalue = coint(prices[pair_a], prices[pair_b])[1]
                if pvalue < self.cointegration_threshold:
                    pairs.append((pair_a, pair_b, pvalue))
        return pairs

    def _determine_state(self, 
                         pair: tuple, 
                         zscore: float, 
                         cw_dict: dict) -> str:
        # if existing position test if converged or not converging. Exit if one of those is happening otherwise do nothing
        if pair[0] in cw_dict and pair[1] in cw_dict:
            if abs(zscore) < self.pairs_exit:
                return "Exit"
            elif abs(zscore) < self.pairs_stop_loss:
                return "Exit"
            else:
                return "Hold"

        if zscore < -self.pairs_entry:
            return "LongSpread"
            # print("long stock a and short stock b")
        elif zscore > self.pairs_entry:
            return "ShortSpread"
            # print("short stock a and long stock b")

        # if zscore < -self.pairs_entry:
        #     print("long stock a and short stock b")
        # elif zscore > self.pairs_entry:
        #     print("short stock a and long stock b")
        # elif abs(zscore) < self.pairs_exit: # exit for profit
        #     print("mean has converged, close position down to realize profit")
        # elif abs(zscore) < self.pairs_stop_loss: # stop loss, exit at loss
        #     print("mean has not converged, close position down and accept loss")
