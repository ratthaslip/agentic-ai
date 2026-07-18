#!/usr/bin/env bash
# ============================================================
# install_ubuntu.sh — ติดตั้ง Docker Engine + Compose plugin บน Ubuntu 24.04
# แล้วเตรียมสภาพแวดล้อมให้พร้อมรัน CGD Reconciliation Agent
#
# ใช้:
#   chmod +x install_ubuntu.sh
#   ./install_ubuntu.sh
#
# หลังรันเสร็จ ให้ logout/login ใหม่ 1 ครั้ง (ให้ group docker มีผล) แล้ว:
#   ./run.sh          # หรือ  docker compose up -d --build
# ============================================================
set -euo pipefail

echo "==> [1/6] ตรวจเวอร์ชัน Ubuntu"
. /etc/os-release
echo "    ตรวจพบ: $PRETTY_NAME"
if [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "    (คำเตือน) สคริปต์นี้ทดสอบกับ Ubuntu 24.04 — เวอร์ชันอื่นอาจต้องปรับ"
fi

echo "==> [2/6] ถอน Docker เวอร์ชันเก่า (ถ้ามี) และติดตั้ง prerequisite"
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" 2>/dev/null || true
done
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

echo "==> [3/6] เพิ่ม Docker official GPG key + apt repository"
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "==> [4/6] ติดตั้ง Docker Engine + Compose plugin"
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> [5/6] เพิ่มผู้ใช้ปัจจุบันเข้า group docker (รันได้โดยไม่ต้อง sudo)"
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker "$USER"

echo "==> [6/6] เตรียมไฟล์ .env และตั้ง AIRFLOW_UID ให้ตรงกับผู้ใช้"
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  cp .env.example .env
fi
# ตั้ง AIRFLOW_UID = id -u ปัจจุบัน (แก้บรรทัดเดิมถ้ามี ไม่งั้น append)
if grep -q '^AIRFLOW_UID=' .env; then
  sed -i "s/^AIRFLOW_UID=.*/AIRFLOW_UID=$(id -u)/" .env
else
  echo "AIRFLOW_UID=$(id -u)" >> .env
fi

# generate Fernet key สำหรับ production (docker-compose.prod.yml) ถ้ายังว่าง
if grep -q '^AIRFLOW_FERNET_KEY=$' .env; then
  FKEY=""
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import cryptography' 2>/dev/null; then
    FKEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
  else
    # fallback: openssl (Fernet key = base64-urlsafe ของ 32 byte)
    FKEY=$(openssl rand -base64 32 | tr '+/' '-_')
  fi
  sed -i "s|^AIRFLOW_FERNET_KEY=$|AIRFLOW_FERNET_KEY=$FKEY|" .env
  echo "    สร้าง AIRFLOW_FERNET_KEY ให้แล้ว"
fi

echo ""
echo "============================================================"
echo " ติดตั้งเสร็จแล้ว"
echo " Docker : $(docker --version 2>/dev/null || echo 'ต้อง logout/login ก่อน')"
echo ""
echo " ขั้นต่อไป:"
echo "   1) LOGOUT แล้ว LOGIN ใหม่ 1 ครั้ง (ให้สิทธิ์ group docker มีผล)"
echo "      หรือรันชั่วคราว:  newgrp docker"
echo "   2) แก้ไฟล์ .env ใส่ OPENAI_API_KEY (จำเป็นเฉพาะ Lab 1/3/4/5)"
echo "   3) เปิด stack ทั้งหมด:   docker compose up -d --build"
echo "      - Postgres + auto seed"
echo "      - Agent (รัน Lab ผ่าน:  docker compose exec agent python lab4_agent.py)"
echo "      - Airflow UI:  http://localhost:8080"
echo "============================================================"
