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
the view's exact name with the "Find tables by name" recipe in `finding-data.md`, using `RAW` (the
database holding its source) as the database and `daily_view` as the search term.

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
Last used: 2026-10-09.

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
Use for: "which products or metrics does account X use". Last used: 2026-10-09.

```sql
SELECT PRODUCT_LINE, METRIC, METRIC_TYPE, COUNT(*) AS DAY_ROWS
FROM USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE
WHERE BILLABLE_RPM_ACCOUNT_ID = {{account_id}}
  AND START_TIME >= '{{start_date}}' AND START_TIME < '{{end_date}}'
GROUP BY PRODUCT_LINE, METRIC, METRIC_TYPE
ORDER BY PRODUCT_LINE, METRIC
```

### Daily GB ingested by one account, US and EU
Use for: daily billed GB when "Daily GB ingested by one account" returns no rows, or for an EU
account. Reads the billing pipeline's customer-rollup views for both regions; `REGION` shows which
one holds the account, and `N_ROWS` above 1 means repeated rows. Last used: 2026-10-23.

```sql
WITH R AS (
    SELECT 'US' AS REGION, * FROM CONFORMED_USAGE_RATING.QBP_BILLING_PIPELINE.STG_QBP_BILLING_PIPELINE_USAGE_DAILY_BILLABLE_CUSTOMERROLLUP_PROD
    UNION ALL
    SELECT 'EU', * FROM CONFORMED_USAGE_RATING.QBP_BILLING_PIPELINE.STG_QBP_BILLING_PIPELINE_USAGE_DAILY_BILLABLE_CUSTOMERROLLUP_EU_PROD
)
SELECT REGION, CUSTOMER_ID, DATE(START_TIME) AS USAGE_DATE,
       ROUND(SUM(USAGE), 2) AS GB_INGESTED, ROUND(SUM(BILLABLE_USAGE), 2) AS GB_BILLABLE,
       COUNT(*) AS N_ROWS
FROM R
WHERE TELEMETRY_ACCOUNT_ID = {{account_id}}
  AND START_TIME >= '{{start_date}}' AND START_TIME < '{{end_date}}'
  AND METRIC = 'GigabytesIngested'
GROUP BY ALL
ORDER BY REGION, CUSTOMER_ID, USAGE_DATE
```

### Customer spend, commitment and run rate
Use for: "how much revenue does New Relic make from X", across a company's Salesforce accounts. Reads
Finance's latest daily snapshot. `BCM_TTM_AMT` is billable consumption over the last 12 months in
dollars at contract prices, including Finance's manual adjustments. `EFFECTIVE_ACR` is the yearly
commitment, which is 0 for pay-as-you-go. `BCM_RUN_RATE` is the last 122 days × 365/122. Spend and
commitment differ, so show both. Check the currency in `CONTRACT_RATE_DAILY_D.CURRENCY_CODE`.
Last used: 2026-10-22.

```sql
WITH D AS (SELECT MAX(REPORT_AS_OF_DT) AS DT FROM TRANSFORMED.FINANCE.MT_DENORM_CONSUMPTION_DAILY_METRICS_HEADER)
SELECT H.REPORT_AS_OF_DT, H.SFDC_ULTIMATE_PARENT_ACCOUNT_NAME, H.SFDC_ACCOUNT_NAME, H.BUYING_PROGRAM,
       H.PARTNERSHIP_NAME, H.BILLABLE_CONTRACT_START_DATE, H.BILLABLE_CONTRACT_END_DATE,
       H.EFFECTIVE_ACR, H.BCM_TTM_AMT, H.BCM_RUN_RATE
FROM TRANSFORMED.FINANCE.MT_DENORM_CONSUMPTION_DAILY_METRICS_HEADER H
JOIN D ON H.REPORT_AS_OF_DT = D.DT
WHERE H.SFDC_ACCOUNT_NAME ILIKE '%{{company_name}}%' OR H.SFDC_ULTIMATE_PARENT_ACCOUNT_NAME ILIKE '%{{company_name}}%'
ORDER BY H.SFDC_ULTIMATE_PARENT_ACCOUNT_NAME, H.EFFECTIVE_ACR DESC NULLS LAST, H.BCM_TTM_AMT DESC NULLS LAST
```

