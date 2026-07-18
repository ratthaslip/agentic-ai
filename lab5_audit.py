"""Lab 5 : guardrails + HITL + รายงานข้อสังเกตภาษาไทย."""
import json
import os
from datetime import datetime

from langchain_core.messages import HumanMessage

from lab4_agent import build_agent
from db_tools import detect_anomalies

# ---------- Guardrail 1: step / recursion limit ----------
RECURSION_LIMIT = 15  # กัน agent วน loop ไม่จบ (cost overrun)

# โฟลเดอร์สำหรับ audit log / รายงาน
# ค่าเริ่มต้น = โฟลเดอร์ปัจจุบัน (การรันแบบ manual เหมือนเดิม)
# เมื่อรันผ่าน Airflow ให้ตั้ง AUDIT_LOG_DIR=/opt/project เพื่อให้ไฟล์ mount กลับมา host
OUTPUT_DIR = os.getenv("AUDIT_LOG_DIR") or os.getenv("REPORT_DIR") or "."


# ---------- Guardrail 2: audit log ----------
def audit_log(action: str, detail: dict):
    """บันทึก action ทุกครั้งเพื่อ traceability."""
    entry = {"ts": datetime.now().isoformat(), "action": action, "detail": detail}
    path = os.path.join(OUTPUT_DIR, "audit_trail.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------- Guardrail 3: output validation ----------
def validate_anomalies(raw: str) -> list:
    """ตรวจว่า output จาก tool เป็น JSON list ที่มี field ครบ."""
    data = json.loads(raw)
    assert isinstance(data, list), "output ต้องเป็น list"
    for item in data:
        assert "type" in item and "over_amount" in item, "field ไม่ครบ"
        assert item["over_amount"] > 0, "over_amount ต้องมากกว่า 0"
    return data


# ---------- HITL gate ----------
def human_approve(prompt: str) -> bool:
    """ขออนุมัติจากเจ้าหน้าที่ (จำลองด้วย input ใน Lab; production = ระบบ ticket/approval)."""
    ans = input(f"{prompt} (y/n): ").strip().lower()
    return ans == "y"


# ---------- รายงานข้อสังเกตภาษาไทย ----------
def build_thai_report(anomalies: list) -> str:
    if not anomalies:
        return "ไม่พบรายการผิดปกติ ทุกสัญญาและงบประมาณอยู่ในวงเงิน"

    lines = ["รายงานข้อสังเกตการตรวจสอบการเบิกจ่าย",
             f"วันที่ออกรายงาน: {datetime.now():%Y-%m-%d %H:%M}",
             f"พบรายการผิดปกติทั้งหมด {len(anomalies)} รายการ", ""]
    for i, a in enumerate(anomalies, 1):
        if a["type"] == "over_contract":
            lines.append(
                f"{i}. [เบิกเกินสัญญา] สัญญา {a['contract_no']} "
                f"({a['vendor_name']}) เบิกเกินวงเงิน {a['over_amount']:,.2f} บาท")
        elif a["type"] == "over_budget":
            lines.append(
                f"{i}. [เบิกเกินงบ] งบ {a['budget_code']} "
                f"({a['budget_name']}) เบิกเกินวงเงินงบ {a['over_amount']:,.2f} บาท")
    lines += ["", "ข้อเสนอแนะ: ให้เจ้าหน้าที่ตรวจสอบเอกสารประกอบและชี้แจงเหตุผล"]
    return "\n".join(lines)


if __name__ == "__main__":
    # 1) ตรวจ anomaly (read-only, ปลอดภัย)
    raw = detect_anomalies.invoke({})
    anomalies = validate_anomalies(raw)  # Guardrail: validate output
    audit_log("detect_anomalies", {"count": len(anomalies)})
    print(f"พบรายการผิดปกติ {len(anomalies)} รายการ")

    # 2) HITL gate ก่อน "ออกรายงาน/บันทึกข้อสังเกต"
    if anomalies and human_approve("ยืนยันออกรายงานข้อสังเกตและบันทึก audit หรือไม่?"):
        report = build_thai_report(anomalies)
        print("\n" + report)
        with open(os.path.join(OUTPUT_DIR, "anomaly_report.txt"), "w", encoding="utf-8") as f:
            f.write(report)
        audit_log("publish_report", {"approved_by": "officer", "count": len(anomalies)})
        print("\n[OK] บันทึกรายงานที่ anomaly_report.txt และ audit_trail.log แล้ว")
    else:
        audit_log("publish_report_declined", {})
        print("ยกเลิกการออกรายงานตามคำสั่งเจ้าหน้าที่")

    # 3) ตัวอย่างเรียก agent พร้อม step limit (กัน loop ไม่จบ)
    agent = build_agent()
    config = {"configurable": {"thread_id": "audit-final"},
              "recursion_limit": RECURSION_LIMIT}
    res = agent.invoke(
        {"messages": [HumanMessage(content="สรุปภาพรวมการกระทบยอดทั้งระบบเป็นภาษาไทย")]},
        config=config)
    print("\n=== สรุปจาก Agent ===")
    print(res["messages"][-1].content)
