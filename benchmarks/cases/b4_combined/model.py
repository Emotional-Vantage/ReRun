import numpy as np

def softmax(z):
    z = z - np.max(z, axis=1, keepdims=True)
    exp_z = np.exp(z)
    return exp_z / np.sum(exp_z, axis=1, keepdims=True)

class SoftmaxRegression:
    def __init__(self, seed, num_classes=10):
        self.rng = np.random.default_rng(seed)
        self.num_classes = num_classes
        self.W = None
        self.b = None
        
    def train(self, X, y, learning_rate, epochs, batch_size, l2):
        num_samples, num_features = X.shape
        self.W = self.rng.standard_normal((num_features, self.num_classes)) * 0.01
        self.b = np.zeros(self.num_classes)
        
        Y = np.zeros((num_samples, self.num_classes))
        Y[np.arange(num_samples), y] = 1
        
        for epoch in range(epochs):
            indices = np.arange(num_samples)
            self.rng.shuffle(indices)
            for start_idx in range(0, num_samples, batch_size):
                batch_idx = indices[start_idx:start_idx + batch_size]
                X_batch = X[batch_idx]
                Y_batch = Y[batch_idx]
                
                z = np.dot(X_batch, self.W) + self.b
                probs = softmax(z)
                
                dz = probs - Y_batch
                dW = np.dot(X_batch.T, dz) / len(batch_idx) + l2 * self.W
                db = np.sum(dz, axis=0) / len(batch_idx)
                
                self.W -= learning_rate * dW
                self.b -= learning_rate * db
                
    def predict(self, X):
        z = np.dot(X, self.W) + self.b
        return np.argmax(softmax(z), axis=1)
