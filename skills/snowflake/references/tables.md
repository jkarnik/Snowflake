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
Holds: Instrumentation Insights (II), GB ingested per account, day, event and instrumentation. Key columns: `"DATE"` (day), `SUB_ACCOUNT_ID` (account the data lands in), `SUBSCRIPTION_ACCOUNT_ID` (customer contract), `USAGE_CATEGORY` (usage label, such as `NetworkMonitoring`), `EVENT_NAME`, `INSTRUMENTATION_NAME`, `INSTRUMENTATION_PROVIDER`, `INSTRUMENTATION_VERSION`, `COLLECTOR_NAME`, `PRODUCT_FAMILY_GROUP` and `PRODUCT_FAMILY_SUBGROUP` (pre-built product split), `TOTAL_GB`. Gotchas: quote `"DATE"`; GB only, no event counts; `INSTRUMENTATION_VERSION` is `'unknown'` for ktranslate; `SUBSCRIPTION_ACCOUNT_ID` mixes `CC-…` contracts with plain account IDs, and an account's value can change mid-window; `USAGE_CATEGORY = 'LoggingArchive'` is not billable; `INGEST_POINT` is a host name (`gov-…`) for some data but only `api.metrics.raw`, `api.events` or `api.logs` for network data. A 30-day scan takes about 30 seconds. See `npm.md`.
Last used: 2026-11-03.

### TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
Holds: ELIA, ingest bytes per entity per day, with the entity type. Key columns: `USAGE_DATE`, `ACCOUNT_ID`, `SUBSCRIPTION_ACCOUNT_ID`, `ENTITY_GUID` (one entity), `DOMAIN_TYPE` (entity type), `METRIC` (usage label), `DAILY_USAGE` (bytes), `INSTRUMENTATION_PROVIDER` (JSON array). Gotchas: huge with no clustering key, so filter on a few days; count `DISTINCT ENTITY_GUID`; `COLLECTOR_NAME` is empty for network devices, and there is no version column; `ENTITY_GUID` is base64 of `account|domain|type|id`; `NEWRELIC_SOURCE` says how the data arrived (`metricAPI`, `prometheusAPI`, `api.logs`, …); there are no entity names. See `npm.md`.
Last used: 2026-10-21.

### USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE
Holds: billed usage per billable account, meter and day, the financial system of record. Key columns: `START_TIME`, `BILLABLE_RPM_ACCOUNT_ID` (number), `PRODUCT_LINE`, `METRIC`, `QUANTITY`, `INSERTED_AT`. Gotchas: append-only, so only read it; de-duplicate repeated inserts; it can be empty for an EU account, so check the billing-pipeline views. See `billing.md`.
Last used: 2026-10-09.

### CONFORMED_USAGE_RATING.QBP_BILLING_PIPELINE.STG_QBP_BILLING_PIPELINE_USAGE_DAILY_BILLABLE_CUSTOMERROLLUP_PROD
Holds: billing-pipeline usage per telemetry account, customer contract, meter and day for US accounts; `…_EU_PROD` is the EU twin. Key columns: `START_TIME`, `TELEMETRY_ACCOUNT_ID` (number), `CUSTOMER_ID` (contract, `CC-…`), `CUSTOMER_STRUCTURE`, `PRODUCT_LINE`, `METRIC` (such as `GigabytesIngested`), `USAGE`, `BILLABLE_USAGE`, `IGNORED_USAGE`. Gotchas: query both regions, since an EU account appeared only in the EU view; `BILLABLE_USAGE` is usage minus the free allowance for everyone, so it is not a paid signal; repeated rows need the latest `INSERTED_AT`. See `billing.md`.
Last used: 2026-10-23.

### TRANSFORMED.SALES.SFDC_RPM_RECORD_D
Holds: RPM account to Salesforce account mapping. Key columns: `RPM_ACCOUNT_ID` (text), `RPM_ACCOUNT_NAME`, `SFDC_ACCOUNT_ID`, `IS_DELETED`. Gotchas: filter `IS_DELETED = FALSE`; `RPM_ACCOUNT_ID` is text, so quote IDs or cast the other side. See `customers.md`.
Last used: 2026-11-03.

