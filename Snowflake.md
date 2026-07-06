# Arshad_Snowflake Skill

Connect to New Relic's Snowflake instance and run analytical queries.

---

## WORKFLOW FLOWCHART (ALWAYS FOLLOW)

```
START
  |
  v
[1] ASK: "Is this DETERMINISTIC research or EXPLORATORY analysis?"
  |
  |---> DETERMINISTIC (specific question, known output)
  |       |
  |       v
  |     [2a] PLAN: Write out the exact queries needed BEFORE executing
  |       |         Show query plan to user for approval
  |       |         Estimate runtime per query
  |       v
  |     [3a] EXECUTE: Run approved queries (parallel if independent, serial if dependent)
  |       |
  |       v
  |     [4a] PRESENT: Return structured results with interpretation
  |
  |---> EXPLORATORY (open-ended, "what's available", discovery)
          |
          v
        [2b] PRESENT LANDSCAPE: Show what data domains exist in plain language
          |                      (use Object Inventory below)
          v
        [3b] NARROW: Ask user which domain/area to explore deeper
          |
          v
        [4b] SAMPLE: Show table structures, sample data, row counts
          |
          v
        [5b] ITERATE: Repeat until user has what they need
```

---

## EXECUTION RULES

1. **Never fire a live query without a plan** (deterministic) or context (exploratory)
2. **Parallel processing**: If multiple independent queries are needed and any single query may take >5 min, run them concurrently using background processes
3. **Serial processing**: If queries depend on each other (e.g., get account_id first, then filter usage), run sequentially
4. **Always estimate cost**: Before running, state which warehouse is being used and approximate data scanned
5. **Use LIMIT liberally**: For exploration, always LIMIT unless aggregating

---

## CONNECTION DETAILS

> **How to actually connect & run queries:** see [CLAUDE.md](CLAUDE.md). Use the
> persistent session (`session_server.py` + `./q`) — a single Okta browser auth per
> work session, not one popup per query. The config below is the canonical source of truth.

```python
import snowflake.connector

conn = snowflake.connector.connect(
    account='pda47359.us-east-1',
    user='JKARNIK',
    authenticator='externalbrowser',
    role='FR_PRODUCT_ANALYST',
    warehouse='TEAM_PRODUCT_ANALYST_XSMALL',
    client_store_temporary_credential=True,
)
```

- **Account**: pda47359.us-east-1
- **User**: JKARNIK
- **Auth**: Okta SSO (externalbrowser)
- **Role**: FR_PRODUCT_ANALYST
- **Warehouse**: TEAM_PRODUCT_ANALYST_XSMALL
- **Token caching**: Enabled (avoids repeat browser auth)

---

## DATA ARCHITECTURE OVERVIEW

The Snowflake warehouse follows a **layered architecture** managed by dbt:

```
RAW (Zone 1)          →  Raw ingested data (Kafka, Fivetran, Segment, S3)
    |
    v
CONFORMED (Zone 2)    →  Staged views on top of raw data (1,068 dbt models, ~36,700 columns)
    |
    v
TRANSFORMED (Zone 3)  →  Mart tables with business logic (336 dbt models, ~26,300 columns)
    |
    v
REPORTING (Zone 4)    →  Views for Looker dashboards (136 dbt models, ~54,200 columns)
```

**Total coverage**: 1,634 dbt models, ~117,000 columns across 3 core databases.

### Tech Stack
- **Snowflake**: Data Warehouse
- **Airflow**: Orchestration (DAGs at source.datanerd.us/dataos/dataos_airflow_dag)
- **DBT**: Transformations (models at source.datanerd.us/dataos/dbt_core_models)
- **Looker**: Visualization (newrelic.cloud.looker.com)
- **GitHub Enterprise**: Version Control (source.datanerd.us)

### Environment Map
| Layer | Production | Staging | Development |
|-------|-----------|---------|-------------|
| Zone 2 | CONFORMED | CONFORMED_STAGING | CONFORMED_DEV |
| Zone 3 | TRANSFORMED | TRANSFORMED_STAGING | TRANSFORMED_DEV |
| Zone 4 | REPORTING | REPORTING_STAGING | REPORTING_DEV |

