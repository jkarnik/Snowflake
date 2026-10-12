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
Use for: "NPM ingest split into SNMP, syslog, flow and traps". Last used: 2026-10-09.

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
Use for: the biggest NPM users in a period. Last used: 2026-09-30.

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
version and subgroup, including Mist and the network agent. Last used: 2026-10-09.

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

## Pitfalls

- **"NPM customers" has three meanings.** It could be accounts with NPM devices reporting (ELIA), accounts with NPM ingest (II), or the companies behind them (join through `customers.md`). Ask which one before counting, and record the answer in `summary.md`. Critical. Last used: 2026-09-30.
- **`NetworkMonitoring` misses Juniper Mist.** The category follows `INSTRUMENTATION_PROVIDER`, and only `kentik` (ktranslate) data gets it. Mist is provider `infrastructure`, so it is booked under `'Metrics'` or `'CustomEvents'`, with II `PRODUCT_FAMILY_GROUP` 'Not Defined'. In ELIA it is `DOMAIN_TYPE LIKE 'INFRA-JUNIPER_MIST_%'`, excluding `NGEP-JUNIPER_MIST_CONNECTION`. In II it is `INSTRUMENTATION_NAME = 'juniper-mist'`. Say in "How I got this" that NPM counts exclude Mist, and include Mist only if the user asks. Critical. Last used: 2026-10-09.
- **`NetworkMonitoring` misses the network agent.** II `COLLECTOR_NAME = 'network-agent'` (provider `newrelic`) runs the same profiles and creates the same EXT-* device types as ktranslate. It is booked under `'Metrics'` or `'CustomEvents'`, though, and its flow and trap rows have `EVENT_NAME = 'CustomEvent'`. In ELIA its EXT-* devices have `INSTRUMENTATION_PROVIDER` `["newrelic"]`. Check whether it has data outside New Relic's own accounts. If it does, include it and say so in "How I got this". Critical. Last used: 2026-10-09.
- **No collector versions.** II `INSTRUMENTATION_VERSION` is `'unknown'` on every ktranslate row. ELIA has no version column, and its `COLLECTOR_NAME` is empty for network devices, so take collectors from II. ktranslate puts its version in the `ver` attribute of its heartbeat metric, which no Snowflake table holds. Get it with NRQL in the customer's account: `FROM Metric SELECT latest(ver) WHERE provider = 'kentik-agent' AND instrumentation.name = 'heartbeat'`. `NR_SILVER_DATALAKE_PROD.NR_SILVER_NRDB_DL_OHIO_PRD.METRIC` is only the raw usage stream behind II, with the same fields. Last used: 2026-10-09.
- **ELIA scans are slow.** The table is huge and has no clustering key; only a date filter prunes, and `DOMAIN_TYPE` doesn't. On the XSMALL warehouse one day takes tens of seconds, and a month takes several minutes, past the 5-minute limit. For ranges over a week, check in first or use II, which is small and fast. Last used: 2026-10-09.
- **Which account column.** `ACCOUNT_ID` is where data lands, and `SUBSCRIPTION_ACCOUNT_ID` is the customer contract. Count `ACCOUNT_ID` for "accounts" and `SUBSCRIPTION_ACCOUNT_ID` for "clients", and say which in "How I got this". Last used: 2026-10-09.
- **Quote `DATE`.** II's date column is called `DATE`, so write `"DATE"`. Last used: 2026-10-09.
- **Text flags.** `IS_REPORTING` and `HAS_DAILY_CONSUMPTION` are text with mixed case (`'true'`, `'True'`), so compare with `LOWER(…) = 'true'`. Their meaning isn't confirmed, so don't filter on them unless the user asks. A few device rows have a blank `METRIC`; they are still live entities. Last used: 2026-09-30.
- **Fresh days can be partial.** If the latest day looks low, compare it with the day before and mention it. Last used: 2026-09-30.
