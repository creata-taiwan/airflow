#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with Apache Airflow for additional information
# regarding copyright ownership. The ASF licenses this file to you under
# the Apache License, Version 2.0.
#
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import html
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "momo_daily_sales.example.json"
SUMMARY_SQL_PATH = PROJECT_ROOT / "sql" / "reports" / "momo_daily_sales_summary.sql"
TOP10_SQL_PATH = PROJECT_ROOT / "sql" / "reports" / "momo_daily_sales_top10.sql"

ALLOWED_CHANNEL_FIELDS = {
    "BA.Remark",
    "BA.UserDef1",
    "BA.UserDef2",
    "BA.DueTo",
    "CU.ShortName",
    "CU.FullName",
    "CU.ID",
}


@dataclass(frozen=True)
class ReportConfig:
    job_id: str
    source_database: str
    timezone: str
    channel_field: str
    channel_pattern: str
    recipients: list[str]
    sender: str
    subject_prefix: str
    output_dir: Path


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def load_env_file(path: Path, *, override: bool = False) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def load_default_env_files() -> None:
    load_env_file(PROJECT_ROOT / ".env")
    load_env_file(PROJECT_ROOT / "airflow" / ".env")


def split_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def require_safe_database_name(database: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", database):
        raise ValueError(f"Unsafe database name: {database!r}")
    return database


def quote_identifier(identifier: str) -> str:
    require_safe_database_name(identifier)
    return f"[{identifier.replace(']', ']]')}]"


def require_channel_field(field: str) -> str:
    if field not in ALLOWED_CHANNEL_FIELDS:
        allowed = ", ".join(sorted(ALLOWED_CHANNEL_FIELDS))
        raise ValueError(f"Unsupported channel field {field!r}. Allowed: {allowed}")
    return field


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_report_config(config_path: Path = DEFAULT_CONFIG_PATH) -> ReportConfig:
    config_data: dict[str, Any] = {}
    if config_path.exists():
        config_data = json.loads(config_path.read_text(encoding="utf-8"))

    channel = config_data.get("channel", {})
    email_config = config_data.get("email", {})

    recipients = split_recipients(os.environ.get("MOMO_REPORT_RECIPIENTS"))
    if not recipients:
        recipients = list(config_data.get("recipients", []))

    output_dir = os.environ.get("MOMO_REPORT_OUTPUT_DIR") or config_data.get(
        "output_dir", "outputs/airflow/momo_daily_sales"
    )

    source_database = os.environ.get("SQL_DATABASE") or config_data.get("source_database", "CHIComp06")
    channel_field = os.environ.get("MOMO_REPORT_CHANNEL_FIELD") or channel.get("field", "BA.Remark")
    channel_pattern = os.environ.get("MOMO_REPORT_CHANNEL_PATTERN") or channel.get("pattern", "%MOMO%")

    return ReportConfig(
        job_id=str(config_data.get("job_id", "momo-daily-sales")),
        source_database=require_safe_database_name(str(source_database)),
        timezone=str(config_data.get("timezone", "Asia/Taipei")),
        channel_field=require_channel_field(str(channel_field)),
        channel_pattern=str(channel_pattern),
        recipients=recipients,
        sender=os.environ.get("GRAPH_SENDER") or email_config.get("sender", "it@creata.com.tw"),
        subject_prefix=str(email_config.get("subject_prefix", "MOMO Daily Sales Report")),
        output_dir=resolve_project_path(output_dir),
    )


def to_report_date(value: str | dt.date | None) -> dt.date:
    if value is None:
        offset = int(os.environ.get("MOMO_REPORT_DATE_OFFSET_DAYS", "1"))
        return dt.datetime.now().date() - dt.timedelta(days=offset)
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(value)


def date_to_int(value: dt.date) -> int:
    return int(value.strftime("%Y%m%d"))


def normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: normalize_value(value) for key, value in row.items()} for row in rows]


def read_sql(path: Path, config: ReportConfig) -> str:
    return path.read_text(encoding="utf-8").format(
        database=quote_identifier(config.source_database),
        source_database=config.source_database,
        channel_field=config.channel_field,
    )


def odbc_value(value: str) -> str:
    if any(char in value for char in ";{}"):
        return "{" + value.replace("}", "}}") + "}"
    return value


