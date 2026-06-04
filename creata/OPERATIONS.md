<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements. See the NOTICE file
 distributed with Apache Airflow for additional information
 regarding copyright ownership. The ASF licenses this file to you under
 the Apache License, Version 2.0.
-->

# Creata Airflow Operations

This document is the day-two runbook for the Creata Airflow Docker deployment.

## Repo Roles

Airflow repo:

```text
C:\Users\creata_f01\Documents\Codex\airflow_repo_compare
https://github.com/creata-taiwan/airflow.git
```

Owns:

- Docker Compose runtime.
- Airflow image customization.
- Dag files and schedule definitions.
- Airflow runtime `.env`.

ERP/report repo:

```text
C:\Users\creata_f01\Documents\Codex\creata_agent_chi
https://github.com/creata-taiwan/creata_agent_chi.git
```

Owns:

- SQL templates.
- Python report runners.
- Report config examples.
- Generated report outputs.
- Validation notes.

## Standard Commands

Always run Docker Compose from:

```powershell
cd C:\Users\creata_f01\Documents\Codex\airflow_repo_compare\creata
$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;' + $env:Path
```

Build:

```powershell
docker compose build
```

Initialize metadata DB and admin user:

```powershell
docker compose up airflow-init
```

Start:

```powershell
docker compose up -d
```

Stop:

```powershell
docker compose down
```

Check status:

```powershell
docker compose ps
```

Check loaded Dags:

```powershell
docker compose exec -T airflow-worker airflow dags list
```

Open UI:

```text
http://localhost:8080
```

Default local login:

```text
airflow / airflow
```

Change the password before live use.

## MOMO Template Validation

Run the sample report without SQL and without sending email:

```powershell
docker compose exec -T airflow-worker python /opt/airflow/workspaces/creata_agent_chi/scripts/momo_daily_sales_report.py --sample-data --dry-run --report-date 2026-06-03
```

While testing an unmerged ERP worktree, replace `creata_agent_chi` with that
worktree folder name, for example:

```text
/opt/airflow/workspaces/creata_agent_chi_airflow_momo
```

Test the Airflow Dag path:

```powershell
docker compose exec -T airflow-worker airflow dags test momo_daily_sales_report 2026-06-03
```

Expected result:

```text
delivery.status = dry_run
recipients = it@creata.com.tw,jason@creata.com.tw
```

## Production Cutover

Keep sample mode and dry-run enabled while validating the template:

```text
MOMO_REPORT_USE_SAMPLE_DATA=true
MOMO_REPORT_DRY_RUN=true
```

For SQL validation without email:

```text
MOMO_REPORT_USE_SAMPLE_DATA=false
MOMO_REPORT_DRY_RUN=true
```

For live delivery after validation and explicit approval:

```text
MOMO_REPORT_USE_SAMPLE_DATA=false
MOMO_REPORT_DRY_RUN=false
```

Before enabling live send:

1. Confirm `CREATA_AGENT_REPO` points to the merged ERP repo path.
2. Confirm SQL Server credentials work from the Airflow worker container.
3. Validate the MOMO channel filter.
4. Reconcile report totals against direct SQL.
5. Confirm Microsoft Graph app-only sending permissions.
6. Confirm recipients and sender.
7. Unpause the Dag in the Airflow UI.

## Common Problems

### no configuration file provided: not found

Cause: `docker compose` was run outside the `creata` folder.

Fix:

```powershell
cd C:\Users\creata_f01\Documents\Codex\airflow_repo_compare\creata
docker compose ps
```

### docker-credential-desktop not found

Cause: Docker Desktop's CLI helper is not on the PowerShell `PATH`.

Fix:

```powershell
$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;' + $env:Path
```

### Report script not found

Check `CREATA_WORKSPACES_HOST_DIR` and `CREATA_AGENT_REPO` in `creata/.env`.

For the merged ERP repo, use:

```text
CREATA_WORKSPACES_HOST_DIR=C:/Users/creata_f01/Documents/Codex
CREATA_AGENT_REPO=/opt/airflow/workspaces/creata_agent_chi
```

For temporary branch testing only, a worktree path may be used.

### Dag is visible but not running

The Dag is created paused by default. This is intentional for safety.

Unpause only after validation passes and live delivery is approved.
