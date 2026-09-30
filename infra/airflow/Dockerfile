FROM apache/airflow:2.8.2-python3.10

USER root
# Cài đặt client utilities nếu cần
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        freetds-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Cài đặt các thư viện phục vụ Ingestion & Transformation vào DuckDB
RUN pip install --no-cache-dir \
    duckdb==1.1.3 \
    pandas>=2.0.0 \
    sqlalchemy>=2.0.0 \
    psycopg2-binary>=2.9.9 \
    pymssql>=2.2.8 \
    dbt-core>=1.8.0 \
    dbt-duckdb>=1.8.0
