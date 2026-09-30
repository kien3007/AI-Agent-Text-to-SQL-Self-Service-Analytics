{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('ecommerce', 'customers') }}
),
cleaned AS (
    SELECT
        COALESCE(customer_id, 0) AS customer_id,
        TRIM(CAST(customer_name AS VARCHAR(255))) AS customer_name
    FROM source
    WHERE customer_id IS NOT NULL
)
SELECT * FROM cleaned
