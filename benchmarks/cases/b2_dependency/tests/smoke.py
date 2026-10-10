import yaml
import sys
import numpy as np

def main():
    try:
        with open('configs/default.yaml', 'r') as f:
            config = yaml.safe_load(f)
        assert 'learning_rate' in config
        assert 'epochs' in config
        
        data = np.genfromtxt('data/digits.csv', delimiter=',', skip_header=1)
        assert data.shape[1] == 65
        print("Smoke test passed")
        sys.exit(0)
    except Exception as e:
        print(f"Smoke test failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