Note: Staging uses production sources. Dev can use either.

---

## OBJECT INVENTORY (Plain Language)

### Core Production Databases

| Database | What It Holds | When To Use |
|----------|--------------|-------------|
| **CONFORMED** | Unified/standardized data from all source systems. The "single source of truth" layer. Contains entities, accounts, orgs, billing, usage metrics, Salesforce, Zuora, user data. 120+ schemas. | When you need clean, deduplicated, joined data across systems |
| **REPORTING** | Final reporting tables used by Looker dashboards. Pre-aggregated metrics. 1,861 Looker PDT objects. | When you need ready-to-consume business metrics |
| **TRANSFORMED** | Intermediate transformation layer. Business logic applied but not yet in final reporting shape. Finance (227 objects), Sales (79), Product Consumption (52). | When REPORTING doesn't have what you need and you want pre-processed data |
| **USAGE_AND_RATING** | Raw and processed usage/consumption data. Daily aggregations per customer/account. Billing meters. THE billing system of record. | When analyzing product usage, consumption patterns, billing |
| **RAW** | Raw ingested data before any transformation. JSON kafka feeds. | Rarely - only when you need untouched source data or raw JSON |
| **NR_SILVER_DATALAKE_PROD** | Kafka streams, NRDB exports, Salesforce, Zuora raw feeds. Fivetran connectors. The "silver" ingest layer. | When you need near-real-time or source-system-specific data |
| **DATA_ANALYTICS** | GTM analytics and Tableau integrations. | GTM/marketing analytics |
| **EA_REPORTING** | Enterprise Account reporting. | EA-specific analysis |

### Key Schemas Within CONFORMED (120+ schemas)

| Schema | Contains | Object Count |
|--------|----------|-------------|
| **ENTITIES** | All monitored entities (hosts, apps, databases, etc.) across US/EU/Staging | 8 objects (views + tables) |
| **SFDC** | Salesforce CRM - accounts, opportunities, contacts, leads | Large (300+ columns per model) |
| **SALESFORCE** | Alternate Salesforce schema | - |
| **ZUORA** | Subscription & billing data | - |
| **ORGANIZATION_DB** | Org hierarchy, org groups, customer contracts | - |
| **USERS_DB** | User accounts and profiles | - |
| **PRODUCT_CONSUMPTION** | Product-level usage metrics (v1) | - |
| **PRODUCT_CONSUMPTION_V2** | Product-level usage metrics (v2 - current) | - |
| **BILLING_PLATFORM** | Billing platform data | - |
| **NRDB_EVENTS_V2** | NRDB event data (telemetry events) | - |
| **NRDB_INGEST_V2** | Data ingest volumes | - |
| **ENTITY_INGEST** | Per-entity ingest metrics | - |
| **GROWTH_ANALYTICS** | Growth/adoption analytics | - |
| **CUSTOMER360** | Unified customer view | - |
| **COMPACT_ENTITLEMENTS_V2** | What features/products each account is entitled to | - |
| **COMPACT_ORG_GROUP_ENTITLEMENTS_V2** | Org-group level entitlements | - |
| **USAGE_COMPUTE** | Compute usage data | - |
| **USAGE_DATA_PLATFORM** | Data platform usage | - |
| **WORKDAY** | HR/people data | - |
| **APM_AGENT_ENVIRONMENT** | APM agent deployment data | - |
| **NR1_ENTITY_MERGED_V2** | Merged entity view for NR1 platform | - |
| **PRODUCT_RATING** | Product rating/billing calculations | - |
| **RUN_RATE** | Revenue run rate data | - |
| **GOOGLE_ADWORDS / LINKEDIN_ADS** | Marketing campaign data | - |
| **MARKETO / MKTO** | Marketing automation data | - |
| **NETSUITE / NETSUITE_V2** | ERP/financial data | - |
| **DBT_ARTIFACTS** | dbt model metadata (pseudo data dictionary) | 20+ tables |
| **ELEMENTARY** | dbt monitoring/testing framework | 20+ tables |