### TRANSFORMED.SALES.SFDC_ACCOUNT_D
Holds: Salesforce accounts. Key columns: `SFDC_ACCOUNT_ID`, `SFDC_ACCOUNT_NAME`, `IS_DELETED`, `OWNER_ID`, `ACCOUNT_OWNER_NAME` and `ACCOUNT_OWNER_ROLE` (the owner, who is the AE), `PARENT_ID`, `ULTIMATE_PARENT_ACCOUNT_ID` (the company family), `ACCOUNT_ARR` and `FAMILY_ARR` (Salesforce ARR), `SFDC_ACCOUNT_TYPE`, and `WEBSITE` and `ZI_*` company fields (to tell look-alike companies apart). Gotchas: the name column is `SFDC_ACCOUNT_NAME`; there is no `NAME`; filter `IS_DELETED = FALSE`; an owner whose role is `Mulesoft User` is an integration, not a person. See `customers.md`.
Last used: 2026-11-03.

### CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ACCOUNTS
Holds: New Relic accounts and their organisation. `…_ORGANIZATIONS` names the orgs (`NAME`, `PRIMARY_REGION_CODE`, `REPORTING_ACCOUNT_ID`), and `…_CUSTOMER_CONTRACTS` maps contracts to a managing org (`CUSTOMER_ID` is the `CC-…`, with `LEGACY_RPM_ID`, `TELEMETRY_ACCOUNT_ID` and `MANAGING_ORGANIZATION_ID`). Key columns: `ID` (account ID), `NAME`, `ORGANIZATION_ID`, `UPDATED_AT`. Gotchas: several rows per ID, so keep the latest `UPDATED_AT` with `QUALIFY ROW_NUMBER()`; orgs named "New Relic Production US/EU" hold New Relic's own accounts. See `customers.md`.
Last used: 2026-11-03.

