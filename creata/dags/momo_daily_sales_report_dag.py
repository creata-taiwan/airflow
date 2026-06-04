#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with Apache Airflow for additional information
# regarding copyright ownership. The ASF licenses this file to you under
# the Apache License, Version 2.0.
#
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pendulum
from airflow.sdk import dag, get_current_context, task


LOCAL_TZ = pendulum.timezone("Asia/Taipei")
DEFAULT_AGENT_REPO = Path("/opt/airflow/workspaces/creata_agent_chi")
AGENT_REPO = Path(os.environ.get("CREATA_AGENT_REPO", str(DEFAULT_AGENT_REPO)))
DEFAULT_SCRIPT = AGENT_REPO / "scripts" / "momo_daily_sales_report.py"
DEFAULT_CONFIG = AGENT_REPO / "configs" / "momo_daily_sales.example.json"


@dag(
    dag_id="momo_daily_sales_report",
    description="Generate and deliver the MOMO daily sales amount and top 10 product report.",
    schedule="0 9 * * *",
    start_date=pendulum.datetime(2026, 6, 1, tz=LOCAL_TZ),
    catchup=False,
    tags=["creata", "momo", "sales", "email"],
)
def momo_daily_sales_report():
    @task
    def run_report() -> dict:
        context = get_current_context()
        interval_end = context["data_interval_end"].in_timezone(LOCAL_TZ)
        offset_days = int(os.environ.get("MOMO_REPORT_DATE_OFFSET_DAYS", "1"))
        report_date = interval_end.subtract(days=offset_days).date()
        script_path = Path(os.environ.get("MOMO_REPORT_SCRIPT", str(DEFAULT_SCRIPT)))
        config_path = Path(os.environ.get("MOMO_REPORT_CONFIG", str(DEFAULT_CONFIG)))

        if not script_path.exists():
            raise FileNotFoundError(f"Report script not found: {script_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"Report config not found: {config_path}")

        command = [
            sys.executable,
            str(script_path),
            "--config",
            str(config_path),
            "--report-date",
            report_date.isoformat(),
        ]
        if os.environ.get("MOMO_REPORT_USE_SAMPLE_DATA", "false").lower() in {"1", "true", "yes", "y", "on"}:
            command.append("--sample-data")
        if os.environ.get("MOMO_REPORT_DRY_RUN", "true").lower() in {"1", "true", "yes", "y", "on"}:
            command.append("--dry-run")
        else:
            command.append("--send")

        result = subprocess.run(
            command,
            cwd=str(script_path.parents[1]),
            env=os.environ.copy(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout)
        return json.loads(result.stdout)

    run_report()


momo_daily_sales_report()
