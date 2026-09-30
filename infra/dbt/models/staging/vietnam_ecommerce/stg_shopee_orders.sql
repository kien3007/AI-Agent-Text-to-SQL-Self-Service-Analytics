{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('vietnam_ecommerce', 'shopee_orders') }}
),
cleaned AS (
    SELECT
        TRIM(CAST(order_sn AS VARCHAR(255))) AS order_sn,
        TRIM(CAST(order_status AS VARCHAR(255))) AS order_status,
        CAST(create_time AS DATE) AS create_time,
        COALESCE(total_order_value, 0) AS total_order_value,
        COALESCE(item_count, 0) AS item_count
    FROM source
    WHERE order_sn IS NOT NULL
)
SELECT * FROM cleaned
