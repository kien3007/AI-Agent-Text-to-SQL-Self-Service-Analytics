---
language:
  - vi
license: cc-by-nc-4.0
task_categories:
  - tabular-regression
tags:
  - real-estate
  - vietnam
  - property
  - geospatial
  - price-prediction
  - tabular
  - vietnamese
  - "Tiếng Việt"
dataset_info:
  features:
    - name: name
      dtype: string
    - name: description
      dtype: string
    - name: property_type_name
      dtype: string
    - name: province_name
      dtype: string
    - name: district_name
      dtype: string
    - name: ward_name
      dtype: string
    - name: street_name
      dtype: string
    - name: project_name
      dtype: string
    - name: price
      dtype: float64
    - name: area
      dtype: float64
    - name: floor_count
      dtype: float64
    - name: frontage_width
      dtype: float64
    - name: house_depth
      dtype: float64
    - name: road_width
      dtype: float64
    - name: bedroom_count
      dtype: float64
    - name: bathroom_count
      dtype: float64
    - name: house_direction
      dtype: string
    - name: balcony_direction
      dtype: string
    - name: published_at
      dtype: string
  splits:
    - name: train
      num_examples: 3500744
---

# 🏠 Tinix Vietnam Real Estate Listings (2025-2026)

**Tinix Vietnam Real Estate Listings 2025-2026** là bộ dữ liệu bất động sản Việt Nam quy mô lớn được thu thập và xử lý bởi [TiniX AI](https://tinix.ai/), bao gồm đúng **3.500.744 tin đăng bán/cho thuê bất động sản** từ tháng 6/2025 đến tháng 3/2026 sau khi đã qua bước lọc loại hình nghiêm ngặt (loại bỏ Nhà mặt phố, Nhà trong ngõ). Đây là tài nguyên phục vụ nghiên cứu về thị trường bất động sản, xây dựng mô hình định giá nhà, phân tích xu hướng thị trường tại Việt Nam.

> **A massive, refined Vietnam real estate listing dataset** containing over 3.5 million property records collected between June 2025 and March 2026, curated and published by [TiniX AI](https://tinix.ai/).

---

## 📊 Market Overview & Statistical Insight

### Property Listing Volume by Month
![Monthly Trend](images/temporal_distribution.png)

### Regional Market Concentration (Top 10 Provinces)
![Regional Concentration](images/geo_provinces.png)

### Property Listing Breakdown by Category
![Property Types](images/property_types.png)

### Market Price Distribution Analysis (VND)
![Price Distribution](images/price_distribution.png)

---

## 📋 Dataset Summary

| Attribute | Value |
|---|---|
| **Total Records** | 3,500,744 |
| **Time Range** | 2025-06-01 → 2026-03-31 |
| **Number of Shards** | 10 (Parquet format) |
| **Provinces Covered** | 63 tỉnh/thành phố Việt Nam |
| **Coordinate System** | WGS 84 (EPSG:4326) |
| **Language** | Vietnamese |
| **License** | CC BY-NC 4.0 |

---

## 🗺️ Geographic Coverage

Dữ liệu trải rộng trên toàn bộ 63 tỉnh thành Việt Nam. Các thị trường lớn nhất theo khối lượng tin đăng:

| # | Province | Listings (Full Dataset) |
|---|---|---|
| 1 | 🏙️ Hồ Chí Minh | 1,357,526 |
| 2 | 🏙️ Hà Nội | 1,140,542 |
| 3 | 🌊 Đà Nẵng | 185,973 |
| 4 | 🏭 Bình Dương | 150,377 |
| 5 | 🌴 Khánh Hòa | 98,377 |
| 6 | ⚓ Hải Phòng | 72,788 |
| 7 | 🌾 Hưng Yên | 65,223 |
| 8 | 🏗️ Đồng Nai | 59,543 |
| 9 | 🌾 Long An | 47,125 |
| 10 | 🌊 Bà Rịa - Vũng Tàu | 45,885 |

> *Figures reflect the final 3.5M record dataset distribution.*

---

## 🏷️ Property Types

Bộ dữ liệu bao gồm các loại hình bất động sản phổ biến trên thị trường Việt Nam:

| Type | Description |
|---|---|
| **Nhà** | Nhà riêng các loại / Residential house |
| **Căn hộ chung cư** | Apartment / Condominium |
| **Đất** | Land plots / Residential or commercial land |
| **Biệt thự / Nhà liền kề** | Villas and townhouses |
| **Nhà mặt phố** | Street-front houses |
| **Shophouse** | Commercial shophouses |

---

## 📁 Data Schema

| Column | Type | Description |
|---|---|---|
| `name` | `string` | Listing title (HTML stripped, phone numbers redacted) |
| `description` | `string` | Full listing description (HTML stripped, phone numbers redacted) |
| `property_type_name` | `string` | Property category (e.g., Căn hộ chung cư, Nhà, Đất, ...) |
| `province_name` | `string` | Province / City name (63 provinces) |
| `district_name` | `string` | District (Quận / Huyện) |
| `ward_name` | `string` | Ward (Phường / Xã) |
| `street_name` | `string` | Street name |
| `project_name` | `string` | Real estate development project name (if applicable) |
| `price` | `float64` | Listed price in **VND** (Vietnamese Dong). `null` if not disclosed. |
| `area` | `float64` | Total floor/land area in **m²** |
| `floor_count` | `float64` | Number of floors in the building |
| `frontage_width` | `float64` | Frontage width in meters |
| `house_depth` | `float64` | Depth of the property in meters |
| `road_width` | `float64` | Width of the road in front of the property (meters) |
| `bedroom_count` | `float64` | Number of bedrooms |
| `bathroom_count` | `float64` | Number of bathrooms |
| `house_direction` | `string` | Cardinal facing direction (Đông, Tây, Nam, Bắc, Đông-Bắc, ...) |
| `balcony_direction` | `string` | Cardinal facing direction of the balcony |
| `published_at` | `string` | ISO 8601 datetime the listing was published |

---

## 💡 Potential Use Cases

- 🏠 **Real Estate Price Prediction** — Xây dựng mô hình định giá bất động sản dựa trên đặc điểm vật lý (diện tích, số phòng, v.v.) và vị trí địa lý.
- 🗺️ **Geospatial Market Analysis** — Phân tích mật độ niêm yết, nhiệt độ giá và xu hướng thị trường theo khu vực địa lý.
- 📈 **Temporal Trend Analysis** — Theo dõi biến động khối lượng tin đăng và mức giá theo tháng.
- 🤖 **Vietnamese NLP on Real Estate Text** — Fine-tune hoặc pre-train các mô hình ngôn ngữ tiếng Việt trên văn bản mô tả bất động sản.
- 📊 **Market Research & Segmentation** — Cung cấp insight về cơ cấu loại hình bất động sản và phân khúc giá thị trường Việt Nam 2025.

---

## 🚀 Quickstart

```python
from datasets import load_dataset
import pandas as pd

# Load full dataset
ds = load_dataset("tinixai/vietnam-real-estates")
df = ds["train"].to_pandas()

# --- Example 1: Listings in Hanoi with known price ---
hanoi = df[
    (df["province_name"] == "Hà Nội") &
    (df["price"] > 0)
]
print(hanoi[["name", "price", "area", "bedroom_count"]].head())

# --- Example 2: Average price per province ---
avg_price = (
    df[df["price"] > 0]
    .groupby("province_name")["price"]
    .mean()
    .sort_values(ascending=False)
)
print(avg_price.head(10))

# --- Example 3: Filter apartments in Hanoi ---
apartments_hanoi = df[
    (df["property_type_name"].str.contains("Căn hộ", na=False)) &
    (df["province_name"] == "Hà Nội")
]
print(f"{len(apartments_hanoi):,} apartment listings in Hanoi")
```

---

## 📜 License & Citation

This dataset is released under the **Creative Commons Attribution Non-Commercial 4.0 International ([CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/))** license.

> ✅ Free to use for academic research and education.  
> ❌ Commercial use requires explicit written permission from TiniX AI.

```bibtex
@dataset{tinix_vietnam_real_estate_2025_2026,
  author    = {TiniX AI},
  title     = {Tinix Vietnam Real Estate Listings 2025-2026},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/tinixai/vietnam-real-estates}
}
```
