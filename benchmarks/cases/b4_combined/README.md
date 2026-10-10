# Digits Softmax Regression

This is a synthetic codebase for evaluating agentic reproduction tools.

## Setup
```bash
pip install -r requirements.txt
```

## Running
Example run with the learning rate from the paper:
```bash
python train.py --config configs/default.yaml
```

Snippet from config:
```yaml
learning_rate: 0.5
epochs: 20
```
