#!/usr/bin/env bash
# ============================================================
# run.sh — รันครบชุดในคำสั่งเดียว
#   ./run.sh            เปิด stack (postgres+seed+agent) แล้วรัน Lab 2 (ไม่ต้องใช้ API key)
#   ./run.sh lab1       รัน Lab 1
#   ./run.sh lab3       รัน Lab 3 ... (lab4 / lab5 เช่นกัน)
#   ./run.sh down       หยุดและลบ container (คง volume ข้อมูลไว้)
#   ./run.sh reset      ลบทุกอย่างรวม volume (seed ใหม่ทั้งหมด)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

# เตรียมไฟล์ .env ถ้ายังไม่มี
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[i] สร้าง .env จาก .env.example แล้ว — อย่าลืมใส่ OPENAI_API_KEY ก่อนรัน lab1/3/4/5"
fi

case "${1:-lab2}" in
  down)  docker compose down; exit 0 ;;
  reset) docker compose down -v; echo "[i] ลบ volume แล้ว รอบหน้าจะ seed ใหม่"; exit 0 ;;
esac

# เปิด postgres + agent (รอ DB healthy อัตโนมัติผ่าน depends_on)
echo "[1/2] เปิด stack และ seed ฐานข้อมูล..."
docker compose up -d --build

TARGET="${1:-lab2}"
case "$TARGET" in
  lab1) CMD="python lab1_llm.py" ;;
  lab2) CMD="python db_tools.py" ;;
  lab3) CMD="python lab3_agent.py" ;;
  lab4) CMD="python lab4_agent.py" ;;
  lab5) CMD="python lab5_audit.py" ;;
  *)    CMD="python db_tools.py" ;;
esac

echo "[2/2] รัน $TARGET → $CMD"
docker compose exec agent $CMD
