from __future__ import division

import multiprocessing as mp
from copy import deepcopy

import numpy as np
from pygam import LogisticGAM
from scipy import stats
from sklearn.base import BaseEstimator, clone
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import brier_score_loss
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import QuantileRegressor
from sklearn.model_selection import train_test_split


# creating paralelized function outside of class
def _retrain_loop_par(coverage_evaluator, model, alpha, X_train, w_train, X_test, seed):
    np.random.seed(seed)
    new_w = stats.binom.rvs(n=1, p=1 - alpha, size=w_train.shape[0])
    new_r = retrain_par(coverage_evaluator, model, X_train, new_w, X_test)
    return np.mean(np.abs(new_r - (1 - alpha)))


def retrain_par(coverage_evaluator, model, X_train, new_w, X_test):
    if coverage_evaluator == "RF" or "sklearn" in str(type((model))):
        model_temp = clone(model).fit(X_train, new_w)
        pred = model_temp.predict_proba(X_test)
        if len(pred[0]) == 1:
            new_r = pred
        else:
            new_r = pred[:, 1]
        return new_r
    elif coverage_evaluator == "GAM":
        model_temp = LogisticGAM().grid_search(X_train, new_w).fit(X_train, new_w)
        new_r = model_temp.predict_proba(X_test)
        return new_r
    else:
        # using cpu instead of gpu
        model_temp = deepcopy(model).move_to_cpu().fit(X_train, new_w)
        new_r = model_temp.predict(X_test).flatten(order="C")
        return new_r


def bootstrap_par(B, alpha, coverage_evaluator, model, X_train, w_train, X_test, seed):
    np.random.seed(seed)
    new_indexes = np.random.randint(X_train.shape[0], size=B)
    new_X_train, new_w_train = X_train[new_indexes, :], w_train[new_indexes]
    new_r = retrain_par(coverage_evaluator, model, new_X_train, new_w_train, X_test)
    t = np.mean(np.abs(new_r - (1 - alpha)))
    return t


