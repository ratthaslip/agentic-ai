-- ============================================================
-- seed.sql : schema + sample data (CGD Reconciliation Lab)
-- ข้อมูลจำลองทั้งหมด ไม่ใช่ข้อมูลจริงของกรมบัญชีกลาง ผู้ค้า หรือบุคคลใด
-- ============================================================
DROP TABLE IF EXISTS disbursement;
DROP TABLE IF EXISTS contract;
DROP TABLE IF EXISTS budget;

-- 1) ตารางงบประมาณ (จำลองรหัสงบประมาณ GFMIS)
CREATE TABLE budget (
    budget_code  VARCHAR(20)  PRIMARY KEY,   -- รหัสงบประมาณ
    budget_name  VARCHAR(200) NOT NULL,      -- ชื่อรายการงบ
    fiscal_year  INT          NOT NULL,      -- ปีงบประมาณ (พ.ศ.)
    total_amount NUMERIC(15,2) NOT NULL      -- วงเงินงบที่ได้รับจัดสรร
);

-- 2) ตารางสัญญา (จำลองสัญญา e-GP)
CREATE TABLE contract (
    contract_no     VARCHAR(20)  PRIMARY KEY,          -- เลขที่สัญญา e-GP
    vendor_name     VARCHAR(200) NOT NULL,             -- ชื่อผู้ค้า/คู่สัญญา
    vendor_tax_id   VARCHAR(13),                       -- เลขประจำตัวผู้เสียภาษี
    budget_code     VARCHAR(20)  REFERENCES budget(budget_code),
    contract_amount NUMERIC(15,2) NOT NULL,            -- วงเงินตามสัญญา
    sign_date       DATE         NOT NULL,             -- วันลงนาม
    status          VARCHAR(20)  DEFAULT 'active'
);

-- 3) ตารางการเบิกจ่าย (จำลองการเบิกจ่าย/ฎีกา GFMIS)
CREATE TABLE disbursement (
    disb_id     SERIAL       PRIMARY KEY,
    contract_no VARCHAR(20)  REFERENCES contract(contract_no),
    pay_date    DATE         NOT NULL,   -- วันที่เบิกจ่าย
    installment INT,                     -- งวดที่
    amount      NUMERIC(15,2) NOT NULL,  -- ยอดเบิกจ่ายงวดนั้น
    voucher_no  VARCHAR(30)              -- เลขที่ฎีกา/voucher
);

-- ---------- ข้อมูลงบประมาณ ----------
INSERT INTO budget (budget_code, budget_name, fiscal_year, total_amount) VALUES
('BG-2567-001', 'งบลงทุน ครุภัณฑ์คอมพิวเตอร์',      2567, 12000000.00),
('BG-2567-002', 'งบดำเนินงาน จ้างเหมาบริการ',       2567,  8000000.00),
('BG-2567-003', 'งบลงทุน ปรับปรุงอาคารสำนักงาน',   2567, 15000000.00);

-- ---------- ข้อมูลสัญญา (e-GP) ----------
INSERT INTO contract (contract_no, vendor_name, vendor_tax_id, budget_code, contract_amount, sign_date, status) VALUES
('67A00012345', 'บริษัท ไทยรุ่งเรืองเทคโนโลยี จำกัด', '0105551000011', 'BG-2567-001', 5000000.00, '2024-01-15', 'active'),
('67A00012346', 'บริษัท สยามซอฟต์แวร์ จำกัด',        '0105552000022', 'BG-2567-001', 4500000.00, '2024-02-01', 'active'),
('67A00022100', 'หจก. รุ่งเรืองบริการ',              '0105553000033', 'BG-2567-002', 3000000.00, '2024-01-20', 'active'),
('67A00022101', 'บริษัท เอราวัณ คลีนนิ่ง จำกัด',      '0105554000044', 'BG-2567-002', 2500000.00, '2024-03-10', 'active'),
('67A00033500', 'บริษัท มั่นคงก่อสร้าง จำกัด',        '0105555000055', 'BG-2567-003', 14000000.00, '2024-02-28', 'active'),
-- สัญญาเพิ่มในงบ BG-2567-003 เพื่อให้ยอดรวมในงบเกินวงเงินงบ (ทดสอบ over_budget ใน Lab 4)
('67A00033501', 'บริษัท เจริญวัสดุก่อสร้าง จำกัด',    '0105556000066', 'BG-2567-003', 2000000.00, '2024-03-05', 'active');

-- ---------- ข้อมูลการเบิกจ่าย (GFMIS) ----------
-- สัญญา 67A00012345 : เบิกจ่ายปกติภายในวงเงิน (3,500,000 < 5,000,000)
INSERT INTO disbursement (contract_no, pay_date, installment, amount, voucher_no) VALUES
('67A00012345', '2024-03-01', 1, 1500000.00, 'V67-0001'),
('67A00012345', '2024-05-01', 2, 2000000.00, 'V67-0002');

-- *** ANOMALY 1: เบิกเกินวงเงินสัญญา (over_contract) ***
-- สัญญา 67A00012346 วงเงิน 4,500,000 แต่เบิกรวม 5,200,000
INSERT INTO disbursement (contract_no, pay_date, installment, amount, voucher_no) VALUES
('67A00012346', '2024-04-01', 1, 2500000.00, 'V67-0010'),
('67A00012346', '2024-06-01', 2, 2700000.00, 'V67-0011');

-- สัญญา 67A00022100 : เบิกจ่ายปกติ (2,000,000 < 3,000,000)
INSERT INTO disbursement (contract_no, pay_date, installment, amount, voucher_no) VALUES
('67A00022100', '2024-03-15', 1, 1000000.00, 'V67-0020'),
('67A00022100', '2024-05-15', 2, 1000000.00, 'V67-0021');

-- สัญญา 67A00022101 : เบิกจ่ายปกติ (2,500,000 = วงเงินพอดี)
INSERT INTO disbursement (contract_no, pay_date, installment, amount, voucher_no) VALUES
('67A00022101', '2024-04-20', 1, 2500000.00, 'V67-0030');

-- *** ANOMALY 2: รวมการเบิกจ่ายในงบ BG-2567-003 เกินวงเงินงบ (over_budget) ***
-- งบ 15,000,000 ; สัญญา 67A00033500 เบิกรวม 13,800,000 (ยังไม่เกินสัญญา 14,000,000)
INSERT INTO disbursement (contract_no, pay_date, installment, amount, voucher_no) VALUES
('67A00033500', '2024-04-05', 1, 7000000.00, 'V67-0040'),
('67A00033500', '2024-06-05', 2, 6800000.00, 'V67-0041');

-- สัญญา 67A00033501 (งบเดียวกัน BG-2567-003) เบิก 1,900,000
-- ยอดเบิกรวมในงบ = 13,800,000 + 1,900,000 = 15,700,000 > 15,000,000 → over_budget
INSERT INTO disbursement (contract_no, pay_date, installment, amount, voucher_no) VALUES
('67A00033501', '2024-05-10', 1, 1900000.00, 'V67-0050');

-- ---------- สร้าง role read-only สำหรับ agent ----------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cgd_readonly') THEN
        CREATE ROLE cgd_readonly LOGIN PASSWORD 'readonly_pass_2026';
    END IF;
END$$;

GRANT CONNECT ON DATABASE cgd_fiscal TO cgd_readonly;
GRANT USAGE ON SCHEMA public TO cgd_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO cgd_readonly;
-- least privilege: ไม่ให้ INSERT/UPDATE/DELETE
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO cgd_readonly;
