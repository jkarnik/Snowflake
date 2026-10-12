# Customers and accounts

Read this for questions about a company or account: Salesforce details, billing addresses, account
owners (AE and TSM), organisations and entitlements, or turning an account ID into a company name.

## How accounts join

The RPM account ID links usage to Salesforce. `ALL_DAILY_USAGE` calls it `BILLABLE_RPM_ACCOUNT_ID`
(`billing.md`), and the NPM tables call it `ACCOUNT_ID` (`npm.md`). `SUBSCRIPTION_ACCOUNT_ID` is the
customer contract (`CC-…`), not an RPM ID, so never join it to `RPM_ACCOUNT_ID`. The steps:

1. `TRANSFORMED.SALES.SFDC_RPM_RECORD_D` maps `RPM_ACCOUNT_ID` (and `RPM_ACCOUNT_NAME`) to `SFDC_ACCOUNT_ID`. Filter `IS_DELETED = FALSE`.
2. `TRANSFORMED.SALES.SFDC_ACCOUNT_D` gives `SFDC_ACCOUNT_NAME` for an `SFDC_ACCOUNT_ID`.
3. `TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D` lists the account team. Its `ACCOUNT_ID` is the Salesforce account ID, with `USER_ID`, `TEAM_MEMBER_ROLE` and `IS_DELETED`. The roles used here are `'AE'` and `'Technical Success Manager'`.
4. `TRANSFORMED.SALES.SFDC_USER_D` gives each `USER_ID`'s `NAME` and `EMAIL`.

`CONFORMED.SFDC.STG_SFDC_ACCOUNT` is the conformed Salesforce account view, with `NAME` and the
`BILLING_STREET`, `BILLING_CITY`, `BILLING_STATE`, `BILLING_POSTAL_CODE` and `BILLING_COUNTRY`
columns.

## Recipes

### Account owners (AE and TSM) for a company
Use for: "who are the AE and TSM for X". An empty owner column means Salesforce has none assigned.
For an account ID, replace the last `WHERE` with `WHERE B.RPM_ACCOUNT_ID = '{{account_id}}'`.
Last used: 2026-09-30.

```sql
WITH base AS (
    SELECT R.RPM_ACCOUNT_ID, R.RPM_ACCOUNT_NAME, R.SFDC_ACCOUNT_ID
    FROM TRANSFORMED.SALES.SFDC_RPM_RECORD_D R
    WHERE R.IS_DELETED = FALSE
),
roles AS (
    SELECT ATM.ACCOUNT_ID AS SFDC_ACCOUNT_ID,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'AE' THEN U.NAME END) AS AE_NAME,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'AE' THEN U.EMAIL END) AS AE_EMAIL,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager' THEN U.NAME END) AS TSM_NAME,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager' THEN U.EMAIL END) AS TSM_EMAIL
    FROM TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D ATM
    JOIN TRANSFORMED.SALES.SFDC_USER_D U ON ATM.USER_ID = U.USER_ID
    WHERE ATM.IS_DELETED = FALSE
      AND ATM.TEAM_MEMBER_ROLE IN ('AE', 'Technical Success Manager')
    GROUP BY ATM.ACCOUNT_ID
)
SELECT ACC.SFDC_ACCOUNT_NAME, B.RPM_ACCOUNT_ID, B.RPM_ACCOUNT_NAME,
       R.AE_NAME, R.AE_EMAIL, R.TSM_NAME, R.TSM_EMAIL
FROM base B
JOIN TRANSFORMED.SALES.SFDC_ACCOUNT_D ACC ON ACC.SFDC_ACCOUNT_ID = B.SFDC_ACCOUNT_ID
LEFT JOIN roles R ON R.SFDC_ACCOUNT_ID = B.SFDC_ACCOUNT_ID
WHERE ACC.SFDC_ACCOUNT_NAME ILIKE '%{{company_name}}%'
ORDER BY ACC.SFDC_ACCOUNT_NAME, B.RPM_ACCOUNT_ID
LIMIT 100
```

