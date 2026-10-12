# Finding data

Read this when no recipe in another note fits, or the user asks what data exists. It covers the
warehouse layout, naming rules and discovery queries.

## Layers and environments

dbt builds four zones. Each zone is fed by the one before it.

| Zone | Database | Holds | Use when |
|---|---|---|---|
| 1 | `RAW` | Untouched feeds: Kafka JSON, Fivetran, Segment, S3 | Rarely; only for raw JSON |
| 2 | `CONFORMED` | Staged views over raw data: entities, accounts, orgs, billing, usage, Salesforce, Zuora, users | You need clean, joined source data |
| 3 | `TRANSFORMED` | Marts with business logic: finance, sales, product consumption | `REPORTING` lacks what you need |
| 4 | `REPORTING` | Views behind Looker dashboards; pre-aggregated metrics | You need ready-made business metrics |

Other production databases:
- `USAGE_AND_RATING`: usage and consumption per account per day. It is the billing system of record (see `billing.md`).
- `CONFORMED_USAGE_RATING`: the billing pipeline's conformed views (schema `QBP_BILLING_PIPELINE`), with separate US and EU views (see `billing.md`).
- `NR_SILVER_DATALAKE_PROD`: the silver ingest layer, with Kafka streams, NRDB exports and raw Salesforce and Zuora feeds.
- `DATA_ANALYTICS`: GTM analytics and Tableau. `EA_REPORTING`: Enterprise Account reporting.

Each zone has `_STAGING` and `_DEV` copies (for example `CONFORMED_STAGING`), and developer sandboxes
start with `DEV_`. Query production only, unless the user asks otherwise.

Tooling: Airflow orchestrates, dbt transforms (`source.datanerd.us/dataos/dbt_core_models`) and Looker
visualises (`newrelic.cloud.looker.com`).

## Schemas worth knowing

- **`CONFORMED`:** `ENTITIES` (monitored entities, US/EU/staging), `SFDC` and `SALESFORCE` (CRM),
  `ZUORA` (subscriptions), `ORGANIZATION_DB` (org hierarchy and contracts), `USERS_DB`,
  `PRODUCT_CONSUMPTION_V2` (current product usage; `PRODUCT_CONSUMPTION` is v1),
  `NRDB_INGEST_V2` (ingest volumes), `ENTITY_INGEST`, `COMPACT_ENTITLEMENTS_V2` and
  `COMPACT_ORG_GROUP_ENTITLEMENTS_V2` (what accounts and org groups may use), `CUSTOMER360`,
  `GROWTH_ANALYTICS`, `PRODUCT_RATING`, `RUN_RATE`, `NETSUITE_V2`, `WORKDAY`, `DBT_ARTIFACTS` (dbt
  metadata) and `ELEMENTARY` (dbt tests).
- **`TRANSFORMED`:** `FINANCE`, `COMMON`, `SALES`, `PRODUCT_CONSUMPTION`, `PRODUCT_ENGINEERING`,
  `PRODUCT_MARKETING`, `PRODUCT_OBSERVABILITY`, `GROSS_MARGIN`, `EDP_OPERATIONS`.
- **`REPORTING`:** `REPORTING_LOOKER_PDT` (Looker persistent tables), `COMMON`, `NREM` (enterprise
  metrics), `CONSUMPTION_METRICS`, `PRODUCT_CONSUMPTION`, `REVENUE`, `PRODUCT_ENGINEERING`.

## Naming and classification

| Pattern | Meaning | Example |
|---|---|---|
| `STG_` | Staged (conformed) view | `STG_SFDC_ACCOUNT` |
| `_D` / `_F` suffix | Dimension / fact table (seen in table names) | `SFDC_ACCOUNT_D`, `ENTITY_INGEST_DAILY_F` |
| `DEV_<USER>_` | Developer sandbox database; never query | `DEV_SNAWAZ_CONFORMED` |
| `SVC_` | Service account | `SVC_AF_ETHEL_FINANCE_DEV` |
| `TEAM_<TEAM>_<SIZE>` | Team warehouse | `TEAM_PRODUCT_ANALYST_XSMALL` |

Governance tags: `data_classification` (Public, Internal, Confidential, Restricted), `is_pii`
(Snowflake should hold no PII), `department` and `owning_team`.

## Recipes

### Find tables by name
Use for: "is there a table with …". Search `CONFORMED`, `TRANSFORMED` and `REPORTING` one at a
time. Last used: 2026-10-09.

```sql
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, ROW_COUNT
FROM {{database}}.INFORMATION_SCHEMA.TABLES
WHERE LOWER(TABLE_NAME) LIKE '%{{search_term}}%'
ORDER BY TABLE_SCHEMA, TABLE_NAME
LIMIT 200
```

### Find columns by name
Use for: "which table has a column for …". Last used: 2026-10-09.

```sql
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM {{database}}.INFORMATION_SCHEMA.COLUMNS
WHERE LOWER(COLUMN_NAME) LIKE '%{{search_term}}%'
ORDER BY TABLE_SCHEMA, TABLE_NAME
LIMIT 200
```

### List a database's schemas
Last used: 2026-09-30.

```sql
SHOW SCHEMAS IN DATABASE {{database}}
```

### Look at one table
Use `DESCRIBE` for columns and types, then a 5-row sample. Last used: 2026-10-09.

```sql
DESCRIBE TABLE {{database}}.{{schema}}.{{table}}
```

```sql
SELECT * FROM {{database}}.{{schema}}.{{table}} LIMIT 5
```

### dbt model, source and exposure metadata
Use for: what a dbt model means, where it comes from and which dashboards use it. Last used: 2026-09-30.

```sql
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__CURRENT_MODELS LIMIT 20
```

```sql
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__SOURCES LIMIT 20
```

```sql
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__EXPOSURES LIMIT 20
```

## Pitfalls

- **One database at a time.** `INFORMATION_SCHEMA` covers only its own database, so search each one. Last used: 2026-10-09.
- **Never search the whole account.** `SHOW TABLES LIKE … IN ACCOUNT` ran past the 5-minute limit or came back empty every time, and a column search of `SNOWFLAKE.ACCOUNT_USAGE.COLUMNS` timed out too. List databases with `SHOW DATABASES`, which takes seconds, then search the likely ones with "Find tables by name" or "Find columns by name". Last used: 2026-10-09.
- **Views have no row count.** `ROW_COUNT` is empty for views, which are most of `CONFORMED` and `REPORTING`. Last used: 2026-09-30.
- **Never `USE`.** The guard refuses `USE`. Write fully qualified `DATABASE.SCHEMA.TABLE` names, which also work across databases. Critical. Last used: 2026-09-30.
- **Never count entities from `STG_ENTITIES`.** Those views sit on a raw entity table of tens of terabytes, with the type parsed from JSON, so even one day is very expensive. Count entities by type from ELIA (`npm.md`) instead, and use `STG_ENTITIES` only for a filtered lookup with `LIMIT`. Last used: 2026-09-30.

## Confluence pages

- [Databases, Schemas, VWs, Roles, Tags](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/2416705705): naming standards, RBAC, warehouse sizing.
- [Onboarding for New Data Engineers](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/3497230586): tech stack, dbt zones, environments.
- [Product Consumption & Billing](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/2419851420): pipeline, table schemas, business rules.
- [Architecture: Product Rating Data Service](https://newrelic.atlassian.net/wiki/spaces/GROW/pages/4357130070) and [Onboarding New Products for Usage Rating](https://newrelic.atlassian.net/wiki/spaces/GROW/pages/4340155340): how products get metered and rated.