### REPORTING Key Schemas

| Schema | Objects | Purpose |
|--------|---------|---------|
| **REPORTING_LOOKER_PDT** | 1,861 | Looker Persistent Derived Tables |
| **COMMON** | 44 | Shared reporting objects |
| **NREM** | 34 | NR Enterprise Metrics |
| **CONSUMPTION_METRICS** | 32 | Consumption reporting |
| **PRODUCT_CONSUMPTION** | 30 | Product consumption reporting |
| **REVENUE** | 14 | Revenue reporting |
| **EDP_OPERATIONS** | 10 | EDP operations |
| **PRODUCT_ENGINEERING** | 2 | Product engineering metrics |

### TRANSFORMED Key Schemas

| Schema | Objects | Purpose |
|--------|---------|---------|
| **FINANCE** | 227 | Financial transformations |
| **COMMON** | 147 | Shared transformed objects |
| **SALES** | 79 | Sales data transformations |
| **WORK** | 68 | Work/project data |
| **PRODUCT_CONSUMPTION** | 52 | Product consumption marts |
| **EDP_OPERATIONS** | 38 | EDP pipeline operations |
| **PRODUCT_ENGINEERING** | - | Product engineering metrics |
| **PRODUCT_MARKETING** | - | Product marketing data |
| **PRODUCT_OBSERVABILITY** | - | Product observability metrics |
| **GROSS_MARGIN** | - | Gross margin calculations |

---

## KEY TABLE DETAILS

### CONFORMED.ENTITIES (DB 360 Analysis)

| Object | Type | Purpose |
|--------|------|---------|
| `STG_ENTITIES` | VIEW | All entities in US Production |
| `STG_ENTITIES_EU_PROD` | VIEW | All entities in EU Production |
| `STG_ENTITIES_STAGING` | VIEW | All entities in Staging |
| `STG_ENTITIES_RELATIONSHIPS` | VIEW | Entity relationship graph (US) |
| `STG_ENTITIES_RELATIONSHIPS_EU_PROD` | VIEW | Entity relationship graph (EU) |
| `STG_ENTITIES_RELATIONSHIPS_STAGING` | VIEW | Entity relationship graph (Staging) |
| `US_GUIDS` | TABLE | 824K rows - US entity GUIDs |
| `EU_GUID` | TABLE | 3 rows - EU reference |

### USAGE_AND_RATING.USAGE (Billing & Consumption)

| Table | Rows | Purpose | CAUTION |
|-------|------|---------|---------|
| `ALL_DAILY_USAGE` | 607M+ | Complete daily usage across all meters | APPEND-ONLY. System of record for financial compliance. NO deletions! |
| `ALL_DAILY_USAGE_CUSTOMER` | 73M+ | Usage rolled up per customer | - |
| `ALL_DAILY_USAGE_DAILY` | 5M+ | Daily aggregation summary | - |
| `DAILY_AGGREGATION_USER_CONSUMPTION_PROD` | 19M+ | Per-user consumption (US) | - |
| `DAILY_AGGREGATION_USER_CONSUMPTION_EU_PROD` | 2.9M+ | Per-user consumption (EU) | - |
| `CUSTOMER_CONTRACT_CUSTOMER_ID_PROD` | 411K | Customer-to-contract mapping | - |
| `CUSTOMER_CONTRACT_CUSTOMER_ID_EU_PROD` | 19K | EU customer-to-contract mapping | - |
| `DAILY_AGGREGATION_PROD` | 137K | Daily aggregation (US) | - |

---

## DATA DICTIONARY

### Live Schema Dictionary (Best Source)

The **Schema Drift Detection Engine** maintains a machine-generated, queryable data dictionary:

```sql
-- Query the live schema dictionary (~118K column definitions)
SELECT DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, COLUMN_NAME,
       DATA_TYPE, IS_NULLABLE, ORDINAL_POSITION,
       CHARACTER_MAX_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
FROM DEV_KNAGENDRA_TRANSFORMED.DIFF_ENGINE.SCHEMA_SNAPSHOTS
WHERE SCAN_ID = (
    SELECT MAX(SCAN_ID)
    FROM DEV_KNAGENDRA_TRANSFORMED.DIFF_ENGINE.DRIFT_SCAN_HISTORY
)
ORDER BY DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, ORDINAL_POSITION;
```

