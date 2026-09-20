/*
    Model Mart: fct_real_estate_analytics
    Mục đích:
    - Bảng Fact chi tiết phục vụ phân tích chuyên sâu cho AI Agent.
    - Gắn nhãn phân khúc giá (Bình dân, Trung cấp, Cao cấp, Siêu cao cấp).
    - Gắn nhãn phân khúc diện tích.
*/

{{ config(
    materialized='table'
) }}

WITH source_stg AS (
    SELECT * FROM {{ ref('stg_real_estate') }}
)

SELECT
    listing_title,
    property_type_name,
    province_name,
    district_name,
    ward_name,
    street_name,
    project_name,
    price_vnd,
    area_sqm,
    price_per_sqm,
    bedroom_count,
    bathroom_count,
    floor_count,
    frontage_width_m,
    road_width_m,
    house_direction,
    balcony_direction,
    published_at,
    published_date,
    published_year,
    published_month,
    published_quarter,
    published_year_month,
    
    -- Phân khúc giá
    CASE 
        WHEN price_vnd < 2000000000 THEN 'Bình dân (< 2 tỷ)'
        WHEN price_vnd BETWEEN 2000000000 AND 5000000000 THEN 'Trung cấp (2 - 5 tỷ)'
        WHEN price_vnd BETWEEN 5000000001 AND 15000000000 THEN 'Cao cấp (5 - 15 tỷ)'
        ELSE 'Siêu cao cấp (> 15 tỷ)'
    END AS price_segment,

    -- Phân khúc diện tích
    CASE 
        WHEN area_sqm < 50 THEN 'Nhỏ (< 50m2)'
        WHEN area_sqm BETWEEN 50 AND 100 THEN 'Tiêu chuẩn (50 - 100m2)'
        WHEN area_sqm BETWEEN 100.1 AND 200 THEN 'Rộng (100 - 200m2)'
        ELSE 'Biệt lập (> 200m2)'
    END AS area_segment

FROM source_stg
