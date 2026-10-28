import pytest

from ask_my_data.grading import extract_numbers, grade, matches_number


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Revenue was $5.62M last year", 5_620_000),
        ("We received 5,499 orders", 5499),
        ("Conversion is 26.4% of sessions", 26.4),
        ("AOV is $85.97", 85.97),
        ("about 330K from Spain", 330_000),
    ],
)
def test_extract_numbers(text, expected):
    assert any(abs(n - expected) < 1e-6 for n in extract_numbers(text))


def test_suffix_not_confused_with_words():
    # "5 months" must not become 5 million
    assert 5_000_000 not in extract_numbers("over 5 months")


def test_matches_rounded_answers():
    assert matches_number("Search drove $5.62M", 5_623_417.73, 0.01)[0]
    assert matches_number("about 26.4%", 26.3626, 0.01)[0]
    assert not matches_number("AOV is $85.51", 85.97, 0.005)[0]


def test_exact_count_requires_exact_match():
    assert matches_number("5,499 orders", 5499, 0.0)[0]
    assert not matches_number("5,500 orders", 5499, 0.0)[0]


def test_grade_flags_forbidden_sql():
    case = {
        "id": "aov",
        "check": "number",
        "rel_tol": 0.005,
        "forbid_sql": [r"(order_items|\boi)\.created_at\s*(<|>|<=|>=|between)"],
    }
    queries = [{"ok": True, "sql": "SELECT ... WHERE oi.created_at <= CURRENT_TIMESTAMP()"}]
    g = grade(case, "AOV is $85.97", queries, 85.97)
    assert not g.passed and "forbidden" in g.reasons[0]


def test_grade_refusal():
    case = {"id": "c", "check": "refusal", "refusal_phrases": ["no campaign"]}
    assert grade(case, "There is no campaign data in this dataset.", [], None).passed
    assert not grade(case, "Campaign A made $10K.", [], None).passed