This covers all columns across CONFORMED, TRANSFORMED, and REPORTING with:
- Data types (TEXT, NUMBER, BOOLEAN, TIMESTAMP_NTZ, etc.)
- Nullability
- Precision/scale for numbers
- Max length for text fields

### dbt Model Metadata

```sql
-- Get all dbt models with descriptions
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__CURRENT_MODELS;

-- Get source definitions
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__SOURCES;

-- Get downstream exposures (dashboards, reports that depend on models)
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__EXPOSURES;
```

### Quick Table Discovery

```sql
-- Describe any table's structure
DESCRIBE TABLE <database>.<schema>.<table>;

-- Sample 5 rows from any table
SELECT * FROM <database>.<schema>.<table> LIMIT 5;

-- Search for tables by name across a database
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, ROW_COUNT
FROM <database>.INFORMATION_SCHEMA.TABLES
WHERE LOWER(TABLE_NAME) LIKE '%<search_term>%'
ORDER BY TABLE_NAME;
```

---

## PRODUCT CONSUMPTION & BILLING (Column-Level Detail)

### Source: Raw Product Consumption

Tables:
```
RAW.PRODUCT_CONSUMPTION.PRODUCT_CONSUMPTION_PRODUCTION_JSON
RAW.PRODUCT_CONSUMPTION.PRODUCT_CONSUMPTION_EU_PRODUCTION_JSON
RAW.PRODUCT_CONSUMPTION.PRODUCT_CONSUMPTION_STAGING_JSON
```

### product_consumption_daily_view Columns

| Column | Type | Description |
|--------|------|-------------|
| `consuming_account_id` | NUMBER | The account being billed |
| `master_account_id` | NUMBER | Parent/master account |
| `poa_account_id` | NUMBER | Partnership Owning Account |
| `billable_entity_id` | NUMBER | Billable entity identifier |
| `account_type` | VARCHAR | Account type classification |
| `usage_start_time` | TIMESTAMP | Start of the usage window (24h) |
| `usage_end_time` | TIMESTAMP | When value was reported (misleading name - more like `reported_at`) |
| `product_line` | VARCHAR | E.g., DataPlatform, FullStackObservability |
| `metric` | VARCHAR | E.g., GigabytesIngested, FullPlatformUsers, CoreUsers |
| `usage_type` | VARCHAR | "count" or "gauge" |
| `dp_bytes_ingested` | NUMBER(38,0) | Raw bytes ingested |
| `dp_gigabytes_ingested` | NUMBER(38,9) | Gigabytes ingested |
| `consumption` | NUMBER(38,9) | Consumption amount (COALESCE of consumption and nr.consumption) |
| `billable_consumption` | NUMBER(38,9) | Billable consumption amount |
| `estimated_cost` | NUMBER(38,9) | Estimated cost |
| `free_limit` | NUMBER | Free tier limit |
| `month` | VARCHAR | Month string |
| `month_timestamp` | TIMESTAMP | Month as timestamp |
| `processed_time` | TIMESTAMP | When product_rating processed the row (use to identify restreams/fixes) |
| `event_type` | VARCHAR | e.g., NrDailyConsumption |
| `event_date` | DATE | Date of event |
| `aggregate_state` | NUMBER | Internal: total usage measured (state / event_count = consumption) |
| `event_count` | NUMBER | Internal: total usage periods measured |
| `version` | VARCHAR | Event version |
| `usage_metric` | VARCHAR | Upstream usage stamper metric name |
| `json_content` | VARIANT | Full raw JSON payload |

### all_daily_usage Columns (CRITICAL TABLE)