def build_connection_string(config: ReportConfig) -> str:
    direct = os.environ.get("SQL_CONNECTION_STRING")
    if direct:
        return direct

    server = os.environ.get("SQL_SERVER") or os.environ.get("DB_SERVER")
    user = os.environ.get("SQL_USER") or os.environ.get("DB_USER")
    password = os.environ.get("SQL_PASSWORD") or os.environ.get("DB_PASSWORD")
    if not server or not user or not password:
        raise RuntimeError("SQL_SERVER, SQL_USER, and SQL_PASSWORD are required for live report runs.")

    port = os.environ.get("SQL_PORT") or os.environ.get("DB_PORT") or "1433"
    driver = os.environ.get("SQL_DRIVER") or os.environ.get("DB_DRIVER") or "ODBC Driver 18 for SQL Server"
    encrypt = os.environ.get("SQL_ENCRYPT") or os.environ.get("DB_ENCRYPT") or "no"
    trust_cert = (
        os.environ.get("SQL_TRUST_SERVER_CERTIFICATE")
        or os.environ.get("DB_TRUST_SERVER_CERTIFICATE")
        or "yes"
    )
    server_part = f"{server},{port}" if port else server

    parts = {
        "DRIVER": "{" + driver + "}",
        "SERVER": odbc_value(server_part),
        "DATABASE": odbc_value(config.source_database),
        "UID": odbc_value(user),
        "PWD": odbc_value(password),
        "Encrypt": encrypt,
        "TrustServerCertificate": trust_cert,
        "Connection Timeout": "30",
    }
    return ";".join(f"{key}={value}" for key, value in parts.items()) + ";"


