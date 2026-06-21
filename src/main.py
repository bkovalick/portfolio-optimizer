from application.experiment_runner import ExperimentRunner
from reporting.report_generation import ExcelGenerator
from simulation.parameter_sweeps import ParameterSweeps
from utils.logging_config import setup_logging

import logging
import json
import uvicorn
import os
from io import BytesIO
from pathlib import Path
from datetime import datetime

setup_logging()
logger = logging.getLogger(__name__)

def create_folder_path(folder_name: str):
    path = Path(folder_name)
    path.mkdir(parents=True, exist_ok=True)

def local_run():
    logger.info("local_run:: Starting local run of experiment")
    with open(f"src/config/experiment_pairs_strategy.json", 'r') as f:
    # with open(f"src/config/experiment_etf_universe.json", 'r') as f:
    # with open(f"src/config/experiment_fwp.json", 'r') as f:
    # with open(f"src/config/experiment_securities_ml_bl_mean_reversion.json", 'r') as f:
        config = json.load(f)

    config = config.copy()
    runner = ExperimentRunner(config)
    experiment_results = runner.run_parallel()
    buffer = BytesIO()
    reporting_module = ExcelGenerator(experiment_results, buffer)
    reporting_module.generate_report()
    folder_path = "backtest_results" + "/" + datetime.now().strftime('%Y-%m-%d')
    create_folder_path(folder_path)
    with open(folder_path + "/backtest_report_" + datetime.now().strftime("%Y%m%d%H%M%S%f") + ".xlsx", "wb") as f:
        f.write(buffer.getvalue())

def run_parameter_sweep():
    with open(f"src/config/experiment_securities_ml_bl_momentum.json", 'r') as f:
        config = json.load(f)

    sweep = ParameterSweeps(config)
    sweep.run()

if __name__ == '__main__':
    run_mode = os.environ.get("RUN_MODE", "api").lower()
    run_mode = "local"
    if run_mode == "local":
        local_run()
        # run_parameter_sweep()
    else:
        uvicorn.run("application.controller:app", reload=True)