# Billing and consumption

Read this for questions about usage, ingest billed per account, consumption, product lines or
metrics. `USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` is the financial system of record. It is
append-only, so only read it.

## Tables

`USAGE_AND_RATING.USAGE`:

| Table | Holds |
|---|---|
| `ALL_DAILY_USAGE` | Daily usage for every meter and account; the table Business Applications invoices from. Very large: always filter by account and date. |
| `ALL_DAILY_USAGE_CUSTOMER` | Usage rolled up per customer |
| `ALL_DAILY_USAGE_DAILY` | Daily summary |
| `DAILY_AGGREGATION_USER_CONSUMPTION_PROD`, `…_EU_PROD` | Per-user consumption, US and EU |
| `CUSTOMER_CONTRACT_CUSTOMER_ID_PROD`, `…_EU_PROD` | Customer-to-contract mapping, US and EU |

`ALL_DAILY_USAGE` key columns:
- `START_TIME`: start of the usage day.
- `BILLABLE_RPM_ACCOUNT_ID`: the billed RPM account, the same ID as `consuming_account_id` upstream.
- `PRODUCT_LINE`, `METRIC` and `USAGE_METRIC` (the upstream stamper's name).
- `METRIC_TYPE`: `count` or `gauge`.
- `QUANTITY`: already in GB for `GigabytesIngested`, since upstream divides bytes by 10^9.
- `INSERTED_AT`: when the row landed. It breaks ties between repeated inserts.

Upstream, the product-consumption daily view has `consuming_account_id`, `master_account_id`,
`poa_account_id` (partnership owner), `usage_start_time`, `usage_end_time` (really "reported at"),
`usage_type`, `dp_gigabytes_ingested`, `consumption`, `billable_consumption`, `estimated_cost`,
`free_limit` and `processed_time` (use it to spot restreams). It is built from
`RAW.PRODUCT_CONSUMPTION.PRODUCT_CONSUMPTION_PRODUCTION_JSON` (`…_EU_PRODUCTION_JSON` for EU). Find
the view's exact name with the "Find tables" recipe in `finding-data.md`, searching `daily_view`.

## Product lines and metrics

| Product line | Metric | Type |
|---|---|---|
| `DataPlatform` | `GigabytesIngested` | count |
| `FullStackObservability` | `OnDemandFullPlatformSessions` | count |
| `FullStackObservability` | `FullPlatformUsers`, `FullUsers`, `CoreUsers` | gauge |

## Pipeline

The Usage Stamper (AAA team) measures usage, and the Usage Rating Service rates it. Kafka carries
it (`product_consumption` topic) to S3, then to Snowflake `RAW`, then daily views. Airflow (Ethel)
joins the usage with Zuora subscriptions into `ALL_DAILY_USAGE`. Business Applications syncs at
2 am PST, and the transform must finish before then. So today's rows may be missing until after
2 am PST. Help: #help-usage-pipeline (stamper) and #help-product-consumption (rating).

## Recipes

### Daily GB ingested by one account
Use for: "how much data did account X ingest per day". Applies the de-duplication rule. Critical.
Last used: 2026-09-30.

```sql
SELECT DATE(START_TIME) AS USAGE_DATE, SUM(QUANTITY) AS GB_INGESTED
FROM (
    SELECT START_TIME, QUANTITY
    FROM USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE
    WHERE BILLABLE_RPM_ACCOUNT_ID = {{account_id}}
      AND PRODUCT_LINE = 'DataPlatform'
      AND METRIC = 'GigabytesIngested'
      AND START_TIME >= '{{start_date}}' AND START_TIME < '{{end_date}}'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY BILLABLE_RPM_ACCOUNT_ID, START_TIME, METRIC, PRODUCT_LINE
        ORDER BY INSERTED_AT DESC) = 1
)
GROUP BY USAGE_DATE
ORDER BY USAGE_DATE
```

### What an account is metered on
Use for: "which products or metrics does account X use". Last used: 2026-09-30.

```sql
SELECT PRODUCT_LINE, METRIC, METRIC_TYPE, COUNT(*) AS DAY_ROWS
FROM USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE
WHERE BILLABLE_RPM_ACCOUNT_ID = {{account_id}}
  AND START_TIME >= '{{start_date}}' AND START_TIME < '{{end_date}}'
GROUP BY PRODUCT_LINE, METRIC, METRIC_TYPE
ORDER BY PRODUCT_LINE, METRIC
```

## Pitfalls

- **Repeated inserts double-count.** Keep one row per account, `START_TIME`, `METRIC` and `PRODUCT_LINE`: `ROW_NUMBER()` over that partition, latest `INSERTED_AT` first. Critical. Last used: 2026-09-30.
- **Gauges aren't additive.** `FullPlatformUsers`, `FullUsers` and `CoreUsers` are levels. Never `SUM` them across days. Critical. Last used: 2026-09-30.
- **Scan size.** `ALL_DAILY_USAGE` has hundreds of millions of rows on an XSMALL warehouse. Always filter by account and a date range, or use `SAMPLE` while exploring. Last used: 2026-09-30.
