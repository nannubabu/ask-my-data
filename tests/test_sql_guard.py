import pytest

from ask_my_data.sql_guard import UnsafeQueryError, check_read_only

SAFE = [
    "SELECT 1",
    "select status, count(*) from `bigquery-public-data.thelook_ecommerce.orders` group by status",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t;",
    "SELECT * FROM t WHERE note = 'please DELETE me; DROP TABLE x'",  # keywords inside a string
    "-- monthly revenue\nSELECT created_at FROM orders",  # 'created_at' contains CREATE but isn't the keyword
    "SELECT * EXCEPT (email) FROM users",
    "(SELECT 1) UNION ALL (SELECT 2)",
    "SELECT REPLACE(country, 'España', 'Spain') AS country FROM users",  # REPLACE() is a function
]

UNSAFE = [
    ("", "Empty"),
    ("   ", "Empty"),
    ("DELETE FROM orders WHERE 1=1", "must start with SELECT"),
    ("UPDATE orders SET status = 'x'", "must start with SELECT"),
    ("DROP TABLE orders", "must start with SELECT"),
    ("SELECT 1; DROP TABLE orders", "one statement"),
    ("SELECT 1; SELECT 2", "one statement"),
    ("WITH x AS (SELECT 1) DELETE FROM orders WHERE TRUE", "DELETE"),
    ("SELECT 1 /* sneaky */ ; INSERT INTO t VALUES (1)", "one statement"),
    ("CREATE TABLE t AS SELECT 1", "must start with SELECT"),
    ("CREATE OR REPLACE VIEW v AS SELECT 1", "must start with SELECT"),
    ("EXPORT DATA OPTIONS(uri='gs://b/*') AS SELECT 1", "must start with SELECT"),
    ("DECLARE x INT64; SELECT x", "one statement"),
    ("DECLARE x INT64", "must start with SELECT"),
    ("(DELETE FROM orders WHERE TRUE)", "must start with SELECT"),
    ("SELECT 1 FROM t WHERE x IN (SELECT 1) MERGE", "MERGE"),
]


@pytest.mark.parametrize("sql", SAFE)
def test_allows_read_only(sql):
    assert check_read_only(sql)


@pytest.mark.parametrize("sql,reason", UNSAFE)
def test_blocks_everything_else(sql, reason):
    with pytest.raises(UnsafeQueryError, match=reason):
        check_read_only(sql)


def test_trailing_semicolon_is_stripped():
    assert check_read_only("SELECT 1;") == "SELECT 1"
