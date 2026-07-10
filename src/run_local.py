from application.experiment_runner import ExperimentRunner
from reporting.report_generation import ExcelGenerator
from simulation.parameter_sweeps import ParameterSweeps
from utils.logging_config import setup_logging

import logging
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime

setup_logging()
logger = logging.getLogger(__name__)

def create_folder_path(folder_name: str):
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)

def local_run(config):
    logger.info("local_run:: Starting local run of experiment")
    config = config.copy()
    runner = ExperimentRunner(config)
    # experiment_results = runner.run_parallel()
    experiment_results = runner.run()
    buffer = BytesIO()
    reporting_module = ExcelGenerator(experiment_results, buffer)
    reporting_module.generate_report()
    folder_path = "backtest_results" + "/" + datetime.now().strftime('%Y-%m-%d')
    create_folder_path(folder_path)
    with open(folder_path + "/backtest_report_" + datetime.now().strftime("%Y%m%d%H%M%S%f") + ".xlsx", "wb") as f:
        f.write(buffer.getvalue())

def run_pairs_strategy():
    logger.info("run_pairs_strategy:: Starting local run of pairs trading strategy")
    with open(f"src/config/experiment_pairs_strategy.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_ml_momentum_strategy():
    logger.info("run_momentum_strategy:: Starting local run of machine learning black-litterman/momentum view strategy")
    with open(f"src/config/experiment_securities_ml_bl_momentum_100.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_ml_mean_reversion_strategy():
    logger.info("run_ml_mean_reversion_strategy:: Starting local run of machine learning black-litterman/mean reversion view strategy")
    with open(f"src/config/experiment_securities_ml_bl_mean_reversion.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_standard_mean_variance_strategy():
    logger.info("run_standard_mean_variance_strategy:: Starting local run of standard mean-variance strategy")
    with open(f"src/config/experiment_securities_mean_variance_only.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_full_suite():
    logger.info("run_full_suite:: Starting local run of full suite of strategies")
    with open(f"src/config/experiment_securities_full_suite.json", 'r') as f:
        config = json.load(f)
    local_run(config)

def run_parameter_sweep():
    with open(f"src/config/experiment_securities_ml_bl_momentum.json", 'r') as f:
        config = json.load(f)

    sweep = ParameterSweeps(config)
    sweep.run()

if __name__ == '__main__':
    # run_full_suite()
    # run_pairs_strategy()
    # run_ml_momentum_strategy()
    # run_ml_mean_reversion_strategy()
    # run_parameter_sweep()
    run_standard_mean_variance_strategy()