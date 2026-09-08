import pytest
from app.api.demo import router
from demo.seed_demo import create_demo_pdfs

def test_create_demo_pdfs(tmp_path):
    doc1, doc2, doc3 = create_demo_pdfs()
    assert doc1.exists()
    assert doc2.exists()
    assert doc3.exists()
    assert doc1.stat().st_size > 0


def test_four_demo_cases_schema():
    from app.api.demo import get_demo_cases
    res = get_demo_cases()
    cases = res["cases"]
    assert len(cases) == 4
    
    # Case 1: Corroboration
    c1 = cases[0]
    assert c1["category"] == "corroborates"
    assert "740" in c1["fact_a"]["value"]
    assert "740" in c1["fact_b"]["value"]
    assert c1["fact_a"]["bbox"] is not None

    # Case 2: Contradiction
    c2 = cases[1]
    assert c2["category"] == "contradicts"
    assert "31,200" in c2["fact_a"]["value"]
    assert "27,450" in c2["fact_b"]["value"]

    # Case 3: Reconciled
    c3 = cases[2]
    assert c3["category"] == "reconciled"
    assert "Q4" in c3["fact_a"]["time_scope"]
    assert "Full Year" in c3["fact_b"]["time_scope"]

    # Case 4: Failure case
    c4 = cases[3]
    assert c4["category"] == "failure_case"
    assert "Exact quote verification" in c4["how_we_handled_it"]
    assert "Substring Verification Guard" in c4["observed_failure"]["system_detection"]
    assert "hallucination" in c4["observed_failure"]["system_detection"].lower()
