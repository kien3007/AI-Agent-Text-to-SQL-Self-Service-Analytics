{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('ecommerce', 'orders') }}
),
cleaned AS (
    SELECT
        COALESCE(order_id, 0) AS order_id,
        CAST(order_date AS DATE) AS order_date,
        total_amount,
        TRIM(CAST(status AS VARCHAR(255))) AS status
    FROM source
    WHERE order_id IS NOT NULL
)
SELECT * FROM cleaned
