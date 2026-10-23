# Customers and accounts

Read this for questions about a company or account: Salesforce details, billing addresses, account
owners (AE and TSM), organisations and entitlements, or turning an account ID into a company name.

## How accounts join

The RPM account ID links usage to Salesforce. `ALL_DAILY_USAGE` calls it `BILLABLE_RPM_ACCOUNT_ID`
(`billing.md`), and the NPM tables call it `ACCOUNT_ID` (`npm.md`). `SUBSCRIPTION_ACCOUNT_ID` is the
customer contract (`CC-…`), not an RPM ID, so never join it to `RPM_ACCOUNT_ID`. The steps:

1. `TRANSFORMED.SALES.SFDC_RPM_RECORD_D` maps `RPM_ACCOUNT_ID` (and `RPM_ACCOUNT_NAME`) to `SFDC_ACCOUNT_ID`. Filter `IS_DELETED = FALSE`.
2. `TRANSFORMED.SALES.SFDC_ACCOUNT_D` gives `SFDC_ACCOUNT_NAME` for an `SFDC_ACCOUNT_ID`.
3. `TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D` lists the account team. Its `ACCOUNT_ID` is the Salesforce account ID, with `USER_ID`, `TEAM_MEMBER_ROLE` and `IS_DELETED`. The role labels are loose (see the pitfall "Team roles are loose").
4. `TRANSFORMED.SALES.SFDC_USER_D` gives each `USER_ID`'s `NAME`, `EMAIL`, `TITLE` and `IS_ACTIVE`.
5. `TRANSFORMED.SALES.SFDC_ACCOUNT_D` also holds the account owner (`ACCOUNT_OWNER_NAME`), who is the AE, and the company family (`ULTIMATE_PARENT_ACCOUNT_ID`).
6. `TRANSFORMED.COMMON.ACCOUNT_DAILY_D` links a customer contract (`CC-…`) to its own Salesforce account (`SFDC_CC_ACCOUNT_ID`).

`CONFORMED.SFDC.STG_SFDC_ACCOUNT` is the conformed Salesforce account view, with `NAME` and the
`BILLING_STREET`, `BILLING_CITY`, `BILLING_STATE`, `BILLING_POSTAL_CODE` and `BILLING_COUNTRY`
columns.

## Recipes

### Account owners (AE, SC and TSM) for a company
Use for: "who are the AE, SC and TSM for X". The AE is the Salesforce account owner, and the team's
AEs fill in only when the owner is the `Mulesoft User` integration. SC and TSM are active team
members with that role or job title. An empty column means Salesforce has nobody in that role. For an
account ID, replace the last `WHERE` with `WHERE B.RPM_ACCOUNT_ID = '{{account_id}}'`.
Last used: 2026-10-13.

