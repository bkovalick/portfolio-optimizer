from typing import List, Optional

import pandas as pd
import numpy as np
import warnings

from utils.lookback_windows import LOOKBACK_WINDOWS
from simulation.market_state import MarketState

class FeatureBuilder:
    """
    Responsible for constructing features and forward 
    returns for ML model training and inference.
    """
    def __init__(self, 
                 market_state: MarketState,
                 benchmark: pd.Series,
                 market_frequency: str = "d",
                 features: Optional[List[str]] = None):
        features = features or []
        self.features = features
        self.prices = market_state.signal_prices.copy()
        self.returns = market_state.signal_returns.copy()
        self.exogenous_universe = market_state.exogenous_universe.copy()
        self.benchmark = benchmark.copy()
        self.benchmark_returns = benchmark.pct_change(fill_method=None).fillna(0)
        self.lookbacks = LOOKBACK_WINDOWS.get(market_frequency, LOOKBACK_WINDOWS["d"])
        self.reversal_window = self.lookbacks.get("1w", 1)
        self.features_cache = None
        self.forward_returns_cache = None
        self.precomputed_horizon = None

    def precompute(self, horizon: int = 21):
        """
        Precompute features for all dates and cache them in memory for
        fast retrieval during training/inference.

        All rolling computations are vectorized over the full history first
        (one O(T) pass each), then a single O(T) loop assembles per-date
        feature matrices — avoiding the O(T²) cost of growing .loc[:date]
        slices inside the loop.
        """
        self.precomputed_horizon = horizon
        w = self.lookbacks
        px = self.prices
        rets = self.returns
        mret = self.benchmark_returns.reindex(rets.index).fillna(0)
        
        # vectorized rolling features
        mom_1m = px / px.shift(w["1m"]) - 1
        mom_12m = px.shift(w["1m"]) / px.shift(w["1y"]) - 1
        vol_1m = rets.rolling(w["1m"]).std()
        vol_3m = rets.rolling(w["3m"]).std()
        reversal = -(px / px.shift(self.reversal_window) - 1)
        max_ret = rets.rolling(w["1m"]).max()
        high_52w = px / px.rolling(w["1y"]).max()
        
        market_var_1m = mret.rolling(w["1m"]).var()
        market_var_1y = mret.rolling(w["1y"]).var()
        beta_1m = rets.rolling(w["1m"]).cov(mret).div(market_var_1m.replace(0, np.nan), axis=0)
        beta_1y = rets.rolling(w["1y"]).cov(mret).div(market_var_1y.replace(0, np.nan), axis=0)
        idiosyncratic_vol = (rets - beta_1y.multiply(mret, axis=0)).rolling(w["1y"]).std()

        if "^VIX" in self.exogenous_universe.columns:
            vix = self.exogenous_universe["^VIX"].reindex(px.index).ffill()
            high_vol_series = (vix > vix.rolling(w["1y"]).median()).astype(float)
        else:
            high_vol_series = pd.Series(0.0, index=px.index)

        # forward returns
        fwd_returns_cache = {}
        for i in range(len(px) - horizon):
            fwd = px.iloc[i + horizon] / px.iloc[i] - 1
            if not fwd.empty:
                fwd_returns_cache[px.index[i]] = fwd

        # assemble per-date feature matrices
        features_cache = {}
        for date in px.index[w["1y"]:]:
            hv = float(high_vol_series.get(date, 0.0))
            feat = pd.DataFrame({
                "mom_1m": mom_1m.loc[date],
                "mom_12m": mom_12m.loc[date],
                "vol_1m":  vol_1m.loc[date],
                "vol_3m":  vol_3m.loc[date],
                "reversal": reversal.loc[date],
                "mom_x_vol_regime": mom_12m.loc[date] * (1 - hv),
                "reversal_x_vol_regime": reversal.loc[date] * hv,
                "max_return": max_ret.loc[date],
                "high_52w": high_52w.loc[date],
                "beta_1m": beta_1m.loc[date],
                "beta_1y": beta_1y.loc[date],
                "idiosyncratic_vol": idiosyncratic_vol.loc[date]
            })
            feat = feat.rank(axis=0, pct=True).dropna()
            if not feat.empty:
                feat = feat[self.features]
                features_cache[date] = feat

        self.features_cache = features_cache
        self.forward_returns_cache = fwd_returns_cache

    def build(self, date: pd.Timestamp) -> pd.DataFrame:
        """
        Build feature matrix for all assets as of a single date, 
        using cached values if available.
        """
        if self.features_cache is None:
            warnings.warn("FeatureBuilder.precompute() has not been called. Falling back to _build_single_date() which is significantly slower.")
        if self.features_cache is not None:
            return self.features_cache.get(date, pd.DataFrame(index=self.prices.columns))
        return self._build_single_date(date)    

    def _build_single_date(self, date: pd.Timestamp) -> pd.DataFrame:
        """
        Build feature matrix for all assets as of a single date.
        Returns DataFrame of shape (n_assets, n_features), index=tickers.
        No future data is used — all lookbacks are strictly backward-looking.
        """
        px   = self.prices.loc[:date]
        rets = self.returns.loc[:date]
        market_rets = self.benchmark_returns.reindex(rets.index).fillna(0)
        vix_prices = self.exogenous_universe["^VIX"].loc[:date] \
            if "^VIX" in self.exogenous_universe else pd.Series(dtype=float)
        high_vol = self._compute_high_vol(vix_prices)

        if len(px) < self.lookbacks["1y"]:
            return pd.DataFrame(index=self.prices.columns)

        features = pd.DataFrame(index=self.prices.columns)
        features["mom_1m"] = px.iloc[-1] / px.iloc[-self.lookbacks["1m"]] - 1
        features["mom_12m"] = px.iloc[-self.lookbacks["1m"]] / px.iloc[-self.lookbacks["1y"]] - 1
        features["vol_1m"] = rets.iloc[-self.lookbacks["1m"]:].std()
        features["vol_3m"] = rets.iloc[-self.lookbacks["3m"]:].std()
        features["reversal"] = -(px.iloc[-1] / px.iloc[-(self.reversal_window + 1)] - 1)
        features["mom_x_vol_regime"] = features["mom_12m"] * (1 - high_vol)
        features["reversal_x_vol_regime"] = features["reversal"] * high_vol
        features["max_return"] = rets.iloc[-self.lookbacks["1m"]:].max()
        features["high_52w"] = px.iloc[-1] / px.iloc[-self.lookbacks["1y"]:].max()
        features["beta_1m"] = self._compute_rolling_beta(rets, market_rets, self.lookbacks["1m"])
        beta_1y = self._compute_rolling_beta(rets, market_rets, self.lookbacks["1y"])
        features["beta_1y"] = beta_1y
        predicted = beta_1y.values * market_rets.iloc[-self.lookbacks["1y"]:].values[:, None]
        residuals = rets.iloc[-self.lookbacks["1y"]:].values - predicted
        features["idiosyncratic_vol"] = pd.Series(residuals.std(axis=0), index=rets.columns)
        features = features.rank(axis=0, pct=True)
        return features.dropna()
    
    def build_forward_returns(self,
                              as_of_date: pd.Timestamp,
                              horizon: int = 21) -> pd.Series:
        """
        Build forward returns for all assets starting from as_of_date 
        over `horizon` days, using cached values if available.
        """
        if self.forward_returns_cache is not None and horizon == self.precomputed_horizon:
            return self.forward_returns_cache.get(as_of_date, pd.Series(dtype=float))
        return self._build_forward_returns_single(as_of_date, horizon)

    def _build_forward_returns_single(self,
                              as_of_date: pd.Timestamp,
                              horizon: int = 21) -> pd.Series:
        """
        Forward returns starting from as_of_date over `horizon` days.
        Used as the label (y) during training.
        """
        px = self.prices
        idx = px.index.get_loc(as_of_date)
        if idx + horizon >= len(px):
            return pd.Series(dtype=float)
        fwd = px.iloc[idx + horizon] / px.iloc[idx] - 1
        return fwd
    
    def _compute_high_vol(self, vix_prices: pd.Series) -> float:
        if vix_prices.empty:
            return 0.0
        vix_now = vix_prices.iloc[-1]
        vix_median = vix_prices.iloc[-self.lookbacks["1y"]:].median()
        high_vol = (vix_now > vix_median).astype(float)
        return high_vol

    def _compute_rolling_beta(self, 
                              stock_returns: pd.DataFrame, 
                              market_returns: pd.Series, 
                              window: int = 21) -> pd.Series:
        """ Compute rolling beta of each stock to the market over the specified window. """
        cov_with_market = stock_returns.iloc[-window:].apply(
            lambda col: col.cov(market_returns.iloc[-window:])
        )

        market_variance = market_returns.iloc[-window:].var()

        if market_variance == 0:
            return pd.Series(np.nan, index=stock_returns.columns)
        
        return cov_with_market / market_variance