import logging
import pandas as pd
import numpy as np
import duckdb as db
import json
import dataclasses
from dataclasses import asdict

from models.experiment import Experiment
from models.strategy_run import StrategyRun


logger = logging.getLogger(__name__)

class _DataclassEncoder(json.JSONEncoder):
    def default(self, obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

def _dumps(obj) -> str:
    return json.dumps(obj, cls=_DataclassEncoder)

class GatewayBase:
    def __init__(self, database_name: str):
        self.conn = db.connect(database_name)
        logger.debug("Opened DuckDB connection to %s", database_name)

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
        logger.debug("Closed DuckDB connection")

class StrategyResultsDataGateway(GatewayBase):
    CREATE_TABLE_STRATEGY_RUN = """
        CREATE TABLE IF NOT EXISTS strategy_runs (
            experiment_id    VARCHAR,
            run_id          VARCHAR PRIMARY KEY,
            strategy_name   VARCHAR,
            strategy_config JSON,
            metadata        JSON
        )
    """

    CREATE_TABLE_BACKTEST_SUMMARY = """
        CREATE TABLE IF NOT EXISTS backtest_summary (
            experiment_id    VARCHAR,
            run_id          VARCHAR PRIMARY KEY,
            strategy_name   VARCHAR,
            strategy_config JSON,
            metadata        JSON
        )
    """

    CREATE_TABLE_BACKTEST_SERIES = """
        CREATE TABLE IF NOT EXISTS backtest_series (
            experiment_id    VARCHAR,
            run_id          VARCHAR PRIMARY KEY,
            strategy_name   VARCHAR,
            strategy_config JSON,
            metadata        JSON
        )
    """

    CREATE_TABLE_IC_SUMMARY = """
        CREATE TABLE IF NOT EXISTS ic_summary (
            experiment_id    VARCHAR,
            run_id          VARCHAR PRIMARY KEY,
            strategy_name   VARCHAR,
            strategy_config JSON,
            metadata        JSON
        )
    """

    CREATE_TABLE_IC_SERIES = """
        CREATE TABLE IF NOT EXISTS ic_series (
            experiment_id    VARCHAR,
            run_id          VARCHAR PRIMARY KEY,
            strategy_name   VARCHAR,
            strategy_config JSON,
            metadata        JSON
        )
    """                

    INSERT_STRATEGY_RUN = """
        INSERT OR REPLACE INTO strategy_runs
            (experiment_id, run_id, strategy_name, strategy_config, metadata)
        VALUES (?, ?, ?, ?, ?)
    """

    INSERT_B_SUMMARY = """
        INSERT OR REPLACE INTO backtest_summary
            (experiment_id, run_id, strategy_name, strategy_config, metadata)
        VALUES (?, ?, ?, ?, ?)
    """    

    INSERT_B_SERIES = """
    INSERT OR REPLACE INTO backtest_series
        (experiment_id, run_id, strategy_name, strategy_config, metadata)
    """        

    INSERT_IC_SUMMARY = """
    INSERT OR REPLACE INTO ic_summary
        (experiment_id, run_id, strategy_name, strategy_config, metadata)
    """
    
    INSERT_IC_SERIES = """
    INSERT OR REPLACE INTO ic_series
        (experiment_id, run_id, strategy_name, strategy_config, metadata)
    """
    
    def __init__(self, database_name: str):
        super().__init__(database_name)
        self._ensure_schema()

    def _ensure_schema(self):
        logger.debug("Ensuring strategy results schema")
        self.conn.execute(self.CREATE_TABLE_STRATEGY_RUN)
        self.conn.execute(self.CREATE_TABLE_BACKTEST_SUMMARY)
        self.conn.execute(self.CREATE_TABLE_BACKTEST_SERIES)
        self.conn.execute(self.CREATE_TABLE_IC_SUMMARY)
        self.conn.execute(self.CREATE_TABLE_IC_SERIES)

    def save_strategy_run(self, experiment_id: str, run: StrategyRun):
        run_dict = run.to_dict()
        logger.info("Saving strategy run %s for experiment %s", run_dict["run_id"], experiment_id)
        self.conn.execute(self.INSERT_STRATEGY_RUN, [
            experiment_id,
            run_dict["run_id"],
            run_dict["strategy_name"],
            _dumps(run_dict["strategy_config"]),
            _dumps(run_dict["metadata"]),
        ])

        self._save_backtest_summary(run_dict)
        self._save_backtest_series(run_dict)
        self._save_ic_summary(run_dict)
        self._save_ic_series(run_dict)
        logger.debug("Finished saving strategy run %s", run_dict["run_id"])

    def _save_backtest_summary(self, backtest_summary: dict):
        self.conn.execute(self.INSERT_B_SUMMARY, [
            json.dumps(backtest_summary["run_id"]),
            json.dumps(backtest_summary["metric_name"]),
            json.dumps(backtest_summary["value"]),
        ])

    def _save_backtest_series(self, backtest_series: dict):
        self.conn.execute(self.INSERT_B_SERIES, [
            json.dumps(backtest_series["run_id"]),
            json.dumps(backtest_series["metric_name"]),
            json.dumps(backtest_series["value"]),
        ])
    
    def _save_ic_summary(self, ic_summary: dict):
        self.conn.execute(self.INSERT_IC_SUMMARY, [
            json.dumps(ic_summary["run_id"]),
            json.dumps(ic_summary["metric_name"]),
            json.dumps(ic_summary["value"]),
        ])        

    def _save_ic_series(self, ic_series: dict):
        self.conn.execute(self.INSERT_IC_SERIES, [
            json.dumps(ic_series["run_id"]),
            json.dumps(ic_series["metric_name"]),
            json.dumps(ic_series["value"]),
        ])     

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
        logger.debug("Ensuring experiment metadata schema")
        self.conn.execute(self.CREATE_TABLE)

    def save_experiment_instance(self, experiment: Experiment):
        d = experiment.to_dict()
        logger.info("Saving experiment metadata for %s", d["experiment_id"])
        self.conn.execute(self.INSERT, [
            d["experiment_id"],
            d["created_at"],
            _dumps(d["market_config"]),
        ])
    