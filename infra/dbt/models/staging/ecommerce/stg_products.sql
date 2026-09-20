{{ config(materialized='view') }}

WITH source_data AS (
    SELECT * FROM products
),
cleaned AS (
    SELECT
        COALESCE(id, 0) AS id,
        TRIM(product_name) AS product_name,
        TRIM(category_name) AS category_name
    FROM source_data
    WHERE id IS NOT NULL
)
SELECT * FROM cleaned
