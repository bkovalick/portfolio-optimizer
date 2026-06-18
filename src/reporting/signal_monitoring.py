import abc
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from scipy import stats

from models.monitoring_stats import MonitoringStats
        
class BaseSignalMonitor(abc.ABC):

    def __init__(self, 
                 forward_data: pd.DataFrame, 
                 scores: pd.DataFrame):
        self.scores = scores
        self.forward_data = forward_data

    def analyze(self) -> MonitoringStats:
        ic_sp_series = self._compute_ic_statistics()
        return MonitoringStats(
            ic_statistics={"spearman": ic_sp_series.to_dict()},
            ic_summary=self._compute_ic_summary(ic_sp_series)
        )

    def _compute_ic_statistics(self) -> pd.Series:
        """
        Computes the Spearman rank correlation (IC) between the signal and 
        forward returns for each date, then applies a rolling mean to smooth the series.
        """
        ic_sp_values = []
        for date in self.scores.index:
            if date not in self.forward_data.index:
                continue
            
            scores = self.scores.loc[date].dropna()
            fwd_data = self.forward_data.loc[date].dropna()
            common = scores.index.intersection(fwd_data.index)
            if len(common) < 5:
                continue

            ic_sp, _ = spearmanr(scores.loc[common], fwd_data.loc[common])
            ic_sp_values.append((date, float(ic_sp)))

        if not ic_sp_values:
            return pd.Series(dtype=float)

        dates, ics_spear = zip(*ic_sp_values)
        return pd.Series(ics_spear, index=dates)

    def _compute_ic_summary(self, ic_series: pd.Series) -> dict:
        """
        Perform a one-sample t-test to determine if the mean IC is significantly different from zero.
        Returns the t-statistic and p-value.
        """
        if len(ic_series.dropna()) < 2:
            return {"t_statistic": np.nan, "p_value": np.nan}
        t_stat, p_value = stats.ttest_1samp(ic_series.dropna(), 0)
        ic_std = ic_series.std()
        ic_ir = ic_series.mean() / ic_std if ic_std > 0 else np.nan
        return {
            "mean_ic": ic_series.mean(),
            "ic_ir": ic_ir,
            "hit_rate": float((ic_series > 0).mean()),
            "t_statistic": t_stat, 
            "p_value": p_value,
            "half_life": self._compute_half_life(ic_series),
            "n_observations": len(ic_series.dropna())
        }
    
    def _compute_half_life(self, ic_series: pd.Series) -> float:
        """
        Estimate the signal decay half-life from signals using AR(1) autocorrelation.

        Fits a first-order autoregressive model and solves for the number of periods
        it takes for the autocorrelation to decay to half its initial value.
        Returns np.nan when phi is outside (0, 1), i.e. the series is non-stationary,
        mean-reverting with no persistence, or negatively autocorrelated.
        """
        phi = ic_series.autocorr(lag=1)

        if phi <= 0 or phi >= 1:
            return np.nan

        half_life = np.log(0.5) / np.log(phi)
        return half_life

class PairsICDiagnostics(BaseSignalMonitor):
    def __init__(self, 
                 pairs_cache: pd.DataFrame):
        super().__init__(forward_data=None, scores=None)
    #     self.pairs_cache = pairs_cache.copy()
    #     self.pairs_cache["FwdReturn"] = self.pairs_cache.groupby("Pair")["RealizedReturn"].shift(-1)

    # def _compute_ic_statistics(self) -> pd.Series:
    #     """
    #     Computes the Spearman rank correlation (IC) between the signal and 
    #     forward returns for each date, then applies a rolling mean to smooth the series.
    #     """
    #     clean = (
    #         self.pairs_cache[["Zscore", "FwdReturn"]]
    #         .replace([np.inf, -np.inf], np.nan)
    #         .dropna()
    #     )
    #     ic_sp, pval = spearmanr(-clean["Zscore"], clean["FwdReturn"])
    #     return pd.Series(ic_sp, dtype=float)
    
class LongOnlyICDiagnostics(BaseSignalMonitor):
    """Monitors signal decay by computing rolling Information Coefficient and half-life of those signals."""
    def __init__(self, 
                 forward_returns: pd.DataFrame,
                 signal: pd.DataFrame):
        super().__init__(forward_returns, signal)