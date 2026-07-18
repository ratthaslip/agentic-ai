# CGD Reconciliation & Audit Agent

Source code จากคู่มือปฏิบัติการ (Hands-on Lab Workbook) — **Agentic AI สำหรับงานกระทบยอดและตรวจสอบการเบิกจ่าย** กรมบัญชีกลาง (Module 5)

> ⚠️ **ข้อมูลทั้งหมดเป็นข้อมูลจำลอง (synthetic)** เพื่อการฝึกอบรม ไม่ใช่ข้อมูลจริงของกรมบัญชีกลาง ผู้ค้า หรือบุคคลใด เมื่อนำไปใช้กับข้อมูลจริง ต้อง mask ข้อมูลส่วนบุคคลก่อนส่งออก external LLM และพิจารณาใช้ local/sovereign model ตามนโยบายกรมบัญชีกลาง (PDPA / data residency)

## Tech stack
Python 3.11+ · LangGraph / LangChain · PostgreSQL 16 (Docker) · OpenAI / Azure OpenAI

## โครงสร้างไฟล์

| ไฟล์ | Lab | หน้าที่ |
|---|---|---|
| `seed.sql` | 0 | schema 3 ตาราง (budget / contract / disbursement) + ข้อมูลจำลอง + role read-only |
| `lab1_llm.py` | 1 | เชื่อม LLM (OpenAI/Azure) + ทดสอบภาษาไทย |
| `db_tools.py` | 2 + 4 | SQL tool read-only + allow-list, `reconcile_contract`, `detect_anomalies` |
| `lab3_agent.py` | 3 | ReAct agent (LLM + SQL tool) |
| `lab4_agent.py` | 4 | agent + tool กระทบยอด/ตรวจ anomaly + memory (MemorySaver) |
| `lab5_audit.py` | 5 | guardrails (step limit, output validation, audit log) + HITL + รายงานภาษาไทย |
| `dags/cgd_recon_dag.py` | Bonus | โครง Airflow DAG รันตรวจ anomaly ประจำวัน |
| `docker-compose.yml` | — | รัน postgres + auto-seed + agent + airflow ครบชุดในคำสั่งเดียว |
| `Dockerfile` | — | image ของ agent runner (Python 3.11 + dependency + UTF-8) |
| `run.sh` | — | helper script เปิด stack + รันแต่ละ Lab |
| `install_ubuntu.sh` | — | ติดตั้ง Docker + Compose บน Ubuntu 24.04 อัตโนมัติ |
| `docker-compose.prod.yml` | — | **Production**: LocalExecutor + Postgres metadata แยก + pre-built image |
| `Dockerfile.airflow` | — | pre-built Airflow image (ฝัง dependency + โค้ด lab ใน image) |

## แนะนำโมเดล LLM (OpenAI)

งานนี้เป็น ReAct agent + SQL tool calling + อ่าน/สรุปภาษาไทย — ตัวชี้วัดหลักคือ **ความแม่นของ tool calling** ไม่ใช่ context ยาว ตั้งค่าผ่าน `OPENAI_MODEL` ใน `.env` (ไม่ต้องแก้โค้ด)

| ระดับใช้งาน | โมเดล | ราคา in/out (ต่อ 1M) | เหตุผล |
|---|---|---|---|
| **แนะนำหลัก (production)** | **`gpt-5.4-mini`** *(default)* | $0.75 / $4.50 | OpenAI จัด positioning ตรงงาน: code generation, **tool invocation**, high-concurrency — tool-calling แม่นกว่า 4o-mini มาก |
| **คุณภาพสูงสุด (audit สำคัญ)** | **`gpt-5.4`** | $2.50 / $15.00 | reasoning ตัวเลขงบเป๊ะกว่า — ครึ่งราคา flagship gpt-5.5 |
| **ประหยัด/dev/ห้องอบรม** | **`gpt-5-mini`** | $0.25 / $2.00 | ถูกกว่า 4o-mini ด้าน output, tool calling ดีกว่า — เหมาะรัน DAG ทุกวัน |

