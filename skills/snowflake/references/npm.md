# NPM adoption and usage

Read this for Network Performance Monitoring questions: devices, device types, accounts reporting
network data, NPM ingest (SNMP, syslog, flow, traps) and trends.

## Two sources, two definitions

| Source | Table | NPM filter | Grain | Use for |
|---|---|---|---|---|
| ELIA (entity-level ingest) | `TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F` | `METRIC = 'NetworkMonitoring'` | Rows can repeat per entity and day, so count `DISTINCT ENTITY_GUID` | Devices, device types, accounts with devices |
| Instrumentation Insights (II) | `TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F` | `USAGE_CATEGORY = 'NetworkMonitoring'` | Ingest per account, event and day | GB ingested, split by data type |

ELIA key columns: `USAGE_DATE`, `ACCOUNT_ID` (the account the data lands in),
`SUBSCRIPTION_ACCOUNT_ID` (the customer contract, `CC-…`, which groups a client's accounts),
`ENTITY_GUID` (one device), `METRIC`, `DOMAIN_TYPE` (the device type, for example
`EXT-MERAKI_DEVICE` or `INFRA-JUNIPER_MIST_SWITCH`), `ENTITY_TYPE`, `DAILY_USAGE` (bytes, additive
across rows), `IS_REPORTING`, `HAS_DAILY_CONSUMPTION`, `DATA_CENTER`, `INSTRUMENTATION_PROVIDER`
and `COLLECTOR_NAME`.

II key columns: `DATE`, `SUB_ACCOUNT_ID`, `SUBSCRIPTION_ACCOUNT_ID`, `EVENT_NAME`, `TOTAL_GB`,
`USAGE_CATEGORY`, `DATA_TYPE`, `INSTRUMENTATION_NAME`, `INSTRUMENTATION_PROVIDER`,
`INSTRUMENTATION_SOURCE`, `COLLECTOR_NAME`, `INGEST_POINT` and the `PRODUCT_FAMILY…` columns. II is
a stream from NR1 with fewer fields than NR1 itself. Adding fields is expensive, so if a field is
missing here, it isn't in Snowflake.

II subgroup from `EVENT_NAME`: `Metric` → SNMP metrics, `Log` → syslog, `KFlow` → flow,
`KSnmpTrap` → SNMP traps, and anything else → other. II holds GB (`TOTAL_GB`), not event counts, so
`KSnmpTrap` rows give trap GB per account per day, not trap counts. The same split is pre-built in
`PRODUCT_FAMILY_SUBGROUP` (`SnmpMetric`, `KFlow`, `Syslog`, `SnmpTrap`, `Other`) under
`PRODUCT_FAMILY_GROUP = 'Network Monitoring'`. `Syslog` also holds ktranslate's own health logs
(`INSTRUMENTATION_NAME = 'ktranslate-health'`), and Meraki API metrics count as `SnmpMetric`. In II,
Meraki is `INSTRUMENTATION_NAME = 'meraki-device'` or `LIKE 'meraki.%'`.

## Recipes

### Devices and accounts by device type, one day
Use for: "how many accounts had network devices reporting on day X, by device type". Last used: 2026-10-01.

```sql
SELECT DOMAIN_TYPE AS DEVICE_TYPE,
       COUNT(DISTINCT ACCOUNT_ID) AS ACCOUNTS,
       COUNT(DISTINCT ENTITY_GUID) AS DEVICES
FROM TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
WHERE METRIC = 'NetworkMonitoring'
  AND USAGE_DATE = '{{start_date}}'
GROUP BY DOMAIN_TYPE
ORDER BY DEVICES DESC
```

### Accounts and devices reporting, per day
Use for: adoption trends. Last used: 2026-09-30.

```sql
SELECT USAGE_DATE,
       COUNT(DISTINCT ACCOUNT_ID) AS ACCOUNTS,
       COUNT(DISTINCT ENTITY_GUID) AS DEVICES
FROM TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
WHERE METRIC = 'NetworkMonitoring'
  AND USAGE_DATE >= '{{start_date}}' AND USAGE_DATE < '{{end_date}}'
GROUP BY USAGE_DATE
ORDER BY USAGE_DATE
```

### NPM ingest GB by subgroup
Use for: "NPM ingest split into SNMP, syslog, flow and traps". Last used: 2026-11-03.

```sql
SELECT CASE EVENT_NAME
           WHEN 'Metric' THEN 'SnmpMetric'
           WHEN 'Log' THEN 'Syslog'
           WHEN 'KFlow' THEN 'KFlow'
           WHEN 'KSnmpTrap' THEN 'SnmpTrap'
           ELSE 'other'
       END AS SUBGROUP,
       SUM(TOTAL_GB) AS GB
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE USAGE_CATEGORY = 'NetworkMonitoring'
  AND "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
GROUP BY SUBGROUP
ORDER BY GB DESC
```

### Top accounts by NPM ingest
Use for: the biggest NPM users in a period. For one subgroup such as syslog, add `AND PRODUCT_FAMILY_SUBGROUP = 'Syslog'` and `AND COALESCE(INSTRUMENTATION_NAME, '') <> 'ktranslate-health'` (ktranslate's own logs); group by `SUB_ACCOUNT_ID` for accounts rather than contracts. Last used: 2026-11-03.

```sql
SELECT SUBSCRIPTION_ACCOUNT_ID, SUM(TOTAL_GB) AS GB
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE USAGE_CATEGORY = 'NetworkMonitoring'
  AND "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
GROUP BY SUBSCRIPTION_ACCOUNT_ID
ORDER BY GB DESC
LIMIT 20
```

### Network data sources for an account
Use for: "what sends network data to account X": collector, profile (`INSTRUMENTATION_NAME`),
version and subgroup, including Mist and the network agent. Last used: 2026-10-30.

```sql
SELECT INSTRUMENTATION_PROVIDER, COLLECTOR_NAME, INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION,
       EVENT_NAME, USAGE_CATEGORY, PRODUCT_FAMILY_SUBGROUP,
       COUNT(DISTINCT "DATE")  AS DAYS,
       ROUND(SUM(TOTAL_GB), 2) AS GB
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE TO_VARCHAR(SUB_ACCOUNT_ID) = '{{account_id}}'
  AND "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
  AND (USAGE_CATEGORY = 'NetworkMonitoring'
       OR INSTRUMENTATION_PROVIDER = 'kentik'
       OR COLLECTOR_NAME = 'network-agent'
       OR INSTRUMENTATION_NAME = 'juniper-mist')
GROUP BY ALL
ORDER BY GB DESC
```

### Networking clients: average daily GB and paying status
Use for: "list our networking customers with their daily data and whether they pay", and the base for
counts, growth or account-team lists. A client is a customer contract; `{{end_date}}` is exclusive,
and the snapshot tables are read on its previous day. To add the AE, SC and TSM, join the result's
contract to a Salesforce account (see "Account owners" in `customers.md`). Last used: 2026-11-03.

```sql
WITH AMAP AS (
    SELECT SUB_ACCOUNT_ID, MAX_BY(SUBSCRIPTION_ACCOUNT_ID, "DATE") AS SUB_ID,
           SUM(IFF(USAGE_CATEGORY = 'NetworkMonitoring', TOTAL_GB, 0)) AS NPM_GB,
           SUM(IFF(USAGE_CATEGORY = 'LoggingArchive', 0, TOTAL_GB)) AS ALL_GB
    FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
    WHERE "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
    GROUP BY SUB_ACCOUNT_ID
),
ACCT AS (
    SELECT * FROM AMAP
    WHERE SUB_ID IN (SELECT SUB_ID FROM AMAP WHERE NPM_GB > 0)
),
ORG AS (
    SELECT TO_VARCHAR(A.ID) AS ACCOUNT_ID, O.NAME AS ORG_NAME
    FROM CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ACCOUNTS A
    LEFT JOIN CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ORGANIZATIONS O ON O.ID = A.ORGANIZATION_ID
    WHERE TO_VARCHAR(A.ID) IN (SELECT TO_VARCHAR(SUB_ACCOUNT_ID) FROM ACCT)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY A.ID ORDER BY A.UPDATED_AT DESC, O.UPDATED_AT DESC) = 1
),
RPM AS (
    SELECT ACCOUNT_ID, IS_PAID, PARTNERSHIP_NAME, FREE_INGEST_GB
    FROM TRANSFORMED.COMMON.RPM_ACCOUNT_DAILY_D
    WHERE REPORT_AS_OF_DT = DATEADD(DAY, -1, '{{end_date}}'::DATE)
      AND ACCOUNT_ID IN (SELECT TO_VARCHAR(SUB_ACCOUNT_ID) FROM ACCT)
),
CC AS (
    SELECT CUSTOMER_CONTRACT_ID AS SUB_ID, COALESCE(MAX(IS_INTERNAL_ACCOUNT::INT), 0) = 1 AS IS_INTERNAL
    FROM TRANSFORMED.COMMON.ACCOUNT_DAILY_D
    WHERE REPORT_AS_OF_DT = DATEADD(DAY, -1, '{{end_date}}'::DATE)
      AND CUSTOMER_CONTRACT_ID IN (SELECT SUB_ID FROM ACCT)
    GROUP BY 1
),
CLIENT AS (
    SELECT A.SUB_ID, SUM(A.NPM_GB) AS NPM_GB, SUM(A.ALL_GB) AS ALL_GB,
           BOOLOR_AGG(COALESCE(R.IS_PAID, FALSE)) AS IS_PAID,
           MAX(R.PARTNERSHIP_NAME) AS PARTNERSHIP,
           COALESCE(MAX(R.FREE_INGEST_GB), 100) AS MAX_FREE_GB
    FROM ACCT A
    LEFT JOIN ORG O ON O.ACCOUNT_ID = TO_VARCHAR(A.SUB_ACCOUNT_ID)
    LEFT JOIN RPM R ON R.ACCOUNT_ID = TO_VARCHAR(A.SUB_ACCOUNT_ID)
    WHERE NOT COALESCE(O.ORG_NAME IN ('New Relic Production US', 'New Relic Production EU'), FALSE)
      AND A.SUB_ID NOT IN (SELECT SUB_ID FROM CC WHERE IS_INTERNAL)
    GROUP BY A.SUB_ID
    HAVING SUM(A.NPM_GB) > 0
       AND NOT BOOLOR_AGG(COALESCE(R.PARTNERSHIP_NAME ILIKE 'New Relic Internal Use%', FALSE))
)
SELECT SUB_ID AS CUSTOMER_ID,
       ROUND(NPM_GB / DATEDIFF(DAY, '{{start_date}}', '{{end_date}}'), 3) AS AVG_DAILY_NETWORK_GB,
       ROUND(ALL_GB / DATEDIFF(DAY, '{{start_date}}', '{{end_date}}'), 1) AS AVG_DAILY_TOTAL_GB,
       CASE WHEN IS_PAID OR PARTNERSHIP IS NOT NULL THEN
                CASE WHEN ALL_GB <= 100 THEN 'No, usage within free 100 GB'
                     WHEN IS_PAID THEN 'Yes'
                     ELSE 'Yes, via partner (' || TRIM(PARTNERSHIP) || ')' END
            WHEN MAX_FREE_GB > 100 THEN 'No, free (trial or program allowance)'
            ELSE 'No, free tier' END AS PAYING
FROM CLIENT
ORDER BY AVG_DAILY_NETWORK_GB DESC
```

### Accounts first and last seen on a data source
Use for: "has any new client started sending X", where X is an II `INSTRUMENTATION_NAME` such as
`juniper-mist`. `FIRST_DAY` can't be earlier than `{{start_date}}`, so start well before the window
you care about. Roll accounts up to contracts as in "Networking clients". Last used: 2026-10-21.

```sql
SELECT SUB_ACCOUNT_ID, MAX_BY(SUBSCRIPTION_ACCOUNT_ID, "DATE") AS SUB_ID,
       MIN("DATE") AS FIRST_DAY, MAX("DATE") AS LAST_DAY, COUNT(DISTINCT "DATE") AS DAYS,
       ROUND(SUM(TOTAL_GB) / COUNT(DISTINCT "DATE"), 3) AS AVG_GB_DAY
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE INSTRUMENTATION_NAME = '{{search_term}}' AND "DATE" >= '{{start_date}}'
GROUP BY SUB_ACCOUNT_ID
ORDER BY FIRST_DAY DESC
```

### Find data sources by name
Use for: "what names does X send data under", when the exact `INSTRUMENTATION_NAME` or collector is
unknown. Found a customer's own `mist-api-poller` that way. Words like "mist" also match unrelated
names, so read the provider and collector columns before counting. Last used: 2026-10-21.

```sql
SELECT INSTRUMENTATION_NAME, INSTRUMENTATION_PROVIDER, COLLECTOR_NAME, USAGE_CATEGORY,
       COUNT(DISTINCT SUB_ACCOUNT_ID) AS ACCOUNTS, MIN("DATE") AS FIRST_DAY,
       ROUND(SUM(TOTAL_GB) / COUNT(DISTINCT "DATE"), 3) AS AVG_GB_DAY
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
  AND (INSTRUMENTATION_NAME ILIKE '%{{search_term}}%' OR COLLECTOR_NAME ILIKE '%{{search_term}}%'
       OR INSTRUMENTATION_PROVIDER ILIKE '%{{search_term}}%')
GROUP BY ALL
ORDER BY AVG_GB_DAY DESC
```

### SNMP device profiles in use
Use for: "which device profiles or vendors do customers poll over SNMP". In II, `INSTRUMENTATION_NAME` on `EVENT_NAME = 'Metric'` rows is the ktranslate device profile (`cisco-catalyst`, `fortinet-fortigate`, …). `heartbeat`, `ping`, `snmp` and `meraki*` aren't device profiles. `base` is the generic fallback when no vendor profile matched, and hand-built profiles carry custom names. II has no device counts or sysObjectID, so demand is accounts and GB. For customers, map accounts to contracts and drop New Relic's own as in "Networking clients". Last used: 2026-10-30.

```sql
SELECT INSTRUMENTATION_NAME, INSTRUMENTATION_PROVIDER, COLLECTOR_NAME,
       COUNT(DISTINCT SUB_ACCOUNT_ID) AS ACCOUNTS,
       ROUND(SUM(TOTAL_GB), 1) AS GB
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
  AND EVENT_NAME = 'Metric'
  AND (USAGE_CATEGORY = 'NetworkMonitoring' OR COLLECTOR_NAME = 'network-agent')
GROUP BY ALL
ORDER BY ACCOUNTS DESC
```

## Pitfalls

- **"NPM customers" has three meanings.** It could be accounts with NPM devices reporting (ELIA), accounts with NPM ingest (II), or the companies behind them (join through `customers.md`). Ask which one before counting, and record the answer in `summary.md`. Critical. Last used: 2026-10-23.
- **`NetworkMonitoring` misses Juniper Mist.** The category follows `INSTRUMENTATION_PROVIDER`, and only `kentik` (ktranslate) data gets it. Mist is provider `infrastructure`, so it is booked under `'Metrics'` or `'CustomEvents'`, with II `PRODUCT_FAMILY_GROUP` 'Not Defined'. In ELIA it is `DOMAIN_TYPE LIKE 'INFRA-JUNIPER_MIST_%'`, excluding `NGEP-JUNIPER_MIST_CONNECTION`. In II it is `INSTRUMENTATION_NAME = 'juniper-mist'`. A customer's own script can also send Mist data: `COLLECTOR_NAME = 'mist-api-poller'`, provider `custom`, through the public Metric and Event APIs. It creates no `INFRA-JUNIPER_MIST_*` entities, so list it separately. Say in "How I got this" that NPM counts exclude Mist, and include Mist only if the user asks. Critical. Last used: 2026-10-23.
- **`NetworkMonitoring` misses the network agent.** II `COLLECTOR_NAME = 'network-agent'` (provider `newrelic`) runs the same profiles and creates the same EXT-* device types as ktranslate. It is booked under `'Metrics'` or `'CustomEvents'`, though, and its flow and trap rows have `EVENT_NAME = 'CustomEvent'`. In ELIA its EXT-* devices have `INSTRUMENTATION_PROVIDER` `["newrelic"]`. Check whether it has data outside New Relic's own accounts. If it does, include it and say so in "How I got this". Critical. Last used: 2026-10-23.
- **No collector versions.** II `INSTRUMENTATION_VERSION` is `'unknown'` on every ktranslate row. ELIA has no version column, and its `COLLECTOR_NAME` is empty for network devices, so take collectors from II. ktranslate puts its version in the `ver` attribute of its heartbeat metric, which no Snowflake table holds. Get it with NRQL in the customer's account: `FROM Metric SELECT latest(ver) WHERE provider = 'kentik-agent' AND instrumentation.name = 'heartbeat'`. `NR_SILVER_DATALAKE_PROD.NR_SILVER_NRDB_DL_OHIO_PRD.METRIC` is only the raw usage stream behind II, with the same fields. Last used: 2026-10-09.
- **ELIA scans are slow.** The table is huge and has no clustering key; only a date filter prunes, and `DOMAIN_TYPE` doesn't. On the XSMALL warehouse one day takes tens of seconds, and a month takes several minutes, past the 5-minute limit. For ranges over a week, check in first or use II, which is small and fast. Last used: 2026-10-09.
- **Which account column.** `ACCOUNT_ID` is where data lands, and `SUBSCRIPTION_ACCOUNT_ID` is the customer contract. Count `ACCOUNT_ID` for "accounts" and `SUBSCRIPTION_ACCOUNT_ID` for "clients", and say which in "How I got this". Last used: 2026-10-23.
- **Quote `DATE`.** II's date column is called `DATE`, so write `"DATE"`. Last used: 2026-10-09.
- **Text flags.** `IS_REPORTING` and `HAS_DAILY_CONSUMPTION` are text with mixed case (`'true'`, `'True'`), so compare with `LOWER(…) = 'true'`. Their meaning isn't confirmed, so don't filter on them unless the user asks. A few device rows have a blank `METRIC`; they are still live entities. Last used: 2026-09-30.
- **Fresh days can be partial.** If the latest day looks low, compare it with the day before and mention it. Last used: 2026-10-13.
- **Contract IDs change mid-window.** II `SUBSCRIPTION_ACCOUNT_ID` mixes `CC-…` contracts with plain account IDs, and an account can switch from one to the other during a month. Map each account to its latest value first (`MAX_BY(SUBSCRIPTION_ACCOUNT_ID, "DATE")`), or one client shows as two rows. A few rows have no contract; count those accounts on their own. Critical. Last used: 2026-10-23.
- **Total GB includes Live Archives.** `USAGE_CATEGORY = 'LoggingArchive'` is not billable and is the only such II category. Leave it out of a client's total GB, and the II total matches billed `GigabytesIngested` within 0.1%; with it, clients that use Live Archives read far too high. Critical. Last used: 2026-10-23.
- **Network data never shows a host name.** `INGEST_POINT` on NetworkMonitoring rows is only `api.metrics.raw`, `api.events` or `api.logs`, so II can't show whether network data used a FedRAMP (`gov-…`) endpoint. Last used: 2026-10-21.
- **Following customers across two periods.** Map each earlier account to the contract it sits under in the later period (its latest ID). The customer is retained if that contract has Networking data later, and dropped if not. A contract with Networking data now and none from earlier accounts is new. Some earlier IDs merge into one contract, so the earlier count falls. The full query is `runs/2026-10-23/networking-growth-12mo/17-16-then-vs-now-cohort-paid-from-jan-2026.sql`. Last used: 2026-10-23.
- **"Paying" has more than one meaning.** The 13 Oct list counts a client as paying with an active paid plan (`IS_PAID`) or a sales partnership, and more than 100 GB of total ingest in the window. Billing meters can't replace it, since `BILLABLE_USAGE` is usage minus the free allowance for everyone (`billing.md`). The user first said "billed for usage" on 2026-10-23, but the 12-month comparison moved to this rule so today's counts match the 13 Oct list. Say which rule you used. Critical. Last used: 2026-10-23.
- **Networking customer:** a company, meaning a customer contract (II `SUBSCRIPTION_ACCOUNT_ID`, each account under its latest ID), not a single New Relic account. Confirmed by the user on 2026-10-23. Critical. Last used: 2026-10-23.
- **Average daily data consumption (networking clients):** both network data (`NetworkMonitoring`) and all data across the client's accounts, each divided by the days in the window. Confirmed by the user on 2026-10-13. Critical. Last used: 2026-10-13.
