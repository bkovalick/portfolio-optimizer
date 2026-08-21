import logging
import math
import numpy as np
import duckdb as db
import json
import dataclasses
from datetime import date, datetime, time

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
        if isinstance(obj, (date, datetime, time)):
            return obj.isoformat()
        return super().default(obj)


def _dumps(obj) -> str:
    return json.dumps(obj, cls=_DataclassEncoder)


def _clean_float(value):
    """NaN/Inf -> None so they land as SQL NULL rather than poisoning aggregates."""
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (int, np.integer)):
        return float(value)
    return None


def _clean_date(value):
    """Normalise index entries to 'YYYY-MM-DD' so the DATE column has one grain."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    text = str(value)
    return text[:10] if len(text) >= 10 else text


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
            run_id        VARCHAR,
            series_name   VARCHAR,
            observed_at   DATE,
            value         DOUBLE,
            PRIMARY KEY (run_id, series_name, observed_at)
        )
    """

    CREATE_TABLE_PORTFOLIO_WEIGHTS = """
        CREATE TABLE IF NOT EXISTS portfolio_weights (
            experiment_id VARCHAR,
            run_id        VARCHAR,
            observed_at   DATE,
            ticker        VARCHAR,
            weight        DOUBLE,
            PRIMARY KEY (run_id, observed_at, ticker)
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
            experiment_id VARCHAR,
            run_id        VARCHAR,
            ic_name       VARCHAR,
            observed_at   DATE,
            value         DOUBLE,
            PRIMARY KEY (run_id, ic_name, observed_at)
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
            (experiment_id, run_id, series_name, observed_at, value)
        VALUES (?, ?, ?, ?, ?)
    """

    INSERT_WEIGHTS = """
        INSERT OR REPLACE INTO portfolio_weights
            (experiment_id, run_id, observed_at, ticker, weight)
        VALUES (?, ?, ?, ?, ?)
    """

    INSERT_IC_SUMMARY = """
        INSERT OR REPLACE INTO ic_summary
            (experiment_id, run_id, ic_summary, regression_summary)
        VALUES (?, ?, ?, ?)
    """

    INSERT_IC_SERIES = """
        INSERT OR REPLACE INTO ic_series
            (experiment_id, run_id, ic_name, observed_at, value)
        VALUES (?, ?, ?, ?, ?)
    """

    # Series entries that are frames rather than date->value series. Weights get
    # their own table; the long variant is derivable from it, so it is dropped.
    _FRAME_SERIES = {"portfolio_weights", "portfolio_weights_long"}

    def __init__(self, database_name: str):
        super().__init__(database_name)
        self._ensure_schema()

    def _ensure_result_table(self, table_name: str, create_statement: str, expected_columns: list[str]):
        table_exists = self.conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()

        existing_columns = [
            row[1]
            for row in self.conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        ] if table_exists else []
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
            ["experiment_id", "run_id", "series_name", "observed_at", "value"],
        )
        self._ensure_result_table(
            "portfolio_weights",
            self.CREATE_TABLE_PORTFOLIO_WEIGHTS,
            ["experiment_id", "run_id", "observed_at", "ticker", "weight"],
        )
        self._ensure_result_table(
            "ic_summary",
            self.CREATE_TABLE_IC_SUMMARY,
            ["experiment_id", "run_id", "ic_summary", "regression_summary"],
        )
        self._ensure_result_table(
            "ic_series",
            self.CREATE_TABLE_IC_SERIES,
            ["experiment_id", "run_id", "ic_name", "observed_at", "value"],
        )

    def save_strategy_run(self, experiment_id: str, run: StrategyRun):
        run_dict = run.to_dict()
        run_id = run_dict["run_id"]
        logger.info("Saving strategy run %s for experiment %s", run_id, experiment_id)
        self.conn.execute(self.INSERT_STRATEGY_RUN, [
            experiment_id,
            run_id,
            run_dict["strategy_name"],
            _dumps(run_dict["strategy_config"]),
            _dumps(run_dict["metadata"]),
        ])

        result = run_dict["result"]
        monitoring_stats = run_dict.get("monitoring_stats") or {}
        series = result.get("series") or {}

        self._save_backtest_summary(experiment_id, run_id, result.get("summary"))
        self._save_backtest_series(experiment_id, run_id, series)
        self._save_portfolio_weights(experiment_id, run_id, series.get("portfolio_weights"))
        self._save_ic_summary(
            experiment_id,
            run_id,
            monitoring_stats.get("ic_summary"),
            monitoring_stats.get("regression_summary"),
        )
        self._save_ic_series(experiment_id, run_id, monitoring_stats.get("ic_statistics"))
        logger.debug("Finished saving strategy run %s", run_id)

    @staticmethod
    def _iter_series_points(payload):
        """Yield (date, value) from either split format or a plain date->value map."""
        if not isinstance(payload, dict):
            return

        index = payload.get("index")
        values = payload.get("values")
        if index is not None and values is not None:
            yield from zip(index, values)
            return

        # plain {date: value} mapping
        for key, value in payload.items():
            yield key, value

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
        if not series:
            logger.debug("No backtest series to save for run %s in experiment %s", run_id, experiment_id)
            return

        rows = []
        for series_name, payload in series.items():
            if series_name in self._FRAME_SERIES:
                continue
            for observed_at, value in self._iter_series_points(payload):
                rows.append((
                    experiment_id,
                    run_id,
                    series_name,
                    _clean_date(observed_at),
                    _clean_float(value),
                ))

        if not rows:
            logger.debug("No flattenable series rows for run %s", run_id)
            return

        self.conn.executemany(self.INSERT_B_SERIES, rows)
        logger.debug("Saved %d series rows for run %s", len(rows), run_id)

    def _save_portfolio_weights(self, experiment_id: str, run_id: str, weights):
        """weights arrives as a DataFrame in split/dict form: date index x ticker columns."""
        if not weights:
            logger.debug("No portfolio weights to save for run %s in experiment %s", run_id, experiment_id)
            return

        rows = []
        index = weights.get("index") if isinstance(weights, dict) else None
        columns = weights.get("columns") if isinstance(weights, dict) else None
        data = weights.get("data") if isinstance(weights, dict) else None

        if index is not None and columns is not None and data is not None:
            # pandas orient="split"
            for observed_at, row_values in zip(index, data):
                cleaned_date = _clean_date(observed_at)
                for ticker, value in zip(columns, row_values):
                    rows.append((experiment_id, run_id, cleaned_date, ticker, _clean_float(value)))
        elif isinstance(weights, dict):
            # pandas default to_dict(): {ticker: {date: weight}}
            for ticker, by_date in weights.items():
                if not isinstance(by_date, dict):
                    continue
                for observed_at, value in by_date.items():
                    rows.append((
                        experiment_id,
                        run_id,
                        _clean_date(observed_at),
                        ticker,
                        _clean_float(value),
                    ))

        if not rows:
            logger.debug("Portfolio weights for run %s were not in a recognised shape", run_id)
            return

        self.conn.executemany(self.INSERT_WEIGHTS, rows)
        logger.debug("Saved %d weight rows for run %s", len(rows), run_id)

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
        """ic_statistics is {ic_name: {date: value}} — e.g. {'spearman': {...}}."""
        if not ic_statistics:
            logger.debug("No IC statistics to save for run %s in experiment %s", run_id, experiment_id)
            return

        rows = []
        for ic_name, payload in ic_statistics.items():
            for observed_at, value in self._iter_series_points(payload):
                rows.append((
                    experiment_id,
                    run_id,
                    ic_name,
                    _clean_date(observed_at),
                    _clean_float(value),
                ))

        if not rows:
            logger.debug("No flattenable IC rows for run %s", run_id)
            return

        self.conn.executemany(self.INSERT_IC_SERIES, rows)
        logger.debug("Saved %d IC rows for run %s", len(rows), run_id)


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