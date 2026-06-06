import logging
import numpy as np
import cvxpy as cp
import pandas as pd

from domain.optimizers.base_optimizer import BaseOptimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_solution import RebalanceSolution
from domain.signals.signals import Signals

class PortfolioRebalancer:
	def __init__(self,
			  	 target_weights: np.ndarray,
				 available_cash: float, 
			  	 prices: np.ndarray):
		self.target_weights = target_weights
		self.available_cash = available_cash
		self.prices = prices

	def generate_trades(self):
		decision_variables = self._setup_decision_variables()
		constraints = self._setup_constraints(decision_variables)
		objective = self._setup_objective(decision_variables)
		prob = cp.Problem(objective, constraints)

		for solver in ["HIGHS"]:
			try:
				prob.solve(solver=solver, verbose=False)
				if prob.status in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]:
					break
			except (cp.SolverError, Exception) as e:
				continue
		else:
			return self.target_weights
				
		optimal_weights = decision_variables.get("optimal_weights").value
		return optimal_weights
	
	def _setup_decision_variables(self):
		n_assets = len(self.target_weights)
		optimal_weights = cp.Variable(n_assets, integer = True)
		remaining_cash = cp.Variable()
		return {
			"optimal_weights": optimal_weights,
			"remaining_cash": remaining_cash
		}
	
	def _setup_constraints(self, decision_variables: dict):
		constraints = []
		constraints.extend(
			self._setup_unallocated_constraint(decision_variables)
		)
		return constraints

	def _setup_unallocated_constraint(self, decision_variables: dict):
		optimal_weights = decision_variables.get("optimal_weights")
		remaining_cash = decision_variables.get("remaining_cash")
		actual_dollars = cp.multiply(self.prices, optimal_weights)
		return [
			remaining_cash + cp.sum(actual_dollars) == self.available_cash,
			remaining_cash >= 0,
			optimal_weights >= 0
		]
		
	def _setup_objective(self, decision_variables: dict):
		optimal_weights = decision_variables.get("optimal_weights")
		remaining_cash = decision_variables.get("remaining_cash")
		target_dollars = self.target_weights * self.available_cash
		actual_dollars = cp.multiply(self.prices, optimal_weights)
		tracking_error = cp.norm1(target_dollars - actual_dollars)
		objective = cp.Minimize(remaining_cash + tracking_error)
		return objective

