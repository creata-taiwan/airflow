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

## Automation Project Gate

Do not add a project-specific Dag until the user explicitly asks to create an
Airflow automation project.

Before enabling a production schedule:

1. Confirm `CREATA_AGENT_REPO` points to the intended report repo.
2. Confirm SQL Server credentials work from the Airflow worker container.
3. Validate the report output against direct SQL or an approved source.
4. Confirm Microsoft Graph app-only sending permissions when email is required.
5. Confirm recipients and sender.
6. Keep dry-run enabled until validation passes.
7. Unpause the Dag in the Airflow UI only after live scheduling is approved.

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

### Dag is visible but not running

The Dag is created paused by default. This is intentional for safety.

Unpause only after validation passes and live scheduling is approved.