def fetch_rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query_live_data(config: ReportConfig, report_date: dt.date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError("pyodbc is required for live SQL Server report runs.") from exc

    report_date_int = date_to_int(report_date)
    params = (report_date_int, config.channel_pattern)
    connection_string = build_connection_string(config)

    with pyodbc.connect(connection_string) as connection:
        summary_cursor = connection.cursor()
        summary_cursor.execute(read_sql(SUMMARY_SQL_PATH, config), params)
        summary_rows = fetch_rows(summary_cursor)

        top_cursor = connection.cursor()
        top_cursor.execute(read_sql(TOP10_SQL_PATH, config), params)
        top_rows = fetch_rows(top_cursor)

    return normalize_rows(summary_rows), normalize_rows(top_rows)


def sample_data(config: ReportConfig, report_date: dt.date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    report_date_int = date_to_int(report_date)
    summary = [
        {
            "source_database": config.source_database,
            "report_date_int": report_date_int,
            "gross_sales_amount": 168420,
            "return_amount": 3200,
            "net_sales_amount": 165220,
            "net_quantity": 87,
            "order_count": 42,
        }
    ]
    products = [
        ("SKU-MOMO-001", "Sample rice cooker", 18, 42800),
        ("SKU-MOMO-002", "Sample air purifier", 9, 36200),
        ("SKU-MOMO-003", "Sample filter pack", 22, 28900),
        ("SKU-MOMO-004", "Sample blender", 7, 18100),
        ("SKU-MOMO-005", "Sample cookware set", 5, 16400),
        ("SKU-MOMO-006", "Sample kettle", 10, 9800),
        ("SKU-MOMO-007", "Sample fan", 4, 8800),
        ("SKU-MOMO-008", "Sample vacuum accessory", 6, 7200),
        ("SKU-MOMO-009", "Sample toaster", 3, 6300),
        ("SKU-MOMO-010", "Sample storage box", 8, 4720),
    ]
    top_rows = [
        {
            "source_database": config.source_database,
            "report_date_int": report_date_int,
            "product_id": product_id,
            "product_name": product_name,
            "net_quantity": qty,
            "net_sales_amount": amount,
            "gross_sales_amount": amount,
            "return_amount": 0,
        }
        for product_id, product_name, qty, amount in products
    ]
    return summary, top_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["no_data"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def write_xlsx(path: Path, summary_rows: list[dict[str, Any]], top_rows: list[dict[str, Any]]) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        return False

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Summary"
    top_sheet = workbook.create_sheet("Top 10 Products")

    def write_sheet(sheet: Any, rows: list[dict[str, Any]]) -> None:
        headers = list(rows[0].keys()) if rows else ["no_data"]
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append([row.get(header) for header in headers])
        for column_cells in sheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 48)
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "#,##0"

    write_sheet(summary_sheet, summary_rows)
    write_sheet(top_sheet, top_rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return True


def number(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def fmt_amount(value: Any) -> str:
    return f"{number(value):,.0f}"


def render_email_html(
    config: ReportConfig,
    report_date: dt.date,
    summary_rows: list[dict[str, Any]],
    top_rows: list[dict[str, Any]],
    *,
    sample_data_used: bool,
) -> str:
    summary = summary_rows[0] if summary_rows else {}
    top_lines = []
    for index, row in enumerate(top_rows, start=1):
        top_lines.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(str(row.get('product_id', '')))}</td>"
            f"<td>{html.escape(str(row.get('product_name', '')))}</td>"
            f"<td style=\"text-align:right\">{fmt_amount(row.get('net_quantity'))}</td>"
            f"<td style=\"text-align:right\">{fmt_amount(row.get('net_sales_amount'))}</td>"
            "</tr>"
        )
    sample_note = "<p><strong>Dry-run sample data.</strong></p>" if sample_data_used else ""
    return f"""<!doctype html>
<html>
<body>
  <p>MOMO daily sales report for {report_date.isoformat()}.</p>
  {sample_note}
  <table border="1" cellspacing="0" cellpadding="6">
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Source database</td><td>{html.escape(str(summary.get('source_database', config.source_database)))}</td></tr>
    <tr><td>Channel filter</td><td>{html.escape(config.channel_field)} LIKE {html.escape(config.channel_pattern)}</td></tr>
    <tr><td>Gross sales amount</td><td style="text-align:right">{fmt_amount(summary.get('gross_sales_amount'))}</td></tr>
    <tr><td>Return amount</td><td style="text-align:right">{fmt_amount(summary.get('return_amount'))}</td></tr>
    <tr><td>Net sales amount</td><td style="text-align:right">{fmt_amount(summary.get('net_sales_amount'))}</td></tr>
    <tr><td>Net quantity</td><td style="text-align:right">{fmt_amount(summary.get('net_quantity'))}</td></tr>
    <tr><td>Order count</td><td style="text-align:right">{fmt_amount(summary.get('order_count'))}</td></tr>
  </table>
  <h3>Top 10 products</h3>
  <table border="1" cellspacing="0" cellpadding="6">
    <tr><th>#</th><th>Product ID</th><th>Product name</th><th>Net quantity</th><th>Net sales amount</th></tr>
    {''.join(top_lines)}
  </table>
</body>
</html>
"""


def report_subject(config: ReportConfig, report_date: dt.date) -> str:
    return f"{config.subject_prefix} - {report_date.isoformat()}"


def build_report(config: ReportConfig, report_date: dt.date | str | None = None, *, sample_data: bool = False) -> dict[str, Any]:
    report_date_value = to_report_date(report_date)
    dated_dir = config.output_dir / report_date_value.strftime("%Y%m%d")
    dated_dir.mkdir(parents=True, exist_ok=True)

    if sample_data:
        summary_rows, top_rows = globals()["sample_data"](config, report_date_value)
    else:
        summary_rows, top_rows = query_live_data(config, report_date_value)

    stem = f"momo_daily_sales_{report_date_value.strftime('%Y%m%d')}"
    summary_csv = dated_dir / f"{stem}_summary.csv"
    top_csv = dated_dir / f"{stem}_top10_products.csv"
    workbook_path = dated_dir / f"{stem}.xlsx"
    email_preview = dated_dir / f"{stem}_email_preview.html"
    manifest_path = dated_dir / f"{stem}_manifest.json"

    write_csv(summary_csv, summary_rows)
    write_csv(top_csv, top_rows)
    xlsx_written = write_xlsx(workbook_path, summary_rows, top_rows)
    email_html = render_email_html(
        config,
        report_date_value,
        summary_rows,
        top_rows,
        sample_data_used=sample_data,
    )
    email_preview.write_text(email_html, encoding="utf-8")

    artifacts = {
        "summary_csv": str(summary_csv),
        "top_products_csv": str(top_csv),
        "email_preview_html": str(email_preview),
        "manifest": str(manifest_path),
    }
    if xlsx_written:
        artifacts["xlsx"] = str(workbook_path)

    summary = summary_rows[0] if summary_rows else {}
    manifest = {
        "job_id": config.job_id,
        "report_date": report_date_value.isoformat(),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_database": config.source_database,
        "channel_filter": {
            "field": config.channel_field,
            "pattern": config.channel_pattern,
        },
        "sample_data": sample_data,
        "recipients": config.recipients,
        "sender": config.sender,
        "subject": report_subject(config, report_date_value),
        "summary": summary,
        "top_product_count": len(top_rows),
        "artifacts": artifacts,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    latest_manifest = config.output_dir / "latest_manifest.json"
    latest_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    return manifest


def graph_access_token() -> str:
    tenant_id = os.environ.get("GRAPH_TENANT_ID")
    client_id = os.environ.get("GRAPH_CLIENT_ID")
    client_secret = os.environ.get("GRAPH_CLIENT_SECRET")
    if not tenant_id or not client_id or not client_secret:
        raise RuntimeError("GRAPH_TENANT_ID, GRAPH_CLIENT_ID, and GRAPH_CLIENT_SECRET are required.")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("requests is required for Microsoft Graph mail delivery.") from exc

    response = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def send_graph_email(
    *,
    sender: str,
    recipients: list[str],
    subject: str,
    html_body: str,
    attachments: list[Path],
) -> dict[str, Any]:
    if not recipients:
        raise RuntimeError("At least one recipient is required.")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("requests is required for Microsoft Graph mail delivery.") from exc

    token = graph_access_token()
    payload_attachments = []
    for path in attachments:
        payload_attachments.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": path.name,
                "contentBytes": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": recipient}} for recipient in recipients],
            "attachments": payload_attachments,
        },
        "saveToSentItems": "true",
    }

    response = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return {"status": "sent", "http_status": response.status_code, "recipients": recipients}


def attachment_paths(manifest: dict[str, Any]) -> list[Path]:
    artifacts = manifest.get("artifacts", {})
    if "xlsx" in artifacts:
        return [Path(artifacts["xlsx"])]
    return [Path(artifacts["summary_csv"]), Path(artifacts["top_products_csv"])]


def deliver_manifest(manifest_path: Path, config: ReportConfig, *, dry_run: bool = True) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    html_body = Path(manifest["artifacts"]["email_preview_html"]).read_text(encoding="utf-8")
    attachments = attachment_paths(manifest)

    missing = [str(path) for path in attachments if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing report attachments: {missing}")

    if dry_run:
        return {
            "status": "dry_run",
            "message": "Email not sent. Set MOMO_REPORT_DRY_RUN=false after validation and approval.",
            "recipients": config.recipients,
            "attachments": [str(path) for path in attachments],
        }

    return send_graph_email(
        sender=config.sender,
        recipients=config.recipients,
        subject=manifest["subject"],
        html_body=html_body,
        attachments=attachments,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and optionally email the MOMO daily sales report.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--env-file", type=Path, action="append", default=[])
    parser.add_argument("--report-date", help="Calendar date to report, formatted as YYYY-MM-DD. Defaults to yesterday.")
    parser.add_argument("--sample-data", action="store_true", help="Generate a no-database sample report.")
    parser.add_argument("--dry-run", action="store_true", help="Do not send email.")
    parser.add_argument("--send", action="store_true", help="Send email through Microsoft Graph.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_default_env_files()
    for env_file in args.env_file:
        load_env_file(env_file, override=True)

    if args.dry_run and args.send:
        raise SystemExit("--dry-run and --send cannot be used together.")

    config = load_report_config(args.config)
    sample = args.sample_data or parse_bool(os.environ.get("MOMO_REPORT_USE_SAMPLE_DATA", "false"))
    dry_run = parse_bool(os.environ.get("MOMO_REPORT_DRY_RUN", "true"), default=True)
    if args.dry_run:
        dry_run = True
    if args.send:
        dry_run = False

    manifest = build_report(config=config, report_date=args.report_date, sample_data=sample)
    delivery = deliver_manifest(Path(manifest["artifacts"]["manifest"]), config=config, dry_run=dry_run)
    print(
        json.dumps(
            {
                "manifest": manifest["artifacts"]["manifest"],
                "delivery": delivery,
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