### Company name for an account ID
Use for: naming the accounts in a usage result. Last used: 2026-10-09.

```sql
SELECT R.RPM_ACCOUNT_ID, R.RPM_ACCOUNT_NAME, ACC.SFDC_ACCOUNT_NAME
FROM TRANSFORMED.SALES.SFDC_RPM_RECORD_D R
JOIN TRANSFORMED.SALES.SFDC_ACCOUNT_D ACC ON ACC.SFDC_ACCOUNT_ID = R.SFDC_ACCOUNT_ID
WHERE R.IS_DELETED = FALSE
  AND R.RPM_ACCOUNT_ID = '{{account_id}}'
```

### Billing address, one line per company
Use for: "what is the billing address of X". Line breaks in the street become spaces, and empty
parts are skipped. Last used: 2026-09-30.

```sql
SELECT NAME,
       ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(
           NULLIF(TRIM(REPLACE(REPLACE(BILLING_STREET, CHR(10), ' '), CHR(13), ' ')), ''),
           NULLIF(TRIM(BILLING_CITY), ''),
           NULLIF(TRIM(COALESCE(BILLING_STATE, '') || ' ' || COALESCE(BILLING_POSTAL_CODE, '')), ''),
           NULLIF(TRIM(BILLING_COUNTRY), '')), ', ') AS ADDRESS
FROM CONFORMED.SFDC.STG_SFDC_ACCOUNT
WHERE NAME ILIKE '%{{company_name}}%'
ORDER BY NAME
LIMIT 50
```

### Organisations and entitlements
Use for: org hierarchy, or what an account may use. Look at the columns first, then filter.
Last used: 2026-09-30.

```sql
SELECT * FROM CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ORGANIZATIONS LIMIT 5
```

```sql
SHOW TABLES IN SCHEMA CONFORMED.COMPACT_ENTITLEMENTS_V2
```

## Pitfalls

- **Match names loosely.** Legal names carry suffixes and non-ASCII letters (`A.Ş.`, `Pty Ltd`), and pasted copies can be garbled. Use `ILIKE '%…%'` on a distinctive word, then confirm with the user if several companies match. Last used: 2026-09-30.
- **Deleted records linger.** Filter `IS_DELETED = FALSE` on `SFDC_RPM_RECORD_D` and `ACCOUNT_TEAM_MEMBER_D`, or former owners appear. Critical. Last used: 2026-09-30.
- **RPM IDs are text in Salesforce but numbers in usage.** `RPM_ACCOUNT_ID` on `SFDC_RPM_RECORD_D` is text, and some IDs aren't numeric, while `BILLABLE_RPM_ACCOUNT_ID` is a number. Joining the two directly, or comparing the text column to a bare number, fails with a numeric-cast error. Quote an ID typed into a query (`'{{account_id}}'`), and cast the usage side when joining: `R.RPM_ACCOUNT_ID = U.BILLABLE_RPM_ACCOUNT_ID::VARCHAR`. Last used: 2026-10-09.
- **One company, many accounts.** A Salesforce account can have several RPM accounts. Show them all, not just the first. Last used: 2026-09-30.
- **Rolling accounts up to clients.** Group by `SUBSCRIPTION_ACCOUNT_ID`, the customer contract (`CC-…`). Label each client with its Salesforce name through `SFDC_RPM_RECORD_D` → `SFDC_ACCOUNT_D`, and fall back to the `ORGANIZATION_DB` org name, since many orgs are just named "Organization …". Last used: 2026-10-09.
- **New Relic's own accounts.** Internal and test accounts sit in the orgs named "New Relic Production US" and "New Relic Production EU". Exclude them from customer counts. Critical. Last used: 2026-10-09.
- **`CONCAT_WS` drops the whole address.** In Snowflake it returns NULL when any part is NULL. Join address parts with `ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(…), ', ')`. Critical. Last used: 2026-09-30.
- **Street line breaks.** `BILLING_STREET` holds `CHR(10)` and `CHR(13)`. Replace both before showing an address. Last used: 2026-09-30.
