/*
    Model Mart: fct_district_monthly_summary
    Mục đích:
    - Bảng Fact tổng hợp sẵn theo Tháng, Tỉnh/Thành, Quận/Huyện và Loại hình BĐS.
    - Giúp AI Agent trả lời các câu hỏi xu hướng thị trường trong sub-second (< 0.1s)
      thay vì phải aggregate trên toàn bộ 3.5 triệu dòng raw.
*/

{{ config(
    materialized='table'
) }}

WITH source_stg AS (
    SELECT * FROM {{ ref('stg_real_estate') }}
)

SELECT
    province_name,
    district_name,
    property_type_name,
    published_year,
    published_month,
    published_year_month,
    COUNT(*) AS total_listings,
    ROUND(AVG(price_vnd), 0) AS avg_price_vnd,
    ROUND(AVG(area_sqm), 1) AS avg_area_sqm,
    ROUND(AVG(price_per_sqm), 0) AS avg_price_per_sqm,
    MIN(price_vnd) AS min_price_vnd,
    MAX(price_vnd) AS max_price_vnd,
    ROUND(STDDEV(price_per_sqm), 0) AS stddev_price_per_sqm
FROM source_stg
GROUP BY
    province_name,
    district_name,
    property_type_name,
    published_year,
    published_month,
    published_year_month
