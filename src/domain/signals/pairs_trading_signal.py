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
                    "AssetA": pair[0],
                    "AssetB": pair[1],
                    "HedgeRatio": hedge_ratio,
                    "Spread": spread.iloc[-1],
                    "SpreadVol": spread_vol.iloc[-1],
                    "Zscore": zscores.iloc[-1],
                    "State": state,
                    "RawWeight": 1 / spread_vol.iloc[-1] if spread_vol.iloc[-1] > 0 else 0
                }
            )
    
        active_pairs_df = pd.DataFrame(active_pairs)
        if active_pairs_df.empty:
            return active_pairs_df
        
        active_pairs_df["FinalWeight"] = active_pairs_df["RawWeight"] / active_pairs_df["RawWeight"].sum()
        active_pairs_df.index = [self.market_state.current_date()] * len(active_pairs_df)
        return active_pairs_df

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
        """
        Determine whether to enter a long or short position on the pair, 
        or exit an existing position, based on the current Z-score and existing weights.
        """
        a_stock = pair[0]
        b_stock = pair[1]

        in_position = (a_stock in cw_dict and cw_dict[a_stock] != 0) and \
                      (b_stock in cw_dict and cw_dict[b_stock] != 0)
        if in_position:
            if abs(zscore) < self.pairs_exit or abs(zscore) > self.pairs_stop_loss:
                return "Exit"
        
            if cw_dict[a_stock] > 0:
                return "HoldLong"
            else:
                return "HoldShort"
        
        if zscore < -self.pairs_entry:
            return "EnterLong"
        elif zscore > self.pairs_entry:
            return "EnterShort"
        else:
            return "Flat"