| Column | Type | Description |
|--------|------|-------------|
| `start_time` | TIMESTAMP | Start of usage period |
| `billable_rpm_account_id` | NUMBER | = consuming_account_id |
| `metric` | VARCHAR | Usage metric name |
| `metric_type` | VARCHAR | "count" or "gauge" |
| `product_line` | VARCHAR | Product line |
| `usage_metric` | VARCHAR | Upstream usage metric |
| `quantity` | NUMBER | Usage quantity (dpBytes divided by 1B for GB) |
| `inserted_at` | TIMESTAMP | When row was inserted (BA uses for tie-breaking) |

**CRITICAL BUSINESS RULES for all_daily_usage**:
- APPEND-ONLY table. Never delete. System of record for financial compliance.
- Business Applications syncs at 2am PST daily.
- `inserted_at` is used to break tie conditions for multiple inserts.
- US/North America usage is prioritized over EU when both report (datacenter ASC ordering).
- De-duplication: ROW_NUMBER() PARTITION BY (consuming_account_id, usage_start_time, metric, product_line).

### Known Product Lines & Metrics

| Product Line | Metrics | Type |
|-------------|---------|------|
| DataPlatform | GigabytesIngested | count |
| FullStackObservability | OnDemandFullPlatformSessions | count |
| FullStackObservability | FullPlatformUsers | gauge |
| FullStackObservability | FullUsers | gauge |
| FullStackObservability | CoreUsers | gauge |

---

## NAMING STANDARDS (Official)

From Snowflake governance documentation:

| Abbreviation | Meaning | Example |
|-------------|---------|---------|
| `{DB}` | Database name | `COMMON_DEV` |
| `{APP}` | Application name | `FIVETRAN`, `DATABRICKS`, `AIRFLOW` |
| `{PRODUCT}` / `{SERVICE}` | Product name | `CLICKSTREAM` |
| `{ENV}` | Environment | `PROD`, `STAGING`, `DEV`, `PR_{PR_ID}` |
| `{TEAM}` | Team name | `PRODUCT_ANALYST`, `DATAOS` |
| `{PERM}` | Permission type | `RO` (read), `RW` (write), `A` (admin) |
| `SVC_` prefix | Service account | `SVC_AF_ETHEL_FINANCE_DEV` |
| `STG_` prefix | Staged/conformed view | `STG_SFDC_ACCOUNT` |
| `DEV_` prefix | Developer sandbox DB | `DEV_SNAWAZ_CONFORMED` |

### Warehouse Naming
- `TEAM_{TEAM_NAME}` - Team query warehouse (e.g., TEAM_PRODUCT_ANALYST_XSMALL)
- `APP_{APP_NAME}_{TEAM}_{ENV}` - Application-specific warehouse
- `DATA_INGEST_{APP}_{ENV}` - Ingest warehouse

### Data Classification Tags
| Tag | Values |
|-----|--------|
| `data_classification` | Public, Internal, Confidential, Restricted |
| `is_pii` | True/False (Snowflake should NOT store PII) |
| `department` | finance, product, ops, go_to_market |
| `owning_team` | dataos-platform, dataos-analytics, etc. |

---

## DATA PIPELINE FLOW (Product Consumption)

```
Usage Stamper (AAA Team)     -- Measures product usage per account
    |
    v
Usage Rating Service (ProdCon) -- Rates/estimates billing cost
    |
    v
Kafka Topics                  -- product_consumption topic (JSON)
    |
    v
Kafka Connect S3             -- Lands in S3 nr-datalake
    |
    v
Snowflake RAW                -- JSON tables (raw.product_consumption.*)
    |
    v
Materialized Views           -- Daily/hourly/monthly views (_daily_view)
    |
    v
Airflow (Ethel)              -- Joins usage + Zuora subscriptions
    |
    v
all_daily_usage              -- Final table for BA invoicing (USAGE_AND_RATING.USAGE)
```

**SLA**: Transform must complete before 2am PST (BA sync time).
**Slack channels**: #help-usage-pipeline (stamper), #help-product-consumption (rating)

---

## PARALLEL PROCESSING GUIDELINES

