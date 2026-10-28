# Data Dictionary — TheLook E-commerce (BigQuery)

**Dataset:** `bigquery-public-data.thelook_ecommerce`
**Billing project:** your own Google Cloud project (a free BigQuery sandbox works; queries are read-only)
**What it is:** A fictitious online clothing store. Google regenerates the data regularly, so row counts and totals change from day to day. Profiled on October 28, 2026.

---

## 1. Tables at a glance

| Table | Grain (one row = …) | Rows* | Date range* |
|---|---|---|---|
| `orders` | one order | 124,916 | Jan 2019 – today |
| `order_items` | one item within an order | 180,946 | Jan 2019 – a few days ahead (see trap T4) |
| `users` | one customer | 100,000 | Jan 2019 – today |
| `products` | one product in the catalog | 29,120 | — |
| `inventory_items` | one physical stock unit | 488,718 | Dec 2018 – a few days ahead |
| `events` | one website event (page view, cart add, purchase…) | 2,421,009 | Jan 2019 – a few days ahead |
| `distribution_centers` | one warehouse | 10 | — |

*As of Oct 28, 2026. Never hard-code these numbers; query them.

## 2. How tables join

```
users.id ──< orders.user_id
orders.order_id ──< order_items.order_id
products.id ──< order_items.product_id
inventory_items.id ──< order_items.inventory_item_id
products.id ──< inventory_items.product_id
distribution_centers.id ──< products.distribution_center_id
users.id ──< events.user_id   (nullable: anonymous visitors)
```

Integrity checks (all passed on Oct 28, 2026): no duplicate IDs, every order has items, every item has a product, every order has a user, `orders.num_of_item` always equals the count of its `order_items` rows.

## 3. Columns

### `orders`
| Column | Type | Meaning |
|---|---|---|
| `order_id` | INT | Primary key |
| `user_id` | INT | → `users.id` |
| `status` | STRING | Processing, Shipped, Complete, Returned, Cancelled |
| `gender` | STRING | Copy of the customer's gender (same as `users.gender`) |
| `created_at` | TIMESTAMP | When the order was placed. **Use this as the order date.** |
| `shipped_at` | TIMESTAMP | NULL for Processing and Cancelled |
| `delivered_at` | TIMESTAMP | NULL for Processing, Cancelled, Shipped |
| `returned_at` | TIMESTAMP | Only filled for Returned |
| `num_of_item` | INT | Number of items in the order |

### `order_items`
| Column | Type | Meaning |
|---|---|---|
| `id` | INT | Primary key |
| `order_id`, `user_id`, `product_id`, `inventory_item_id` | INT | Foreign keys |
| `status` | STRING | Same 5 values as orders; always matches the parent order's status |
| `created_at`, `shipped_at`, `delivered_at`, `returned_at` | TIMESTAMP | Item-level lifecycle |
| `sale_price` | FLOAT | Price charged for this item. **The only source of revenue.** Always equals `products.retail_price` (no discounts in this dataset). |

### `products`
| Column | Type | Meaning |
|---|---|---|
| `id` | INT | Primary key |
| `name`, `brand`, `sku` | STRING | `brand` NULL for 24 products, `name` NULL for 2 |
| `category` | STRING | 26 categories (e.g. Jeans, Tops & Tees) |
| `department` | STRING | Women or Men |
| `cost` | FLOAT | What the store paid for the product |
| `retail_price` | FLOAT | List price |
| `distribution_center_id` | INT | → `distribution_centers.id` |

### `users`
| Column | Type | Meaning |
|---|---|---|
| `id` | INT | Primary key |
| `first_name`, `last_name`, `email`, `street_address`, `postal_code` | STRING | Fake personal data. Do not output in bulk. |
| `age` | INT | 12–70 |
| `gender` | STRING | M or F |
| `city`, `state`, `country` | STRING | See trap T6 for dirty values |
| `traffic_source` | STRING | How the customer first arrived: Search, Organic, Facebook, Email, Display |
| `created_at` | TIMESTAMP | Sign-up date |

### `events`
| Column | Type | Meaning |
|---|---|---|
| `id`, `sequence_number` | INT | Event ID and order within a session |
| `session_id` | STRING | Browsing session |
| `user_id` | INT | **NULL for ~46% of events** (anonymous visitors) |
| `event_type` | STRING | home, department, product, cart, purchase, cancel |
| `traffic_source` | STRING | Email, Adwords, YouTube, Facebook, Organic (different list from users — trap T5) |
| `browser`, `uri`, `ip_address`, `city`, `state`, `postal_code` | STRING | Session details |
| `created_at` | TIMESTAMP | Event time |

### `inventory_items`
Physical units in stock. Holds `cost`, `sold_at` (NULL = unsold) and copies of product attributes (`product_category`, `product_brand`, etc.). Use for stock and unit-cost questions.

### `distribution_centers`
10 warehouses with `name`, `latitude`, `longitude`.

## 4. Metric definitions

| Metric | Definition (SQL logic) |
|---|---|
| **Gross revenue** | `SUM(order_items.sale_price)` over all statuses |
| **Net revenue** (default "revenue") | `SUM(order_items.sale_price)` where `status NOT IN ('Cancelled','Returned')` |
| **Orders** | `COUNT(DISTINCT order_id)` |
| **Average order value (AOV)** | Net revenue ÷ count of distinct non-cancelled, non-returned orders |
| **Gross margin** | `SUM(sale_price - products.cost)` on net items |
| **Return rate** | Returned items ÷ items that reached Shipped, Complete or Returned |
| **Cancellation rate** | Cancelled orders ÷ all orders |
| **Customers** | `COUNT(DISTINCT user_id)` from orders (buyers), not from users (sign-ups) |
| **Conversion rate** | Sessions with a `purchase` event ÷ all sessions (from `events`) |

When a user just says "revenue" or "sales", use **net revenue** and say so in the answer.

Reference values (Oct 28, 2026): gross revenue $10,742,764.17; net revenue $8,062,107.98.

## 5. Traps — rules the agent must follow

- **T1 — Revenue lives in `order_items`, not `orders`.** `orders` has no price column.
- **T2 — Join fan-out.** Joining `orders` → `order_items` gives one row per item. Never `COUNT(*)` or `SUM` order-level columns (like `num_of_item`) after that join; use `COUNT(DISTINCT order_id)`.
- **T3 — Status filters.** Decide explicitly whether to exclude Cancelled and Returned. Default for revenue: exclude both. State the choice in the answer.
- **T4 — Date every sale by `orders.created_at`.** `order_items.created_at` does not match the order's timestamp (it is off by hours to days, in both directions), and 1,440 items on already-placed orders carry future dates. Filtering on the item date splits orders and understated 2026 revenue by about $54K in testing. Always join to `orders` and filter on `orders.created_at`. Never filter sales on `order_items.created_at`.
- **T5 — Two different traffic sources.** `users.traffic_source` = how the customer first signed up. `events.traffic_source` = source of each visit. They use different category lists. Ask or state which one is meant.
- **T6 — Dirty country values.** "España" (2 rows) vs "Spain"; Brazil is stored as "Brasil". Normalize when grouping by country.
- **T7 — Anonymous events.** ~46% of `events` have NULL `user_id`. Use `session_id` for traffic and funnel metrics, not `user_id`.
- **T8 — Data refreshes.** Totals change over time. Never quote a cached number as current; re-run the query.
- **T9 — Partial periods.** The current month and today are incomplete. Flag this when comparing periods.
- **T10 — Personal data.** Don't return names, emails or addresses of individual customers in bulk; aggregate instead.