```sql
WITH base AS (
    SELECT R.RPM_ACCOUNT_ID, R.RPM_ACCOUNT_NAME, R.SFDC_ACCOUNT_ID
    FROM TRANSFORMED.SALES.SFDC_RPM_RECORD_D R
    WHERE R.IS_DELETED = FALSE
),
team AS (
    SELECT ATM.ACCOUNT_ID AS SFDC_ACCOUNT_ID,
           LISTAGG(DISTINCT IFF(ATM.TEAM_MEMBER_ROLE = 'AE', U.NAME, NULL), '; ') AS TEAM_AE,
           LISTAGG(DISTINCT IFF(U.TITLE ILIKE '%Solution% Consultant%' OR ATM.TEAM_MEMBER_ROLE = 'Solutions Consultant', U.NAME, NULL), '; ') AS SC,
           LISTAGG(DISTINCT IFF(U.TITLE ILIKE '%Technical Success Manager%' OR ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager', U.NAME, NULL), '; ') AS TSM,
           LISTAGG(DISTINCT IFF(U.TITLE ILIKE '%Technical Success Manager%' OR ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager', U.EMAIL, NULL), '; ') AS TSM_EMAIL
    FROM TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D ATM
    JOIN TRANSFORMED.SALES.SFDC_USER_D U ON U.USER_ID = ATM.USER_ID
    WHERE ATM.IS_DELETED = FALSE AND U.IS_ACTIVE
    GROUP BY ATM.ACCOUNT_ID
)
SELECT ACC.SFDC_ACCOUNT_NAME, B.RPM_ACCOUNT_ID, B.RPM_ACCOUNT_NAME,
       COALESCE(IFF(ACC.ACCOUNT_OWNER_ROLE = 'Mulesoft User', NULL,
                    NULLIF(COALESCE(OWN.NAME, ACC.ACCOUNT_OWNER_NAME), '') || IFF(COALESCE(OWN.IS_ACTIVE, TRUE), '', ' (inactive)')),
                NULLIF(T.TEAM_AE, '')) AS AE,
       IFF(ACC.ACCOUNT_OWNER_ROLE = 'Mulesoft User', NULL, OWN.EMAIL) AS AE_EMAIL,
       NULLIF(T.SC, '') AS SC, NULLIF(T.TSM, '') AS TSM, NULLIF(T.TSM_EMAIL, '') AS TSM_EMAIL
FROM base B
JOIN TRANSFORMED.SALES.SFDC_ACCOUNT_D ACC ON ACC.SFDC_ACCOUNT_ID = B.SFDC_ACCOUNT_ID AND ACC.IS_DELETED = FALSE
LEFT JOIN TRANSFORMED.SALES.SFDC_USER_D OWN ON OWN.USER_ID = ACC.OWNER_ID
LEFT JOIN team T ON T.SFDC_ACCOUNT_ID = B.SFDC_ACCOUNT_ID
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

### FedRAMP and HIPAA flags
Use for: "which accounts or customers need FedRAMP or HIPAA", "is account X FedRAMP". The flags are
entitlements. This counts accounts and customers by flag and value. To check one account, add
`AND TO_VARCHAR(RPM_ACCOUNT_ID) = '{{account_id}}'` and select the IDs instead of counting. For one
customer, filter `NR_CUSTOMER_ID` on its `CC-…`. Last used: 2026-10-21.

```sql
SELECT 'ACCOUNT' AS LVL, ENTITLEMENT_TYPE, ENTITLEMENT_VALUE, IS_ACTIVE,
       COUNT(DISTINCT TO_VARCHAR(RPM_ACCOUNT_ID)) AS IDS
FROM TRANSFORMED.COMMON.ACCOUNT_ENTITLEMENTS_NEW_D_TV
WHERE ENTITLEMENT_TYPE IN ('IS_FEDRAMP', 'IS_FEDRAMP_CAPABLE', 'IS_HIPAA', 'IS_HIPAA_CAPABLE')
GROUP BY ALL
UNION ALL
SELECT 'CUSTOMER', ENTITLEMENT_TYPE, ENTITLEMENT_VALUE, IS_ACTIVE,
       COUNT(DISTINCT NR_CUSTOMER_ID)
