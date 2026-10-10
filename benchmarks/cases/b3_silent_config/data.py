import numpy as np

def load_digits_csv(path):
    data = np.genfromtxt(path, delimiter=',', skip_header=1)
    X = data[:, :-1]
    y = data[:, -1].astype(int)
    # Scale features to [0,1]
    X = X / 16.0
    return X, y

def split(X, y, test_size, split_seed):
    rng = np.random.default_rng(split_seed)
    indices = np.arange(len(X))
    rng.shuffle(indices)
    
    split_idx = int(len(X) * (1 - test_size))
    train_idx = indices[:split_idx]
    test_idx = indices[split_idx:]
    
    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]