### TRANSFORMED.COMMON.ACCOUNT_DAILY_D
Holds: a daily snapshot per RPM account, with its contract and the contract's own Salesforce account. Key columns: `REPORT_AS_OF_DT` (snapshot day), `ACCOUNT_ID` (text), `CUSTOMER_CONTRACT_ID` (the `CC-…`), `SFDC_ACCOUNT_ID`, `SFDC_CC_ACCOUNT_ID` and `SFDC_CC_ACCOUNT_NAME` (the contract's Salesforce account), `IS_INTERNAL_ACCOUNT` (New Relic's own), `IS_PARTNER`. Gotchas: huge with no clustering key, so always filter `REPORT_AS_OF_DT` (one day runs in seconds); `IS_INTERNAL_ACCOUNT` is the reliable internal flag, but it was almost empty in 2025 snapshots; a 2025 snapshot holds only a small share of the accounts that were sending data then, so don't use it for history; `PARTNERSHIP_NAME` is mostly empty, so use the RPM table's. See `customers.md`.
Last used: 2026-11-03.

### TRANSFORMED.COMMON.RPM_ACCOUNT_DAILY_D
Holds: a daily snapshot per RPM account, with its plan. Key columns: `REPORT_AS_OF_DT`, `ACCOUNT_ID` (text), `IS_PAID` (true when the account has an active buying program), `PARTNERSHIP_NAME` (sales partnership, such as New Relic Japan KK, a reseller or a marketplace), `POA_ACCOUNT_ID`, `FREE_INGEST_GB` (free allowance; above 100 means a trial or program), `CUSTOMER_CONTRACT_ID`, `BUYING_PROGRAM`, `ACCOUNT_TYPE` (master or sub), `ULTIMATE_PARENT_ACCOUNT_ID`, `ACCOUNT_PAY_METHOD`. Gotchas: history starts 2026-01-01, so earlier paid status isn't here; filter `REPORT_AS_OF_DT` (one day runs in seconds); `IS_INTERNAL_ACCOUNT` is TRUE on every networking account, so ignore it and use `ACCOUNT_DAILY_D`'s; customers who buy through New Relic Japan KK or its resellers show `IS_PAID = FALSE` plus a partnership. See `customers.md`.
Last used: 2026-11-03.

### TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D
Holds: the Salesforce account team. Key columns: `ACCOUNT_ID` (Salesforce account), `USER_ID`, `TEAM_MEMBER_ROLE`, `IS_DELETED`. Gotchas: role labels are loose. Most TSMs sit under "Expansion Driver", and the "AE" role also holds SCs, TSMs and past AEs, so classify people by `SFDC_USER_D.TITLE`. The SC label is "Solutions Consultant" (plural). See `customers.md`.
Last used: 2026-10-13.

### TRANSFORMED.SALES.SFDC_USER_D
Holds: Salesforce users. Key columns: `USER_ID`, `NAME`, `EMAIL`, `TITLE`, `IS_ACTIVE`. Gotchas: filter `IS_ACTIVE` to drop people who have left. See `customers.md`.
Last used: 2026-10-13.

### TRANSFORMED.FINANCE.CONTRACT_RATE_DAILY_D
Holds: contract terms per contract and day. Key columns: `REPORT_AS_OF_DT`, `CUSTOMER_CONTRACT_ID` and `CUSTOMER_ACCOUNT_ID` (`CC-…`), `SFDC_ULT_PARENT_ACCOUNT_ID`, `BUYING_PROGRAM` (Savings Plan, Volume Plan, PAYG, …), `CONTRACT_STATUS`, `CONTRACT_START_DATE`, `CONTRACT_END_DATE`, `ACR` (yearly commitment), `TOTAL_CONTRACT_VALUE`, `CURRENCY_CODE`, `PRODUCT_NAME`. Gotchas: filter `REPORT_AS_OF_DT`; history starts 2026-04-12, so contracts that ended earlier are missing; `SFDC_ACCOUNT_ID` was empty, so match by `SFDC_ULT_PARENT_ACCOUNT_ID` or `CUSTOMER_ACCOUNT_ID`; customers billed through New Relic Japan KK have no row. See `billing.md`.
Last used: 2026-10-23.

### TRANSFORMED.FINANCE.CUSTOMER_DAILY_D
Holds: customers on a buying program, per day; `IS_PAID` in `RPM_ACCOUNT_DAILY_D` is derived from it. Key columns: `REPORT_AS_OF_DT`, `CUSTOMER_ACCOUNT_ID` (`CC-…`), `CONTRACT_ID`, `BUYING_PROGRAM`, `SRC`. Gotchas: read the `FINANCE` copy, since the `COMMON` copy isn't readable; 2025 rows miss customers on the newer billing platform (`SRC = 'BillingPlatform'` appears only from 2026), so big paying customers look free. Don't use it for past paid status. See `customers.md`.
Last used: 2026-10-23.

### TRANSFORMED.FINANCE.MT_DENORM_CONSUMPTION_DAILY_METRICS_HEADER
Holds: Finance's daily consumption and contract metrics per Salesforce account. Key columns: `REPORT_AS_OF_DT`, `SFDC_ACCOUNT_ID`, `SFDC_ACCOUNT_NAME`, `SFDC_ULTIMATE_PARENT_ACCOUNT_NAME`, `BUYING_PROGRAM`, `PARTNERSHIP_NAME`, `EFFECTIVE_ACR` (yearly commitment), `BCM_TTM_AMT` (billable consumption over 12 months, in dollars), `BCM_RUN_RATE`, `BILLABLE_CONTRACT_START_DATE` and `…_END_DATE`. Gotchas: read the latest `REPORT_AS_OF_DT`; contracts that have ended drop out of it. The look-alike `MT_DENORM_CONSUMPTION_DAILY_METRICS` (no `_HEADER`) stopped in March 2026, so use `_HEADER` or `_DETAIL`; `REPORTING.CONSUMPTION_METRICS` has views with the same names, which have their own entry. See `billing.md`.
Last used: 2026-11-03.

### TRANSFORMED.FINANCE.MT_BCM_XACTLY_INTEGRATION
Holds: monthly consumption per Salesforce account from the Xactly integration. Key columns: `CREDIT_MONTH`, `SFDC_ACCOUNT_ID`, `SFDC_ULTIMATE_PARENT_ID`, `SUBSCRIPTION_ACCOUNT_ID`, `TOTAL_CONSUMPTION`, `ADJ_CONSUMPTION_AMT`, `YTD_CONSUMPTION_AMT`. Gotchas: use the YTD column, which resets each April 1; adding `TOTAL_CONSUMPTION` and `ADJ_CONSUMPTION_AMT` over-counts. It still holds contracts that have left the `_HEADER` table. See `billing.md`.
Last used: 2026-10-22.

### TRANSFORMED.COMMON.ACCOUNT_ENTITLEMENTS_NEW_D_TV
Holds: entitlements per RPM account; `CUSTOMER_ENTITLEMENTS_D_TV` is the per-customer twin, keyed by `NR_CUSTOMER_ID` (`CC-…`). Key columns: `RPM_ACCOUNT_ID`, `ENTITLEMENT_TYPE` (such as `IS_FEDRAMP` or `IS_HIPAA`), `ENTITLEMENT_VALUE`, `IS_ACTIVE`, `PRODUCT_LINE`. Gotchas: take value 1 with `IS_ACTIVE`; value 0 means switched off; the `…_CAPABLE` types mean eligible only. Filtered queries run in seconds. The raw feed `CONFORMED.COMPACT_ENTITLEMENTS_V2.*` holds the same flags as JSON keys, but its `MESSAGE_KEY` is a hash, so use these tables. See `customers.md`.
Last used: 2026-10-21.

### REPORTING.CONSUMPTION_METRICS.CONSUMPTION_DAILY_METRICS_DETAIL
Holds: Finance's daily consumption, price and forecast per customer account, meter and product, a view over `TRANSFORMED.FINANCE.MT_DENORM_CONSUMPTION_DAILY_METRICS_DETAIL` with excluded rows dropped. `…_HEADER` in the same schema has one row per account and day, with names, ACR and pricing flags. Key columns: `REPORT_AS_OF_DT` (snapshot day), `CUSTOMER_ACCOUNT_ID` (a `CC-…`, or a `BP-…` or plain account ID on older rows; `SUBSCRIPTION_ACCOUNT_ID` is an alias of it), `UOM_CATEGORY` (the meter: `Ingest`, `Full User`, `Core User`, `CCU`, `Synthetics`, …), `UOM_SUBCATEGORY`, `MTD_ACTUALS_QTY` and `MTD_ACTUALS_BILLED_QTY` (month-to-date quantity, and the part above the free allowance), `MTD_EFF_AMT` and `MTD_CONTR_AMT` (effective and contractual amount), `MTD_EFF_UNIT_PRICE` and `MTD_CONTR_UNIT_PRICE`, `MTHLY_FCST_*` (the month's forecast versions), `DISCOUNT_RATE`. Header: `EFFECTIVE_ACR`, `EFFECTIVE_SUBSCRIPTION_ACCOUNT_NAME`, `HAS_CCU_SKUS`, `IS_TIERED_PRICING`, `BUYING_PROGRAM`. Gotchas: filter `REPORT_AS_OF_DT` (one day runs in seconds), and read the snapshot on a month's last day for its final figure; an account has several rows per meter (US, EU, logs, product), so sum amounts and quantities, then divide; a unit price is amount ÷ billed quantity and is empty when nothing is billed; effective price isn't contractual × (1 − `DISCOUNT_RATE`); network ingest is under `Ingest`, and `CCU` is a separate meter; there is no currency column; customers billed through New Relic Japan KK, one-time deals and many free-tier accounts have no `Ingest` rows. See `billing.md`.
Last used: 2026-11-03.

### CONFORMED.SFDC.STG_SFDC_CONTACT
Holds: Salesforce contacts, the people at a customer company. Key columns: `ACCOUNT_ID` (Salesforce account), `NAME`, `TITLE`, `EMAIL`, `CONTACT_STATUS_C`, `IS_DELETED`, `IS_EMAIL_BOUNCED`, `HAS_OPTED_OUT_OF_EMAIL`, `LAST_MODIFIED_DATE`. Gotchas: a company can have hundreds of contacts, so pick one with `QUALIFY ROW_NUMBER()`; drop deleted, bounced and opted-out contacts; a contact isn't necessarily a user of the New Relic account. Email columns also exist in `BILLING_PLATFORM.STG_BILLING_PLATFORM_BILLING_PROFILE` and `COMMON.STG_RPM_ACCOUNTS_DB_PRODUCTION_RPM_PRODUCTION_USERS`, not tried yet. See `customers.md`.
Last used: 2026-11-03.
