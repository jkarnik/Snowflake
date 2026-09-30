WITH
    BaseRecords AS (
        SELECT
            R.RPM_ACCOUNT_ID,
            R.RPM_ACCOUNT_NAME,
            R.ACCOUNT_NAME,
            R.SFDC_ACCOUNT_ID
        FROM
            TRANSFORMED.SALES.SFDC_RPM_RECORD_D R
        WHERE
            R.IS_DELETED = FALSE
    ),
    PivotedRoles AS (
        -- 3. Aggregate (Pivot) the Team Member data FIRST (One row per SFDC_ACCOUNT_ID)
        SELECT
            ATM.ACCOUNT_ID AS SFDC_ACCOUNT_ID,
            -- Conditional Aggregation for roles
            MAX(
                CASE
                    WHEN ATM.TEAM_MEMBER_ROLE = 'AE' THEN U.NAME
                END
            ) AS AE_NAME,
            MAX(
                CASE
                    WHEN ATM.TEAM_MEMBER_ROLE = 'AE' THEN U.EMAIL
                END
            ) AS AE_EMAIL,
            MAX(
                CASE
                    WHEN ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager' THEN U.NAME
                END
            ) AS TSM_NAME,
            MAX(
                CASE
                    WHEN ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager' THEN U.EMAIL
                END
            ) AS TSM_EMAIL,
        FROM
            TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D AS ATM
            INNER JOIN TRANSFORMED.SALES.SFDC_USER_D U ON ATM.USER_ID = U.USER_ID
        WHERE
            ATM.IS_DELETED = FALSE
            AND ATM.TEAM_MEMBER_ROLE IN ('AE', 'Technical Success Manager')
        GROUP BY
            ATM.ACCOUNT_ID
    )
    -- 4. Final Join and Selection
SELECT
    -- Base Record and Owner Details
    R.RPM_ACCOUNT_ID,
    R.RPM_ACCOUNT_NAME,
    ACC.SFDC_ACCOUNT_NAME,
    R.ACCOUNT_NAME,
    -- Pivoted Role Details (from the dedicated CTE)
    PR.AE_NAME,
    PR.AE_EMAIL,
    PR.TSM_NAME,
    PR.TSM_EMAIL
FROM
    BaseRecords R
    LEFT OUTER JOIN PivotedRoles PR ON R.SFDC_ACCOUNT_ID = PR.SFDC_ACCOUNT_ID
    LEFT OUTER JOIN TRANSFORMED.SALES.SFDC_ACCOUNT_D ACC ON ACC.SFDC_ACCOUNT_ID = R.SFDC_ACCOUNT_ID
WHERE
    ACC.SFDC_ACCOUNT_NAME IS NOT NULL
    AND (PR.AE_NAME IS NOT NULL OR PR.TSM_NAME IS NOT NULL)
ORDER BY
    R.RPM_ACCOUNT_ID;