### Monthly consumption from the Xactly table
Use for: spend for contracts that have left the `_HEADER` table (ended or renewed), or a month-by-month
view. New Relic's fiscal year starts April 1, so `YTD_CONSUMPTION_AMT` resets then. A 12-month total
is the YTD at last March − the YTD at the same month a year ago + the current YTD. It matches
`BCM_TTM_AMT` to the dollar where both exist. Last used: 2026-10-22.

```sql
SELECT X.SFDC_ACCOUNT_NAME, X.SUBSCRIPTION_ACCOUNT_ID, X.CREDIT_MONTH,
       X.TOTAL_CONSUMPTION, X.ADJ_CONSUMPTION_AMT, X.YTD_CONSUMPTION_AMT
FROM TRANSFORMED.FINANCE.MT_BCM_XACTLY_INTEGRATION X
WHERE X.CREDIT_MONTH >= '{{start_date}}'
  AND X.SFDC_ACCOUNT_NAME ILIKE '%{{company_name}}%'
ORDER BY X.SFDC_ACCOUNT_NAME, X.CREDIT_MONTH
```

### Network monitoring ARR at effective prices
Use for: "yearly value of network monitoring ingest if a month's ingest repeats for a year", by contract. Sums each contract's network GB in the window and prices it at the contract's effective price per GB (`MTD_EFF_AMT` ÷ `MTD_ACTUALS_BILLED_QTY` over its `Ingest` rows) on the snapshot of the window's last day. ARR is shown ×12 for a calendar-month window, as the daily rate × 365 for any window, and at contractual prices. `STATUS` separates priced contracts from ones that can't be priced. For a contract list, select from `J` instead of rolling up. For a window before 2026, read `RPMX` and `CCX` on `2026-01-01` (see "Past paid status" in `customers.md`). Consumption value, not booked revenue. Last used: 2026-11-03.

