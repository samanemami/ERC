# Author: Seyedsaman Emami
# Licence: GNU Lesser General Public License v2.1 (LGPL-2.1)

import copy
import random
from tabnanny import verbose
import numpy as np
from Base import _base
from sklearn.base import clone
from sklearn.model_selection import KFold
from sklearn.metrics import mean_squared_error


class erc(_base.BaseEstimator):
    def __init__(self,
                 *,
                 model,
                 cv,
                 direct,
                 seed,
                 verbose,
                 chain=1,
                 ):

        super().__init__(model=model,
                         cv=cv,
                         direct=direct,
                         seed=seed,
                         verbose=verbose)

        self.chain = chain

    """ Ensemble of Regressor Chains


    parameters
    ------------
    chain : int, default=1,
        The number of Ensemble chains.
        If the chain is equal to 1, the model 
        returns the RC model.

    """

    def _fit_chain(self, X, y, chain):

        kfold = KFold(n_splits=self.cv,
                      shuffle=True,
                      random_state=self.seed)

        pred = np.zeros_like(y)

        models = np.empty((self.n,), dtype=object)
        permutation = self.permutation[:, chain]

        for i, perm in enumerate(permutation):

            # Build a new variable and deep copy the object
            exec(f'model_{perm} = clone(self.model)')
            exec(f'model_{perm}.fit(X, y[:, perm])')
            # Save the trained model as a binary object in the NumPy array
            exec(f'models[perm] = model_{perm}')

            if i+1 == len(permutation):
                break

            for (train_index, test_index) in kfold.split(X, y):
                x_train, x_test = X[train_index], X[test_index]
                y_train, y_test = y[train_index], y[test_index]

                model_ = clone(self.model)
                model_.fit(x_train, y_train[:, perm])

                # meta-variable generation
                if not self.direct:
                    pred[test_index, perm] = model_.predict(x_test)
                else:
                    pred[train_index, perm] = model_.predict(x_train)

            X = np.append(X, pred[:, perm][:, np.newaxis], axis=1)

        return models

    def fit(self, X, y):

        n = random.randint(0, 100)
        np.random.seed(n)

        self.n = y.shape[1]
        # Chains include RC models
        self.chains = []
        self.permutation = np.zeros(
            (self.n, self.chain), dtype=np.int32)
        for chain in range(self.chain):
            if self.verbose and self.chain > 1:
                self.ProgressBar((chain/np.abs(self.chain-1)), self.chain)
            self.permutation[:, chain] = np.random.permutation(self.n)
            self.chains.append(copy.deepcopy(self._fit_chain(X, y, chain)))
        return self

    def predict(self, X):
        pred = np.zeros((X.shape[0], self.n))
        for i, chain in enumerate(self.chains):
            pred_ = np.zeros_like(pred)
            permutation = self.permutation[:, i]
            XX = X
            for p, perm in enumerate(permutation):
                model = chain[perm]
                pred_[:, perm] = model.predict(XX)
                XX = np.append(XX, pred_[:, perm][:, np.newaxis], axis=1)
                if p+1 == len(permutation):
                    break
            pred += pred_

        # The final prediction is equal to the 
        #   mean of the k chains for each target.
        return (pred)/(self.chain)

    def _get_permutation(self):
        return self.permutation


class sst(_base.BaseEstimator):
    def __init__(self,
                 *,
                 model,
                 cv,
                 direct,
                 seed,
                 verbose
                 ):
        super().__init__(model=model,
                         cv=cv,
                         direct=direct,
                         seed=seed,
                         verbose=verbose)

    """ Stacked single-target"""

    def fit(self, X, y):

        np.random.seed(self.seed)

        self.n = y.shape[1]
        kfold = KFold(n_splits=3,
                      shuffle=True,
                      random_state=self.seed
                      )

        pred = np.zeros_like(y)
        self.models = np.empty((self.n, 2), dtype=object)

        # 1st training stage
        for i in range(self.n):

            exec(f'model_{i} = clone(self.model)')
            exec(f'self.models[i, 0] = model_{i}.fit(X, y[:, i])')

            for (train_index, test_index) in (kfold.split(X, y)):

                x_train, x_test = X[train_index], X[test_index]
                y_train, y_test = y[train_index], y[test_index]

                model = clone(self.model)

                model.fit(x_train, y_train[:, i])

                # meta-variable generation
                if not self.direct:
                    # Returns the cv model
                    pred[test_index, i] = model.predict(x_test)
                else:
                    # Returns the true model
                    pred[train_index, i] = model.predict(x_train)

            self.score_ = mean_squared_error(y, pred)

        # 2nd training stage
        for i in range(self.n):
            if self.verbose and self.n > 1:
                self.ProgressBar((i/np.abs((self.n)-1)), self.n)
            XX = np.append(X, np.delete(pred, i, 1), axis=1)
            exec(f'model_{i} = clone(self.model)')
            exec(f'self.models[i, 1] = model_{i}.fit(XX, y[:, i])')

        return self

    def predict(self, X):

        # Use the save model
        pred_ = np.zeros((X.shape[0], self.n))
        pred = np.zeros_like(pred_)

        for i in range(self.n):
            model = self.models[i, 0]
            pred_[:, i] = model.predict(X)
        self.pred = pred_

        for i in range(self.n):
            XX = np.append(X, np.delete(pred_, i, 1), axis=1)
            model = self.models[i, 1]
            pred[:, i] = model.predict(XX)

        return pred

    def _get_intrain_score(self):
        return self.score_

    def _get_first_stage_pred(self):
        return self.pred
