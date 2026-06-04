<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements. See the NOTICE file
 distributed with Apache Airflow for additional information
 regarding copyright ownership. The ASF licenses this file to you under
 the Apache License, Version 2.0.
-->

# Creata Airflow Docker Runbook

This folder contains the Apache Airflow Docker Compose runtime used for Creata
ERP automation scheduling.

Airflow is the scheduler. Report extraction, analysis, SQL templates, and report
generation stay in `creata_agent_chi` or another explicitly selected report
repository.

## Repository Boundary

Use this repo for scheduling and runtime operations only:

- Docker Compose services.
- Airflow image customization.
- Dag files.
- Schedule definitions.
- Airflow UI/runtime state.
- Runtime `.env` used by Airflow containers.

Use `creata_agent_chi` for report implementation:

- SQL templates.
- Python report runners.
- Report config examples.
- Generated report outputs.
- Validation documentation.

Do not duplicate report SQL or report scripts into this repo. Airflow should
mount the report repo and call its runner scripts.

## Files

- `docker-compose.yaml` - Airflow services and project volume mounts.
- `Dockerfile` - Extends the Airflow image with Microsoft ODBC Driver 18 and
  Python runtime dependencies needed by report scripts.
- `.env.example` - Runtime, SQL Server, report, and Graph mail variables.
- `dags/` - Airflow Dag files. Keep empty until a specific automation project
  is approved.
- `OPERATIONS.md` - Day-two commands, validation, and troubleshooting.

## First Run

Run from this `creata` folder:

```powershell
cd C:\Users\creata_f01\Documents\Codex\airflow_repo_compare\creata
$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;' + $env:Path
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

The default local user comes from `.env`. Change it before live use.

If Docker says:

```text
no configuration file provided: not found
```

you are not in the `creata` folder.

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

## Adding An Automation Project

Create a project-specific Dag only after the user asks for Airflow automation
and the report logic has been validated in the report repo.

Minimum gate before adding a Dag:

1. The report runner exists in the report repo.
2. The runner supports dry-run and writes a manifest.
3. SQL totals and report output are validated.
4. Recipients and sender are confirmed.
5. Live delivery is explicitly approved before disabling dry-run.

## Maintenance

See `OPERATIONS.md` for routine commands, restart procedures, log checks, and
the production cutover checklist.
