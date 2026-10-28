"""Evaluation cases: tricky questions, each graded against an independent reference query.

The reference SQL is written separately from the agent (different joins/filters where
possible), so agreement between the two is real evidence, not the agent grading itself.

Check types
-----------
number       The answer must contain a number within ``rel_tol`` of the reference value.
             Answers like "$5.62M", "85.97", "26.4%" and "5,499" are all understood.
contains     The answer must mention every string in ``must_mention`` (case-insensitive).
refusal      The answer must say the data can't answer it (``refusal_phrases``).

Behaviour checks (optional, graded on the SQL the agent actually ran)
---------------------------------------------------------------------
forbid_sql   Regexes that must not appear in any successful query (e.g. filtering
             sales on the item timestamp, the bug found during manual testing).
"""

DATASET = "bigquery-public-data.thelook_ecommerce"
ITEM_DATE_FILTER = r"(order_items|\boi)\.created_at\s*(<|>|<=|>=|between)"

CASES = [
    {
        "id": "orders_last_month",
        "question": "How many orders did we get last month?",
        "trap": "Calendar-month boundaries; orders counted once each",
        "check": "number",
        "reference_sql": f"""
            SELECT COUNT(*) AS value FROM `{DATASET}.orders`
            WHERE created_at >= TIMESTAMP(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH))
              AND created_at <  TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), MONTH))""",
        "rel_tol": 0.0,
    },
    {
        "id": "aov",
        "question": "What is our average order value?",
        "trap": "T4 item timestamps; AOV is per order, not per item",
        "check": "number",
        "reference_sql": f"""
            WITH per_order AS (
              SELECT o.order_id, SUM(oi.sale_price) AS total
              FROM `{DATASET}.orders` o JOIN `{DATASET}.order_items` oi USING (order_id)
              WHERE o.status NOT IN ('Cancelled','Returned') AND o.created_at <= CURRENT_TIMESTAMP()
              GROUP BY o.order_id)
            SELECT AVG(total) AS value FROM per_order""",
        "rel_tol": 0.005,
        "forbid_sql": [ITEM_DATE_FILTER],
    },
    {
        "id": "top_traffic_source",
        "question": "Which traffic source brings in the most revenue?",
        "trap": "T5 two different traffic_source columns",
        "check": "number",
        "must_mention": ["Search"],
        "reference_sql": f"""
            SELECT SUM(oi.sale_price) AS value
            FROM `{DATASET}.order_items` oi
            JOIN `{DATASET}.orders` o USING (order_id)
            JOIN `{DATASET}.users` u ON u.id = o.user_id
            WHERE o.status NOT IN ('Cancelled','Returned') AND u.traffic_source = 'Search'""",
        "rel_tol": 0.01,
    },
    {
        "id": "spain_revenue",
        "question": "How much revenue came from customers in Spain?",
        "trap": "T6 'Spain' and 'España' are the same country",
        "check": "number",
        "reference_sql": f"""
            SELECT SUM(oi.sale_price) AS value
            FROM `{DATASET}.order_items` oi
            JOIN `{DATASET}.orders` o USING (order_id)
            JOIN `{DATASET}.users` u ON u.id = o.user_id
            WHERE o.status NOT IN ('Cancelled','Returned') AND u.country IN ('Spain','España')""",
        "rel_tol": 0.01,
    },
    {
        "id": "top_margin_category",
        "question": "Which product category makes us the most gross margin?",
        "trap": "Margin uses product cost; net items only",
        "check": "number",
        "must_mention": ["Outerwear"],
        "reference_sql": f"""
            SELECT SUM(oi.sale_price - ii.cost) AS value
            FROM `{DATASET}.order_items` oi
            JOIN `{DATASET}.orders` o USING (order_id)
            JOIN `{DATASET}.inventory_items` ii ON ii.id = oi.inventory_item_id
            WHERE o.status NOT IN ('Cancelled','Returned') AND ii.product_category = 'Outerwear & Coats'""",
        "rel_tol": 0.01,
    },
    {
        "id": "conversion_rate",
        "question": "What is our website conversion rate?",
        "trap": "T7/T12 anonymous sessions; user-based conversion is meaningless",
        "check": "number",
        "reference_sql": f"""
            SELECT 100 * COUNT(DISTINCT IF(event_type = 'purchase', session_id, NULL))
                       / COUNT(DISTINCT session_id) AS value
            FROM `{DATASET}.events` WHERE created_at <= CURRENT_TIMESTAMP()""",
        "rel_tol": 0.01,
    },
    {
        "id": "revenue_ytd",
        "question": "What is our total revenue so far this year?",
        "trap": "T4 item timestamps understate revenue; T9 partial month",
        "check": "number",
        "reference_sql": f"""
            SELECT SUM(oi.sale_price) AS value
            FROM `{DATASET}.order_items` oi JOIN `{DATASET}.orders` o USING (order_id)
            WHERE o.status NOT IN ('Cancelled','Returned')
              AND o.created_at >= TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), YEAR))
              AND o.created_at <= CURRENT_TIMESTAMP()""",
        "rel_tol": 0.01,
        "forbid_sql": [ITEM_DATE_FILTER],
    },
    {
        "id": "campaign_profit",
        "question": "What was our profit by marketing campaign last quarter?",
        "trap": "Unanswerable: there is no campaign data",
        "check": "refusal",
        "refusal_phrases": [
            "no campaign",
            "doesn't contain",
            "does not contain",
            "not available",
            "isn't available",
            "doesn't have",
            "does not have",
            "no marketing campaign",
            "can't answer",
            "cannot answer",
            "not tracked",
            "isn't tracked",
            "no data on",
            "not in the data",
        ],
    },
]
