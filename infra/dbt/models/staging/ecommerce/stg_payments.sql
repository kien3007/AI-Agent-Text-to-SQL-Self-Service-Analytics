{{ config(materialized='view') }}

WITH source_data AS (
    SELECT * FROM payments
),
cleaned AS (
    SELECT
        COALESCE(id, 0) AS id,
        COALESCE(order_id, 0) AS order_id,
        TRIM(payment_method) AS payment_method,
        amount
    FROM source_data
    WHERE id IS NOT NULL
)
SELECT * FROM cleaned