class Optimizer(BaseOptimizer):
	"""Optimizer using Cvxpy's minimize function."""
	def __init__(self):
		super().__init__()
		self.logger = logging.getLogger(__name__)
			
	def optimize(self, 
			  	 rebalance_problem: RebalanceProblem, 
			  	 signals: Signals = None,
			  	 current_weights: np.ndarray = None) -> RebalanceSolution:
		"""Optimize portfolio weights for the given rebalance problem."""
		if current_weights is None:
			tickers = rebalance_problem.investment_universe
			current_weights = np.array([
				rebalance_problem.initial_weights.get(ticker, 0.0) 
				for ticker in tickers
			])

		decision_variables = self._setup_decision_variables(rebalance_problem)
		constraints = self._setup_constraints(decision_variables, rebalance_problem, current_weights)
		objective = self._setup_objective(decision_variables, rebalance_problem, signals)
		prob = cp.Problem(objective, constraints)

		for solver in [cp.CLARABEL, cp.ECOS, cp.SCS, cp.OSQP]:
			try:
				prob.solve(solver=solver, verbose=False)
				if prob.status in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]:
					break
			except (cp.SolverError, Exception) as e:
				continue
		else:
			return current_weights

		optimal_weights = decision_variables['portfolio_weights'].value
		return optimal_weights	

	def _get_risky_indices(self, 
						   rebalance_problem: RebalanceProblem) -> list[int]:
		"""Returns indices of non-cash assets."""
		investment_universe = getattr(rebalance_problem, "investment_universe")
		if rebalance_problem.has_cash:
			cash_idx = rebalance_problem.cash_index
			return [i for i, _ in enumerate(investment_universe) if i != cash_idx]
		return [ i for i, _ in enumerate(investment_universe) ]
	
	def _setup_decision_variables(self, 
							      rebalance_problem: RebalanceProblem) -> dict:
		"""Setup decision variables for the optimization problem."""
		n_assets = rebalance_problem.n_assets
		n_risky_assets = len(self._get_risky_indices(rebalance_problem))
		portfolio_weights = cp.Variable(n_assets)
		portfolio_buys = cp.Variable(n_risky_assets, nonneg=True)
		portfolio_sells = cp.Variable(n_risky_assets, nonneg=True)
		return {
			'portfolio_weights': portfolio_weights,
			'portfolio_buys': portfolio_buys,
			'portfolio_sells': portfolio_sells
		}

	def _setup_constraints(self, 
						   decision_variables: dict,
						   rebalance_problem: RebalanceProblem,
						   current_weights: np.ndarray = None) -> list:
		"""Setup constraints for the optimization problem."""
		constraints = []
		constraints.extend(
			self._setup_portfolio_constraints(decision_variables, rebalance_problem, current_weights)
		)
		constraints.extend(
			self._setup_turnover_constraints(decision_variables, rebalance_problem, current_weights)
		)
		constraints.extend(
			self._setup_asset_class_constraints(decision_variables, rebalance_problem)
		)
		constraints.extend(
			self._setup_sector_constraints(decision_variables, rebalance_problem)
		)
		return constraints
	
	def _setup_portfolio_constraints(self, 
								     decision_variables: dict,
								     rebalance_problem: RebalanceProblem,
									 current_weights: np.ndarray = None) -> list: 
		"""Setup basic portfolio constraints (weights sum to 1, bounds)."""
		min_position_size = getattr(rebalance_problem, 'min_position_size', 0.0)
		max_position_size = getattr(rebalance_problem, 'max_position_size', 1.0)
		portfolio_weights = decision_variables.get('portfolio_weights')
		portfolio_buys = decision_variables.get('portfolio_buys')
		portfolio_sells = decision_variables.get('portfolio_sells')
		risky_idx = self._get_risky_indices(rebalance_problem)
		risky_current = current_weights[risky_idx]
		risky_weights = portfolio_weights[risky_idx]

		return [
				cp.sum(portfolio_weights) == 1,
				risky_weights - risky_current == portfolio_buys - portfolio_sells,
				portfolio_weights >= min_position_size,
				portfolio_weights <= max_position_size
			]
	
	def _setup_volatility_constraints(self, 
								   	  decision_variables: dict,
								   	  rebalance_problem: RebalanceProblem,
								   	  signals: Signals) -> list:
		optimizer_vol_constraint = getattr(rebalance_problem, 'optimizer_vol_constraint', None)
		if optimizer_vol_constraint is None or signals is None:
			return []
		
		portfolio_weights = decision_variables.get('portfolio_weights')
		risky_idx = self._get_risky_indices(rebalance_problem)
		risky_weights = portfolio_weights[risky_idx]
		cov_matrix = signals.covariance_matrix()[np.ix_(risky_idx, risky_idx)]
		portfolio_risk = cp.quad_form(risky_weights, cov_matrix)
		return [
			portfolio_risk <= optimizer_vol_constraint ** 2
		]

	def _setup_turnover_constraints(self, 
								    decision_variables: dict,
								    rebalance_problem: RebalanceProblem,
									current_weights: np.ndarray = None) -> list: 
		"""Setup turnover constraints based on turnover limit."""
		if getattr(rebalance_problem, 'turnover_limit') is None or current_weights is None:
			return []
		
		portfolio_weights = decision_variables.get('portfolio_weights')	
		risky_idx = self._get_risky_indices(rebalance_problem)
		risky_current = current_weights[risky_idx]
		risky_weights = portfolio_weights[risky_idx]

		return [
			cp.norm1(risky_weights - risky_current) <= rebalance_problem.turnover_limit
		]

	def _setup_asset_class_constraints(self, 
								       decision_variables: dict,
								       rebalance_problem: RebalanceProblem) -> list:
		"""Setup asset class size constraints: Equity < 90%, Fixed < 20%, etc..."""
		if getattr(rebalance_problem, "asset_class_constraints") is None:
			return []

		portfolio_weights = decision_variables.get('portfolio_weights')
		asset_class_map = rebalance_problem.asset_class_map
		asset_class_constraints = rebalance_problem.asset_class_constraints
		constraints = []
		if asset_class_constraints is None:
			return constraints
		
		for asset_class, min_max in asset_class_constraints.items():
			if asset_class not in asset_class_map:
				continue
	
			min_weight, max_weight = min_max[0], min_max[1]
			indices = [idx[0] for idx in asset_class_map[asset_class]] \
				if asset_class != "Cash" else [asset_class_map[asset_class][0]] 
			class_weight = cp.sum(portfolio_weights[indices])
			
			if min_weight > 0:
				constraints.append(class_weight >= min_weight)
			
			if max_weight < 1:
				constraints.append(class_weight <= max_weight)
		return constraints

	def _setup_sector_constraints(self, 
								  decision_variables: dict,
								  rebalance_problem: RebalanceProblem) -> list:
		"""Setup asset class size constraints: Financials < 15%, Tech: 20%, etc..."""
		if getattr(rebalance_problem, "sector_constraints") is None:
			return []

		portfolio_weights = decision_variables.get('portfolio_weights')
		sector_constraints = rebalance_problem.sector_constraints
		sector_map = rebalance_problem.sector_map
		constraints = []
		if sector_constraints is None:
			return constraints
				
		for sector, min_max in sector_constraints.items():
			if sector not in sector_map:
				continue

			min_weight, max_weight = min_max[0], min_max[1]
			indices = [idx[0] for idx in sector_map[sector]] \
				if sector != "Cash" else [sector_map[sector][0]] 
			
			sector_weight = cp.sum(portfolio_weights[indices])

			if min_weight > 0:
				constraints.append(sector_weight >= min_weight)

			if max_weight < 1:
				constraints.append(sector_weight <= max_weight)
		return constraints
		
	def _setup_objective(self, 
					   	 decision_variables: dict, 
					   	 rebalance_problem: RebalanceProblem, 
					   	 signals: Signals = None) -> callable:
		"""Set the objective function based on rebalance problem settings."""
		objectives = {
			'apply_max_return_objective': self._set_maximize_return_objective,
		}
		for flag, builder in objectives.items():
			if getattr(rebalance_problem, flag, False):
				return builder(decision_variables, rebalance_problem, signals)
		raise ValueError("No objective function configured. Set one of: " + ", ".join(objectives))
		
	def _set_maximize_return_objective(self, 
									   decision_variables: dict,
									   rebalance_problem: RebalanceProblem, 
									   signals: Signals) -> callable:
		"""Set objective to maximize returns minus risk penalty."""
		risk_aversion = getattr(rebalance_problem, 'risk_aversion', 1.0)
		transaction_cost = getattr(rebalance_problem, 'transaction_cost', 0.003)
		portfolio_weights = decision_variables.get('portfolio_weights')
		mean_vector = signals.mean_returns()
		cov_matrix = signals.covariance_matrix()

		risky_idx = self._get_risky_indices(rebalance_problem)
		risky_weights = portfolio_weights[risky_idx]
		cov_matrix = signals.covariance_matrix()[np.ix_(risky_idx, risky_idx)]
		mean_vector = mean_vector[risky_idx]

		portfolio_risk = cp.quad_form(risky_weights, cp.psd_wrap(cov_matrix))
		concentration_objective = self._get_concentration_objective(risky_weights, rebalance_problem)
		transaction_cost_penalty = self._get_transaction_cost_penalty(transaction_cost, decision_variables)
		objective = cp.Maximize(mean_vector @ risky_weights - risk_aversion * \
						  portfolio_risk - concentration_objective - transaction_cost_penalty)
		return objective
	
	def _get_concentration_objective(self, 
									 risky_weights,
								 	 rebalance_problem: RebalanceProblem):
		"""Set concentration objective that will penalize large weights."""
		concentration_penalty = cp.sum_squares(risky_weights)
		concentration_strength = getattr(rebalance_problem, "concentration_strength", 0.0)
		if concentration_strength == 0:
			return 0
		return concentration_penalty * concentration_strength
	
	def _get_transaction_cost_penalty(self,
								   	  transaction_cost: float,
									  decision_variables: dict): 
		"""Set transaction cost penalty based on turnover from current weights to new weights."""
		portfolio_buys = decision_variables.get('portfolio_buys')
		portfolio_sells = decision_variables.get('portfolio_sells')
		return transaction_cost * (cp.sum(portfolio_buys) + cp.sum(portfolio_sells))

	def _log_failure_diagnostics(self, prob, current_weights, signals):
		"""Log diagnostic info when optimization fails."""
		self.logger.warning(f"Status: {prob.status}")
		self.logger.warning(f"Current weights: {current_weights}")
		self.logger.warning(f"Current weights sum: {current_weights.sum():.6f}")
		self.logger.warning(f"Num constraints: {len(prob.constraints)}")
		if signals is not None:
			mean_ret = signals.mean_returns()
			cov = signals.covariance_matrix()
			self.logger.warning(f"Mean returns range: [{mean_ret.min():.6f}, {mean_ret.max():.6f}]")
			self.logger.warning(f"Cov matrix condition number: {np.linalg.cond(cov):.2e}")
			self.logger.warning(f"Any NaN in mean: {np.any(np.isnan(mean_ret))}, cov: {np.any(np.isnan(cov))}")