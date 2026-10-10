from tools.errors import classify

def test_classify_gpu():
    log = "some log\nTorch not compiled with CUDA\nend"
    res = classify(log)
    assert res["error_class"] == "gpu_required"
    assert res["signature_id"] == "gpu-cuda"

def test_classify_modnotfound():
    log = "Traceback...\nModuleNotFoundError: No module named 'yaml'"
    res = classify(log)
    assert res["error_class"] == "dependency_missing"
    assert res["signature_id"] == "modnotfound"

def test_classify_unknown():
    log = "just a normal crash\nValueError: something bad"
    res = classify(log)
    assert res["error_class"] == "unknown"
