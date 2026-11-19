import math

import torch

from .base import Model, accuracy


class LogisticRegression(Model):
    """z = X W                          logits
    p = sigma(z) = 1 / (1 + e^-z)       P(y = 1 | x)"""

    eps = 1e-9

    def forward(self, X):
        z = X @ self.W
        return 1 / (1 + torch.exp(-z))

    # J = -mean( y log p + (1-y) log(1-p) )
    def loss(self, y, p):
        return -torch.mean(y * torch.log(p + self.eps) + (1 - y) * torch.log(1 - p + self.eps))

    # dJ/dp = -( y/p - (1-y)/(1-p) ) / n = (p - y) / (n p(1-p))
    # dp/dz = e^-z / (1 + e^-z)^2 = p (1 - p)          sigmoid derivative
    # dJ/dz = dJ/dp dp/dz = (p - y) / n                p(1-p) cancels
    # dJ/dW = X.T dJ/dz = X.T (p - y) / n
    def grad(self, X, y, p):
        return X.T @ (p - y) / X.shape[0]

    def predict(self, X, threshold=0.5):
        return (self.forward(X) >= threshold).float()

    def score(self, X, y):
        return accuracy(y, self.predict(X))

    # H = X.T diag(p(1-p)) X / n  and  p(1-p) <= 1/4  ->  lam_max <= lam_max(X.T X / n) / 4
    # so the quadratic bound 2 / lam_max loosens to 8 / lam_max(X.T X / n)
    def max_lr(self, X):
        lam = torch.linalg.eigvalsh(X.T @ X / X.shape[0]).max()
        return (8 / lam).item()


class WeightedLogisticRegression(LogisticRegression):
    """same logistic regression, but every point's log loss is scaled by a weight for its class
    c_i = n / (2 n_class)    ->    each class carries half the loss (sklearn's class_weight='balanced')
    it acts like copying every click c_pos / c_neg times, so p is pushed up and stops being the real click rate"""

    def weights(self, y):
        n, n_pos = len(y), y.sum()
        self.c_pos = (n / (2 * n_pos)).item()
        self.c_neg = (n / (2 * (n - n_pos))).item()

    def train(self, X, y, X_val=None, y_val=None, log_every=None):
        self.weights(y)
        return super().train(X, y, X_val, y_val, log_every)

    def c(self, y):
        return torch.where(y > 0, self.c_pos, self.c_neg)

    # J = -mean( c [y log p + (1-y) log(1-p)] )
    def loss(self, y, p):
        ll = y * torch.log(p + self.eps) + (1 - y) * torch.log(1 - p + self.eps)
        return -torch.mean(self.c(y) * ll)

    # same chain rule as LogisticRegression, each point now pulls with strength c
    # dJ/dW = X.T (c (p - y)) / n
    def grad(self, X, y, p):
        return X.T @ (self.c(y) * (p - y)) / X.shape[0]

    # H = X.T diag(c p(1-p)) X / n  ->  lam_max <= max(c) lam_max(X.T X / n) / 4  ->  a < 8 / (max(c) lam_max)
    # needs y because c comes from the labels
    def max_lr(self, X, y):
        self.weights(y)
        return super().max_lr(X) / max(self.c_pos, self.c_neg)

    # the bias row of dJ/dW = 0 gives  sum c (p - y) = 0, so the weighted mean of p is 1/2, not the real ctr
    # in odds the weights only rescale:  p_w / (1 - p_w) = (c_pos / c_neg) p / (1 - p)
    # so  z - log(c_pos / c_neg)  is the unweighted logit again (exact when the model is right)
    def forward_unweighted(self, X):
        z = X @ self.W - math.log(self.c_pos / self.c_neg)
        return 1 / (1 + torch.exp(-z))