| Scenario | Strategy |
|----------|----------|
| Multiple independent counts/aggregations | Run in parallel (background bash processes) |
| Queries on 100M+ row tables | Warn user, estimate time, consider SAMPLE or date filters |
| Sequential dependency (need ID from query A to filter query B) | Serial execution |
| Same table, different filters | Parallel safe |
| Cross-database joins | Serial (may need USE DATABASE) |
| Full schema scan (all 3 DBs) | ~15-25 seconds total |
| Single model schema lookup | ~5-7 seconds |

---

## QUICK REFERENCE PATTERNS

### Get entity counts by type
```sql
SELECT TYPE, COUNT(*) as cnt
FROM CONFORMED.ENTITIES.STG_ENTITIES
GROUP BY TYPE
ORDER BY cnt DESC;
```

### Get account/org info
```sql
SELECT * FROM CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ORGANIZATIONS
WHERE <filter>
LIMIT 10;
```

### Check product usage for an account
```sql
SELECT * FROM USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE_CUSTOMER
WHERE CUSTOMER_ID = '<id>'
ORDER BY USAGE_DATE DESC
LIMIT 100;
```

### Find a table by name (across any database)
```sql
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, ROW_COUNT
FROM <DATABASE>.INFORMATION_SCHEMA.TABLES
WHERE LOWER(TABLE_NAME) LIKE '%<search>%'
ORDER BY TABLE_NAME;
```

### Get column definitions for a specific model (from live dictionary)
```sql
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, ORDINAL_POSITION
FROM DEV_KNAGENDRA_TRANSFORMED.DIFF_ENGINE.SCHEMA_SNAPSHOTS
WHERE DATABASE_NAME = '<DB>'
  AND SCHEMA_NAME = '<SCHEMA>'
  AND TABLE_NAME = '<TABLE>'
  AND SCAN_ID = (SELECT MAX(SCAN_ID) FROM DEV_KNAGENDRA_TRANSFORMED.DIFF_ENGINE.DRIFT_SCAN_HISTORY)
ORDER BY ORDINAL_POSITION;
```

### Check what products/entitlements an account has
```sql
SELECT * FROM CONFORMED.COMPACT_ENTITLEMENTS_V2.<table>
WHERE ACCOUNT_ID = <id>
LIMIT 20;
```

### Get Salesforce account data
```sql
SELECT * FROM CONFORMED.SFDC.STG_SFDC_ACCOUNT
WHERE <filter>
LIMIT 10;
```

---

## CONFLUENCE REFERENCE PAGES

| Page | Space | What It Covers | URL |
|------|-------|---------------|-----|
| Databases, Schemas, VWs, Roles, Tags | DATA | Official naming standards, RBAC, warehouse sizing | [Link](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/2416705705) |
| Onboarding for New Data Engineers | DATA | Tech stack, DBT zones, git workflows, environment map | [Link](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/3497230586) |
| Schema Drift Detection Engine | DATA | Column-level schema for all 117K columns, drift tracking | [Link](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/5214897306) |
| Product Consumption & Billing | DATA | Pipeline architecture, table schemas, business rules | [Link](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/2419851420) |
| Architecture: Product Rating Data Service | GROW | Product rating system architecture | [Link](https://newrelic.atlassian.net/wiki/spaces/GROW/pages/4357130070) |
| Onboarding New Products for Usage Rating | GROW | How new products get metered and billed | [Link](https://newrelic.atlassian.net/wiki/spaces/GROW/pages/4340155340) |

---

## IMPORTANT CAVEATS

1. **all_daily_usage is sacred** - Never suggest DELETE/DROP. Append-only for financial compliance.
2. **STG_ENTITIES views can be large** - Always use filters (TYPE, DOMAIN, ACCOUNT_ID) or LIMIT.
3. **XSMALL warehouse** - Our warehouse is extra-small. Queries on 600M+ row tables will be slow. Consider date filters or SAMPLE.
4. **No PII in Snowflake** - Per data classification rules, Snowflake should not store PII.
5. **Production vs Dev** - Always query production databases (CONFORMED, TRANSFORMED, REPORTING) unless explicitly testing.
6. **Token caching** - First connection requires browser auth. Subsequent connections in same session reuse the token.
