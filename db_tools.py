"""SQL tool แบบ read-only + allow-list (Lab 2)
รวมเครื่องมือกระทบยอดและตรวจ anomaly (Lab 4) ไว้ในไฟล์เดียวกัน.

ไฟล์นี้ถูกใช้ต่อใน Lab 3-5.
"""
import os
import re
import json

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from langchain_core.tools import tool
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

READONLY_DSN = os.getenv("PG_READONLY_DSN")
ALLOWED_TABLES = {"budget", "contract", "disbursement"}
MAX_ROWS = 200

_engine: Engine | None = None


def _get_engine() -> Engine:
    """สร้าง SQLAlchemy engine ครั้งเดียว (lazy) โดยใช้ DSN เดิมจาก env.
    ใช้ creator เพื่อคง semantics ของ PG_READONLY_DSN (รองรับทั้งรูปแบบ URL
    และ libpq keyword string) และไม่เปิดเผย credential ใน URL ของ engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: psycopg2.connect(READONLY_DSN),
            pool_pre_ping=True,
        )
    return _engine


# ============================================================
# Lab 2 : SQL tool แบบ read-only + allow-list
# ============================================================
def _validate_sql(sql: str) -> str:
    """ตรวจความปลอดภัยของ SQL ก่อนรัน. คืนค่า SQL ที่ปลอดภัย หรือ raise."""
    s = sql.strip().rstrip(";").strip()

    # 1) อนุญาตเฉพาะ read-only (SELECT / WITH)
    # หมายเหตุ: table allow-list (ข้อ 4) จะมอง alias ของ CTE (WITH x AS ...) เป็น "ตาราง"
    # จึงอาจ reject query ที่ใช้ WITH-CTE — เป็นพฤติกรรมตามคู่มือ (เน้น fail-safe)
    # หากต้องการรองรับ CTE ให้เพิ่ม alias เข้า ALLOWED_TABLES ก่อนตรวจ
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        raise ValueError("อนุญาตเฉพาะคำสั่ง SELECT/WITH (read-only) เท่านั้น")

    # 2) ปฏิเสธคำสั่งอันตราย (กัน DML/DDL ที่อาจซ่อนใน subquery)
    forbidden = r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy)\b"
    if re.search(forbidden, s, re.IGNORECASE):
        raise ValueError("พบคำสั่งที่ไม่อนุญาต (DML/DDL)")

    # 3) ปฏิเสธ stacked queries (หลายคำสั่งใน statement เดียว)
    if ";" in s:
        raise ValueError("ไม่อนุญาตหลายคำสั่งใน query เดียว")

    # 4) table allow-list — ตารางทุกตัวที่อ้างถึงต้องอยู่ในรายการอนุญาต
    referenced = set(re.findall(
        r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", s, re.IGNORECASE))
    illegal = {t.lower() for t in referenced} - ALLOWED_TABLES
    if illegal:
        raise ValueError(f"ไม่อนุญาตให้เข้าถึงตาราง: {', '.join(illegal)}")

    # 5) ใส่ LIMIT ถ้ายังไม่มี
    if not re.search(r"\blimit\b", s, re.IGNORECASE):
        s = f"{s} LIMIT {MAX_ROWS}"

    return s


def _run_readonly(sql: str) -> pd.DataFrame:
    """เปิด connection แบบ read-only ผ่าน SQLAlchemy แล้วรัน query.
    ส่ง SQLAlchemy connection ให้ pandas (ไม่ใช่ DBAPI connection ดิบ)
    เพื่อให้ pd.read_sql_query ไม่เตือน และบังคับ read-only ที่ระดับ transaction."""
    engine = _get_engine()
    # postgresql_readonly=True -> SET TRANSACTION READ ONLY (เทียบเท่า set_session เดิม)
    with engine.connect().execution_options(postgresql_readonly=True) as conn:
        df = pd.read_sql_query(text(sql), conn)
    return df


@tool
def run_sql_query(sql: str) -> str:
    """รัน SQL แบบ read-only กับฐานข้อมูลการคลัง (ตาราง budget, contract, disbursement)
    ใช้สำหรับดึงข้อมูลสัญญา การเบิกจ่าย และงบประมาณ. รับเฉพาะคำสั่ง SELECT/WITH.
    คืนผลลัพธ์เป็นตารางข้อความ."""
    try:
        safe_sql = _validate_sql(sql)
        df = _run_readonly(safe_sql)
        if df.empty:
            return "ไม่พบข้อมูลตามเงื่อนไข"
        return df.to_string(index=False)
    except Exception as e:
        return f"ERROR: {e}"


# ============================================================
# Lab 4 : เครื่องมือกระทบยอด + ตรวจ anomaly
# ============================================================
@tool
def reconcile_contract(contract_no: str) -> str:
    """กระทบยอดสัญญา 1 ฉบับ: เทียบวงเงินสัญญากับยอดเบิกจ่ายสะสม
    คืนผลเป็น JSON: วงเงินสัญญา, ยอดเบิกจ่ายรวม, ส่วนต่าง, สถานะ."""
    sql = f'''
        SELECT c.contract_no, c.vendor_name, c.contract_amount,
               COALESCE(SUM(d.amount), 0) AS paid_total
        FROM contract c
        LEFT JOIN disbursement d ON d.contract_no = c.contract_no
        WHERE c.contract_no = '{contract_no}'
        GROUP BY c.contract_no, c.vendor_name, c.contract_amount
    '''
    df = _run_readonly(_validate_sql(sql))
    if df.empty:
        return json.dumps({"error": f"ไม่พบสัญญา {contract_no}"}, ensure_ascii=False)

    row = df.iloc[0]
    contract_amount = float(row["contract_amount"])
    paid = float(row["paid_total"])
    diff = paid - contract_amount
    pct = round(paid / contract_amount * 100, 1) if contract_amount else None
    status = "over_contract" if diff > 0 else "ok"

    return json.dumps({
        "contract_no": row["contract_no"],
        "vendor_name": row["vendor_name"],
        "contract_amount": contract_amount,
        "paid_total": paid,
        "difference": diff,      # บวก = เบิกเกินสัญญา
        "paid_percent": pct,
        "status": status,
    }, ensure_ascii=False)


@tool
def detect_anomalies() -> str:
    """ตรวจ anomaly ทั้งระบบ: (1) สัญญาที่เบิกเกินวงเงิน (over_contract)
    และ (2) งบประมาณที่ยอดเบิกจ่ายรวมเกินวงเงินงบ (over_budget).
    คืนผลเป็น JSON list ของรายการผิดปกติ."""
    anomalies = []

    # (1) over_contract : SUM(disbursement) > contract_amount
    sql_contract = '''
        SELECT c.contract_no, c.vendor_name, c.contract_amount,
               COALESCE(SUM(d.amount),0) AS paid_total
        FROM contract c
        LEFT JOIN disbursement d ON d.contract_no = c.contract_no
        GROUP BY c.contract_no, c.vendor_name, c.contract_amount
        HAVING COALESCE(SUM(d.amount),0) > c.contract_amount
    '''
    for _, r in _run_readonly(_validate_sql(sql_contract)).iterrows():
        anomalies.append({
            "type": "over_contract",
            "contract_no": r["contract_no"],
            "vendor_name": r["vendor_name"],
            "over_amount": float(r["paid_total"]) - float(r["contract_amount"]),
        })

    # (2) over_budget : SUM(disbursement ในงบ) > budget.total_amount
    sql_budget = '''
        SELECT b.budget_code, b.budget_name, b.total_amount,
               COALESCE(SUM(d.amount),0) AS paid_total
        FROM budget b
        LEFT JOIN contract c ON c.budget_code = b.budget_code
        LEFT JOIN disbursement d ON d.contract_no = c.contract_no
        GROUP BY b.budget_code, b.budget_name, b.total_amount
        HAVING COALESCE(SUM(d.amount),0) > b.total_amount
    '''
    for _, r in _run_readonly(_validate_sql(sql_budget)).iterrows():
        anomalies.append({
            "type": "over_budget",
            "budget_code": r["budget_code"],
            "budget_name": r["budget_name"],
            "over_amount": float(r["paid_total"]) - float(r["total_amount"]),
        })

    return json.dumps(anomalies, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # ทดสอบ tool โดยตรง
    print(run_sql_query.invoke({
        "sql": "SELECT contract_no, vendor_name, contract_amount FROM contract"
    }))
    print("---- ทดสอบ guardrail (ต้องถูกปฏิเสธ) ----")
    print(run_sql_query.invoke({"sql": "DELETE FROM contract"}))
