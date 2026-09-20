/*
    Model Staging: stg_real_estate
    Mục đích:
    - Làm sạch và chuẩn hóa dữ liệu tin đăng bất động sản thô.
    - Loại bỏ tin rác (giá <= 0, diện tích <= 0).
    - Chuẩn hóa các trường ngày tháng và tách phân rã năm/tháng/quý.
*/

WITH raw_source AS (
    SELECT
        name,
        description,
        property_type_name,
        province_name,
        district_name,
        ward_name,
        street_name,
        project_name,
        price,
        area,
        bedroom_count,
        bathroom_count,
        floor_count,
        frontage_width,
        house_depth,
        road_width,
        house_direction,
        balcony_direction,
        published_at
    FROM {{ source('raw_data', 'real_estate_listings') }}
    WHERE price > 0 AND area > 0
),

cleaned AS (
    SELECT
        TRIM(name) AS listing_title,
        description,
        property_type_name,
        province_name,
        district_name,
        ward_name,
        street_name,
        COALESCE(NULLIF(TRIM(project_name), ''), 'Đang cập nhật') AS project_name,
        CAST(price AS DOUBLE) AS price_vnd,
        CAST(area AS DOUBLE) AS area_sqm,
        ROUND(price / NULLIF(area, 0), 0) AS price_per_sqm,
        CAST(bedroom_count AS INT) AS bedroom_count,
        CAST(bathroom_count AS INT) AS bathroom_count,
        CAST(floor_count AS INT) AS floor_count,
        CAST(frontage_width AS DOUBLE) AS frontage_width_m,
        CAST(road_width AS DOUBLE) AS road_width_m,
        house_direction,
        balcony_direction,
        published_at,
        DATE(published_at) AS published_date,
        YEAR(published_at) AS published_year,
        MONTH(published_at) AS published_month,
        QUARTER(published_at) AS published_quarter,
        DATE_FORMAT(published_at, '%Y-%m') AS published_year_month
    FROM raw_source
)

SELECT * FROM cleaned