class Valid_pred_sets(BaseEstimator):
    """
    Validation of conditional coverage. Here we test $H0: P(Y  \in R(X)|X) = 1 - \alpha$
    -----------
    conf: model object
      already calibrated Conformal Prediction model from noncoformist package or any model with predict method
    alpha: float between 0 and 1
      significance level for testing
    coverage evaluator: string
      which coverage evaluator to use: for now, using only Regression Trees (CART), Random Forest (RF), Generalized additive models (GAM) and neural networks (nnet)
    prune: bool
      whether to prune or not the regression tree coverage evaluator. Works only if coverage_evaluator = "CART"
    """

    def __init__(
        self,
        conf,
        alpha,
        isnc=False,
        islcp=False,
        coverage_evaluator="CART",
        prune=True,
        split_train=True,
    ):
        self.conf = conf
        self.alpha = alpha
        self.nc = isnc
        self.islcp = islcp
        self.coverage_evaluator = coverage_evaluator
        self.prune = prune
        self.split_train = split_train

    def fit(
        self,
        X_calib,
        y_calib,
        random_seed=1250,
        prune_seed=650,
        test_size=0.2,
        **kwargs
    ):
        # predicting each interval
        if self.nc:
            preds = self.conf.predict(X_calib, significance=self.alpha)
        elif self.islcp:
            preds = np.stack((self.conf.predict_pi(X_calib, method="qrf")), axis=-1)
        else:
            preds = np.array(self.conf.predict(X_calib))

        np.random.seed(random_seed)
        # obtaining each w
        w = np.zeros(y_calib.shape[0])
        for i in range(y_calib.shape[0]):
            w[i] = int(y_calib[i] >= preds[i, 0] and y_calib[i] <= preds[i, 1])
        # splitting training and testing sets
        if self.split_train:
            self.X_train, self.X_test, self.w_train, self.w_test = train_test_split(
                X_calib, w, test_size=test_size
            )
        else:
            self.X_train, self.w_train = X_calib, w

        # regressing w on x using select coverage evaluator model
        return self._init_coverage_evaluator(
            random_seed=random_seed, prune_seed=prune_seed, **kwargs
        )

    def _init_coverage_evaluator(self, random_seed, prune_seed, **kwargs):
        """
        Coverage evaluator initializer
        -----------
        random_seed: Random seed provided
        **kwargs: Arguments passed to it correspondent coverage evaluator model
        """
        if self.coverage_evaluator == "CART":
            self.model = DecisionTreeClassifier(
                random_state=random_seed, min_samples_leaf=100
            ).set_params(**kwargs)
            if self.prune:
                (
                    X_train_prune,
                    X_test_prune,
                    w_train_prune,
                    w_test_prune,
                ) = train_test_split(
                    self.X_train,
                    self.w_train,
                    test_size=0.5,
                    random_state=prune_seed,
                )
                optim_ccp = self.prune_tree(
                    X_train_prune, X_test_prune, w_train_prune, w_test_prune
                )
                # pruning decision tree
                self.model.set_params(ccp_alpha=optim_ccp).fit(
                    self.X_train, self.w_train
                )

            else:
                self.model = (
                    DecisionTreeClassifier(min_samples_leaf=100)
                    .set_params(**kwargs)
                    .fit(self.X_train, self.w_train)
                )
        elif self.coverage_evaluator == "RF":
            self.model = RandomForestClassifier(**kwargs).fit(
                self.X_train, self.w_train
            )
        elif self.coverage_evaluator == "GAM":
            self.model = (
                LogisticGAM()
                .gridsearch(self.X_train, self.w_train)
                .fit(self.X_train, self.w_train)
            )
        else:
            self.model = self.coverage_evaluator.set_params(**kwargs).fit(
                self.X_train, self.w_train
            )
        return self

    def prune_tree(self, X_train, X_valid, w_train, w_valid):
        prune_path = self.model.cost_complexity_pruning_path(X_train, w_train)
        ccp_alphas = prune_path.ccp_alphas
        current_loss = float("inf")
        # cross validation by data splitting to choose alphas
        for ccp_alpha in ccp_alphas:
            preds_ccp = (
                clone(self.model)
                .set_params(ccp_alpha=ccp_alpha)
                .fit(X_train, w_train)
                .predict(X_valid)
            )
            loss_ccp = brier_score_loss(w_valid, preds_ccp)
            if loss_ccp < current_loss:
                current_loss = loss_ccp
                optim_ccp = ccp_alpha

        return optim_ccp

    def predict(self, X_test):
        if self.coverage_evaluator == "RF" or "sklearn" in str(type((self.model))):
            pred = self.model.predict_proba(X_test)
            if len(pred[0]) == 1:
                return pred
            else:
                return pred[:, 1]
        elif self.coverage_evaluator == "GAM":
            pred = self.model.predict_proba(X_test)
            return pred
        elif self.coverage_evaluator == "nnet":
            pred = self.model.predict(X_test).flatten(order="C")
            return pred

    def retrain(self, X_train, new_w, X_test):
        if self.coverage_evaluator == "RF" or "sklearn" in str(type((self.model))):
            model_temp = clone(self.model).fit(X_train, new_w)
            pred = model_temp.predict_proba(self.X_test)
            if len(pred[0]) == 1:
                new_r = pred
            else:
                new_r = pred[:, 1]
            return new_r
        elif self.coverage_evaluator == "GAM":
            model_temp = LogisticGAM().grid_search(X_train, new_w).fit(X_train, new_w)
            new_r = model_temp.predict_proba(self.X_test)
            return new_r
        else:
            model_temp = deepcopy(self.model).fit(X_train, new_w)
            new_r = model_temp.predict(X_test).flatten(order="C")
            return new_r

    def r_prob(self, X_grid):
        # predicting for each x in X_grid
        r = self.predict(X_grid)
        return r

    # def _retrain_loop_par(self, seed):
    #   np.random.seed(seed)
    #  new_w = stats.binom.rvs(n = 1, p = 1 - self.alpha, size = self.w_train.shape[0])
    # new_r = self.retrain(self.X_train, new_w, self.X_test)
    # return np.mean(np.abs(new_r - (1 - self.alpha)))

    def compute_dif(self):
        if self.split_train:
            r = self.predict(self.X_test)
        else:
            r = self.predict(self.X_train)
        t_obs = np.mean(np.abs(r - (1 - self.alpha)))
        t_max = np.max(np.abs(r - (1 - self.alpha)))
        return t_obs, t_max

    def monte_carlo_test(self, B=1000, random_seed=1250, par=False):
        # observed statistic
        t_obs = self.compute_dif()

        # computing monte-carlo samples
        np.random.seed(random_seed)

        # generating new weights from bernoulli
        if not par:
            t_b = np.zeros(B)
            for i in range(B):
                new_w = stats.binom.rvs(
                    n=1, p=1 - self.alpha, size=self.w_train.shape[0]
                )
                new_r = self.retrain(self.X_train, new_w, self.X_test)
                t_b[i] = np.mean(np.abs(new_r - (1 - self.alpha)))
        else:
            ctx = mp.get_context("spawn")
            cpus = mp.cpu_count()
            pool = ctx.Pool(cpus - 1)
            seeds = np.random.randint(1e8, size=B)
            t_b = []
            for seed in seeds:
                result = pool.apply_async(
                    _retrain_loop_par,
                    args=(
                        self.coverage_evaluator,
                        self.model,
                        self.alpha,
                        self.X_train,
                        self.w_train,
                        self.X_test,
                        seed,
                    ),
                )
                t_b.append(result)

            t_b = np.array([result.get() for result in t_b])
            pool.close()
            pool.join()

        # computing p-value from the proportion of generated t's larger than the observed t
        p_value = (t_b > t_obs).mean()
        return {"p-value": p_value, "Observed statistic": t_obs}

    def bootstrap_ci(self, B=1000, sig_b=0.05, random_seed=1250, par=False):
        # computing original
        r = self.predict(self.X_test)
        t_obs = np.mean(np.abs(r - (1 - self.alpha)))

        # computing boostrap samples
        np.random.seed(random_seed)
        # generating statistic array by bootstrap
        if not par:
            t_vec = np.zeros(B)
            for i in range(B):
                new_indexes = np.random.randint(self.X_train.shape[0], size=B)
                new_X_train, new_w_train = (
                    self.X_train[new_indexes, :],
                    self.w_train[new_indexes],
                )
                new_r = self.retrain(new_X_train, new_w_train, self.X_test)
                t_vec[i] = np.mean(np.abs(new_r - (1 - self.alpha)))
        else:
            ctx = mp.get_context("spawn")
            cpus = mp.cpu_count()
            pool = ctx.Pool(cpus - 1)
            seeds = np.random.randint(1e8, size=B)
            t_vec = []
            for seed in seeds:
                result = pool.apply_async(
                    bootstrap_par,
                    args=(
                        B,
                        self.alpha,
                        self.coverage_evaluator,
                        self.model,
                        self.alpha,
                        self.X_train,
                        self.w_train,
                        self.X_test,
                        seed,
                    ),
                )
                t_vec.append(result)

            t_vec = np.array([result.get() for result in t_vec])
            pool.close()
            pool.join()

        # finally obtaining bootstrap CI
        epb = np.sqrt(1 / (B - 1) * np.sum((t_vec - np.mean(t_vec)) ** 2))
        se_int = np.array(
            [
                t_obs - stats.norm.ppf(1 - sig_b / 2) * epb,
                t_obs + stats.norm.ppf(1 - sig_b / 2) * epb,
            ]
        )
        percent_int = np.array(
            [np.quantile(t_vec, sig_b / 2), np.quantile(t_vec, 1 - sig_b / 2)]
        )
        int_boot = {
            "t_obs": t_obs,
            "SE confidence interval": se_int,
            "Percentile interval": percent_int,
        }

        return int_boot


