# ============================================================
# Dockerfile — CGD Reconciliation Agent (Lab runner)
# ใช้รันโค้ด Lab 1-5 ภายใน container ที่เชื่อมกับ postgres service
# ============================================================
FROM python:3.11-slim

# ตั้งค่าภาษา/encoding ให้รองรับภาษาไทยใน terminal (ตาม Troubleshooting ในคู่มือ)
ENV PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

WORKDIR /app

# ติดตั้ง dependency ก่อน (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# คัดลอกซอร์สโค้ดทั้งหมด
COPY . .

# ค่าเริ่มต้น: เปิด shell ค้างไว้ให้ exec เข้าไปรันแต่ละ Lab เอง
# (docker compose จะ override ด้วย command ตามต้องการ)
CMD ["sleep", "infinity"]
