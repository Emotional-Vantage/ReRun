import os
from sklearn.datasets import load_digits

def export_digits():
    digits = load_digits(as_frame=True)
    df = digits.frame
    os.makedirs('benchmarks/template/data', exist_ok=True)
    df.to_csv('benchmarks/template/data/digits.csv', index=False)
    print("Exported digits.csv")

if __name__ == '__main__':
    export_digits()
