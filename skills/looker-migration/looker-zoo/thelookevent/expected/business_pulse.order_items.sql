-- Ground-truth SQL for the `business_pulse` dashboard, `order_items` explore cluster.
-- Dialect: BigQuery (the model's connection is BigQuery; the LookML sql: blocks are
-- already BigQuery — TIMESTAMP_DIFF / FORMAT_TIMESTAMP / INT64 / backtick identifiers).
-- Tables are `looker-private-demo.ecomm.*` in the source; repoint to
-- `bigquery-public-data.thelook_ecommerce.*` (same schema) to actually run this.
--
-- This is a hand-derived expected output for the fidelity gate — NOT what the skill
-- auto-produced. It rebuilds the two Looker PDTs inline as CTEs (per the skill's
-- "rebuild derived tables inline" rule) and clusters the order_items tiles onto one
-- shared base, with a companion query per tile.

-- ===========================================================================
-- Shared base derivation: order_items at order-item grain + the joins the
-- business_pulse order_items tiles need. Every companion below reads this.
-- ===========================================================================
WITH repeat_purchase_facts AS (   -- rebuilt from views/13 (raw-SQL derived_table)
  SELECT
      oi.order_id AS order_id,
      oi.created_at,
      COUNT(DISTINCT roi.id)      AS number_subsequent_orders,
      MIN(roi.created_at)         AS next_order_date,
      MIN(roi.order_id)           AS next_order_id
  FROM `looker-private-demo.ecomm.order_items` oi
  LEFT JOIN `looker-private-demo.ecomm.order_items` roi
    ON oi.user_id = roi.user_id
   AND oi.created_at < roi.created_at
  GROUP BY 1, 2
),
base AS (
  SELECT
      oi.id                                  AS order_item_id,      -- users.count grain key
      oi.order_id,
      oi.user_id,
      oi.sale_price,
      oi.created_at,
      -- dimension_group `created` timeframes (created_at is TIMESTAMP):
      DATE(oi.created_at)                    AS created_date,
      FORMAT_TIMESTAMP('%B', oi.created_at)  AS created_month_name, -- STRING label
      EXTRACT(MONTH FROM oi.created_at)      AS created_month_num,  -- for chrono sort (see FINDINGS #2)
      EXTRACT(YEAR  FROM oi.created_at)      AS created_year,
      -- gross margin chain: sale_price - inventory_items.cost
      (oi.sale_price - ii.cost)              AS gross_margin,
      u.id                                   AS users_id,           -- COUNT(DISTINCT) target, not COUNT(*)
      u.state, u.city, u.traffic_source, u.gender, u.country,
      DATE(u.created_at)                     AS user_created_date,
      p.category                             AS product_category,
      -- days_until_next_order → repeat_purchase_within_30d (transitive, via the PDT)
      TIMESTAMP_DIFF(rpf.next_order_date, oi.created_at, DAY) AS days_until_next_order
  FROM `looker-private-demo.ecomm.order_items` oi
  -- ⚠️ LookML joins inventory_items as FULL OUTER one_to_one; a full outer adds
  -- unmatched inventory rows to the base and would inflate COUNT(*) (FINDINGS #3).
  -- The business_pulse count tiles want order rows only → LEFT JOIN is the faithful
  -- intent here. Flagged, not silently changed.
  LEFT JOIN `looker-private-demo.ecomm.inventory_items` ii ON ii.id = oi.inventory_item_id
  LEFT JOIN `looker-private-demo.ecomm.users`           u  ON oi.user_id = u.id
  LEFT JOIN `looker-private-demo.ecomm.products`        p  ON p.id = ii.product_id
  LEFT JOIN repeat_purchase_facts rpf                        ON oi.order_id = rpf.order_id
)

-- ===========================================================================
-- Companion — Tile "Total Sales, Year over Year" (looker_line, pivot on year)
--   fields: created_month_name, total_sale_price, created_year (pivot)
--   filters: created_date <= end of last full month ("before 0 months ago");
--            created_year within last 4 years
-- ⚠️ ORDER BY created_month_num (not the STRING name) so months sort Jan..Dec.
-- ===========================================================================
SELECT
    created_month_name,
    created_year,
    SUM(sale_price) AS total_sale_price
FROM base
WHERE created_date < DATE_TRUNC(CURRENT_DATE(), MONTH)               -- "before 0 months ago"
  AND created_year >= EXTRACT(YEAR FROM CURRENT_DATE()) - 3          -- "4 years" (incl. current)
GROUP BY created_month_name, created_month_num, created_year
ORDER BY created_year DESC, created_month_num;

-- ===========================================================================
-- Companion — Tile "Orders by Day and Category" (looker_area)
--   fields: products.category, order_items.count, order_items.created_date
--   order_items.count = type:count on the BASE view → COUNT(*) is correct here.
-- ===========================================================================
SELECT
    created_date,
    product_category,
    COUNT(*) AS order_items_count
FROM base
GROUP BY created_date, product_category
ORDER BY created_date;

-- ===========================================================================
-- KPI — Tile "Number of First Purchasers" (single_value), fields: [users.count]
--   users.count is type:count on a JOINED view → COUNT(DISTINCT users.id),
--   NOT COUNT(*) (the order_items→users join fans out). (skill §2 — covered)
--   tile filter: users.created_date last 7 days; + dashboard "Date" default 90d
--   on order_items.created_date; goal=10000 is a constant dynamic_field (literal).
-- ===========================================================================
SELECT COUNT(DISTINCT users_id) AS users_count
FROM base
WHERE user_created_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  AND created_date       >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY);

-- ===========================================================================
-- KPI — Tile "Average Order Sale Price" (single_value)
--   order_items.average_sale_price = type:average of sale_price → AVG(sale_price)
-- ===========================================================================
SELECT AVG(sale_price) AS average_sale_price
FROM base;

-- ===========================================================================
-- Multi-hop measure — order_items.30_day_repeat_purchase_rate (percent_1)
--   = count_with_repeat_purchase_within_30d / count
--   where the numerator is COUNT(DISTINCT id) FILTERED on repeat_purchase_within_30d
--   (yesno = days_until_next_order <= 30), which depends on the repeat_purchase_facts
--   PDT. Ratio-of-measures → SUM(CASE..)/COUNT, NULLIF-guarded. (skill covers each
--   piece; composing 4 constructs for one KPI is the real test — FINDINGS #5.)
-- ===========================================================================
SELECT
    SAFE_DIVIDE(
      COUNT(DISTINCT CASE WHEN days_until_next_order <= 30 THEN order_item_id END),
      NULLIF(COUNT(*), 0)
    ) AS repeat_purchase_rate_30d
FROM base;
