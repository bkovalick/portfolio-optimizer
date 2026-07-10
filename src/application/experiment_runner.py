import uuid, logging, multiprocessing, pandas as pd
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from domain.portfolio.portfolio import Portfolio
from reporting.performance_analyzer import PerformanceAnalyzer
from reporting.signal_monitoring import LongOnlyICDiagnostics, PairsSpreadDiagnostics
from simulation.backtesting_engine import BacktestingEngine
from simulation.market_state import MarketState
from services.strategy_factory import StrategyFactory
from services.optimizer_factory import OptimizerFactory
from services.rebalance_problem_builder import RebalanceProblemBuilder
from models.strategy_run import StrategyRun
from models.market_config import MarketStoreConfig, MarketStateConfig
from models.rebalance_config import RebalanceProblemConfig
from models.signals_config import SignalsConfig
from models.experiment import Experiment
from infrastructure.market_data_gateway import MarketDataStore
from infrastructure.strategy_results_data_gateway import ExperimentMetaDataDataGateway, StrategyResultsDataGateway

logger = logging.getLogger(__name__)

def build_signal_config(strategy_cfg: dict) -> SignalsConfig:
    cfg = strategy_cfg.get("signals_config")
    if not cfg: raise ValueError("Error: Signal configuration must be present to run a backtest")
    return SignalsConfig.from_dict(cfg, strategy_cfg.get("market_state_config", {}).get("market_frequency", "d"))

def build_market_state_config(strategy_cfg: dict) -> MarketStateConfig:
    cfg = strategy_cfg.get("market_state_config")
    if not cfg: raise ValueError("Error: Market state configuration must be present to run a backtest")
    return MarketStateConfig.from_dict(cfg)

def run_strategy_worker(strategy_cfg: dict, market_store_config: MarketStoreConfig) -> StrategyRun:
    logger.info(f"Running strategy: {strategy_cfg.get('name', 'Unnamed Strategy')}")
    market_store = MarketDataStore(market_store_config)
    market_state_config = build_market_state_config(strategy_cfg)
    market_state = MarketState(market_store, market_state_config)
    
    rebalance_problem = RebalanceProblemBuilder(
        RebalanceProblemConfig.from_dict(strategy_cfg["rebalance_problem"]), market_state
    ).build()
    
    optimizer = OptimizerFactory.create_optimizer(rebalance_problem.optimizer_type)
    strategy = StrategyFactory.create_strategy(rebalance_problem, optimizer)
    benchmark = market_store.prices[market_store_config.benchmark]
    
    run = BacktestingEngine(Portfolio(), strategy, market_state, build_signal_config(strategy_cfg), benchmark).run_backtest(rebalance_problem)
    
    portfolio_results = PerformanceAnalyzer().compute(run.portfolio, market_store_config, market_state_config, benchmark)
    
    monitor_ref = {"long_only": LongOnlyICDiagnostics, "pairs": PairsSpreadDiagnostics}.get(rebalance_problem.monitoring_type)
    portfolio_statistics = monitor_ref(run).analyze() if monitor_ref else None
    
    return StrategyRun(
        str(uuid.uuid4()), strategy_cfg["name"], rebalance_problem, portfolio_results, portfolio_statistics,
        {"timestamp": datetime.now(), "username": "bkovalick", "engine_version": "1.0.0"}
    )

class ExperimentRunner:
    def __init__(self, config: dict):
        self.config = config
        self.max_workers = min(8, multiprocessing.cpu_count())

    def _get_market_config(self) -> MarketStoreConfig:
        cfg = self.config.get("market_store_config")
        if not cfg: raise ValueError("Error: Market store configuration must be present")
        return MarketStoreConfig.from_dict(cfg)

    def _create_experiment(self, m_cfg: MarketStoreConfig) -> Experiment:
        return Experiment(experiment_id=str(uuid.uuid4()), created_at=datetime.now(), market_config=m_cfg)

    def run(self) -> Experiment:
        m_cfg = self._get_market_config()
        experiment = self._create_experiment(m_cfg)
        for strategy_cfg in self.config["strategies"]:
            experiment.add_run(run_strategy_worker(strategy_cfg, m_cfg))
        # self._save_results(experiment)
        return experiment

    def run_parallel(self) -> Experiment:
        m_cfg = self._get_market_config()
        experiment = self._create_experiment(m_cfg)
        strategies = self.config["strategies"]
        
        logger.info(f"Running {len(strategies)} strategies in parallel with max_workers={self.max_workers}")
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(run_strategy_worker, s_cfg, m_cfg) for s_cfg in strategies]
            for future in as_completed(futures):
                experiment.add_run(future.result())
        # self._save_results(experiment)
        return experiment

    def _save_results(self, experiment: Experiment):
        db = self.config.get("results_database", "research.duckdb")
        with ExperimentMetaDataDataGateway(db) as exp_gateway:
            exp_gateway.save_experiment_instance(experiment)
        with StrategyResultsDataGateway(db) as strategy_gateway:
            for run in experiment.strategy_runs:
                strategy_gateway.save_strategy_run(experiment.experiment_id, run)

if __name__ == "__main__":
    pass