FROM TRANSFORMED.COMMON.CUSTOMER_ENTITLEMENTS_D_TV
WHERE ENTITLEMENT_TYPE IN ('IS_FEDRAMP', 'IS_FEDRAMP_CAPABLE', 'IS_HIPAA', 'IS_HIPAA_CAPABLE')
GROUP BY ALL
ORDER BY 1, 2, 3, 4
```

## Pitfalls

- **Match names loosely.** Legal names carry suffixes and non-ASCII letters (`A.Ş.`, `Pty Ltd`), and pasted copies can be garbled. Use `ILIKE '%…%'` on a distinctive word, then confirm with the user if several companies match. Last used: 2026-10-22.
- **Deleted records linger.** Filter `IS_DELETED = FALSE` on `SFDC_RPM_RECORD_D`, `SFDC_ACCOUNT_D` and `ACCOUNT_TEAM_MEMBER_D`, or former owners and removed accounts appear. Critical. Last used: 2026-10-22.
- **RPM IDs are text in Salesforce but numbers in usage.** `RPM_ACCOUNT_ID` on `SFDC_RPM_RECORD_D` is text, and some IDs aren't numeric, while `BILLABLE_RPM_ACCOUNT_ID` is a number. Joining the two directly, or comparing the text column to a bare number, fails with a numeric-cast error. Quote an ID typed into a query (`'{{account_id}}'`), and cast the usage side when joining: `R.RPM_ACCOUNT_ID = U.BILLABLE_RPM_ACCOUNT_ID::VARCHAR`. Last used: 2026-10-13.
- **One company, many accounts.** A Salesforce account can have several RPM accounts. Show them all, not just the first. Last used: 2026-10-22.
- **Rolling accounts up to clients.** Group by the customer contract (`CC-…`; for II, see "Contract IDs change mid-window" in `npm.md`). Label each client with the contract's own Salesforce account (`ACCOUNT_DAILY_D.SFDC_CC_ACCOUNT_NAME`), then the account behind most of its data (`SFDC_RPM_RECORD_D` → `SFDC_ACCOUNT_D`), then the `ORGANIZATION_DB` org name, since many orgs are just named "Organization …". Where the two Salesforce routes differ, the contract's account is the parent company. Last used: 2026-10-23.
- **New Relic's own accounts.** Internal and test accounts sit in the orgs named "New Relic Production US" and "New Relic Production EU", in contracts with `ACCOUNT_DAILY_D.IS_INTERNAL_ACCOUNT` set, and in the "New Relic Internal Use" partnership. Exclude all three from customer counts. Don't use `RPM_ACCOUNT_DAILY_D.IS_INTERNAL_ACCOUNT`, which is TRUE on every networking account. Critical. Last used: 2026-10-23.
- **`CONCAT_WS` drops the whole address.** In Snowflake it returns NULL when any part is NULL. Join address parts with `ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(…), ', ')`. Critical. Last used: 2026-09-30.
- **Street line breaks.** `BILLING_STREET` holds `CHR(10)` and `CHR(13)`. Replace both before showing an address. Last used: 2026-09-30.
- **Team roles are loose.** The "AE" role on `ACCOUNT_TEAM_MEMBER_D` lists past AEs and also SCs and TSMs, and most TSMs sit under "Expansion Driver". The account owner on `SFDC_ACCOUNT_D` is the AE; an owner with role `Mulesoft User` is an integration, so use the team's active AEs instead. Take SCs and TSMs from active people whose `TITLE` says so. SCs are rarely recorded, so blanks are normal, and `TSM_MAP` on the account is a spreadsheet link, not a person. Critical. Last used: 2026-10-13.
- **Companies with similar names.** Short names such as UPS, BRI, NSW or Jio match unrelated accounts, so match them as whole words: `REGEXP_LIKE(name, '(.*[^A-Za-z])?(UPS)([^A-Za-z].*)?')`. Group a company by `ULTIMATE_PARENT_ACCOUNT_ID`, but some subsidiaries sit under their own parent, so also sweep for subsidiary names. To rule out a look-alike, compare `WEBSITE`, the `ZI_*` company fields, `PARENT_ID`, the sales region and the owner on `SFDC_ACCOUNT_D`. Last used: 2026-10-22.
- **Past paid status.** `RPM_ACCOUNT_DAILY_D` starts 2026-01-01, `ACCOUNT_DAILY_D` holds few of 2025's accounts, and `FINANCE.CUSTOMER_DAILY_D` misses 2025 customers on the newer billing platform, so big paying customers look free. For a date before 2026, use the earliest RPM snapshot and say that customers who changed plan since are misclassified. Critical. Last used: 2026-10-23.
- **Compliance flags.** `IS_FEDRAMP_CAPABLE` and `IS_HIPAA_CAPABLE` mean eligible and are set on most accounts, so never read them as "requires". Use `IS_FEDRAMP` or `IS_HIPAA` with value 1 and `IS_ACTIVE`; value 0 means switched off. New Relic enables FedRAMP only for approved customers, so "enabled" is the best proxy for "requires", and prospects that need it won't show. Critical. Last used: 2026-10-21.
- **Nothing for IL4.** Column names in `CONFORMED`, `TRANSFORMED`, `REPORTING` and `RAW`, and the org capabilities, features and regions, hold no IL4, impact-level, StateRAMP or GovCloud field. Salesforce syncs only `HIPAA_COMPLIANT_C`. `CUSTOMER360.STG_C360_INCUBATOR_ADHOC.FEDRAMP_INCUBATOR_ENABLED` hasn't been updated since 2025. As of 2026-10-21, say IL4 isn't in Snowflake. Last used: 2026-10-21.
