#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with Apache Airflow for additional information
# regarding copyright ownership. The ASF licenses this file to you under
# the Apache License, Version 2.0.
#
from __future__ import annotations

import os
from pathlib import Path

import pendulum
from airflow.sdk import dag, get_current_context, task


LOCAL_TZ = pendulum.timezone("Asia/Taipei")
PROJECT_ROOT = Path(os.environ.get("CREATA_PROJECT_ROOT", "/opt/airflow/project"))
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "momo_daily_sales.example.json"


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
    def generate_report() -> str:
        from scripts.momo_daily_sales_report import (
            build_report,
            load_default_env_files,
            load_report_config,
            parse_bool,
        )

        load_default_env_files()
        context = get_current_context()
        interval_end = context["data_interval_end"].in_timezone(LOCAL_TZ)
        offset_days = int(os.environ.get("MOMO_REPORT_DATE_OFFSET_DAYS", "1"))
        report_date = interval_end.subtract(days=offset_days).date()
        config_path = Path(os.environ.get("MOMO_REPORT_CONFIG", str(DEFAULT_CONFIG)))
        config = load_report_config(config_path)
        sample_data = parse_bool(os.environ.get("MOMO_REPORT_USE_SAMPLE_DATA", "false"))
        manifest = build_report(config=config, report_date=report_date, sample_data=sample_data)
        return manifest["artifacts"]["manifest"]

    @task
    def deliver_report(manifest_path: str) -> dict:
        from scripts.momo_daily_sales_report import (
            deliver_manifest,
            load_default_env_files,
            load_report_config,
            parse_bool,
        )

        load_default_env_files()
        config_path = Path(os.environ.get("MOMO_REPORT_CONFIG", str(DEFAULT_CONFIG)))
        config = load_report_config(config_path)
        dry_run = parse_bool(os.environ.get("MOMO_REPORT_DRY_RUN", "true"))
        return deliver_manifest(Path(manifest_path), config=config, dry_run=dry_run)

    deliver_report(generate_report())


momo_daily_sales_report()
