"""Lab 1 : LLM call แรก + ทดสอบภาษาไทย."""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()  # โหลดค่าจากไฟล์ .env


def build_llm():
    """สร้าง chat model. รองรับทั้ง OpenAI และ Azure OpenAI."""
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini"),
            api_version=os.getenv("OPENAI_API_VERSION", "2024-10-21"),
            temperature=0,
        )
    # ค่าเริ่มต้น: OpenAI
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        temperature=0,  # ตอบแบบ deterministic เหมาะกับงานตรวจสอบ
    )


if __name__ == "__main__":
    llm = build_llm()
    messages = [
        SystemMessage(content=(
            "คุณเป็นผู้ช่วยด้านการตรวจสอบการเบิกจ่ายของกรมบัญชีกลาง "
            "ตอบเป็นภาษาไทยที่กระชับและถูกต้อง"
        )),
        HumanMessage(content="อธิบายสั้น ๆ ว่า 'การกระทบยอด' (reconciliation) คืออะไร"),
    ]
    resp = llm.invoke(messages)
    print("=== คำตอบจาก LLM ===")
    print(resp.content)
