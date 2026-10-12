# Table index

Check this before searching the catalog. `/snowflake learn` builds it from past runs, following
`updater.md`. Each entry says what a table holds, its key columns and their meaning, its gotchas and
when a question last used it. It never holds row counts, full column lists or customer data.

Entry format:

```text
### DATABASE.SCHEMA.TABLE
Holds: <one line>. Key columns: `COL` (meaning), `COL` (meaning). Gotchas: <or "none">.
Last used: YYYY-MM-DD.
```

## Tables

### TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
Holds: Instrumentation Insights (II), GB ingested per account, day, event and instrumentation. Key columns: `"DATE"` (day), `SUB_ACCOUNT_ID` (account the data lands in), `SUBSCRIPTION_ACCOUNT_ID` (customer contract), `USAGE_CATEGORY` (usage label, such as `NetworkMonitoring`), `EVENT_NAME`, `INSTRUMENTATION_NAME`, `INSTRUMENTATION_PROVIDER`, `INSTRUMENTATION_VERSION`, `COLLECTOR_NAME`, `PRODUCT_FAMILY_GROUP` and `PRODUCT_FAMILY_SUBGROUP` (pre-built product split), `TOTAL_GB`. Gotchas: quote `"DATE"`; GB only, no event counts; `INSTRUMENTATION_VERSION` is `'unknown'` for ktranslate. Small and fast. See `npm.md`.
Last used: 2026-10-09.

### TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
Holds: ELIA, ingest bytes per entity per day, with the entity type. Key columns: `USAGE_DATE`, `ACCOUNT_ID`, `SUBSCRIPTION_ACCOUNT_ID`, `ENTITY_GUID` (one entity), `DOMAIN_TYPE` (entity type), `METRIC` (usage label), `DAILY_USAGE` (bytes), `INSTRUMENTATION_PROVIDER` (JSON array). Gotchas: huge with no clustering key, so filter on a few days; count `DISTINCT ENTITY_GUID`; `COLLECTOR_NAME` is empty for network devices, and there is no version column. See `npm.md`.
Last used: 2026-10-09.

### USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE
Holds: billed usage per billable account, meter and day, the financial system of record. Key columns: `START_TIME`, `BILLABLE_RPM_ACCOUNT_ID` (number), `PRODUCT_LINE`, `METRIC`, `QUANTITY`, `INSERTED_AT`. Gotchas: append-only, so only read it; de-duplicate repeated inserts; it can be empty for an EU account, so check the billing-pipeline views. See `billing.md`.
Last used: 2026-10-09.

### CONFORMED_USAGE_RATING.QBP_BILLING_PIPELINE.STG_QBP_BILLING_PIPELINE_USAGE_DAILY_BILLABLE_CUSTOMERROLLUP_PROD
Holds: billing-pipeline usage per telemetry account, customer contract, meter and day for US accounts; `…_EU_PROD` is the EU twin. Key columns: `START_TIME`, `TELEMETRY_ACCOUNT_ID` (number), `CUSTOMER_ID` (contract, `CC-…`), `CUSTOMER_STRUCTURE`, `PRODUCT_LINE`, `METRIC` (such as `GigabytesIngested`), `USAGE`, `BILLABLE_USAGE`, `IGNORED_USAGE`. Gotchas: query both regions, since an EU account appeared only in the EU view. See `billing.md`.
Last used: 2026-10-09.

### TRANSFORMED.SALES.SFDC_RPM_RECORD_D
Holds: RPM account to Salesforce account mapping. Key columns: `RPM_ACCOUNT_ID` (text), `RPM_ACCOUNT_NAME`, `SFDC_ACCOUNT_ID`, `IS_DELETED`. Gotchas: filter `IS_DELETED = FALSE`; `RPM_ACCOUNT_ID` is text, so quote IDs or cast the other side. See `customers.md`.
Last used: 2026-10-09.

### TRANSFORMED.SALES.SFDC_ACCOUNT_D
Holds: Salesforce accounts. Key columns: `SFDC_ACCOUNT_ID`, `SFDC_ACCOUNT_NAME`. Gotchas: the name column is `SFDC_ACCOUNT_NAME`; there is no `NAME`. See `customers.md`.
Last used: 2026-10-09.

### CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ACCOUNTS
Holds: New Relic accounts and their organisation. `…_ORGANIZATIONS` names the orgs, and `…_CUSTOMER_CONTRACTS` maps contracts (`CUSTOMER_ID`, `CC-…`) to a managing org. Key columns: `ID` (account ID), `NAME`, `ORGANIZATION_ID`, `UPDATED_AT`. Gotchas: several rows per ID, so keep the latest `UPDATED_AT` with `QUALIFY ROW_NUMBER()`; orgs named "New Relic Production US/EU" hold New Relic's own accounts. See `customers.md`.
Last used: 2026-10-09.
