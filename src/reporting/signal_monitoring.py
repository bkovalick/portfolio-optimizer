import abc
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from scipy import stats
from models.monitoring_stats import MonitoringStats
        
class BaseSignalMonitor(abc.ABC):
    def analyze(self) -> MonitoringStats:
        ic_series = self._compute_ic_statistics()
        return MonitoringStats(
            ic_statistics=ic_series.to_dict(),
            ic_summary=self._compute_ic_summary(ic_series)
        )

    @abc.abstractmethod
    def _compute_ic_statistics(self): ...

    # @abc.abstractmethod
    def _compute_ic_summary(self, ic_series: pd.Series): 
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

class PairsICDiagnostics(BaseSignalMonitor):
    def __init__(self, 
                 pairs_cache: list):
        self.pairs_cache = pairs_cache
        # self.forward_spread = forward_spread
        # self.zscores = zscores
    
    def _ic_for_date(self, z_array, fwd_spread):
        z_score = -z_array
        common = z_score.index.intersection(fwd_spread.index)
        if len(common) < 5:
            return

        ic_ = spearmanr(z_score.loc[common], fwd_spread.loc[common])
        return ic_

    def _compute_ic_statistics(self): 
        # ic_values = []
        ic_values = [ (date, self._ic_for_date(self.zscores.loc[date], self.forward_spread.loc[date])) \
                     for date in self.zscores.index ]

        # for date in self.zscores.index:
        #     if date not in self.forward_spread.index:
        #         continue

        #     scores = self.zscores.loc[date]
        #     fwd_spread = self.forward_spread.loc[date]
        #     common = scores.index.intersection(fwd_spread.index)
        #     if len(common) < 5:
        #         continue

        #     ic_ = spearmanr(scores.loc[common], fwd_spread.loc[common])
        #     ic_values.append((date, ic_))

        if not ic_values:
            return pd.Series(dtype=float)
        
        dates, ics = zip(*ic_values)
        return pd.Series(ics, index=dates)

class LongOnlyICDiagnostics(BaseSignalMonitor):
    """Monitors signal decay by computing rolling Information Coefficient and half-life of those signals."""
    def __init__(self, 
                 forward_returns: pd.DataFrame,
                 signal: pd.DataFrame):
        self.forward_returns = forward_returns
        self.signal = signal

    def _compute_ic_statistics(self) -> pd.Series:
        """
        Computes the Spearman rank correlation (IC) between the signal and 
        forward returns for each date, then applies a rolling mean to smooth the series.
        """
        ic_values = []
        for date in self.signal.index:
            if date not in self.forward_returns.index:
                continue

            scores = self.signal.loc[date].dropna()
            fwd_returns = self.forward_returns.loc[date].dropna()
            common = scores.index.intersection(fwd_returns.index)
            if len(common) < 5:
                continue

            ic, _ = spearmanr(scores.loc[common], fwd_returns.loc[common])
            ic_values.append((date, ic))
    
        if not ic_values:
            return pd.Series(dtype=float)
        
        dates, ics = zip(*ic_values)
        return pd.Series(ics, index=dates)

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