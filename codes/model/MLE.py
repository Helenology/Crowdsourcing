#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/2/19 18:12
# @Author  : Helenology
# @Site    : 
# @File    : MLE.py
# @Software: PyCharm

import numpy as np
from numpy.linalg import norm
import copy
from scipy.optimize import minimize


class MLE:
    def __init__(self, X, Y, A, K, initial_beta, initial_sigma):
        self.n = X.shape[0]
        self.p = X.shape[1]
        self.M = Y.shape[1]
        self.K = K
        # data preparation
        self.X = X
        self.XXT = self.compute_XXT()
        self.Y = Y
        self.Y_onehot = self.compute_Y_onehot()  # (n, K, M)
        self.A = A
        # parameter initialization
        self.beta = initial_beta                           # (K, p)
        self.sigma = initial_sigma                         # (M,)
        self.theta = np.ones((self.K * self.p + self.M,))  # (pK+M,)
        self.theta[0:(self.K * self.p)] = self.beta.ravel()
        self.theta[(self.K * self.p):] = self.sigma
        # optimization initialization
        self.gradient = None
        self.Hessian = None
        self.steps = 0
        self.likelihood_list = [-np.Inf]

    def compute_XXT(self):
        """Compute $X_i X_i^\top$ for $1 \leq i \leq n$"""
        XXT = (self.X.reshape(self.n, self.p, 1)) * (self.X.reshape(self.n, 1, self.p))
        return XXT

    def compute_likelihood(self):
        p_ikm = np.zeros((self.n, (self.K+1), self.M))  # (n, (K+1), M)
        p_ikm[:, 1:] = self.compute_pikm()
        p_ikm[:, 0] = 1 - p_ikm[:, 1:].sum(axis=1)      #
        p_ikm += 1e-10
        p_ikm /= p_ikm.sum(axis=1, keepdims=True)
        Y_onehot = np.ones((self.n, (self.K+1), self.M))
        for k in range(self.K):
            Y_onehot[:, k, :] = (self.Y == k).astype(int)
        likelihood = self.A.reshape(self.n, 1, self.M) * Y_onehot * np.log(p_ikm)
        likelihood = likelihood.sum() / self.n
        return likelihood

    def compute_Y_onehot(self):
        Y_onehot = np.ones((self.n, self.K, self.M))
        Y_onehot *= self.Y.reshape(self.n, 1, self.M)
        for k in range(self.K):
            Y_onehot[:, k, :] = (Y_onehot[:, k, :] == (k + 1)).astype(int)
        return Y_onehot

    def copy_beta_sigma(self):
        beta = self.theta[0:(self.p * self.K)].reshape(self.K, self.p)
        sigma = self.theta[(self.p * self.K):]
        return beta, sigma

    def compute_pikm(self):
        value_ik = self.X.dot(np.transpose(self.beta)).reshape(self.n, self.K, 1)
        value_ikm = value_ik / self.sigma.reshape(1, 1, self.M)
        value_ikm = np.exp(value_ikm)
        value_sum = value_ikm.sum(axis=1, keepdims=True) + 1  # +1 due to class 0
        p_ikm = value_ikm / value_sum
        return p_ikm
    #
    # def GA_alg(self, max_steps=100, epsilon=1e-5, eta=0.01, lbd=0.01):
    #     """Gradient ascending"""
    #     while True:
    #         self.steps += 1
    #         likelihood = self.compute_likelihood()
    #         self.likelihood_list.append(likelihood)
    #         # gradient
    #         self.gradient = self.derivative_calcu(order=1) / self.n
    #         # penalty for $\|B^\top B\| = 1$
    #         penalty = np.zeros_like(self.gradient)
    #         penalty[0:(self.p * self.K)] = -(lbd * 2) * self.beta.ravel()
    #         # update theta
    #         self.theta = self.theta + eta * self.gradient + penalty  # Maximum it because MLE
    #         self.beta, self.sigma = self.copy_beta_sigma()
    #         # calculate difference
    #         theta_diff = norm(eta * self.gradient + penalty)
    #         # print(f"[step {self.steps}] with likelihood: {likelihood:.6f}; theta diff: {theta_diff: .6f}")
    #         if (theta_diff < epsilon) or (self.steps > max_steps) or \
    #                 np.isnan(theta_diff) or (likelihood < self.likelihood_list[-2]):
    #             break
    #     self.beta, self.sigma = self.copy_beta_sigma()

    def NR_alg(self, max_steps=10, epsilon=1e-5, lbd=0.1):
        while True:
            self.steps += 1
            likelihood = self.compute_likelihood()
            self.likelihood_list.append(likelihood)
            # print(f"[step {self.steps}] with likelihood: {likelihood: .6f}")
            # gradient & Hessian
            self.gradient, self.Hessian = self.derivative_calcu(order=2)
            self.gradient /= self.n
            self.Hessian /= self.n
            # update theta
            theta_diff = -np.linalg.inv(self.Hessian) @ self.gradient
            self.theta = self.theta + theta_diff
            self.beta, self.sigma = self.copy_beta_sigma()
            diff_norm = norm(theta_diff)
            print(f"[Step {self.steps}] theta difference norm:{diff_norm:.5f}")

            # terminal condition
            if (diff_norm < epsilon) or (self.steps > max_steps) \
                    or (np.isnan(diff_norm)) or (likelihood < self.likelihood_list[-2]):
                break
        self.beta, self.sigma = self.copy_beta_sigma()
        return self.beta.ravel(), self.sigma

    def compute_A_diff(self):
        self.p_ikm = self.compute_pikm()       # (n, K, M)
        diff = self.Y_onehot - self.p_ikm      # (n, K, M)
        A = self.A.reshape(self.n, 1, self.M)  # (n, 1, M)
        A_diff = A * diff                      # (n, K, M)
        return A_diff                          # (n, K, M)

    def derivative_calcu(self, order=1):
        ##################################### 1st derivative #####################################
        # partial beta
        A_diff = self.compute_A_diff()
        delta = A_diff / self.sigma.reshape(1, 1, self.M)  # (n, K, M)
        delta = delta.sum(axis=2)                          # (n, K)
        partial_beta = np.transpose(delta) @ self.X        # (K, n) @ (n, p) = (K, p)

        # partial sigma
        partial_sigma = -A_diff / self.sigma.reshape(1, 1, self.M) ** 2  # (n, K, M)
        partial_sigma *= (self.X @ np.transpose(self.beta)).reshape((self.n, self.K, 1))  # (n, K, 1)
        partial_sigma = partial_sigma.sum(axis=(0, 1))  # (M,)

        # gradient
        gradient = np.zeros_like(self.theta)
        gradient[:(self.K * self.p)] = partial_beta.ravel()
        gradient[(self.K * self.p):] = partial_sigma
        if order == 1:
            return gradient

        ##################################### 2st derivative #####################################
        A11 = np.zeros((self.K * self.p, self.K * self.p))  # partial beta^2: (pK, pK)
        A22 = -2 * partial_sigma / self.sigma               # partial sigma^2 (M, 1)
        # A12 = np.zeros((self.K * self.p, self.M))         # partial beta partial sigma (pK, M)
        for j in range(self.K):
            for k in range(self.K):
                App = int(j == k) * (self.p_ikm[:, j, :]) - self.p_ikm[:, j, :] * self.p_ikm[:, k, :]  # (n, M)
                App = self.A * App                                                   # (n, M)
                Sigma_jk = -App / (self.sigma.reshape((1, self.M))**2)               # (n, M)
                Sigma_jk = Sigma_jk.reshape((self.n, self.M, 1, 1))                  # (n, M, 1, 1)
                Sigma_jk = Sigma_jk * self.XXT.reshape((self.n, 1, self.p, self.p))  # (n, M, p, p)
                # A11
                A11[(j * self.p):((j+1) * self.p), (k * self.p):((k+1) * self.p)] = Sigma_jk.sum(axis=(0, 1))  # (p, p)
                # A22 & A12
                Sigma_jk = Sigma_jk.sum(axis=0)  # (M, p, p)
                for m in range(self.M):
                    A22[m] += self.beta[j] @ Sigma_jk[m] @ self.beta[k] / self.sigma[m] ** 2
                    # A12[(j * self.p):((j+1) * self.p), m] -= Sigma_jk[m] @ self.beta[k] / self.sigma[m]**1

        # delta = A_diff / self.sigma.reshape(1, 1, self.M)**2  # (n, K, M)
        # for m in range(self.M):
        #     delta_m = np.transpose(delta[:, :, m])            # (K, n)
        #     A12[:, m] -= (delta_m @ self.X).ravel()           # (K, p)-> (pK,)
        matrix = np.zeros((self.K * self.p + self.M, self.K * self.p + self.M))
        matrix[:(self.K * self.p), :(self.K * self.p)] = A11
        matrix[(self.K * self.p):, (self.K * self.p):] = np.diag(A22)
        # matrix[:(self.K * self.p), (self.K * self.p):] = A12
        # matrix[(self.K * self.p):, :(self.K * self.p)] = np.transpose(A12)
        return gradient, matrix




