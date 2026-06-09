import abc
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from scipy import stats
from models.monitoring_stats import MonitoringStats

class BaseSignalMonitor(abc.ABC):

    @property
    @abc.abstractmethod
    def _scores(self) -> pd.DataFrame: ...

    @property
    @abc.abstractmethod
    def _forward_data(self) -> pd.DataFrame: ...

    def analyze(self) -> MonitoringStats:
        ic_series = self._compute_ic_statistics()
        return MonitoringStats(
            ic_statistics=ic_series.to_dict(),
            ic_summary=self._compute_ic_summary(ic_series)
        )

    def _compute_ic_statistics(self) -> pd.Series:
        ic_values = []
        for date in self._scores.index:
            if date not in self._forward_data.index:
                continue

            scores = self._scores.loc[date].dropna()
            fwd = self._forward_data.loc[date].dropna()
            common = scores.index.intersection(fwd.index)
            if len(common) < 5:
                continue

            ic, _ = spearmanr(scores.loc[common], fwd.loc[common])
            ic_values.append((date, ic))

        if not ic_values:
            return pd.Series(dtype=float)

        dates, ics = zip(*ic_values)
        return pd.Series(ics, index=dates)

    def _compute_ic_summary(self, ic_series: pd.Series) -> dict:
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
        phi = ic_series.autocorr(lag=1)
        if phi <= 0 or phi >= 1:
            return np.nan
        return np.log(0.5) / np.log(phi)

class LongOnlyICDiagnostics(BaseSignalMonitor):
    def __init__(self,
                 forward_returns: pd.DataFrame,
                 signal: pd.DataFrame):
        self.forward_returns = forward_returns
        self.signal = signal

    @property
    def _scores(self) -> pd.DataFrame:
        return self.signal

    @property
    def _forward_data(self) -> pd.DataFrame:
        return self.forward_returns

class PairsICDiagnostics(BaseSignalMonitor):
    def __init__(self,
                 pairs_cache: pd.DataFrame):
        self.pairs_cache = pairs_cache
        self.forward_spread = pd.DataFrame()
        self.zscores = pd.DataFrame()

    @property
    def _scores(self) -> pd.DataFrame:
        return -self.zscores

    @property
    def _forward_data(self) -> pd.DataFrame:
        return self.forward_spread