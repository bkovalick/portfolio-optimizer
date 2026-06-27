import pandas as pd
import numpy as np

from domain.portfolio.portfolio import Portfolio
from models.backtest_result import BacktestResult
from models.rebalance_problem import RebalanceProblem
from models.market_config import MarketStoreConfig, MarketStateConfig

class PerformanceAnalyzer:
    """Computes performance metrics from backtest results."""
    def compute(self,
                rebalance_problem: RebalanceProblem,
                portfolio: Portfolio,
                market_store_config: MarketStoreConfig,
                market_state_config: MarketStateConfig,
                benchmark_index: pd.Series) -> BacktestResult:
        """ Build each piece of the backtest result """
        self._rebalance_problem = rebalance_problem
        self._portfolio = portfolio
        self._market_store_config = market_store_config
        self._market_state_config = market_state_config
        self._benchmark_index = benchmark_index
        self._annual_trading_days = market_state_config.annual_trading_days
        self._market_frequency = market_state_config.market_frequency
        self._rule = {"d": "B", "w": "W-FRI", "m": "ME"}[self._market_frequency]
        performance_metrics = self._calculate_performance_metrics(
            self._portfolio, self._market_store_config, self._benchmark_index
        )
        performance_series = self._build_performance_series(performance_metrics)
        summary = self._build_summary(performance_metrics)
        return BacktestResult(
            summary=summary,
            series=performance_series
        )
    
    @property
    def benchmark_returns(self):
        portfolio_returns = self._portfolio.returns
        if portfolio_returns is None or len(portfolio_returns) == 0:
            raise ValueError("Portfolio Returns must exist in order to reindex Benchmark")

        benchmark_resampled = self._benchmark_index.resample(self._rule).last()
        benchmark_returns = benchmark_resampled.pct_change(fill_method=None).fillna(0)
        return benchmark_returns.reindex(portfolio_returns.index).fillna(0)
    
    @property
    def benchmark_wealth_factors(self):
        if self.benchmark_returns is None or len(self.benchmark_returns) == 0:
            raise ValueError("Missing Benchmark Returns")
        
        wealth_factors = (1 + self.benchmark_returns).cumprod()
        return wealth_factors
    
    def _calculate_performance_metrics(self,
                                       portfolio: Portfolio,
                                       market_store_config: MarketStoreConfig,
                                       benchmark_index: pd.Series) -> dict:
        """Calculate performance metrics for the portfolio."""
        risk_free_rate = market_store_config.risk_free_rate
        portfolio_weights = portfolio.weights
        portfolio_trades = portfolio.weights.diff().abs().fillna(0)
        if isinstance(portfolio_trades, pd.DataFrame):
            portfolio_trades = portfolio_trades.sum(axis=1)

        portfolio_returns = portfolio.returns
        portfolio_turnover = portfolio.turnover
        benchmark_returns = self.benchmark_returns
        wealth_factors = (1 + portfolio_returns).cumprod()
        cumulative_returns = wealth_factors - 1
        num_periods = cumulative_returns.shape[0]
        years = num_periods / self._annual_trading_days
        annualized_return = wealth_factors.iloc[-1] ** (1 / years) - 1
        arithmetic_annualized_return = portfolio_returns.mean() * self._annual_trading_days
        annualized_volatility = portfolio_returns.std() * np.sqrt(self._annual_trading_days) 
        sharpe_ratio = (
            (arithmetic_annualized_return - risk_free_rate) / annualized_volatility
            if annualized_volatility != 0 else 0.0
        )

        if self._annual_trading_days > 0:
            drawdown_returns = cumulative_returns.iloc[self._annual_trading_days:]
            rolling_dd = self._calculate_rolling_drawdown(drawdown_returns, self._annual_trading_days)
            rolling_dd = align_series_to_dataframe(cumulative_returns.copy(), rolling_dd)
        else:
            drawdown_returns = cumulative_returns
            rolling_dd = self._calculate_rolling_drawdown(drawdown_returns, self._annual_trading_days)
            rolling_dd = align_series_to_dataframe(cumulative_returns.copy(), rolling_dd)

        max_drawdown = abs(self._calculate_max_drawdown(drawdown_returns))
        max_drawdown_days = self._calculate_max_drawdown_days(drawdown_returns)
        tracking_error = self._calculate_tracking_error(portfolio_returns, benchmark_returns)
        information_ratio = self._calculate_information_ratio(annualized_return, portfolio_returns, benchmark_returns)
        performance_metrics = {
            "portfolio_wealth_factors": wealth_factors,
            "portfolio_trades": portfolio_trades,
            "portfolio_weights": portfolio_weights,
            "portfolio_returns": portfolio_returns,
            "portfolio_turnover": portfolio_turnover,
            "cumulative_returns": cumulative_returns,
            "rolling_returns": self._calculate_rolling_returns(portfolio_returns, self._annual_trading_days),
            "rolling_volatility": self._calculate_rolling_volatility(portfolio_returns, self._annual_trading_days),
            "rolling_sharpe_ratio": self._calculate_rolling_sharpe_ratio(portfolio_returns, risk_free_rate, self._annual_trading_days),
            "rolling_drawdown": rolling_dd,
            "rolling_turnover": self._calculate_rolling_turnover(portfolio_turnover, self._annual_trading_days),
            "return": annualized_return,
            "volatility": annualized_volatility,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": self._calculate_sortino_ratio(arithmetic_annualized_return, portfolio_returns, risk_free_rate),
            "max_drawdown": max_drawdown,
            "max_drawdown_days": max_drawdown_days,
            "avg_drawdown": self._calculate_avg_drawdown(drawdown_returns),
            "turnover": portfolio_turnover.mean() * self._annual_trading_days,
            "alpha": self._calculate_alpha(portfolio_returns, self._annual_trading_days, benchmark_index),
            "calmar_ratio": annualized_return / max_drawdown if max_drawdown != 0 else 0.0,
            "tracking_error": tracking_error,
            "information_ratio": information_ratio,
            "win_rate": (portfolio_returns > 0).mean(),
            "loss_rate": (portfolio_returns < 0).mean(),
            "average_win": portfolio_returns[portfolio_returns > 0].mean() if (portfolio_returns > 0).any() else 0.0,
            "average_loss": portfolio_returns[portfolio_returns < 0].mean() if (portfolio_returns < 0).any() else 0.0,
            "skewness": portfolio_returns.skew(),
            "kurtosis": portfolio_returns.kurt(),
            "var_95": portfolio_returns.quantile(0.05),
            "var_97.5": portfolio_returns.quantile(0.025),
            "var_99": portfolio_returns.quantile(0.01),
            "cvar_95": portfolio_returns[portfolio_returns < portfolio_returns.quantile(0.05)].mean() if len(portfolio_returns) > 0 else 0.0,
            "cvar_97.5": portfolio_returns[portfolio_returns < portfolio_returns.quantile(0.025)].mean() if len(portfolio_returns) > 0 else 0.0,
            "cvar_99": portfolio_returns[portfolio_returns < portfolio_returns.quantile(0.01)].mean() if len(portfolio_returns) > 0 else 0.0,
            "alpha_decay": self._calculate_alpha(
                portfolio_returns[-self._annual_trading_days:],
                self._annual_trading_days,
                benchmark_index[-self._annual_trading_days:]
            ) if len(portfolio_returns) >= self._annual_trading_days else None
        }
        return performance_metrics
    
    def _calculate_sortino_ratio(self, annualized_return: float, portfolio_returns: pd.Series, risk_free_rate: float) -> float:
        """ Calculate Annualised Sortino ratio: excess return over rf divided by downside deviation. """
        downside_std = portfolio_returns[portfolio_returns < 0].std()
        if not pd.notna(downside_std) or downside_std == 0:
            return 0.0
        return (annualized_return - risk_free_rate) / (downside_std * np.sqrt(self._annual_trading_days))
    
    def _calculate_max_drawdown(self, cumulative_returns: pd.Series):
        """Calculate maximum drawdown from cumulative returns."""
        wealth = 1 + cumulative_returns
        running_max = wealth.cummax()
        drawdown = (wealth - running_max) / running_max
        return drawdown.min()

    def _calculate_max_drawdown_days(self, cumulative_returns: pd.Series) -> int:
        """Calculate the longest drawdown duration in periods (peak to recovery or end)."""
        running_max = cumulative_returns.cummax()
        is_underwater = (cumulative_returns < running_max).astype(int)
        not_underwater_cumsum = (1 - is_underwater).cumsum()
        max_streak = is_underwater.groupby(not_underwater_cumsum).sum().max()
        return int(max_streak) if not pd.isna(max_streak) else 0

    def _calculate_avg_drawdown(self, cumulative_returns: pd.Series) -> float:
        """Mean of all individual drawdown values at each point in time."""
        wealth = 1 + cumulative_returns
        running_max = wealth.cummax()
        drawdown = (wealth - running_max) / running_max
        negative_drawdowns = drawdown[drawdown < 0]
        if negative_drawdowns.empty:
            return 0.0
        result = float(negative_drawdowns.mean())
        return result if np.isfinite(result) else 0.0

    def _calculate_rolling_drawdown(self, cumulative: pd.Series, window: int):
        """Calculate rolling drawdown series over a specified window."""
        return cumulative.rolling(window, min_periods=1).apply(self._calculate_max_drawdown, raw=False)

    def _calculate_rolling_returns(self, returns: pd.Series, window: int):
        """Calculate rolling return over a specified window."""
        rolling_return = (1 + returns).rolling(window=window).apply(np.prod, raw=True) - 1
        return rolling_return

    def _calculate_rolling_volatility(self, returns: pd.Series, window: int):
        """Calculate rolling volatility over a specified window."""
        return returns.rolling(window=window).std() * np.sqrt(window)

    def _calculate_rolling_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float, window: int):
        """Calculate rolling Sharpe ratio over a specified window, annualised by annual_trading_days."""
        rf_per_period = risk_free_rate / self._annual_trading_days
        rolling_mean = returns.rolling(window=window).mean()
        rolling_std = returns.rolling(window=window).std()
        sharpe = ((rolling_mean - rf_per_period) / rolling_std) * np.sqrt(self._annual_trading_days)
        return sharpe.replace([np.inf, -np.inf], np.nan)

    def _calculate_rolling_turnover(self, turnover: pd.Series, window: int):
        """Calculate rolling annualised turnover over a specified window."""
        return turnover.rolling(window=window).mean() * self._annual_trading_days

    def _calculate_tracking_error(self, portfolio_returns, benchmark_returns):
        """Calculate tracking error as the annualised standard deviation of excess returns."""
        return (portfolio_returns - benchmark_returns).std() * np.sqrt(self._annual_trading_days)

    def _calculate_information_ratio(self, annualized_return: float, portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """Calculate Information Ratio: annualised active return divided by tracking error."""
        benchmark_annualized = (1 + benchmark_returns).prod() ** (self._annual_trading_days / len(benchmark_returns)) - 1
        active_return = annualized_return - benchmark_annualized
        tracking_error = self._calculate_tracking_error(portfolio_returns, benchmark_returns)
        if tracking_error == 0:
            return 0.0
        return active_return / tracking_error        

    def _calculate_alpha(self,
                         portfolio_returns: pd.Series,
                         annualization_factor: int, 
                         benchmark_returns: pd.Series):
        """Calculate alpha of the portfolio against a benchmark."""
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join='inner')
        aligned.columns = ['portfolio', 'benchmark']

        portfolio_annualized = (1 + aligned['portfolio']).prod() ** (annualization_factor / len(aligned)) - 1
        benchmark_annualized = (1 + aligned['benchmark']).prod() ** (annualization_factor / len(aligned)) - 1
        return portfolio_annualized - benchmark_annualized

    def _build_performance_series(self, performance_metrics: dict) -> dict:
        """Create performance series dictionary for BacktestResult dataclass."""
        if performance_metrics is None:
            return {}
        
        try:
            _w = performance_metrics["portfolio_weights"]
            port_weights_long = pd.DataFrame({
                "Date": np.repeat(_w.index, len(_w.columns)),
                "Ticker": np.tile(_w.columns, len(_w.index)),
                "Weight": _w.values.ravel(),
            })
        except MemoryError:
            port_weights_long = pd.DataFrame(columns=["Date", "Ticker", "Weight"])
        return {
            "benchmark_wealth_factors": self.benchmark_wealth_factors,
            "benchmark_returns": self.benchmark_returns,            
            "portfolio_wealth_factors": performance_metrics["portfolio_wealth_factors"],
            "portfolio_trades": performance_metrics["portfolio_trades"],
            "portfolio_weights": performance_metrics["portfolio_weights"],
            "portfolio_weights_long": port_weights_long,
            "portfolio_returns": performance_metrics["portfolio_returns"],
            "portfolio_turnover": performance_metrics["portfolio_turnover"],
            "cumulative_returns": performance_metrics["cumulative_returns"],
            "rolling_returns": performance_metrics["rolling_returns"],
            "rolling_volatility": performance_metrics["rolling_volatility"],
            "rolling_sharpe_ratio": performance_metrics["rolling_sharpe_ratio"],
            "rolling_drawdown": performance_metrics["rolling_drawdown"],
            "rolling_turnover": performance_metrics["rolling_turnover"]
        }

    def _build_summary(self, performance_metrics) -> dict:
        """Create summary dictionary for BacktestResult dataclass."""
        if performance_metrics is None:
            return {}
        
        return {
            "return": performance_metrics["return"],
            "volatility": performance_metrics["volatility"],
            "sharpe_ratio": performance_metrics["sharpe_ratio"],
            "sortino_ratio": performance_metrics["sortino_ratio"],
            "max_drawdown": performance_metrics["max_drawdown"],
            "avg_drawdown": performance_metrics["avg_drawdown"],
            "max_drawdown_duration": performance_metrics["max_drawdown_days"],
            "turnover": performance_metrics["turnover"],
            "alpha": performance_metrics["alpha"],
            "calmar_ratio": performance_metrics["calmar_ratio"],
            "tracking_error": performance_metrics["tracking_error"],
            "information_ratio": performance_metrics["information_ratio"],
            "win_rate": performance_metrics["win_rate"],
            "loss_rate": performance_metrics["loss_rate"],
            "average_win": performance_metrics["average_win"],
            "average_loss": performance_metrics["average_loss"],
            "skewness": performance_metrics["skewness"],
            "kurtosis": performance_metrics["kurtosis"],
            "var_95": performance_metrics["var_95"],
            "var_97.5": performance_metrics["var_97.5"],
            "var_99": performance_metrics["var_99"],
            "cvar_95": performance_metrics["cvar_95"],
            "cvar_97.5": performance_metrics["cvar_97.5"],
            "cvar_99": performance_metrics["cvar_99"],
            "alpha_decay": performance_metrics["alpha_decay"]
        }


def align_series_to_dataframe(df: pd.DataFrame, series: pd.Series) -> pd.Series:
    n = len(df) - len(series)
    nan_part = pd.Series([np.nan] * n, index=df.index[:n])
    aligned = pd.concat([nan_part, series])
    aligned = aligned.reindex(df.index)
    return aligned
