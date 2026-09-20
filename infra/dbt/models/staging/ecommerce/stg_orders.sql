{{ config(materialized='view') }}

WITH source_data AS (
    SELECT * FROM orders
),
cleaned AS (
    SELECT
        COALESCE(id, 0) AS id,
        COALESCE(customer_id, 0) AS customer_id,
        TRIM(status) AS status,
        total_amount,
        CAST(created_at AS DATE) AS created_at
    FROM source_data
    WHERE id IS NOT NULL
)
SELECT * FROM cleaned
