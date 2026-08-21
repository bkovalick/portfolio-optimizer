import logging
import numpy as np
import duckdb as db
import json
import dataclasses

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
            experiment_id VARCHAR,
            run_id        VARCHAR PRIMARY KEY,
            summary       JSON
        )
    """

    CREATE_TABLE_BACKTEST_SERIES = """
        CREATE TABLE IF NOT EXISTS backtest_series (
            experiment_id VARCHAR,
            run_id        VARCHAR PRIMARY KEY,
            series        JSON
        )
    """

    CREATE_TABLE_IC_SUMMARY = """
        CREATE TABLE IF NOT EXISTS ic_summary (
            experiment_id       VARCHAR,
            run_id              VARCHAR PRIMARY KEY,
            ic_summary          JSON,
            regression_summary  JSON
        )
    """

    CREATE_TABLE_IC_SERIES = """
        CREATE TABLE IF NOT EXISTS ic_series (
            experiment_id  VARCHAR,
            run_id         VARCHAR PRIMARY KEY,
            ic_statistics  JSON
        )
    """                

    INSERT_STRATEGY_RUN = """
        INSERT OR REPLACE INTO strategy_runs
            (experiment_id, run_id, strategy_name, strategy_config, metadata)
        VALUES (?, ?, ?, ?, ?)
    """

    INSERT_B_SUMMARY = """
        INSERT OR REPLACE INTO backtest_summary
            (experiment_id, run_id, summary)
        VALUES (?, ?, ?)
    """    

    INSERT_B_SERIES = """
        INSERT OR REPLACE INTO backtest_series
            (experiment_id, run_id, series)
        VALUES (?, ?, ?)
    """        

    INSERT_IC_SUMMARY = """
        INSERT OR REPLACE INTO ic_summary
            (experiment_id, run_id, ic_summary, regression_summary)
        VALUES (?, ?, ?, ?)
    """
    
    INSERT_IC_SERIES = """
        INSERT OR REPLACE INTO ic_series
            (experiment_id, run_id, ic_statistics)
        VALUES (?, ?, ?)
    """
    
    def __init__(self, database_name: str):
        super().__init__(database_name)
        self._ensure_schema()

    def _ensure_result_table(self, table_name: str, create_statement: str, expected_columns: list[str]):
        existing_columns = [
            row[1]
            for row in self.conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        ]
        if existing_columns and existing_columns != expected_columns:
            legacy_table_name = f"{table_name}_legacy"
            legacy_exists = self.conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                [legacy_table_name],
            ).fetchone()
            if legacy_exists:
                raise RuntimeError(
                    f"Cannot migrate {table_name}: {legacy_table_name} already exists. "
                    "Review or remove the legacy backup before retrying."
                )

            logger.warning(
                "Migrating legacy %s schema with columns %s to %s",
                table_name,
                existing_columns,
                expected_columns,
            )
            self.conn.execute(f"CREATE TABLE {legacy_table_name} AS SELECT * FROM {table_name}")
            self.conn.execute(f"DROP TABLE {table_name}")

        self.conn.execute(create_statement)

    def _ensure_schema(self):
        logger.debug("Ensuring strategy results schema")
        self.conn.execute(self.CREATE_TABLE_STRATEGY_RUN)
        self._ensure_result_table(
            "backtest_summary",
            self.CREATE_TABLE_BACKTEST_SUMMARY,
            ["experiment_id", "run_id", "summary"],
        )
        self._ensure_result_table(
            "backtest_series",
            self.CREATE_TABLE_BACKTEST_SERIES,
            ["experiment_id", "run_id", "series"],
        )
        self._ensure_result_table(
            "ic_summary",
            self.CREATE_TABLE_IC_SUMMARY,
            ["experiment_id", "run_id", "ic_summary", "regression_summary"],
        )
        self._ensure_result_table(
            "ic_series",
            self.CREATE_TABLE_IC_SERIES,
            ["experiment_id", "run_id", "ic_statistics"],
        )

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

        result = run_dict["result"]
        monitoring_stats = run_dict.get("monitoring_stats") or {}
        self._save_backtest_summary(experiment_id, run_dict["run_id"], result["summary"])
        self._save_backtest_series(experiment_id, run_dict["run_id"], result["series"])
        self._save_ic_summary(
            experiment_id,
            run_dict["run_id"],
            monitoring_stats.get("ic_summary"),
            monitoring_stats.get("regression_summary"),
        )
        self._save_ic_series(experiment_id, run_dict["run_id"], monitoring_stats.get("ic_statistics"))
        logger.debug("Finished saving strategy run %s", run_dict["run_id"])

    def _save_backtest_summary(self, experiment_id: str, run_id: str, summary: dict):
        if summary is None:
            logger.debug("No backtest summary to save for run %s in experiment %s", run_id, experiment_id)
            return
        
        self.conn.execute(self.INSERT_B_SUMMARY, [
            experiment_id,
            run_id,
            _dumps(summary),
        ])

    def _save_backtest_series(self, experiment_id: str, run_id: str, series: dict):
        if series is None:
            logger.debug("No backtest series to save for run %s in experiment %s", run_id, experiment_id)
            return
        
        self.conn.execute(self.INSERT_B_SERIES, [
            experiment_id,
            run_id,
            _dumps(series),
        ])
    
    def _save_ic_summary(self,
                         experiment_id: str,
                         run_id: str,
                         ic_summary: dict | None,
                         regression_summary: dict | None):
        if ic_summary is None and regression_summary is None:
            logger.debug("No IC summary or regression summary to save for run %s in experiment %s", run_id, experiment_id)
            return
        
        self.conn.execute(self.INSERT_IC_SUMMARY, [
            experiment_id,
            run_id,
            _dumps(ic_summary) if ic_summary is not None else None,
            _dumps(regression_summary) if regression_summary is not None else None,
        ])        

    def _save_ic_series(self, experiment_id: str, run_id: str, ic_statistics: dict | None):
        if ic_statistics is None:
            logger.debug("No IC statistics to save for run %s in experiment %s", run_id, experiment_id)
            return
        
        self.conn.execute(self.INSERT_IC_SERIES, [
            experiment_id,
            run_id,
            _dumps(ic_statistics) if ic_statistics is not None else None,
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
    