```sql
WITH NPM AS (
    SELECT SUB_ACCOUNT_ID,
           MAX_BY(SUBSCRIPTION_ACCOUNT_ID, "DATE") AS SUB_ID,
           SUM(TOTAL_GB) AS NPM_GB
    FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
    WHERE USAGE_CATEGORY = 'NetworkMonitoring'
      AND "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
    GROUP BY SUB_ACCOUNT_ID
),
ORGX AS (
    SELECT TO_VARCHAR(A.ID) AS ACCOUNT_ID, O.NAME AS ORG_NAME
    FROM CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ACCOUNTS A
    LEFT JOIN CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ORGANIZATIONS O ON O.ID = A.ORGANIZATION_ID
    WHERE TO_VARCHAR(A.ID) IN (SELECT TO_VARCHAR(SUB_ACCOUNT_ID) FROM NPM)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY A.ID ORDER BY A.UPDATED_AT DESC, O.UPDATED_AT DESC) = 1
),
RPMX AS (
    SELECT ACCOUNT_ID, PARTNERSHIP_NAME
    FROM TRANSFORMED.COMMON.RPM_ACCOUNT_DAILY_D
    WHERE REPORT_AS_OF_DT = DATEADD(DAY, -1, '{{end_date}}'::DATE)
      AND ACCOUNT_ID IN (SELECT TO_VARCHAR(SUB_ACCOUNT_ID) FROM NPM)
),
CCX AS (
    SELECT CUSTOMER_CONTRACT_ID AS SUB_ID, COALESCE(MAX(IS_INTERNAL_ACCOUNT::INT), 0) = 1 AS IS_INTERNAL
    FROM TRANSFORMED.COMMON.ACCOUNT_DAILY_D
    WHERE REPORT_AS_OF_DT = DATEADD(DAY, -1, '{{end_date}}'::DATE)
      AND CUSTOMER_CONTRACT_ID IN (SELECT SUB_ID FROM NPM)
    GROUP BY 1
),
CLIENT AS (
    SELECT N.SUB_ID, COUNT(*) AS ACCOUNTS, SUM(N.NPM_GB) AS NPM_GB,
           BOOLOR_AGG(COALESCE(O.ORG_NAME IN ('New Relic Production US', 'New Relic Production EU'), FALSE)
                      OR COALESCE(R.PARTNERSHIP_NAME ILIKE 'New Relic Internal Use%', FALSE)) AS ACC_INTERNAL
    FROM NPM N
    LEFT JOIN ORGX O ON O.ACCOUNT_ID = TO_VARCHAR(N.SUB_ACCOUNT_ID)
    LEFT JOIN RPMX R ON R.ACCOUNT_ID = TO_VARCHAR(N.SUB_ACCOUNT_ID)
    GROUP BY N.SUB_ID
),
PRICE AS (
    SELECT CUSTOMER_ACCOUNT_ID AS SUB_ID,
           SUM(MTD_ACTUALS_BILLED_QTY) AS BILLED_GB,
           SUM(MTD_EFF_AMT) AS EFF_AMT, SUM(MTD_CONTR_AMT) AS CONTR_AMT
    FROM REPORTING.CONSUMPTION_METRICS.CONSUMPTION_DAILY_METRICS_DETAIL
    WHERE REPORT_AS_OF_DT = DATEADD(DAY, -1, '{{end_date}}'::DATE) AND UOM_CATEGORY = 'Ingest'
    GROUP BY 1
),
J AS (
    SELECT C.SUB_ID, C.ACCOUNTS, C.NPM_GB,
           P.EFF_AMT / NULLIF(P.BILLED_GB, 0) AS EFF_PRICE_PER_GB,
           P.CONTR_AMT / NULLIF(P.BILLED_GB, 0) AS CONTR_PRICE_PER_GB,
           CASE WHEN C.ACC_INTERNAL OR COALESCE(X.IS_INTERNAL, FALSE) THEN 'Internal (New Relic own)'
                WHEN P.SUB_ID IS NULL THEN 'No Finance row'
                WHEN COALESCE(P.BILLED_GB, 0) = 0 THEN 'No billed ingest (within free allowance)'
                WHEN COALESCE(P.EFF_AMT, 0) = 0 THEN 'Billed at $0 (credit, trial or free program)'
                ELSE 'Priced' END AS STATUS
    FROM CLIENT C
    LEFT JOIN PRICE P ON P.SUB_ID = C.SUB_ID
    LEFT JOIN CCX X ON X.SUB_ID = C.SUB_ID
)
SELECT COALESCE(STATUS, 'ALL CONTRACTS') AS STATUS,
       COUNT(*) AS CONTRACTS, SUM(ACCOUNTS) AS ACCOUNTS,
       ROUND(SUM(NPM_GB), 0) AS NPM_GB,
       ROUND(SUM(NPM_GB * EFF_PRICE_PER_GB), 0) AS PERIOD_VALUE_EFF,
       ROUND(SUM(NPM_GB * EFF_PRICE_PER_GB * 12), 0) AS ARR_EFF_X12,
       ROUND(SUM(NPM_GB * EFF_PRICE_PER_GB * 365 / DATEDIFF(DAY, '{{start_date}}', '{{end_date}}')), 0) AS ARR_EFF_DAILY_RATE_X365,
       ROUND(SUM(NPM_GB * CONTR_PRICE_PER_GB * 12), 0) AS ARR_CONTR_X12
FROM J
GROUP BY ROLLUP(STATUS)
ORDER BY STATUS NULLS LAST
```

## Pitfalls

