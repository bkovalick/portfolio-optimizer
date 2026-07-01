# Quant-Research-Platform

## Overview

Experiment-driven research platform for systematic strategy development and evaluation across asset classes — multi-strategy backtesting, ML-based signal research, portfolio optimization, and signal monitoring. The architecture is designed for extensibility, reproducibility, and clear separation of concerns.

## Project Structure

```
src/
├── main.py
├── application/
│   ├── controller.py
│   └── experiment_runner.py
├── config/
│   └── experiment_*.json
├── domain/
│   ├── machine_learning/
│   │   ├── cross_sectional_model.py
│   │   ├── feature_builder.py
│   │   └── return_predictor.py
│   ├── optimizers/
│   │   ├── ioptimizer.py
│   │   └── optimizer.py
│   ├── portfolio/
│   │   ├── iportfolio.py
│   │   └── portfolio.py
│   ├── signals/
│   │   ├── black_litterman_signal.py
│   │   ├── machine_learning_signals.py
│   │   ├── mean_reversion_signals.py
│   │   ├── momentum_signals.py
│   │   ├── moving_average_signals.py
│   │   ├── pairs_trading_signal.py
│   │   ├── risk_return_signals.py
│   │   ├── signals.py
│   │   └── volatility_forecasting_signals.py
│   └── strategies/
│       ├── equal_weight_strategy.py
│       ├── fixed_weight_strategy.py
│       ├── istrategy.py
│       ├── pairs_trading_strategy.py
│       └── systematic_strategy.py
├── infrastructure/
│   ├── market_data_gateway.py
│   └── strategy_results_data_gateway.py
├── models/
│   ├── backtest_result.py
│   ├── backtest_run.py
│   ├── experiment.py
│   ├── experiment_model.py
│   ├── machine_learning_config.py
│   ├── market_config.py
│   ├── monitoring_stats.py
│   ├── rebalance_config.py
│   ├── rebalance_problem.py
│   ├── rebalance_solution.py
│   ├── signals_config.py
│   └── strategy_run.py
├── reference/
│   └── market_metadata.py
├── reporting/
│   ├── performance_analyzer.py
│   ├── report_generation.py
│   └── signal_monitoring.py
├── services/
│   ├── optimizer_factory.py
│   ├── rebalance_problem_builder.py
│   └── strategy_factory.py
├── simulation/
│   ├── backtesting_engine.py
│   ├── market_state.py
│   └── parameter_sweeps.py
└── utils/
    ├── lookback_windows.py
    └── rebalance_steps.py
```

## Key Modules & Their Purpose

