select case event_name when 'Metric' then 'SnmpMetric' when 'Log' then 'Syslog'
            when 'KFlow' then 'KFlow' when 'KSnmpTrap' then 'SnmpTrap' else 'other' end as subgroup,
       sum(total_gb) as gb
from transformed.product_consumption.nrdb_tdp_usage_daily_f
where usage_category = 'NetworkMonitoring'
  and "DATE" >= '2026-08-01' and "DATE" < '2026-09-01'
group by subgroup
order by subgroup