- **Repeated inserts double-count.** Keep one row per account, `START_TIME`, `METRIC` and `PRODUCT_LINE`: `ROW_NUMBER()` over that partition, latest `INSERTED_AT` first. Critical. Last used: 2026-10-23.
- **Gauges aren't additive.** `FullPlatformUsers`, `FullUsers` and `CoreUsers` are levels. Never `SUM` them across days. Critical. Last used: 2026-09-30.
- **Scan size.** `ALL_DAILY_USAGE` is one of the largest tables (billions of rows), and queries run on an XSMALL warehouse. Always filter by account and a date range, or use `SAMPLE` while exploring. Last used: 2026-09-30.
- **No billing rows doesn't mean no usage.** `ALL_DAILY_USAGE` returned nothing, over several months, for an EU account that was ingesting data. Its usage sat only in the billing pipeline's EU view. Before reporting zero usage, run "Daily GB ingested by one account, US and EU". Critical. Last used: 2026-10-09.
- **Billable usage isn't a paid signal.** In the billing-pipeline views, `BILLABLE_USAGE` is usage minus the free allowance for everyone. `CoreCCU`, `BillionScannedEvents` and `BillionInspectedCount` are billable for nearly every customer, and `Unbilled…` meters aren't charged, so none of them says who pays. `GigabytesIngested` is billable only above the free 100 GB a month, so a paying customer under it shows zero. Use `RPM_ACCOUNT_DAILY_D.IS_PAID` (`npm.md`, "Networking clients"). Critical. Last used: 2026-10-23.
- **Matching II companies to billing customers.** II `SUBSCRIPTION_ACCOUNT_ID` is a `CC-…` for some and a plain account ID for others, so matching billing `CUSTOMER_ID` alone misses most of them. Match three ways and union them: billing `TELEMETRY_ACCOUNT_ID` = the company's accounts, `CUSTOMER_ID` = its ID, and `TELEMETRY_ACCOUNT_ID` = its ID. Some companies share a billing customer with another ID, so count billing customers when you need companies. Critical. Last used: 2026-10-23.
- **Monthly adjustments aren't additive.** In the Xactly table, `ADJ_CONSUMPTION_AMT` can be a delta or a replacement for that month's `TOTAL_CONSUMPTION`, so adding them over-counts. Use `YTD_CONSUMPTION_AMT`. Critical. Last used: 2026-10-22.
- **Revenue is not booked revenue.** `BCM_TTM_AMT` is consumption, and a commitment is a floor: a customer under its commitment still pays the commitment. Partner deals are at the customer's contract value, so New Relic's net after partner margin may be lower. Show consumption, commitment and run rate together. Last used: 2026-11-03.
- **Use `_HEADER`, not the old table.** `TRANSFORMED.FINANCE.MT_DENORM_CONSUMPTION_DAILY_METRICS` stopped in March 2026. Its replacements are `…_HEADER` and `…_DETAIL`. Critical. Last used: 2026-10-22.
- **Unpriced network GB.** `CONSUMPTION_DAILY_METRICS_DETAIL` has no `Ingest` row for customers billed through New Relic Japan KK or its resellers, for one-time deals ("One Time Fulfilled" partnership) and for many free-tier accounts, so their network GB is unpriced, not free. Show it as its own line next to the priced total, and say so. Critical. Last used: 2026-11-03.
- **Price network GB with `Ingest`, not `CCU`.** Network data is metered as GB ingested (`UOM_CATEGORY = 'Ingest'`). The `CCU` meter (Core and Advanced CCU) is a different product. Last used: 2026-11-03.
- **Join key in past months.** For an earlier window, II's contract ID is often a plain account ID rather than a `CC-…`, and Finance's `CUSTOMER_ACCOUNT_ID` carries the same plain ID on that date, so join them as they are. Mapping the account to its later `CC-…` contract added almost no matches. Last used: 2026-11-03.
