import math
from agent.state import Claim, Tolerance
from tools.compare import compare

def test_compare_abs_within():
    c = Claim(id="c1", statement="x", metric="m", reported=0.90, source_ref="p", source_quote="x")
    c.tolerance = Tolerance(type="abs", value=0.01)
    res = compare(c, 0.905)
    assert res["within_tolerance"] is True

def test_compare_abs_outside():
    c = Claim(id="c1", statement="x", metric="m", reported=0.90, source_ref="p", source_quote="x")
    c.tolerance = Tolerance(type="abs", value=0.01)
    res = compare(c, 0.88)
    assert res["within_tolerance"] is False

def test_compare_rel_within():
    c = Claim(id="c1", statement="x", metric="m", reported=100.0, source_ref="p", source_quote="x")
    c.tolerance = Tolerance(type="rel", value=0.05)
    res = compare(c, 96.0)
    assert res["within_tolerance"] is True

def test_compare_missing_nan():
    c = Claim(id="c1", statement="x", metric="m", reported=0.90, source_ref="p", source_quote="x")
    assert compare(c, None)["within_tolerance"] is None
    assert compare(c, float('nan'))["within_tolerance"] is None
