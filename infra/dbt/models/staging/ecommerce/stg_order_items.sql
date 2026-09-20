{{ config(materialized='view') }}

WITH source_data AS (
    SELECT * FROM order_items
),
cleaned AS (
    SELECT
        COALESCE(id, 0) AS id,
        COALESCE(order_id, 0) AS order_id,
        COALESCE(product_id, 0) AS product_id,
        COALESCE(quantity, 0) AS quantity,
        unit_price
    FROM source_data
    WHERE id IS NOT NULL
)
SELECT * FROM cleaned
