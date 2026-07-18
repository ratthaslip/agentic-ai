"""Lab 4 : ReAct agent + reconciliation tools + memory."""
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

from lab1_llm import build_llm
from db_tools import run_sql_query, reconcile_contract, detect_anomalies

SYSTEM_PROMPT = """คุณเป็นผู้ช่วยกระทบยอดและตรวจสอบการเบิกจ่ายของกรมบัญชีกลาง
เครื่องมือที่มี:
- run_sql_query : query ข้อมูลทั่วไป (read-only)
- reconcile_contract : กระทบยอดสัญญา 1 ฉบับ (เทียบวงเงินกับยอดเบิกจ่าย)
- detect_anomalies : ตรวจรายการผิดปกติทั้งระบบ (เบิกเกินสัญญา/เกินงบ)

เมื่อผู้ใช้ขอ "กระทบยอด" สัญญา ให้เรียก reconcile_contract
เมื่อผู้ใช้ขอ "ตรวจรายการผิดปกติ" ให้เรียก detect_anomalies
สรุปผลเป็นภาษาไทย ชี้ชัดว่ารายการใดผิดปกติและเกินเท่าไร
"""


def build_agent():
    llm = build_llm()
    tools = [run_sql_query, reconcile_contract, detect_anomalies]
    memory = MemorySaver()  # เก็บ state/ประวัติการสนทนา
    return create_agent(llm, tools, system_prompt=SYSTEM_PROMPT, checkpointer=memory)


if __name__ == "__main__":
    agent = build_agent()
    # thread_id ระบุ session — ข้อความใน thread เดียวกันจะถูกจำไว้
    config = {"configurable": {"thread_id": "audit-session-1"}}
    for q in [
        "กระทบยอดสัญญาเลขที่ 67A00012346 ให้หน่อย",
        "แล้วมีสัญญาไหนอีกบ้างที่เบิกเกินวงเงิน",  # ใช้ memory เข้าใจบริบทต่อเนื่อง
    ]:
        print(f"\n>>> {q}")
        res = agent.invoke({"messages": [HumanMessage(content=q)]}, config=config)
        print(res["messages"][-1].content)
