import argparse
import json
import os
import yaml
import numpy as np

from data import load_digits_csv, split
from model import SoftmaxRegression
from evaluate import accuracy

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    if args.learning_rate is not None:
        config['learning_rate'] = args.learning_rate
    if args.epochs is not None:
        config['epochs'] = args.epochs
    if args.batch_size is not None:
        config['batch_size'] = args.batch_size

    X, y = load_digits_csv('data/digits.csv')
    X_train, X_test, y_train, y_test = split(X, y, config['test_size'], config['split_seed'])

    results = {
        "seeds": config['seeds'],
        "test_accuracy_per_seed": []
    }

    for seed in config['seeds']:
        model = SoftmaxRegression(seed=seed)
        model.train(
            X_train, y_train, 
            learning_rate=config['learning_rate'],
            epochs=config['epochs'],
            batch_size=config['batch_size'],
            l2=config['l2']
        )
        preds = model.predict(X_test)
        acc = accuracy(y_test, preds)
        results["test_accuracy_per_seed"].append(float(acc))
        print(f"Seed {seed}: accuracy {acc:.4f}")

    results["test_accuracy_mean"] = float(np.mean(results["test_accuracy_per_seed"]))
    results["test_accuracy_std"] = float(np.std(results["test_accuracy_per_seed"]))

    os.makedirs('outputs', exist_ok=True)
    with open('outputs/results.json', 'w') as f:
        json.dump(results, f, indent=2)
    with open('outputs/effective_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print(f"test_accuracy_mean={results['test_accuracy_mean']:.4f}")

if __name__ == '__main__':
    main()
