{{ config(materialized='view') }}

WITH source_data AS (
    SELECT * FROM customers
),
cleaned AS (
    SELECT
        COALESCE(id, 0) AS id,
        TRIM(name) AS name,
        TRIM(province) AS province
    FROM source_data
    WHERE id IS NOT NULL
)
SELECT * FROM cleaned
