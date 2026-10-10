import json
from pathlib import Path
import pymupdf

def test_registry_cases_structure():
    reg_path = Path("benchmarks/registry.json")
    assert reg_path.exists()
    
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)
        
    cases = registry.get("cases", [])
    assert len(cases) == 5
    case_ids = [c["id"] for c in cases]
    assert case_ids == ["b1_control", "b2_dependency", "b3_silent_config", "b4_combined", "b5_unable"]

    required_files = [
        "train.py", "model.py", "data.py", "evaluate.py",
        "requirements.txt", "README.md", "configs/default.yaml",
        "data/digits.csv", "tests/smoke.py"
    ]

    for case in cases:
        case_dir = Path(case["case_path"])
        assert case_dir.is_dir(), f"Case directory missing: {case_dir}"
        for rf in required_files:
            file_path = case_dir / rf
            assert file_path.exists(), f"File {rf} missing in {case_dir}"

        gold_path = Path(case["gold_path"])
        assert gold_path.exists(), f"Gold file missing: {gold_path}"
        with open(gold_path, "r", encoding="utf-8") as gf:
            gold_data = json.load(gf)
            assert gold_data["case_id"] == case["id"]
            assert "expected_status" in gold_data

def test_paper_pdf_extractable():
    pdf_path = Path("benchmarks/papers/digits_softmax.pdf")
    assert pdf_path.exists()
    
    doc = pymupdf.open(str(pdf_path))
    assert len(doc) >= 1
    text = doc[0].get_text()
    assert "Softmax Regression on Digits Dataset" in text
    assert "test accuracy of 0.956" in text
    assert "learning rate = 0.5" in text
    assert "Table 1" in text

def test_adversarial_fixtures():
    adv_dir = Path("benchmarks/adversarial")
    assert adv_dir.is_dir()
    fixtures = list(adv_dir.glob("x*.json"))
    assert len(fixtures) == 9
    
    for fix in fixtures:
        with open(fix, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "id" in data
        assert "proposal" in data
        assert "expected_block_layer" in data
        assert data["expected_block_layer"] in ["policy", "critic"]