# creating a adapter class to quantile regression in python which outputs a matrix of predictions
class LinearQuantileRegression(BaseEstimator):
    def __init__(
        self,
        coverage=0.05,
        alpha=0,
        fit_intercept=True,
        solver="highs",
        solver_options=None,
    ):
        for prop in dir():
            if prop != "self":
                setattr(self, prop, locals()[prop])
        self.lower = QuantileRegressor()
        self.upper = clone(QuantileRegressor())

    def fit(self, X, y):
        # creating upper and lower fit according to specified coverage
        quantiles = [self.coverage / 2, 1 - self.coverage / 2]
        self.lower.set_params(
            quantile=quantiles[0],
            alpha=self.alpha,
            fit_intercept=self.fit_intercept,
            solver=self.solver,
            solver_options=self.solver_options,
        )
        self.lower.fit(X, y)

        self.upper.set_params(
            quantile=quantiles[1],
            alpha=self.alpha,
            fit_intercept=self.fit_intercept,
            solver=self.solver,
            solver_options=self.solver_options,
        )

        self.upper.fit(X, y)
        return self

    def predict(self, X, **kwargs):
        # predicting for both lower and upper and then concatenating in numpy matrix
        lower = self.lower.predict(X)
        upper = self.upper.predict(X)
        interval = np.vstack((lower, upper)).T
        return interval


# gradient boosting quantile regression for conformal prediction
class GradientBoostingQuantileRegression(BaseEstimator):
    def __init__(self, coverage=0.05, loss="quantile", **kwargs):
        self.coverage = coverage
        self.loss = loss
        quantiles = [self.coverage / 2, 1 - self.coverage / 2]
        self.lower = GradientBoostingRegressor(
            loss=self.loss, alpha=quantiles[0], **kwargs
        )
        self.upper = clone(
            GradientBoostingRegressor(loss=self.loss, alpha=quantiles[1], **kwargs)
        )

    def fit(self, X, y):
        self.lower.fit(X, y)
        self.upper.fit(X, y)
        return self

    def predict(self, X, **kwargs):
        lower = self.lower.predict(X)
        upper = self.upper.predict(X)
        interval = np.vstack((lower, upper)).T
        return interval