หลีกเลี่ยง: `gpt-4o-mini` (default เดิม) ถูกจัดเป็น legacy แล้ว tool-calling ด้อยกว่า gpt-5 มาก · o-series (o3/o4-mini) คิดเงิน thinking token ที่ output rate ทำให้ต้นทุนจริงบานปลาย เกินจำเป็น

เปลี่ยนโมเดล — แก้แค่ `.env` ไม่ต้องแก้โค้ด:

```bash
OPENAI_MODEL=gpt-5.4        # เช่น เปลี่ยนเป็นตัวคุณภาพสูง
```

### Azure OpenAI (แนะนำสำหรับข้อมูลราชการจริง — data residency / PDPA)

OpenAI API โดยตรงส่งข้อมูลออกนอกประเทศ และยังไม่มี region ในไทย — เมื่อขึ้นข้อมูลงบประมาณจริง ควรใช้ **Azure OpenAI** เพื่อคุม tenancy/สัญญา/region — โค้ด `build_llm()` รองรับอยู่แล้ว (ถ้าตั้ง `AZURE_OPENAI_ENDPOINT` จะสลับไปใช้ Azure อัตโนมัติ)

เปิดคอมเมนต์ใน `.env` แล้วตั้งค่า (แทนกลุ่ม OpenAI):

```bash
AZURE_OPENAI_API_KEY=xxxxxxxx
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.4-mini      # ชื่อ deployment ที่สร้างใน Azure portal (ไม่ใช่ชื่อโมเดล)
OPENAI_API_VERSION=2024-10-21             # ตรวจ version ล่าสุดที่ Azure รองรับ
```

> เมื่อรันผ่าน docker compose ส่งค่าเหล่านี้ผ่าน `.env` (env_file) ได้เลย — ไม่ต้องแก้ compose

