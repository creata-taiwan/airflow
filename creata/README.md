<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements. See the NOTICE file
 distributed with Apache Airflow for additional information
 regarding copyright ownership. The ASF licenses this file to you under
 the Apache License, Version 2.0.
-->

# Creata Airflow Docker Runbook

This project now includes an Apache Airflow 3.2.2 Docker Compose runtime for ERP
report automation scheduling. The report extraction and analysis code stays in
`C:\Users\creata_f01\Documents\Codex\creata_agent_chi`; Airflow mounts that
workspace and calls its scripts.

## Files

- `creata/docker-compose.yaml` - Airflow services and project volume mounts.
- `creata/Dockerfile` - Extends the Airflow image with Microsoft ODBC Driver 18
  and Python runtime dependencies needed by report scripts.
- `creata/.env.example` - Runtime, SQL Server, report, and Graph mail variables.
- `creata/dags/momo_daily_sales_report_dag.py` - Daily 09:00 Asia/Taipei Dag.
- `creata_agent_chi/scripts/momo_daily_sales_report.py` - Report generation and
  Graph mail delivery script.
- `creata_agent_chi/configs/momo_daily_sales.example.json` - MOMO report settings.
- `creata_agent_chi/sql/reports/momo_daily_sales_*.sql` - SELECT-only SQL templates.

## First Run

Run from the `creata` folder:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose build
docker compose up airflow-init
docker compose up -d
```

Open Airflow at:

```text
http://localhost:8080
```

The default example user comes from `.env`. Change it before live use.

## Required Secrets

Keep these in `creata/.env` only. Do not commit them.

```text
SQL_USER=
SQL_PASSWORD=
GRAPH_TENANT_ID=
GRAPH_CLIENT_ID=
GRAPH_CLIENT_SECRET=
GRAPH_SENDER=it@creata.com.tw
```

The workspace mount defaults to:

```text
CREATA_WORKSPACES_HOST_DIR=C:/Users/creata_f01/Documents/Codex
CREATA_AGENT_REPO=/opt/airflow/workspaces/creata_agent_chi
```

The Docker image installs Microsoft ODBC Driver 18 for SQL Server. The default
SQL settings use:

```text
SQL_SERVER=192.168.0.253
SQL_PORT=1433
SQL_DATABASE=CHIComp06
SQL_ENCRYPT=no
SQL_TRUST_SERVER_CERTIFICATE=yes
```

## MOMO Report Schedule

The Dag id is:

```text
momo_daily_sales_report
```

Schedule:

```text
0 9 * * * Asia/Taipei
```

The job reports the previous calendar day by default:

```text
MOMO_REPORT_DATE_OFFSET_DAYS=1
```

Recipients:

```text
it@creata.com.tw,jason@creata.com.tw
```

## Live Delivery Gate

The Dag is created paused by default and the report defaults to dry-run:

```text
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
MOMO_REPORT_DRY_RUN=true
```

After SQL validation and explicit approval for live delivery, set:

```text
MOMO_REPORT_DRY_RUN=false
```

Then restart the Airflow services and unpause the Dag in the UI.

## MOMO Channel Assumption

The initial channel filter is intentionally configurable:

```text
MOMO_REPORT_CHANNEL_FIELD=BA.Remark
MOMO_REPORT_CHANNEL_PATTERN=%MOMO%
```

This means the SQL uses:

```sql
BA.Remark LIKE N'%MOMO%'
```

If MOMO is later validated against another field, change the field to one of:

```text
BA.Remark
BA.UserDef1
BA.UserDef2
BA.DueTo
CU.ID
CU.ShortName
CU.FullName
```

Do not add arbitrary SQL fragments to the channel filter.

## Dry-Run Test

Generate a no-database sample report and email preview:

```powershell
docker compose run --rm airflow-worker python /opt/airflow/workspaces/creata_agent_chi/scripts/momo_daily_sales_report.py --sample-data --dry-run --report-date 2026-06-03
```

Generated files are written under:

```text
C:\Users\creata_f01\Documents\Codex\creata_agent_chi\outputs\airflow\momo_daily_sales\
```

For a live SQL dry-run without sending email:

```powershell
docker compose run --rm airflow-worker python /opt/airflow/workspaces/creata_agent_chi/scripts/momo_daily_sales_report.py --dry-run --report-date 2026-06-03
```

## Validation Checklist

Before enabling live send:

1. Confirm SQL connection from inside the Airflow worker container.
2. Run the report with `--dry-run` for a known date.
3. Compare summary net sales with a direct SQL total for the same date and MOMO
   filter.
4. Confirm Top 10 product totals reconcile to the detail query.
5. Confirm generated Excel numeric cells are numeric.
6. Confirm recipients and Graph sender are correct.
7. Set `MOMO_REPORT_DRY_RUN=false` only after validation passes and live delivery
   is approved.
