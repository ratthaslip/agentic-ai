"""Lab 3 : ReAct agent + SQL tool."""
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from lab1_llm import build_llm          # ใช้ LLM จาก Lab 1
from db_tools import run_sql_query        # ใช้ SQL tool จาก Lab 2

SYSTEM_PROMPT = """คุณเป็นผู้ช่วยตรวจสอบการเบิกจ่ายของกรมบัญชีกลาง
มีเครื่องมือ run_sql_query สำหรับ query ฐานข้อมูล (read-only)

Schema:
- budget(budget_code, budget_name, fiscal_year, total_amount)
- contract(contract_no, vendor_name, vendor_tax_id, budget_code, contract_amount, sign_date, status)
- disbursement(disb_id, contract_no, pay_date, installment, amount, voucher_no)

กติกา:
1. เขียน SQL ที่ถูกต้องตาม schema ข้างต้นเท่านั้น
2. เมื่อต้องการยอดรวม ให้ใช้ SUM(amount) และ GROUP BY ตามเหมาะสม
3. สรุปคำตอบสุดท้ายเป็นภาษาไทย พร้อมตัวเลขที่จัดรูปแบบอ่านง่าย
"""


def build_agent():
    llm = build_llm()
    tools = [run_sql_query]
    # create_agent สร้าง graph ReAct ให้อัตโนมัติ (reason -> tool -> observe -> ...)
    return create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)


if __name__ == "__main__":
    agent = build_agent()
    question = "ยอดเบิกจ่ายรวมของสัญญาเลขที่ 67A00012345 เท่าไร"
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    # ข้อความสุดท้ายคือคำตอบของ agent
    print(result["messages"][-1].content)
