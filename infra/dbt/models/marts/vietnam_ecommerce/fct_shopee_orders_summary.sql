{{ config(materialized='table') }}

SELECT
    DATEFROMPARTS(YEAR(create_time), MONTH(create_time), 1) AS report_month,
    order_status,
    COUNT(*) AS total_records,
    ROUND(SUM(total_order_value), 2) AS total_total_order_value,
    ROUND(AVG(total_order_value), 2) AS avg_total_order_value,
    ROUND(SUM(item_count), 2) AS total_item_count,
    ROUND(AVG(item_count), 2) AS avg_item_count
FROM {{ ref('stg_shopee_orders') }}
WHERE create_time IS NOT NULL
GROUP BY DATEFROMPARTS(YEAR(create_time), MONTH(create_time), 1), order_status
ORDER BY report_month DESC
