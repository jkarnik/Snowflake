# Quimbly Foods Salesforce account

Answer: Quimbly Foods has Salesforce account 0019900002.

How I got this: 01 failed with SQL_ERROR "invalid identifier 'NAME'". `TRANSFORMED.SALES.SFDC_ACCOUNT_D` calls the column `SFDC_ACCOUNT_NAME`; `NAME` is the column in `CONFORMED.SFDC.STG_SFDC_ACCOUNT`. 02 used `SFDC_ACCOUNT_NAME` and worked.

Check-in: none. Recipes used: none. Table entries used: none.
