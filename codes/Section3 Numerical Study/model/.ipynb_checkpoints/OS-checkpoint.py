#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/7/8 23:49
# @Author  : Helenology
# @Site    : 
# @File    : OS.py
# @Software: PyCharm

import os
import sys
import numpy as np
import time
from sklearn.metrics import mean_squared_error
from statsmodels.discrete.discrete_model import Probit
import copy
sys.path.append(os.path.abspath('../'))
sys.path.append(os.path.abspath('../data/'))
sys.path.append(os.path.abspath('../model/'))
from synthetic_dataset import *  # codes to generate a synthetic dataset
from synthetic_annotators import *
from utils import *


class OS:
    def __init__(self, X, Y, A):
        self.X = X
        self.Y = Y
        self.A = A
        self.n = X.shape[0]
        self.p = X.shape[1]
        self.M = Y.shape[1]
        # beta initialization
        self.beta_initial = None
        self.beta_hat = None
        self.initialize_beta()
        # sigma initialization
        self.sigma_initial = None
        self.sigma_hat = None
        self.initialize_sigma()
        print(f"================= OS Algorithm =================")

    def initialize_beta(self):
        A1 = self.A[:, 0]
        Y1 = self.Y[A1 == 1, 0]
        X1 = self.X[A1 == 1, :]
        model = Probit(Y1, X1)
        probit_model = model.fit(disp=0)
        # print(probit_model.summary())
        beta_hat = probit_model.params.reshape(-1, 1)
        self.beta_initial = beta_hat
        self.beta_hat = copy.copy(beta_hat)

    def initialize_sigma(self):
        self.sigma_initial = np.ones(self.M)
        Z = self.X.dot(self.beta_hat)
        for annotator_index in range(1, self.M):
            Ai = self.A[:, annotator_index]
            Yi = self.Y[Ai == 1, annotator_index]
            Zi = Z[Ai == 1]
            probit_model = Probit(Yi, Zi)
            model_outcome = probit_model.fit(disp=0)
            self.sigma_initial[annotator_index] = 1 / model_outcome.params[0]
        self.sigma_hat = copy.copy(self.sigma_initial)

    def update_beta(self):
        U = np.dot(self.X, self.beta_hat) / self.sigma_hat
        phi, Phi, Phi_minus = compute_phi_Phi(U)
        phi_dot = phi_dot_function(U)
        Delta = (self.Y - Phi) / Phi / Phi_minus
        rho, rho_minus = rho_function(phi, Phi, Phi_minus)

        # update beta - hessian inverse
        tmp_hess = self.A * (Delta * phi_dot - (Delta * phi)**2) / (self.sigma_hat**2)
        tmp_hess = tmp_hess.sum(axis=1).reshape(self.n, 1)
        tmp_hess = self.X.transpose().dot(self.X * tmp_hess)
        tmp_hess_inv = np.linalg.inv(tmp_hess)

        # update beta - score
        tmp_score = self.A * (self.Y * rho - (1 - self.Y) * rho_minus) / self.sigma_hat
        tmp_score = tmp_score.sum(axis=1).reshape(self.n, 1)
        tmp_score = self.X * tmp_score
        tmp_score = tmp_score.sum(axis=0)

        # update beta
        new_beta_hat = self.beta_hat - tmp_hess_inv.dot(tmp_score).reshape(-1, 1)
        beta_mse = mean_squared_error(new_beta_hat, self.beta_hat)
        self.beta_hat = new_beta_hat
        return beta_mse

    def update_sigma(self):
        U = np.dot(self.X, self.beta_hat) / self.sigma_hat
        phi, Phi, Phi_minus = compute_phi_Phi(U)
        phi_dot = phi_dot_function(U)
        Delta = (self.Y - Phi) / Phi / Phi_minus
        rho, rho_minus = rho_function(phi, Phi, Phi_minus)

        # update sigma - first item
        tmp_1 = self.A * U * (self.Y * rho - (1 - self.Y) * rho_minus) / (self.sigma_hat ** 2)
        tmp_1 = 2 * tmp_1.sum(axis=0)

        # update sigma - second item
        tmp_2 = self.A * U ** 2 * (Delta * phi_dot - (Delta * phi) ** 2) / (self.sigma_hat ** 2)
        tmp_2 = tmp_2.sum(axis=0)

        # update sigma - third item
        tmp_3 = self.A * U * (- self.Y * rho + (1 - self.Y) * rho_minus) / self.sigma_hat
        tmp_3 = tmp_3.sum(axis=0)

        # update sigma
        new_sigma_hat = self.sigma_hat - 1 / (tmp_1 + tmp_2) * tmp_3
        new_sigma_hat[0] = 1
        sigma_mse = mean_squared_error(self.sigma_hat[1:], new_sigma_hat[1:])
        self.sigma_hat = new_sigma_hat

        return sigma_mse

    def OS_algorithm(self):
        beta_mse = self.update_beta()
        print(f"update_beta: beta mse({beta_mse:.4f})")
        sigma_mse = self.update_sigma()
        print(f"update_sigma: sigma mse({sigma_mse:.4f})")


if __name__ == '__main__':
    N = 1000000
    p = 20
    M = 50
    seed = 0
    np.random.seed(seed)  # set random seed
    np.set_printoptions(precision=3)  # 设置小数位置为3位

    beta_star = np.ones(p)  # the true parameter of interest
    sigma_star = np.ones(M)
    # sigma_star[1:] *= np.arange(start=0.1, stop=10.1, step=(10 / M))[:(-1)]
    sigma_star[1:int(M / 2)] *= 0.1
    sigma_star[int(M / 2):] *= 10
    print(f"true beta: {beta_star}")
    print(f"true sigma: {sigma_star}")
    X, Y_true = construct_synthetic_dataset(N, p, beta_star, seed=0)  # generate synthetic dataset
    alpha_list = [0.1] * M
    A_annotation, Y_annotation = synthetic_annotation(X, beta_star, M, sigma_star, alpha_list, seed=seed)

    t1 = time.time()
    os = OS(X, Y_annotation, A_annotation)
    os.OS_algorithm()
    t2 = time.time()
    print("=================================")
    print(f"Time: {t2 - t1:.4f}")
    print("------------- beta --------------")
    print(f"true beta: {beta_star}")
    print(f"estimate beta: {os.beta_hat.reshape(-1)}")
    print(f"final MSE: {mean_squared_error(beta_star, os.beta_hat):.6f}")
    print("------------- sigma -------------")
    print(f"true sigma: {sigma_star}")
    print(f"estimate sigma: {os.sigma_hat}")
    print(f"final MSE: {mean_squared_error(sigma_star, os.sigma_hat):.6f}")