อ้างอิงราคา/positioning: [OpenAI model selection guide 2026](https://api.treerouter.ai/en/blog/openai-gpt-models-2026-selection-guide) · [BenchLM pricing](https://benchlm.ai/openai/api-pricing) · [G2 OpenAI API pricing](https://www.g2.com/articles/openai-api-pricing)

## ติดตั้งบน Ubuntu 24.04

**ความต้องการขั้นต่ำ:** RAM ≥ 4GB (แนะนำ 8GB เพราะ Airflow) · ดิสก์ว่าง ≥ 5GB · Docker Compose v2.14+

### วิธีที่ง่ายที่สุด: สคริปต์อัตโนมัติ

```bash
cd cgd-recon-agent
chmod +x install_ubuntu.sh run.sh
./install_ubuntu.sh          # ติดตั้ง Docker Engine + Compose plugin + ตั้ง AIRFLOW_UID ให้
# --- LOGOUT แล้ว LOGIN ใหม่ 1 ครั้ง (ให้สิทธิ์ group docker มีผล) ---
nano .env                    # ใส่ OPENAI_API_KEY
docker compose up -d --build # เปิด stack ทั้งหมด
```

> `install_ubuntu.sh` ทำตาม[คู่มือ Docker ทางการ](https://docs.docker.com/engine/install/ubuntu/): ถอน package เก่า · เพิ่ม GPG key + apt repo ทางการ · ติดตั้ง docker-ce + compose plugin · เพิ่ม user เข้า group `docker`

### หรือติดตั้ง Docker เองทีละขั้น (สรุปจากคู่มือ Docker)

```bash
# 1) เพิ่ม repo ทางการของ Docker
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 2) ติดตั้ง
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 3) รันได้โดยไม่ต้อง sudo
sudo usermod -aG docker $USER && newgrp docker

# 4) เตรียม project
cp .env.example .env
sed -i "s/^AIRFLOW_UID=.*/AIRFLOW_UID=$(id -u)/" .env   # ให้ Airflow เขียนไฟล์ permission ตรง host
nano .env                                              # ใส่ OPENAI_API_KEY
docker compose up -d --build
```

> **หมายเหตุเรื่อง permission (Linux):** container Airflow รันด้วย UID `AIRFLOW_UID` (ตั้งจาก `id -u`) เพื่อให้ไฟล์ที่เขียน (logs, `audit_trail.log`) มี owner ตรงกับผู้ใช้ host — `install_ubuntu.sh` ตั้งค่านี้ให้อัตโนมัติ

### ตรวจหลังติดตั้ง

```bash
docker --version && docker compose version    # ควรเห็น v2.14+
docker ps                                     # ควรเห็น cgd-postgres, cgd-agent, cgd-airflow
docker compose exec agent python db_tools.py  # Lab 2 (ไม่ต้องใช้ API key)
```

---

## วิธีที่ A — รันครบชุดด้วย Docker Compose (แนะนำ)

รัน PostgreSQL + auto-seed + agent ในคำสั่งเดียว — `seed.sql` ถูกรันอัตโนมัติตอนสร้าง DB ครั้งแรก (initdb) และ agent จะรอ DB พร้อมอัตโนมัติผ่าน healthcheck

```bash
# 1) เตรียม .env (ใส่ OPENAI_API_KEY จริงก่อนรัน Lab 1/3/4/5)
cp .env.example .env      # แก้ไฟล์ .env ใส่ OPENAI_API_KEY

# 2) เปิด stack ทั้งหมด + seed อัตโนมัติ (คำสั่งเดียว)
docker compose up -d --build

# 3) รันแต่ละ Lab (agent container มี dependency ครบแล้ว)
docker compose exec agent python lab1_llm.py     # Lab 1
docker compose exec agent python db_tools.py     # Lab 2 (ไม่ต้องใช้ API key)
docker compose exec agent python lab3_agent.py   # Lab 3
docker compose exec agent python lab4_agent.py   # Lab 4
docker compose exec -it agent python lab5_audit.py  # Lab 5 (มี HITL input y/n)

# 4) หยุด / ล้าง
 docker compose down       # หยุด (เก็บข้อมูลใน volume)
 docker compose down -v    # ลบข้อมูลด้วย (seed ใหม่รอบหน้า)
```

หรือใช้ helper script `run.sh` ให้สั้นกว่า:

```bash
./run.sh          # เปิด stack + seed + รัน Lab 2 (ไม่ต้องใช้ API key)
./run.sh lab4     # รัน Lab 4
./run.sh reset    # ล้างทุกอย่างรวม volume
```

> ภายใน compose network agent เชื่อม DB ที่ host = `postgres` (ชื่อ service) — DSN ถูก override ให้ใน `docker-compose.yml` แล้ว ไม่ต้องแก้ .env

### รัน DAG ด้วย Airflow (Bonus)

service `airflow` เปิดมาพร้อมกับ `docker compose up` แล้ว (โหมด standalone: webserver + scheduler + สร้าง admin user อัตโนมัติ)

```bash
docker compose up -d --build              # เปิด postgres + agent + airflow

# ดู log รอ Airflow พร้อม (ครั้งแรกใช้เวลาติดตั้ง dependency สักครู่)
docker compose logs -f airflow
```

เปิด UI ที่ http://localhost:8080
- รหัสผ่าน: username `admin`, password ดูจาก log (บรรทัด `Password for user 'admin': ...`) หรือดึงจากไฟล์ใน container: `docker compose exec airflow cat /opt/airflow/standalone_admin_password.txt`
- จะเห็น DAG ชื่อ `cgd_reconciliation` (schedule 07:00 ทุกวัน) — กด **Trigger** เพื่อรันทันที

หรือรัน DAG จาก command line โดยไม่ต้องเปิด UI:

```bash
docker compose exec airflow airflow dags test cgd_reconciliation 2026-07-18
```

> DAG import `db_tools` / `lab5_audit` จากโค้ด project ที่ mount ไว้ที่ `/opt/project` (ตั้ง `PYTHONPATH`) และติดตั้ง langgraph/langchain ผ่าน `_PIP_ADDITIONAL_REQUIREMENTS` — ครั้งแรกอาจใช้เวลา build สักครู่

#### Pipeline ของ DAG: `detect_anomalies` → `send_report`

DAG มี 2 task ต่อเนื่องกัน:

1. **`detect_anomalies`** — ตรวจ anomaly (read-only) + validate output + สร้างรายงานภาษาไทย → ส่งต่อผ่าน XCom
2. **`send_report`** — รับรายงานจาก XCom แล้วส่งตามช่องทางที่ตั้งใน `REPORT_CHANNEL`

เลือกช่องทางส่งรายงานผ่าน env `REPORT_CHANNEL` ใน `.env`:

| ค่า | พฤติกรรม | env ที่ต้องตั้งเพิ่ม |
|---|---|---|
| `dry_run` (ค่าเริ่มต้น) | แสดงรายงานใน log เฉย ๆ (ไม่ส่งจริง) | — เหมาะกับห้องอบรม |
| `email` | ส่ง email ผ่าน SMTP (รองรับ STARTTLS) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `REPORT_EMAIL_FROM`, `REPORT_EMAIL_TO` |
| `ticket` | POST JSON เข้า webhook (Jira/ServiceNow/Teams/Line) | `TICKET_WEBHOOK_URL`, `TICKET_AUTH_HEADER` (optional) |

พฤติกรรมสำคัญ: ถ้าไม่พบ anomaly → ข้ามการส่ง · ถ้าส่งไม่สำเร็จ → บันทึก `send_report_failed` และ mark task failed · ทุกการส่งถูกบันทึกใน `audit_trail.log`

> ค่าลับ (SMTP password / ticket token) มาจาก env ทั้งหมด — ไม่ hardcode ใน DAG

---

## Production setup (LocalExecutor + Postgres metadata แยก + pre-built image)

`docker-compose.yml` (ข้างบน) ใช้โหมด **standalone** — เหมาะ dev/ห้องอบรม (SQLite metadata, SequentialExecutor, ติดตั้ง dependency ตอน start)

สำหรับใช้งานจริงให้ใช้ **`docker-compose.prod.yml`** ซึ่งต่างกันดังนี้:

| หัวข้อ | standalone (dev) | prod |
|---|---|---|
| Executor | SequentialExecutor | **LocalExecutor** (รัน task ขนานได้) |
| Metadata DB | SQLite ใน container | **Postgres แยก** (`airflow-db`) |
| Dependency | ติดตั้งตอน start (ช้า) | **pre-built ใน image** (`Dockerfile.airflow`) |
| โค้ด lab | bind-mount | **ฝังใน image** (ไม่พึ่ง host path) |
| Service | `airflow` ตัวเดียว | **`airflow-init` / `airflow-webserver` / `airflow-scheduler`** |
| Secrets | — | **Fernet key** เข้ารหัส connection/variable |
| restart | — | `unless-stopped` ทุก service |

### ขั้นตอนรัน (prod)

```bash
cp .env.example .env
sed -i "s/^AIRFLOW_UID=.*/AIRFLOW_UID=$(id -u)/" .env

# 1) generate Fernet key (หรือใช้ install_ubuntu.sh ที่ generate ให้อัตโนมัติ)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# นำค่าที่ได้ไปใส่ AIRFLOW_FERNET_KEY ใน .env

# 2) ตั้งรหัส admin ใน .env: AIRFLOW_ADMIN_PASSWORD, AIRFLOW_DB_PASSWORD, OPENAI_API_KEY

# 3) build + เปิด stack ทั้งหมด (airflow-init จะ migrate DB + สร้าง admin ให้ก่อน)
docker compose -f docker-compose.prod.yml up -d --build
```

UI: http://localhost:8080 (login ด้วย `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` ที่ตั้งใน .env)

คำสั่งจัดการ prod:

```bash
docker compose -f docker-compose.prod.yml ps         # สถานะทุก service
docker compose -f docker-compose.prod.yml logs -f airflow-scheduler
docker compose -f docker-compose.prod.yml down       # หยุด (เก็บ volume)
```

> หมายเหตุ: เมื่อแก้โค้ด lab ใน prod ต้อง `docker compose -f docker-compose.prod.yml up -d --build` ใหม่ (โค้ดถูกฝังใน image ไม่ใช่ bind-mount) — ส่วน DAG ใน `dags/` ยัง mount อยู่ แก้แล้ว scheduler เห็นเอง

## วิธีที่ B — รันบนเครื่องโดยตรง (ตามคู่มือ Lab 0 เดิม)

```bash
# 1) สร้าง virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1

# 2) ติดตั้ง dependency
pip install --upgrade pip
pip install -r requirements.txt

# 3) รัน PostgreSQL ผ่าน Docker
docker run --name cgd-postgres \
  -e POSTGRES_USER=cgd_admin \
  -e POSTGRES_PASSWORD=cgd_pass_2026 \
  -e POSTGRES_DB=cgd_fiscal \
  -p 5432:5432 -d postgres:16

# 4) สร้างไฟล์ .env จากตัวอย่าง แล้วใส่ค่าจริง (OPENAI_API_KEY ฯลฯ)
cp .env.example .env

# 5) seed ฐานข้อมูล
docker exec -i cgd-postgres psql -U cgd_admin -d cgd_fiscal < seed.sql

# 6) รันแต่ละ Lab
python lab1_llm.py     # Lab 1 : LLM ตอบภาษาไทย
python db_tools.py     # Lab 2 : SQL tool + ทดสอบ guardrail (DELETE ถูกปฏิเสธ)
python lab3_agent.py   # Lab 3 : ReAct agent ตอบยอดเบิกจ่าย
python lab4_agent.py   # Lab 4 : กระทบยอด + ตรวจ anomaly + memory
python lab5_audit.py   # Lab 5 : guardrails + HITL + ออกรายงานภาษาไทย
```

## ข้อมูลจำลอง — จุดที่ตั้งใจให้เป็น anomaly

| รายการ | ประเภท | รายละเอียด |
|---|---|---|
| สัญญา `67A00012346` | `over_contract` | วงเงิน 4,500,000 แต่เบิกรวม 5,200,000 → เกิน 700,000 |
| งบ `BG-2567-003` | `over_budget` | วงเงินงบ 15,000,000 แต่เบิกรวม 15,700,000 (67A00033500 = 13,800,000 + 67A00033501 = 1,900,000) → เกิน 700,000 |

> หมายเหตุ: คู่มือต้นฉบับระบุว่า over_budget "จะทดสอบใน Lab 4" โดยยอดเดิม 13,800,000 ยังไม่เกิน — source code ชุดนี้จึงเพิ่มสัญญา `67A00033501` (1,900,000) ในงบเดียวกันเพื่อให้ `detect_anomalies` ตรวจเจอ over_budget ได้จริง

## Guardrails ที่ใส่ (Lab 5)

| Guardrail | ป้องกัน | วิธีในโค้ด |
|---|---|---|
| Read-only role + allow-list | การเขียน/ลบข้อมูล, SQL injection | `cgd_readonly` + `_validate_sql` |
| Step / recursion limit | loop ไม่จบ, cost overrun | `recursion_limit=15` |
| Output validation | ผลลัพธ์ผิดรูป/หลอน | `validate_anomalies()` |
| Human-in-the-loop | action ที่ย้อนกลับไม่ได้ | `human_approve()` ก่อนออกรายงาน |
| Audit log | ตรวจสอบย้อนหลังไม่ได้ | `audit_log()` ทุก action |

## แหล่งเรียนรู้ต่อ
- [LangGraph](https://langchain-ai.github.io/langgraph/) · [create_react_agent](https://langchain-ai.github.io/langgraph/reference/prebuilt/) · [Human-in-the-loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [LangChain Tools](https://python.langchain.com/docs/concepts/tools/) · [Persistence / Checkpointers](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [New GFMIS Thai](https://newgfmisthai.gfmis.go.th/) · [PostgreSQL docs](https://www.postgresql.org/docs/) · [Apache Airflow docs](https://airflow.apache.org/docs/)
