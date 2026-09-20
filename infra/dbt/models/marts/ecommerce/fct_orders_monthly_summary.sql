{{ config(materialized='table') }}

SELECT
    DATE_FORMAT(created_at, '%Y-%m') AS report_month,
    status,
    COUNT(*) AS total_records,
    ROUND(SUM(total_amount), 2) AS total_total_amount,
    ROUND(AVG(total_amount), 2) AS avg_total_amount
FROM {{ ref('stg_orders') }}
GROUP BY
    1, 2
ORDER BY report_month DESC
