# eMRO Inventory Monitor & Dashboard Sync 🚀

ระบบดึงและ Monitor ข้อมูล **Inventory Transaction History** จาก eMRO (Location: **DM01**) แบบอัตโนมัติทุก 1 นาที ด้วย **Playwright Browser Automation** และ Sync ข้อมูลไปยัง **Google Sheets Dashboard** แบบ Real-time

> 📖 **หมายเหตุการพัฒนา กฎระบบ และประวัติการแก้ไข:** ดูรายละเอียดได้ที่ [PROJECT_NOTES.md](file:///D:/Project%20dashboard/PROJECT_NOTES.md)

---

## 🌟 ฟีเจอร์หลัก (Features)

1. **รองรับ Authenticator (2FA):** 
   - รันครั้งแรกด้วย `HEADLESS=false` หน้าต่างเบราว์เซอร์จะเปิดขึ้นมาให้คุณ Login และกรอก Authenticator (OTP) ด้วยตัวเอง
   - ระบบจะบันทึก Session Cookie ไว้ในโฟลเดอร์ `data/browser_session` อัตโนมัติ
   - ครั้งถัดไปสามารถรันเงียบๆ ในโหมด `HEADLESS=true` ได้เลยโดยไม่ต้อง Login ซ้ำ
2. **Keep-Alive ป้องกัน Session Expired:**
   - Polling ทุก 60 วินาที ช่วยรีเฟรช session ของ eMRO ตลอดเวลา ไม่โดนตัด Session Timeout (5-10 นาที)
3. **ดึงข้อมูลครบ 27 ฟิลด์สำคัญ:**
   - Transaction Type (ISSUED, INITIAL/RECEIVING, PO/RECEIVING, BIN/TRANSFER, RTS/WO)
   - P/N, S/N, Batch, GRB, Vendor Lot
   - Location (DM01), Bin, Condition, QTY
   - Unit Cost, Secondary Cost, CUR EXC Rate
   - A/C, W/O - S/O, Issued To, Issued To Name
   - Order Type, Order NO, Line, Vendor/Customer, Vendor Name, Reference
   - Transaction NO, Status, Created By, Created Date, Name, G/L, Defect Description
4. **Change Detection:**
   - ตรวจจับ Transaction ใหม่และแจ้งเตือนทันที
   - บันทึกประวัติลงแผ่นงาน "Activity Log" ใน Google Sheets
5. **Google Sheets Sync:**
   - อัปเดตข้อมูลลงชีต `Live Transactions`
   - สามารถเปิดดูและมอนิเตอร์ได้จากทั้งคอมพิวเตอร์และแอปมือถือ ฟรี 100%

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
D:\Project dashboard\
├── .env                          # ไฟล์ตั้งค่าระบบและ Credentials
├── .env.example                  # ตัวอย่างไฟล์ตั้งค่า
├── requirements.txt              # รายการ Python dependencies
├── main.py                       # สคริปต์หลักสำหรับเริ่มทำงาน
├── credentials.json              # Service Account Key สำหรับ Google Sheets (ถ้ามี)
├── README.md                     # เอกสารแนะนำการใช้งาน
│
├── scraper/
│   ├── __init__.py
│   ├── config.py                 # โหลดการตั้งค่าจาก .env
│   ├── emro_scraper.py           # ตัวควบคุม Playwright และดึงข้อมูล eMRO
│   ├── parser.py                 # ตัวแปลงข้อมูลตาราง HTML ของ PrimeFaces
│   └── change_detector.py        # ตรวจจับ Transaction ใหม่และที่เปลี่ยนแปลง
│
├── sheets/
│   ├── __init__.py
│   └── google_sheets.py          # ตัวเชื่อมต่อและอัปเดต Google Sheets
│
├── data/
│   ├── browser_session/          # โฟลเดอร์เก็บ Session / Cookies หลังจาก Login
│   ├── screenshots/              # รูปภาพจับหน้าจอเมื่อเกิดข้อผิดพลาด
│   └── cache.json                # ข้อมูล Transaction ล่าสุดที่แคชไว้
│
└── scripts/
    ├── install.ps1               # สคริปต์ติดตั้งสำหรับ PowerShell
    └── run.ps1                   # สคริปต์เริ่มต้นรันระบบ
```

---

## 🛠️ ขั้นตอนการติดตั้งและการใช้งาน (Quick Start)

### ขั้นตอนที่ 1: ตรวจสอบการตั้งค่าใน `.env`
เปิดไฟล์ `D:\Project dashboard\.env` และตั้งค่าดังนี้:
```env
EMRO_URL=https://emro.lionair.com/emro/Home.trax
MONITOR_LOCATION=DM01
POLL_INTERVAL_SECONDS=60

# สำหรับการรันครั้งแรก ให้เป็น false เพื่อเปิดหน้าต่างเบราว์เซอร์ให้กรอก Authenticator (2FA)
HEADLESS=false

# Google Sheets (ถ้ามี)
GOOGLE_SHEET_ID=
GOOGLE_CREDENTIALS_FILE=credentials.json
```

### ขั้นตอนที่ 2: เริ่มต้นการทำงานครั้งแรก
เปิด PowerShell ในโฟลเดอร์นี้ แล้วรัน:
```powershell
.\scripts\run.ps1
# หรือ
python main.py
```

1. หน้าต่างเบราว์เซอร์ Chromium จะเปิดขึ้นมาอัตโนมัติ
2. กรุณาทำการ **Login eMRO และยืนยัน Authenticator (2FA)** ให้เรียบร้อย
3. เมื่อเข้าสู่ระบบเสร็จสิ้น ระบบจะตรวจจับและแจ้งว่า:
   `[eMROScraper] Successfully authenticated and logged in! Session cookies saved.`
4. ระบบจะเริ่มดึงข้อมูล Transaction ของ Location `DM01` ทุกๆ 60 วินาที

### ขั้นตอนที่ 3: เปิดโหมดรันแบบเงียบ (Headless)
หลังจากที่ Login ผ่านแล้วในครั้งแรก และมี Session ถูกบันทึกไว้ใน `data/browser_session` แล้ว:
1. เปิดไฟล์ `.env`
2. เปลี่ยนเป็น:
   ```env
   HEADLESS=true
   ```
3. รัน `python main.py` ได้เลย คราวนี้ระบบจะทำงานอยู่เบื้องหลังโดยไม่ต้องมีหน้าต่างเด้งขึ้นมากวนใจ!

---

## 📊 การเชื่อมต่อ Google Sheets (ไม่บังคับ แต่แนะนำ)

1. สร้าง Google Sheet ใหม่ แล้วคัดลอก Spreadsheet ID จาก URL:
   `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`
2. สร้าง Google Cloud Service Account และดาวน์โหลดคีย์ JSON มาวางที่ `D:\Project dashboard\credentials.json`
3. กดแชร์ (Share) Google Sheet นั้นให้กับ Email ของ Service Account (ให้สิทธิ์ Editor)
4. ใส่ `GOOGLE_SHEET_ID` ลงใน `.env`
