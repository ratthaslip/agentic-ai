# dags/cgd_recon_dag.py (Bonus — Airflow)
# Pipeline ตรวจ anomaly ประจำวัน แล้วส่งรายงานเข้า email หรือ ticket ต่อ
#
#   detect_anomalies  ->  send_report
#
# การตั้งค่าช่องทางส่ง (ผ่าน environment variable / .env):
#   REPORT_CHANNEL = email | ticket | dry_run   (ค่าเริ่มต้น dry_run สำหรับห้องอบรม)
#
#   -- email (SMTP) --
#   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
#   REPORT_EMAIL_FROM, REPORT_EMAIL_TO   (คั่นหลายผู้รับด้วย ,)
#
#   -- ticket (HTTP webhook เช่น Jira/ServiceNow/Line Notify/MS Teams) --
#   TICKET_WEBHOOK_URL, TICKET_AUTH_HEADER (เช่น "Bearer xxxx")  [optional]
#
# หมายเหตุ: ค่าลับทั้งหมดมาจาก env — ห้าม hardcode ในไฟล์นี้
import os
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


# ------------------------------------------------------------------
# Task 1: ตรวจ anomaly + validate + สร้างรายงานภาษาไทย -> ส่งต่อผ่าน XCom
# ------------------------------------------------------------------
def _detect_anomalies(**context):
    from db_tools import detect_anomalies
    from lab5_audit import validate_anomalies, build_thai_report, audit_log

    raw = detect_anomalies.invoke({})
    anomalies = validate_anomalies(raw)          # Guardrail: validate output
    audit_log("scheduled_detect", {"count": len(anomalies)})

    report = build_thai_report(anomalies)
    # ส่ง count + รายงาน ให้ task ถัดไปผ่าน XCom
    context["ti"].xcom_push(key="count", value=len(anomalies))
    context["ti"].xcom_push(key="report", value=report)
    print(f"[detect] พบรายการผิดปกติ {len(anomalies)} รายการ")
    return len(anomalies)


# ------------------------------------------------------------------
# ช่องทางส่ง: email
# ------------------------------------------------------------------
def _send_email(subject: str, body: str):
    import smtplib
    from email.mime.text import MIMEText

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("REPORT_EMAIL_FROM", user or "noreply@cgd.local")
    recipients = [x.strip() for x in os.getenv("REPORT_EMAIL_TO", "").split(",") if x.strip()]

    if not (host and recipients):
        raise ValueError("ยังไม่ได้ตั้งค่า SMTP_HOST หรือ REPORT_EMAIL_TO")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        try:
            smtp.starttls()                       # ใช้ TLS ถ้า server รองรับ
            smtp.ehlo()
        except smtplib.SMTPException:
            pass                                  # server ที่ไม่รองรับ STARTTLS
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(sender, recipients, msg.as_string())
    print(f"[send_report] ส่ง email ไปยัง {recipients} แล้ว")


# ------------------------------------------------------------------
# ช่องทางส่ง: ticket (HTTP webhook)
# ------------------------------------------------------------------
def _send_ticket(subject: str, body: str):
    import json
    import urllib.request

    url = os.getenv("TICKET_WEBHOOK_URL")
    if not url:
        raise ValueError("ยังไม่ได้ตั้งค่า TICKET_WEBHOOK_URL")

    payload = json.dumps({"title": subject, "description": body},
                         ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    auth = os.getenv("TICKET_AUTH_HEADER")
    if auth:
        req.add_header("Authorization", auth)

    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"[send_report] สร้าง ticket แล้ว (HTTP {resp.status})")


# ------------------------------------------------------------------
# Task 2: ส่งรายงานตามช่องทางที่ตั้งค่าไว้
# ------------------------------------------------------------------
def _send_report(**context):
    from lab5_audit import audit_log

    ti = context["ti"]
    count = ti.xcom_pull(task_ids="detect_anomalies", key="count") or 0
    report = ti.xcom_pull(task_ids="detect_anomalies", key="report") or ""

    if count == 0:
        print("[send_report] ไม่พบรายการผิดปกติ — ไม่ส่งรายงาน")
        audit_log("send_report_skipped", {"reason": "no_anomaly"})
        return

    channel = os.getenv("REPORT_CHANNEL", "dry_run").lower()
    subject = f"[CGD] รายงานข้อสังเกตการเบิกจ่าย พบ {count} รายการ ({datetime.now():%Y-%m-%d})"

    try:
        if channel == "email":
            _send_email(subject, report)
        elif channel == "ticket":
            _send_ticket(subject, report)
        else:  # dry_run — พิมพ์รายงานออก log อย่างเดียว (เหมาะกับห้องอบรม/ยังไม่ตั้งค่า)
            print(f"[send_report] (dry_run) ช่องทางยังไม่ถูกตั้งค่า — แสดงรายงานใน log:\n")
            print(subject + "\n\n" + report)
        audit_log("send_report", {"channel": channel, "count": count, "subject": subject})
    except Exception as e:
        # ส่งไม่สำเร็จ = เหตุการณ์ที่ต้องตรวจสอบ -> log ไว้แล้ว raise ให้ Airflow mark failed
        audit_log("send_report_failed", {"channel": channel, "error": str(e)})
        raise


# ------------------------------------------------------------------
# DAG definition
# ------------------------------------------------------------------
with DAG(
    "cgd_reconciliation",
    start_date=datetime(2026, 1, 1),
    schedule="0 7 * * *",           # ทุกวัน 07:00
    catchup=False,
    default_args={"retries": 1},
    tags=["cgd", "reconciliation", "audit"],
) as dag:
    detect = PythonOperator(
        task_id="detect_anomalies",
        python_callable=_detect_anomalies,
    )
    send = PythonOperator(
        task_id="send_report",
        python_callable=_send_report,
    )

    detect >> send          
