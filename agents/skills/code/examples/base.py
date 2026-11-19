import torch


class Model:
    """X: (n, d) with a constant column already appended, W: (d, 1), y: (n, 1)
    n samples and d - 1 features 
    every model here is  out = f(X W)  fitted by full batch gradient descent
        W <- W - a dJ/dW
    a subclass only has to define f, J and dJ/dW."""

    def __init__(self, lr=0.01, epochs=1000):
        self.lr = lr
        self.epochs = epochs
        self.W = None
        self.history = []

    def train(self, X, y, X_val=None, y_val=None, log_every=None):
        if self.W is None:
            self.W = torch.zeros((X.shape[1], 1), dtype=X.dtype, device=X.device)

        for epoch in range(self.epochs):
            out = self.forward(X)
            train_loss = self.loss(y, out).item()
            self.W -= self.lr * self.grad(X, y, out)

            # same J, the held out X_val instead of X: it stops falling once we overfit
            val_loss = None if X_val is None else self.loss(y_val, self.forward(X_val)).item()
            self.history.append((train_loss, val_loss))
            if log_every and epoch % log_every == 0:
                print(f"Epoch {epoch} | Loss: {train_loss:.4f}" + ("" if val_loss is None else f" | Val loss: {val_loss:.4f}"))
        return self

    def forward(self, X):
        raise NotImplementedError

    def loss(self, y, out):
        raise NotImplementedError

    # out is the forward pass already computed for this step
    def grad(self, X, y, out):
        raise NotImplementedError

    def predict(self, X):
        return self.forward(X)

    def score(self, X, y):
        raise NotImplementedError

    # gradient descent on a quadratic contracts by (1 - a lam) along each eigen
    # direction of the Hessian, so it converges only while |1 - a lam| < 1
    #   0 < a < 2 / lam_max
    def max_lr(self, X):
        raise NotImplementedError


def accuracy(y_true, y_pred):
    return (y_pred == y_true).float().mean().item()