- **main.py**: FastAPI entry point; exposes `/run-experiment` and `/download` endpoints.
- **application/**:
  - `controller.py`: FastAPI route definitions.
  - `ExperimentRunner`: Orchestrates the full pipeline from config to results.
- **config/**: JSON experiment configs. Each file defines `market_store_config` and a list of strategies, each with a `market_state_config` (including `universe_tickers` and `exogenous_tickers`), `signals_config`, and `rebalance_problem`.
- **infrastructure/**:
  - `MarketDataGateway`: Market data ingestion via yfinance.
  - `StrategyResultsDataGateway`: Persists backtest results and monitoring stats to DuckDB.
- **reference/**: Static metadata — asset class and sector maps (`market_metadata.py`).
- **domain/**:
  - **machine_learning/**: `FeatureBuilder` constructs cross-sectional features (momentum, volatility, reversal, beta, VIX regime interactions). `CrossSectionalModel` trains and scores assets using Ridge regression. `ReturnPredictor` wraps model training and inference.
  - **optimizers/**: `IOptimizer` interface and optimizer implementations.
  - **portfolio/**: `Portfolio` tracks weights, returns, and turnover through time.
  - **signals/**: Signal generation — momentum, mean reversion, Black-Litterman (with optional ML views), ML scores, volatility forecasting.
  - **strategies/**: Strategy implementations that combine signals and optimizers to produce target weights on each rebalance date.
- **models/**: Pure data containers — no business logic. Key types: `RebalanceProblem`, `BacktestResult`, `MonitoringStats`, `StrategyRun`, `ExperimentModel`.
- **reporting/**:
  - `PerformanceAnalyzer`: Computes annualised return, volatility, Sharpe, Sortino, Calmar, tracking error, information ratio, VaR/CVaR, drawdown metrics, alpha, alpha decay, and turnover.
  - `LongOnlyICDiagnostics` / `PairsSpreadDiagnostics`: Both inherit `BaseMonitor`. `LongOnlyICDiagnostics` computes rolling Spearman IC, IC IR, hit rate, AR(1) half-life, and t-test significance. `PairsSpreadDiagnostics` computes IC from z-score vs realised return for pairs strategies.
  - `report_generation.py`: Excel report generation via `ExcelGenerator` — exports summary metrics, time-series charts, and weights.
- **services/**: Factories for optimizers and strategies; `RebalanceProblemBuilder` assembles all numeric inputs for the optimizer.
- **simulation/**: `BacktestingEngine` drives the time-step loop. `MarketState` manages the investable universe (`prices`, `returns`) and exogenous series (`exogenous_universe`, e.g. VIX) separately. `parameter_sweeps.py` supports grid search over strategy configs.
- **utils/**: Lookback window definitions (frequency-adjusted period counts), rebalance step logic.

## Market State Config

Each strategy's `market_state_config` supports two asset lists:

- `universe_tickers` — investable assets; used to initialise the portfolio and optimizer.
- `exogenous_tickers` — observational series (e.g. `"^VIX"`) available to signals and feature builders but never allocated to.

```json
"market_state_config": {
  "lookback_window_key": "1y",
  "market_frequency": "d",
  "cash_allocation": 0.05,
  "universe_tickers": ["AAPL", "MSFT", "..."],
  "exogenous_tickers": ["^VIX"]
}
```

## Example Workflow

### 1. Running an Experiment

```python
import json
from application.experiment_runner import ExperimentRunner

with open("config/experiment_full_suite.json") as f:
    config = json.load(f)

runner = ExperimentRunner(config)
experiment = runner.run_parallel()
```

### 2. Building a Rebalance Problem

```python
from services.rebalance_problem_builder import RebalanceProblemBuilder

builder = RebalanceProblemBuilder(config=strategy_config, universe_meta=universe_meta)
rebalance_problem = builder.build()
```

### 3. Configuring a Strategy

```python
from services.optimizer_factory import OptimizerFactory
from services.strategy_factory import StrategyFactory

optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type)
strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
new_weights = strategy.rebalance(signals, current_weights)
```

### 4. Backtesting

```python
from simulation.backtesting_engine import BacktestingEngine

engine = BacktestingEngine(
    portfolio=portfolio,
    strategy=strategy,
    market_state=market_state,
    signals_cfg=signals_cfg
)
portfolio = engine.run_backtest(rebalance_problem)
```

### 5. Signal Monitoring

```python
from reporting.signal_monitoring import LongOnlyICDiagnostics

# run is a BacktestRun with scores_history, fwd_history, and portfolio populated
monitor = LongOnlyICDiagnostics(run=backtest_run)
results = monitor.analyze()
# results: MonitoringStats with ic_statistics (Spearman IC series) and ic_summary
# ic_summary keys: mean_ic, ic_ir, hit_rate, t_statistic, p_value, half_life, n_observations
```

### 6. Reporting

```python
from reporting.report_generation import ExcelGenerator

report = ExcelGenerator(experiment, output_path="backtest_results")
report.generate_report()
```

## Adding a New Strategy or Optimizer

- Implement your strategy in `domain/strategies/` inheriting `IStrategy`, or optimizer in `domain/optimizers/` inheriting `IOptimizer`.
- Register it in the appropriate factory in `services/`.
- Optimizers must inherit `IOptimizer` and be registered in the optimizer factory.

## Project Conventions

- **Pure data models**: No business logic in models; all calculations in builders, services, or domain classes.
- **Absolute imports**: Always import from the `src` root (e.g. `from domain.signals.signals import Signals`).
- **Exogenous vs universe**: Keep `exogenous_tickers` out of portfolio initialisation — `MarketState.exogenous_universe` is separate from `MarketState.prices`.
- **No relative imports.**

## Dependencies

- Python 3.10+
- scikit-learn, scipy, numpy, pandas, yfinance, fastapi, uvicorn, cvxpy
- openpyxl (Excel report generation)
- duckdb (backtest result persistence)
- pandas_datareader (Fama-French factor data)
- See `requirements.txt` for pinned versions

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

---

# Running the UI (Frontend & Backend)

## Backend

```bash
cd src
uvicorn application.controller:app --reload
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` and expects the backend at `http://localhost:8000`.

### Frontend Components
- **`Sidebar`**: Experiment configuration, Strategy Lab (per-strategy editor with tooltips), pinned run management, and report download.
- **`StrategyGrid`**: Table of all strategy runs with summary metrics (return, vol, Sharpe, max DD, turnover) and a benchmark row.
- **`StrategyDetails`**: Cumulative wealth chart with dual-range slider, rolling metrics, and IC analysis panel.
- **`AnalysisPanel`**: IC statistics, signal monitoring charts, and diagnostics display.
