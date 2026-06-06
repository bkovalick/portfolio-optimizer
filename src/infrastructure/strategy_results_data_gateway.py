import pandas as pd
import duckdb as db
import json
import dataclasses
from dataclasses import asdict

from models.experiment import Experiment
from models.strategy_run import StrategyRun


class _DataclassEncoder(json.JSONEncoder):
    """Serialises dataclass instances that survive into JSON payloads."""
    def default(self, obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return super().default(obj)


def _dumps(obj) -> str:
    return json.dumps(obj, cls=_DataclassEncoder)

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
            experiment_id    VARCHAR,
            run_id          VARCHAR PRIMARY KEY,
            strategy_name   VARCHAR,
            strategy_config JSON,
            metadata        JSON
        )
    """

    INSERT = """
        INSERT OR REPLACE INTO strategy_runs
            (experiment_id, run_id, strategy_name, strategy_config, metadata)
        VALUES (?, ?, ?, ?, ?)
    """

    INSERT_IC_SUMMARY = """
    
    """
    
    INSERT_IC_SERIES = """
    
    """    
    
    def __init__(self, database_name: str):
        super().__init__(database_name)
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(self.CREATE_TABLE)

    def save_strategy_run(self, experiment_id: str, run: StrategyRun):
        d = run.to_dict()
        self.conn.execute(self.INSERT, [
            experiment_id,
            d["run_id"],
            d["strategy_name"],
            _dumps(d["strategy_config"]),
            _dumps(d["metadata"]),
        ])

        self._save_backtest_summary(d)
        self._save_backtest_series(d)
        self._save_ic_summary(d)
        self._save_ic_series(d)

    def _save_backtest_summary(self, backtest_summary: dict):
        self.conn.execute(self.INSERT_B_SUMMARY [
            json.dumps(backtest_summary["run_id"]),
            json.dumps(backtest_summary["metric_name"]),
            json.dumps(backtest_summary["value"]),
        ])

    def _save_backtest_series(self, backtest_series: dict):
        self.conn.execute(self.INSERT_B_SERIES [
            json.dumps(backtest_series["run_id"]),
            json.dumps(backtest_series["metric_name"]),
            json.dumps(backtest_series["value"]),
        ])
    
    def _save_ic_summary(self, ic_summary: dict):
        self.conn.execute(self.INSERT_IC_SUMMARY [
            json.dumps(ic_summary["run_id"]),
            json.dumps(ic_summary["metric_name"]),
            json.dumps(ic_summary["value"]),
        ])        

    def _save_ic_series(self, ic_series: dict):
        self.conn.execute(self.INSERT_IC_SERIES [
            json.dumps(ic_series["run_id"]),
            json.dumps(ic_series["metric_name"]),
            json.dumps(ic_series["value"]),
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
            market_config JSON
        )
    """

    INSERT = """
        INSERT OR REPLACE INTO experiments
            (experiment_id, created_at, market_config)
        VALUES (?, ?, ?)
    """

    def __init__(self, database_name: str):
        super().__init__(database_name)
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute(self.CREATE_TABLE)

    def save_experiment_instance(self, experiment: Experiment):
        d = experiment.to_dict()
        self.conn.execute(self.INSERT, [
            d["experiment_id"],
            d["created_at"],
            _dumps(d["market_config"]),
        ])
    