-- Two ingest data sources: ELIA (entities) and instrumentation insights (billable ingest)
select * from transformed.product_engineering.entity_ingest_daily_f limit 10;
show columns in transformed.product_engineering.entity_ingest_daily_f;
/* column_name
USAGE_DATE
SUBSCRIPTION_ACCOUNT_ID
ACCOUNT_ID
ENTITY_GUID
NEWRELIC_SOURCE
METRIC
DAILY_USAGE
DOMAIN_NAME
ENTITY_TYPE
DOMAIN_TYPE
IS_REPORTING
HAS_DAILY_CONSUMPTION
ENTITY_D_TV_KEY
EDW_CREATE_TIMESTAMP
EDW_CREATE_USER
DATA_CENTER
INSTRUMENTATION_PROVIDER
COLLECTOR_NAME
*/
-- ELIA definition for network monitoring: metric = 'NetworkMonitoring'
-- ELIA domain_type represents device type

-- Instrumentation insights data -- stream from NR1. NR1 has more data fields in it than our data stream does, its possible to add more but also very expensive
select * from transformed.product_consumption.nrdb_tdp_usage_daily_f where usage_category = 'NetworkMonitoring' limit 100;
show columns in transformed.product_consumption.nrdb_tdp_usage_daily_f;
/*
column_name
DATE
SUB_ACCOUNT_ID
SUBSCRIPTION_ACCOUNT_ID
METRIC_NAME
DATA_CENTER
INSTRUMENTATION_NAME
INSTRUMENTATION_PROVIDER
INSTRUMENTATION_SOURCE
INSTRUMENTATION_VERSION
NEWRELIC_SOURCE
COLLECTOR_NAME
DATA_TYPE
EVENT_NAME
TOTAL_GB
INGEST_POINT
USAGE_CATEGORY
ADJUSTED_II
PRODUCT_FAMILY
PRODUCT_FAMILY_GROUP
PRODUCT_FAMILY_SUBGROUP
*/
-- II definition for network monitoring: usage_category = 'NetworkMonitoring'
-- subgroup definition: based on event_name
    -- 'Metric' : 'SnmpMetric'
    -- 'Log' : 'Syslog'
    -- 'KFlow' : 'KFlow'
    -- 'KSnmpTrap' : 'SnmpTrap'
    -- <anything else> : 'other'
    
;