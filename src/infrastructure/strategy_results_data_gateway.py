import pandas as pd
import duckdb as db
import json
from dataclasses import asdict

from models.experiment import Experiment
from models.backtest_result import BacktestResult
from models.strategy_run import StrategyRun
from models.monitoring_stats import MonitoringStats

class GatewayBase:
    def __init__(self, database_name: str):
        self.conn = db.connect(database_name)

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

class StrategyResultsDataGateway(GatewayBase):
    CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS strategy_runs (
            run_id          VARCHAR PRIMARY KEY,
            strategy_name   VARCHAR,
            strategy_config JSON,
            result          JSON,
            monitoring_stats JSON,
            metadata        JSON
        )
    """

    INSERT = """
        INSERT OR REPLACE INTO strategy_runs
            (run_id, strategy_name, strategy_config, result, monitoring_stats, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    def __init__(self, config):
        super().__init__(config["database_name"])
        self.config = config
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(self.CREATE_TABLE)

    def save(self, run: StrategyRun):
        d = run.to_dict()
        self.conn.execute(self.INSERT, [
            d["run_id"],
            d["strategy_name"],
            json.dumps(d["strategy_config"]),
            json.dumps(d["result"]),
            json.dumps(d["monitoring_stats"]),
            json.dumps(d["metadata"]),
        ])

    # def save(self, run: StrategyRun):
    #     # 1. main row
    #     self.conn.execute(INSERT_RUN, [...])
        
    #     # 2. scalar metrics from result
    #     self.conn.execute(INSERT_METRICS, [run.run_id, run.result.sharpe, ...])
        
    #     # 3. time-series — DuckDB can ingest a DataFrame directly
    #     df = run.result.returns_df          # pandas DataFrame
    #     df["run_id"] = run.run_id
    #     self.conn.execute("INSERT INTO strategy_run_returns SELECT * FROM df")        

class ExperimentMetaDataDataGateway(GatewayBase):
    CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id VARCHAR PRIMARY KEY,
            created_at    TIMESTAMP,
            market_config JSON,
            strategy_runs JSON
        )
    """

    INSERT = """
        INSERT OR REPLACE INTO experiments
            (experiment_id, created_at, market_config, strategy_runs)
        VALUES (?, ?, ?, ?)
    """

    def __init__(self, config):
        super().__init__(config["database_name"])
        self.config = config
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(self.CREATE_TABLE)

    def save_experiment_instance(self, experiment: Experiment):
        d = experiment.to_dict()
        self.conn.execute(self.INSERT, [
            d["experiment_id"],
            d["created_at"],
            json.dumps(d["market_config"]),
            json.dumps(d["strategy_runs"]),
        ])        
    