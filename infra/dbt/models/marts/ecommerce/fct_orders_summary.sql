{{ config(materialized='table') }}

SELECT
    DATEFROMPARTS(YEAR(order_date), MONTH(order_date), 1) AS report_month,
    status,
    COUNT(*) AS total_records,
    ROUND(SUM(total_amount), 2) AS total_total_amount,
    ROUND(AVG(total_amount), 2) AS avg_total_amount
FROM {{ ref('stg_orders') }}
WHERE order_date IS NOT NULL
GROUP BY DATEFROMPARTS(YEAR(order_date), MONTH(order_date), 1), status
ORDER BY report_month DESC
