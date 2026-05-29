from domain.portfolio.portfolio import Portfolio
from reporting.performance_analyzer import PerformanceAnalyzer
from reporting.signal_monitoring import SignalICDiagnostics
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState
from services.strategy_factory import StrategyFactory
from services.optimizer_factory import OptimizerFactory
from services.rebalance_problem_builder import RebalanceProblemBuilder
from models.strategy_run import StrategyRun
from models.market_config import MarketStoreConfig, MarketStateConfig
from models.rebalance_config import RebalanceProblemConfig
from models.signals_config import SignalsConfig
from models.rebalance_problem import RebalanceProblem
from models.experiment import Experiment
from models.monitoring_stats import MonitoringStats
from infrastructure.market_data_gateway import MarketDataStore
from infrastructure.strategy_results_data_gateway import ExperimentMetaDataDataGateway, StrategyResultsDataGateway

import uuid
import logging
from datetime import datetime
import pandas as pd
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

logger = logging.getLogger(__name__)

def build_signal_config(strategy_cfg: dict) -> SignalsConfig:
    logger.info(f"Building signal configuration for strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
    signals_config = strategy_cfg.get("signals_config", None)
    if signals_config is None:
        raise ValueError("Error: Signal configuration must be present to run a backtest")
    market_frequency = strategy_cfg.get("market_state_config", {}).get("market_frequency", "d")
    return SignalsConfig.from_dict(signals_config, market_frequency)

def build_market_state_config(strategy_cfg: dict) -> MarketStateConfig:
    logger.info(f"Building market state configuration for strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
    market_state_config = strategy_cfg.get("market_state_config", None)
    if market_state_config is None:
        raise ValueError("Error: Market state configuration must be present to run a backtest")
    return MarketStateConfig.from_dict(market_state_config)

def run_strategy_worker(strategy_cfg: dict, market_store_config: MarketStoreConfig):
    logger.info(f"Running strategy worker for strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
    market_store = MarketDataStore(market_store_config)
    portfolio = Portfolio()
    metrics_computer = PerformanceAnalyzer()

    state_config = build_market_state_config(strategy_cfg)
    market_state = MarketState(market_store, state_config)

    rebalance_problem = RebalanceProblemBuilder(
        RebalanceProblemConfig.from_dict(strategy_cfg["rebalance_problem"]), 
        market_state
    ).build()
    
    signals_config = build_signal_config(strategy_cfg)

    optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type) 
    strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)

    benchmark = market_store.prices[market_store_config.benchmark]
    engine = BacktestingEngine(
        portfolio,
        strategy,
        market_state,
        signals_config,
        benchmark
    )

    run = engine.run_backtest(rebalance_problem)

    backtest_result = metrics_computer.compute(
        rebalance_problem, 
        run.portfolio, 
        market_store_config, 
        state_config,
        market_store.prices[market_store_config.benchmark]
    )
    
    monitoring_stats = None
    if run.scores_history and run.fwd_returns_history:
        scores_history_df = pd.DataFrame(run.scores_history).T
        fwd_df = pd.DataFrame(run.fwd_returns_history).T
        monitor = SignalICDiagnostics(
            fwd_df,
            scores_history_df
        )
        monitoring_stats = monitor.analyze()

    run_id = str(uuid.uuid4())
    return StrategyRun(
        run_id, 
        strategy_cfg["name"],
        rebalance_problem, 
        backtest_result, 
        monitoring_stats,
        {
            "timestamp": datetime.now(), 
            "username": "bkovalick", 
            "engine_version": "1.0.0"
        }
    )    

class ExperimentRunner:
    def __init__(self, config):
        self.config = config
        self.max_workers = min(8, multiprocessing.cpu_count())
        self.max_workers = 4

    def run(self) -> Experiment:
        market_store_config = self._build_market_store_config()
        market_store = self._build_market_store(market_store_config)
        experiment = self._create_experiment(market_store_config)
        for strategy_cfg in self.config["strategies"]:
            logger.info(f"Running strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
            run = self._run_strategy(strategy_cfg, market_store, market_store_config)
            experiment.add_run(run)
        self._save_results(experiment)
        return experiment
    
    def run_parallel(self) -> Experiment:
        market_store_config = self._build_market_store_config()
        experiment = self._create_experiment(market_store_config)
        strategies = self.config["strategies"]
        logger.info(f"Running {len(strategies)} strategies in parallel with max_workers={self.max_workers}")
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(run_strategy_worker,
                                strategy_cfg, market_store_config
                )
                for strategy_cfg in strategies
            ]

            for future in as_completed(futures):
                run = future.result()
                experiment.add_run(run)

        self._save_results(experiment)
        return experiment
    
    def _run_strategy(self, 
                      strategy_cfg: dict, 
                      market_store: MarketDataStore, 
                      market_store_config: MarketStoreConfig) -> StrategyRun:
        logger.info(f"Running strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
        portfolio = Portfolio()
        metrics_computer = PerformanceAnalyzer()

        state_config = self._build_market_state_config(strategy_cfg)
        state = self._build_market_state(market_store, state_config)

        rebalance_problem = self._build_rebalance_problem(strategy_cfg, state)

        signals_config = self._build_signal_config(strategy_cfg)

        optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type) 
        strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)

        benchmark = market_store.prices[market_store_config.benchmark]
        engine = BacktestingEngine(
            portfolio,
            strategy,
            state,
            signals_config,
            benchmark
        )

        run = engine.run_backtest(rebalance_problem)

        backtest_result = metrics_computer.compute(
            rebalance_problem, 
            run.portfolio, 
            market_store_config, 
            state_config,
            benchmark
        )

        monitoring_stats = None
        if run.scores_history and run.fwd_returns_history:
            scores_history_df = pd.DataFrame(run.scores_history).T
            fwd_df = pd.DataFrame(run.fwd_returns_history).T
            monitor = SignalICDiagnostics(
                fwd_df,
                scores_history_df
            )
            monitoring_stats = monitor.analyze()

        run_id = str(uuid.uuid4())
        return StrategyRun(
            run_id, 
            strategy_cfg["name"],
            rebalance_problem, 
            backtest_result,
            monitoring_stats, 
            {
                "timestamp": datetime.now(), 
                "username": "bkovalick", 
                "engine_version": "1.0.0"
            }
        )
    
    def _create_experiment(self, market_store_cfg: dict) -> Experiment:
        logger.info(f"Creating experiment with market store configuration: {market_store_cfg}")
        return Experiment(
            experiment_id = str(uuid.uuid4()), 
            created_at = datetime.now(),
            market_config = market_store_cfg 
        )
    
    def _save_results(self, experiment: Experiment):
        logger.info(f"Saving experiment results for experiment ID: {experiment.experiment_id}")
        self._save_experiment(experiment)
        for run in experiment.strategy_runs:
            self._save_strategy_run(run)

    def _save_experiment(self, experiment: Experiment):
        logger.info(f"Saving experiment metadata for experiment ID: {experiment.experiment_id}")
        database_name = self.config.get("results_database", "research.duckdb")
        with ExperimentMetaDataDataGateway(database_name) as exp_gateway:
            exp_gateway.save_experiment_instance(
                experiment
            )

    def _save_strategy_run(self, run: StrategyRun):
        logger.info(f"Saving strategy run results for run ID: {run.run_id}")
        database_name = self.config.get("results_database", "research.duckdb")
        with StrategyResultsDataGateway(database_name) as strategy_gateway:
            strategy_gateway.save_strategy_run(run)

    def _build_market_store_config(self) -> MarketStoreConfig:
        logger.info("Building market store configuration")
        market_store_config = self.config.get("market_store_config", None)
        if market_store_config is None:
            raise ValueError("Error: Market store configuration must be present to run a backtest")
        return MarketStoreConfig.from_dict(market_store_config)

    def _build_market_store(self, 
                            market_store_config: MarketStoreConfig) -> MarketDataStore:
        logger.info("Building market data store")
        return MarketDataStore(market_store_config)

    def _build_market_state_config(self, strategy_cfg: dict) -> MarketStateConfig:
        logger.info(f"Building market state configuration for strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
        market_state_config = strategy_cfg.get("market_state_config", None)
        if market_state_config is None:
            raise ValueError("Error: Market state configuration must be present to run a backtest")
        return MarketStateConfig.from_dict(market_state_config)
    
    def _build_market_state(self, 
                            market_store: MarketDataStore, 
                            market_state_config: MarketStateConfig) -> MarketState:
        logger.info("Building market state")
        return MarketState(market_store, market_state_config)
    
    def _build_rebalance_problem(self, 
                                 strategy_cfg: dict, 
                                 market_state: MarketState) -> RebalanceProblem:
        logger.info(f"Building rebalance problem for strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
        builder = RebalanceProblemBuilder(
            RebalanceProblemConfig.from_dict(strategy_cfg["rebalance_problem"]),
            market_state
        )
        try:
            rebalance_problem = builder.build()
            return rebalance_problem
        except ValueError as e:
            logger.error(f"Error building rebalance problem for {strategy_cfg['strategy_type']}: {e}")

    def _build_signal_config(self, strategy_cfg: dict) -> SignalsConfig:
        logger.info(f"Building signal configuration for strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
        signals_config = strategy_cfg.get("signals_config", None)
        if signals_config is None:
            raise ValueError("Error: Signal configuration must be present to run a backtest")
        market_frequency = strategy_cfg.get("market_state_config", {}).get("market_frequency", "d")
        return SignalsConfig.from_dict(signals_config, market_frequency) 

    def _build_metadata(self) -> dict:
        logger.info("Building metadata for strategy run")
        return {
            "timestamp": datetime.now(), 
            "username": "bkovalick", 
            "engine_version": "1.0.0"
        }