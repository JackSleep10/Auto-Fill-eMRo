# GSE Work Order Automation — Project Notes & Incident Log
> **บันทึกประวัติการทำงาน ข้อผิดพลาด แนวทางแก้ไข และกฎระเบียบของระบบ**  
> *เอกสารนี้ต้องได้รับการอัปเดตทุกครั้งที่มีการแก้ไข ปรับปรุงฟีเจอร์ หรือตรวจพบข้อผิดพลาดตามคำสั่งของผู้ใช้งาน*

---

## 📌 1. กฎเหล็กและข้อกำหนดสำคัญของระบบ (System Rules & Policies)

1. **การรักษาความถูกต้องของชื่อผู้เปิดใบงาน (Identity & Accountability Rule)**
   - ระบบ eMRO ของสายการบินจะบันทึกว่า **ใคร (User ใด) เป็นผู้เปิดใบงาน**
   - **ข้อห้าม:** ห้ามใช้บัญชีอื่นเปิดแทนเด็ดขาด หาก User ที่ล็อกอินหน้าเว็บยังไม่ได้ลงทะเบียนบัญชี eMRO (ไม่มี Password / 2FA TOTP Secret)
   - **พฤติกรรมระบบ:** หาก User ที่ยังไม่ผูก eMRO พยายามกดเปิดใบงานเดี่ยว หรือเริ่มงานชุด ระบบจะ **บล็อกทันที (HTTP 403)** พร้อมแจ้งเตือนให้ติดต่อผู้ดูแลระบบ

2. **การจัดการหน้าต่างแจ้งเตือนและป๊อปอัปบน eMRO (Popup Handling Rule)**
   - **ลำดับที่ 1:** หากมีปุ่มกากบาท `[X]` (Close) ให้กดปุ่มกากบาทก่อนเสมอ
   - **ลำดับที่ 2:** หากไม่มีปุ่มกากบาท แต่เป็น Checkbox หรือ Radio ให้เลือกติ๊ก **"NO"** แล้วกด **"Submit"**
   - **ลำดับที่ 3:** ป้องกันปัญหา Modal Overlay (`div.ui-widget-overlay`) ค้างบังหน้าจอ เพื่อไม่ให้ระบบค้าง

3. **การรักษาความเร็วสูง (Warm Browser Session Rule)**
   - ใช้ `GSEWorker` บน Dedicated Event Loop ค้างไว้ในหน่วยความจำ
   - ห้ามเปิด-ปิด Chromium ใหม่ทุกครั้งที่สร้างใบงาน เพราะจะทำให้ช้า (~30 วินาที)
   - การคง Session ไว้ทำให้การสร้างใบงานเดี่ยวใช้เวลาเพียง **~3–5 วินาที** ⚡

4. **การบริหารจัดการแท็บบน eMRO (Tab Limit Rule)**
   - eMRO มีข้อจำกัดเปิดได้ไม่เกิน 9–10 แท็บ
   - ทุกครั้งที่เปิดใบงานสำเร็จ ระบบต้องสั่งปิดแท็บ Detail นั้นทันที เพื่อไม่ให้เกิดปัญหาสะสมจนหน้าจอเต็ม

5. **การส่งข้อมูลเข้า Google Sheets (Async Sync Rule)**
   - ต้องส่งข้อมูลทาง Background Thread เสมอ เพื่อให้หน้าเว็บส่งผลลัพธ์ W/O ให้ผู้ใช้เห็นทันที โดยไม่ต้องรอ Network Round-Trip ของ Google Sheets

6. **การแยกการบันทึกข้อมูล Sheet (Sheet Separation & Audit Policy)**
   - **Monthly PM Tracking Sheet (`1luje0x1QX...`):** กำหนดสำหรับงาน **PM ตามรอบเดือนเท่านั้น** บันทึกเฉพาะงาน PM จากหน้าเปิดใบงานชุด (Batch PM) ห้ามนำรายการ CM (แจ้งซ่อมด่วน) ไปบันทึกปะปนเด็ดขาด
   - **Master W/O Log Sheet (`1BdMWDX9...`):** หรือ **sheet บันทึกข้อมูล W/O** สำหรับบันทึก **รายการแจ้งซ่อมด่วน (CM) เท่านั้น** โดยงานจากหน้าเปิดใบ PM หลายใบจะไม่ถูกนำมาลงใน Sheet นี้ เพื่อป้องกันไม่ให้ข้อมูลงาน PM รายเดือนไปปะปนกับบันทึกการแจ้งซ่อมด่วน

---

## 📜 2. ประวัติการแก้ไขและเหตุการณ์สำคัญ (Changelog & Incident History)

### [2026-10-20] ปรับปรุงหน้าเปิดใบ PM หลายใบไม่บันทึกลง Sheet บันทึกข้อมูล W/O
- **ความต้องการของผู้ใช้:**
  - ปรับแก้ไขให้หน้าเปิดใบ PM หลายใบ (Batch PM) ไม่ต้องเอาข้อมูลไปลง sheet บันทึกข้อมูล W/O (Master W/O Log Sheet: `1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA`)
- **การแก้ไข:**
  1. แก้ไข [web_app.py](file:///D:/Project%20dashboard/web_app.py) ในฟังก์ชัน `run_batch_thread`:
     - ตัดการเรียก `GSEWorkOrderCreator.log_to_google_sheet(BATCH_STATE["results"])` ออก
     - บันทึกประวัติลงไฟล์เครื่อง local (`append_history`) เพื่อแสดงผลในแท็บประวัติบนเว็บตามปกติ
     - ส่งข้อมูลเฉพาะเข้า Monthly PM Tracking Sheet (`sync_to_google_sheet`) สำหรับติดตามงาน PM ตามรอบเดือนเท่านั้น
  2. ปรับปรุง [scraper/gse_wo_creator.py](file:///D:/Project%20dashboard/scraper/gse_wo_creator.py) ในฟังก์ชัน `log_to_google_sheet`:
     - เพิ่มตัวกรองคัดกรองอัตโนมัติ ตัดรายการที่เป็น `PM` หรือ `SCHED` ออกก่อนส่งเข้า Master W/O Log Sheet (sheet บันทึกข้อมูล W/O) เพื่อให้รองรับเฉพาะรายการแจ้งซ่อมด่วน (`CM` / `UNSCHED`) อย่างปลอดภัยแบบสองชั้น (Defense in Depth)

### [2026-10-04] แยกการจัดเก็บ Sheet และสร้างหัวตาราง Master W/O Log Sheet
- **ความต้องการของผู้ใช้:**
  1. ชีตติดตามเดิม (`1luje0x1QXrh...`) กำหนดไว้เฉพาะรอบ PM เท่านั้น ห้ามนำรายการ CM ไปลง ให้คงไว้เฉพาะ PM อย่างเดียวเหมือนเดิม
  2. สร้าง Log รวมประวัติการเปิดใบงานทั้งหมดลงใน Sheet ใหม่: `https://docs.google.com/spreadsheets/d/1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA/` เพื่อตรวจสอบย้อนหลังได้ว่าใครเปิด รถอะไร เลข W/O อะไร อาการอะไร
  3. เนื่องจากใน Sheet ใหม่ยังไม่มีข้อมูล ให้ระบบสร้างหัวตาราง (Headers) ให้อัตโนมัติ
- **การแก้ไข:**
  1. เพิ่มตัวแปร `LOG_SPREADSHEET_ID=1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA` ใน [.env](file:///D:/Project%20dashboard/.env) และ [scraper/config.py](file:///D:/Project%20dashboard/scraper/config.py)
  2. แก้ไข `sync_to_google_sheet` ใน [scraper/gse_wo_creator.py](file:///D:/Project%20dashboard/scraper/gse_wo_creator.py) ให้กรองส่งเฉพาะใบงาน `PM` เข้า Monthly Tracking Sheet เท่านั้น (หากเป็น CM จะถูกข้ามทันที)
  3. เพิ่มฟังก์ชัน `log_to_google_sheet` และ `init_log_sheet_headers` สำหรับส่งข้อมูลและสร้างหัวตารางเข้า Master Log Sheet ใหม่
  4. อัปเดต `web_app.py` ให้การเปิดใบงานแจ้งซ่อมด่วน (CM) ส่งเข้า Master Log Sheet โดยตรง ไม่ส่งเข้า Sheet PM และงานชุด PM ส่งสำเนาเข้า Log Sheet ด้วย
  5. อัปเดต [google_apps_script.js](file:///D:/Project%20dashboard/google_apps_script.js) เพิ่ม Action `init_wo_log_headers` และ `append_wo_log` พร้อมจัดรูปแบบหัวตารางสี Dark Slate (`#0F172A`), ตัวอักษรสีขาวหนา, กึ่งกลาง, Freeze แถวที่ 1 และแบ่งสี Type (CM สีส้ม / PM สีเขียว)
  6. เพิ่มระบบบันทึกประวัติสำรองลงในเครื่องคอมพิวเตอร์ที่ `data/work_order_history.json`
  7. ดึงข้อมูล Log เก่าที่เคยสร้างไว้ทั้งหมด **192 รายการ** (งาน PM 191 รายการ + งาน CM 1 รายการ) บันทึกส่งเข้า Master Log Sheet (`1BdMWDX9...`) สำเร็จครบถ้วน 100%

### [2026-10-04] แก้ไขปัญหาเปิดใบงานในเครื่องอื่น/ผ่าน Cloudflare แล้วติด Timeout 30000ms ("Favorites")
- **ปัญหาที่พบ:** ผู้ใช้งานล็อกอินด้วย `TL248006` จากคอมพิวเตอร์อีกเครื่องผ่าน Cloudflare URL แล้วกดเปิดใบงาน CM (แจ้งซ่อมด่วน) พบข้อผิดพลาด:
  `Failed: Locator.click: Timeout 30000ms exceeded. Call log: - waiting for locator(":text(\"Favorites\")").first`
- **สาเหตุ (Root Cause):**
  1. **รหัสผ่าน eMRO ของ TL248006:** ในไฟล์ `.env` ช่องรหัสผ่านของ `TL248006` ว่างอยู่ ระบบจึงหยิบรหัสผ่านสำรอง `<REDACTED>` (ของ TL248005) ไปกรอก ทำให้หน้าล็อกอิน eMRO แสดงข้อความ `Password Incorrect password entered.`
  2. **จังหวะรอ 2FA เร็วเกินไป (Timing Bug):** ในฟังก์ชัน `ensure_logged_in` เดิมใช้ `await asyncio.sleep(2)` หลังกดปุ่ม Submit เพื่อเช็คกรอบ 2FA (`#mainForm:MFADlg`) แต่ eMRO ใช้เวลา 2.5–4.5 วินาทีในการโหลด Modal 2FA ทำให้โค้ดเดิมเข้าใจผิดว่า "ล็อกอินสำเร็จแล้วโดยไม่ต้องใส่ 2FA"
  3. **การกด Favorites โดยไม่ตรวจสอบ (Blind Click):** ฟังก์ชัน `open_new_detail_tab` สั่ง `await fav.click()` ทันที เมื่อเบราว์เซอร์ยังคงค้างอยู่ที่หน้าล็อกอินหรือ 2FA เมนู `Favorites` จึงไม่ปรากฏและเกิด Timeout 30 วินาที
- **การแก้ไข:**
  1. ตรวจสอบและบันทึกรหัสผ่านที่ถูกต้องของ `TL248006` (คือ `TL248006`) ลงใน `.env` และ `scraper/config.py`
  2. ปรับปรุง `ensure_logged_in` ใน [scraper/gse_wo_creator.py](file:///D:/Project%20dashboard/scraper/gse_wo_creator.py) ให้ใช้ **Dynamic Polling Loop (15 วินาที)** ดักจับทั้งหน้าต่าง 2FA, ข้อความแจ้งเตือนข้อผิดพลาดทุกประเภท (เช่น รหัสผ่านผิด), และหน้า Dashboard
  3. เมื่อป้อน 2FA TOTP เสร็จแล้ว ระบบจะรอจนกว่าหน้า Dashboard และเมนู `Favorites` ปรากฏจริงก่อนยืนยันว่าเข้าสู่ระบบสำเร็จ
  4. เพิ่มการป้องกันใน `open_new_detail_tab` โดยใช้ `wait_for(state="visible", timeout=8000)` พร้อมฟังก์ชันปิดป๊อปอัปอัตโนมัติหากมีหน้าต่างบัง
- **ผลการทดสอบ (Verification):**
  - จำลองการเข้าสู่ระบบด้วยบัญชี `TL248006` และสั่งเปิดใบงาน CM บน eMRO
  - ระบบทำการสลับ Session, ป้อนรหัสผ่าน, กรอก OTP 2FA และเปิดใบงานให้อัตโนมัติอย่างราบรื่น
  - **สร้างใบงานสำเร็จ 100%: W/O #`2346873` (GSE: TLM-TR-031, S/N: 132110)** ความเร็วประมาณ 4 วินาที

### [2026-10-04] แก้ไขปัญหา `TL248006` แสดงสถานะ "ยังไม่ผูก eMRO"
- **ปัญหาที่พบ:** เมื่อผู้ใช้ล็อกอินเข้าหน้าเว็บด้วย `TL248006` ระบบแสดงป้ายเตือนสีแดง `🔴 ยังไม่ผูก eMRO` ทั้งที่เคยผูก 2FA Key ไว้แล้ว
- **สาเหตุ (Root Cause):** 
  - ฟังก์ชัน `Config.has_emro_account` เดิมมีการเช็คว่าต้องมีทั้ง Password และ TOTP Secret พร้อมกัน
  - แต่ใน `.env` ตัวแปร `EMRO_USER_TL248006_PASS=` ถูกเว้นว่างไว้ จึงทำให้ได้ค่า string ว่าง `""` ส่งผลให้เงื่อนไขตรวจสอบกลายเป็น `False`
- **การแก้ไข:**
  - ปรับเงื่อนไข `Config.has_emro_account(user)` ให้ตรวจสอบจากการมี **2FA TOTP Secret Key (`totp_secret`)** ซึ่งเป็นกุญแจสำคัญที่สุดในการเชื่อม eMRO
  - เพิ่ม Fallback ให้กับ Password ของ `TL248006` หากไม่ระบุให้ดึงจาก `Config.EMRO_PASSWORD` หรือข้อมูลแคชบราวเซอร์
  - ผลลัพธ์: บัญชี `TL248006` ขึ้นสถานะ `🟢 eMRO: เชื่อมต่อแล้ว` และเปิดใบงานได้ตามปกติทันที

### [2026-10-04] การตรวจสอบและแก้ไขกรณี `TLM-BC-371` ติด Error
- **ปัญหาที่พบ:** ในการรันงานชุด Batch 191 รายการ มีรายการ `TLM-BC-371` รายการเดียวที่ไม่ได้รับเลข W/O (`Failed to generate W/O number after retries.`)
- **สาเหตุ (Root Cause):** จาก Log เวลา 16:02:18 พบว่าหลังจากกด Save เซิร์ฟเวอร์ eMRO มีความล่าช้าชั่วขณะ (Network/AJAX delay) ทำให้ช่องเลข W/O ว่างเปล่า ลูป Retry เดิมพยายามกด Save ซ้ำบนฟอร์มเดิมที่สถานะการส่งข้อมูลค้างอยู่ eMRO จึงไม่ออกเลขใหม่ให้
- **การแก้ไข:** 
  1. ตรวจสอบสถานะ `TLM-BC-371` ใน eMRO พบว่าอุปกรณ์ Active ปกติ
  2. สั่งเปิดใบงานซ้ำในแท็บใหม่ ผลปรากฏว่า **เปิดสำเร็จ ได้รับเลข W/O #`2346867` (S/N: TLM-BC-371)**
  3. อัปเดตผลลัพธ์ลงใน `data/last_batch_results.json` และซิงค์เข้า Google Sheets สำเร็จครบถ้วน 100% (191/191 รายการ)

### [2026-10-04] ระบบบล็อกผู้ใช้งานที่ยังไม่ผูก eMRO (Block Unlinked Users)
- **ความต้องการ:** บัญชีที่ยังไม่ได้ให้ User eMRO ต้องเปิดใบงานไม่ได้ และต้องขึ้นแจ้งเตือนทันที เพื่อไม่ให้ระบบ eMRO บันทึกชื่อผู้เปิดผิดคน
- **การแก้ไข:**
  - เพิ่มฟังก์ชัน `Config.has_emro_account(user)` ตรวจสอบสิทธิ์
  - เพิ่มระบบตรวจสอบใน `/api/create-single` และ `/api/start-batch` บล็อกด้วย HTTP 403 หากไม่มีสิทธิ์
  - อัปเดตหน้า Dashboard ให้แสดง Badge สถานะ `🟢 eMRO: เชื่อมต่อแล้ว` หรือ `🔴 ยังไม่ผูก eMRO`
  - ตรวจจับฝั่ง Client-side แจ้งเตือนป๊อปอัปทันทีก่อนส่งคำขอ

### [2026-10-04] เพิ่มประสิทธิภาพความเร็วสูง (High-Speed Warm Worker)
- **ปัญหาเดิม:** การเปิดใบงานแจ้งซ่อมด่วน (Ad-Hoc CM) แต่ละใบใช้เวลานาน ~25–35 วินาที เนื่องจากเปิด Browser ใหม่ทุกครั้ง
- **การแก้ไข:**
  - พัฒนาคลาส `GSEWorker` รัน Browser ใน Background พร้อม Pre-warming ล็อกอินรอไว้ล่วงหน้า
  - ปรับปรุงการรอแบบ Smart Polling สำหรับช่องเลข W/O หลุดลูปทันทีที่ eMRO ออกเลข
  - ความเร็วลดลงเหลือเพียง **~3–5 วินาทีต่อใบงาน**

### [2026-10-04] เพิ่มข้อมูลผู้ใช้งาน eMRO: `TL248005`
- **การแก้ไข:** เพิ่มบัญชี `TL248005` (Password `<REDACTED>`, TOTP Secret `<REDACTED - see .env>`) ใน `.env`, `scraper/config.py` และ `web_app.py` พร้อมสิทธิ์เข้าใช้งานระบบ

### [2026-10-04] เปลี่ยนระบบ Remote Access จาก ngrok เป็น Cloudflare Tunnel
- **การแก้ไข:** ถอน ngrok ออกอย่างสมบูรณ์ และใช้งาน Cloudflare Tunnel (`cloudflared.exe`) บริการความเร็วสูง เสถียร ไม่จำกัดแบนด์วิดท์ พร้อมอัปเดตสคริปต์ `.bat` บน Desktop ให้อ่าน URL อัตโนมัติ

### [2026-10-04] ปรับปรุงหน้าแจ้งซ่อมด่วน (Ad-Hoc CM UI)
- **การแก้ไข:** เพิ่มระบบค้นหาและดึงรหัสอุปกรณ์อัตโนมัติ (Autocomplete Dropdown & Quick Chips) รองรับการค้นหาตาม GSE NO., Serial Number, ประเภทอุปกรณ์ หรือเครื่องยนต์ พร้อมแถบสรุปข้อมูลอุปกรณ์ที่เลือก

### [2026-10-04] การแยก Google Sheets และระบบ Master Audit Log Sheet
- **ความต้องการของผู้ใช้:**
  1. ชีต Monthly PM Tracking (`1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs`) ต้องรับเฉพาะงาน **PM (Scheduled W/O)** เท่านั้น ห้ามใส่งาน CM เข้าไปเด็ดขาด
  2. สร้างชีตใหม่ **"LOG eMRO W/O"** (`1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA`) สำหรับ Audit ย้อนหลังว่าใครเปิด รถคันไหน เลข W/O อะไร อาการอะไร
  3. ดึง Log เก่าทั้งหมด (192 รายการ: 191 PM + 1 CM) บันทึกลงในชีตใหม่
- **การแก้ไข:**
  - สร้างสคริปต์ Google Apps Script (`log_sheet_apps_script.js`) บรรจุประวัติ 192 รายการ พร้อมฟังก์ชัน `initAndImportAllLogs()` จัดหัวตาราง Dark Slate, Freeze Header, สีแบ่ง PM (เขียว) / CM (ส้ม)
  - เชื่อมต่อ Webhook URL: `https://script.google.com/macros/s/AKfycbyL9vjvTJn2nI84kGKYTTfMsmCTXB6JJbvLTkl-VhB-uBNtkMEKXHz7S-ulckCdg0z9/exec`
  - ปรับปรุง `scraper/gse_wo_creator.py`:
    - `sync_to_google_sheet(results)`: กรองเฉพาะ PM ก่อนส่งเข้า Monthly Tracking Sheet
    - `log_to_google_sheet(results)`: ส่งข้อมูลทุกใบงาน (ทั้ง PM และ CM) เข้า Master Audit Log Webhook และบันทึกประวัติลง `data/work_order_history.json` อัตโนมัติแบบเรียลไทม์
  - อัปเดต `.env` และ `scraper/config.py` ให้รองรับ `LOG_SPREADSHEET_ID` และ `LOG_APPS_SCRIPT_URL`

### [2026-10-09] เพิ่มระบบการเชื่อมต่อผ่าน Local IP (Fixed LAN / Wi-Fi URL)
- **ความต้องการของผู้ใช้:** ต้องการให้มีลิงก์เข้าใช้งานแบบ IP address ประจำเครื่อง เพื่อให้คอมพิวเตอร์หรือโทรศัพท์เครื่องอื่นในวงเครือข่ายเข้าได้ตลอด โดย URL คงที่ ไม่เปลี่ยนทุกรอบเหมือน Cloudflare
- **การแก้ไข:**
  1. เพิ่มฟังก์ชัน `get_lan_ip()` ใน `web_app.py` ตรวจจับ IP ปัจจุบันของเครื่อง (`172.21.1.111`) ส่งผ่าน API `/api/me`
  2. อัปเดตไฟล์สคริปต์บน Desktop: `Start_GSE_Work_Order.bat` ให้ตรวจหา Local IP อัตโนมัติ และแสดงแยกหมวดหมู่ชัดเจน:
     - `[1] ลิงก์ภายในวงเน็ต LAN / Wi-Fi`: `http://172.21.1.111:8000` (ลิงก์คงที่ ไม่เปลี่ยน)
     - `[2] ลิงก์ออนไลน์ภายนอก Cloudflare`: สำหรับเข้านอกสถานที่/เน็ตมือถือ 4G/5G
     - `[3] ลิงก์เครื่องนี้`: `http://localhost:8000`
  3. เพิ่มปุ่ม Badge บนแถบ Header ของ Dashboard (`data/gse_dashboard.html`) แสดง IP ปัจจุบัน พร้อมฟังก์ชันคลิกเพื่อคัดลอก (1-Click Copy Link) สะดวกต่อการแชร์

### [2026-10-10] แก้ไขปัญหาไฟล์ Start_GSE_Work_Order.bat เปิดแล้วเข้าไม่ได้ (CP1252 Encoding & Batch Parsing Fix)
- **ปัญหาที่พบ:** ผู้ใช้งานดับเบิลคลิกไฟล์ `Start_GSE_Work_Order.bat` บน Desktop แล้วหน้าต่างปิดตัวลงทันที และเข้าเว็บไม่ได้
- **สาเหตุ (Root Cause):**
  1. ใน `.bat` เดิมมีไวยากรณ์ `for /f` ซ้อนวงเล็บ `()` และเครื่องหมายคำพูดของคำสั่ง Python ส่งผลให้ cmd.exe มองเป็นคำสั่งผิดพลาด (`2> was unexpected at this time.`) และปิดหน้าต่าง
  2. เมื่อ Python สั่ง `print()` ข้อความภาษาไทยบน Windows Console เริ่มต้นด้วย Code Page 1252 ทำให้เกิด `UnicodeEncodeError: 'charmap' codec can't encode characters` ส่งผลให้สคริปต์แครช
  3. เบราว์เซอร์ถูกสั่งเปิดก่อนที่เซิร์ฟเวอร์ `web_app.py` จะเปิดพอร์ต 8000 เสร็จสมบูรณ์
- **การแก้ไข:**
  1. สร้างตัวจัดการระบบ `run_system.py` ในโฟลเดอร์โปรเจกต์ รับหน้าที่ดูแล `web_app.py` และ `cloudflared.exe` แบบเบ็ดเสร็จ
  2. ใส่คำสั่งบังคับ UTF-8 (`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`) ป้องกันปัญหาตัวอักษรไทย 100%
  3. เพิ่มระบบ Socket Polling รอจนกระทั่งพอร์ต 8000 ตอบรับจริง จึงสั่งเปิดเบราว์เซอร์อัตโนมัติ
  4. เพิ่มระบบเคลียร์พอร์ต (`free_port / netstat PID kill`) เคลียร์โปรเซสตกค้างก่อนเริ่มเสมอ ป้องกันพอร์ตชน
  5. ปรับปรุง `Start_GSE_Work_Order.bat` บน Desktop ให้เรียก `python run_system.py` โดยตรง สั้น สะอาด และเสถียรที่สุด

### [2026-10-10] เพิ่มแท็บ "ประวัติใบงานทั้งหมด (History Log)" รองรับทั้ง PM และ CM (แบบ B)
- **ความต้องการของผู้ใช้:** ผู้ใช้งานสอบถามเรื่องหน้าผลลัพธ์ W/O เดิมที่แสดงเฉพาะงานชุด PM และเลือก **แบบ B** เพื่อให้มีแท็บดูประวัติใบงานย้อนหลังทั้งหมดที่ครอบคลุมทั้ง PM และ CM
- **การแก้ไข:**
  1. พัฒนา API `/api/history` ใน `web_app.py`:
     - โหลดข้อมูลจาก `data/work_order_history.json`
     - เรียงลำดับจากล่าสุดไปเก่าสุด (Newest First)
     - รองรับ Query parameters: `type` (PM/CM) และ `q` (ค้นหาตามเลข W/O, รหัส GSE, S/N, อาการ, ผู้เปิด)
     - คืนค่าสถิติ `total`, `pm_count`, `cm_count`, และ `filtered_count`
  2. เพิ่มปุ่มแท็บ `ประวัติใบงานทั้งหมด (History)` บนแถบ Navigation พร้อม Badge แสดงจำนวน W/O สะสม
  3. ออกแบบหน้าจอแท็บ `tab-history` ใน `data/gse_dashboard.html`:
     - **Stat Cards 4 ช่อง:** ใบงานทั้งหมด, งานชุด PM, แจ้งซ่อมด่วน CM, ปุ่มเปิด Google Sheet Master Log
     - **Pill Filters:** ปุ่มกรองดูเฉพาะ PM หรือ CM พร้อมตัวเลขนับจำนวน
     - **Search Box:** ค้นหาแบบ Real-time Debounce
     - **View Switcher:** สลับดูแบบตาราง (Table View) หรือการ์ดมือถือ (Card View)
     - **Quick Actions:** ปุ่มรีเฟรช และปุ่มคัดลอกเลข W/O ทั้งหมดในคลิกเดียว
     - ตารางแสดงสัญลักษณ์แบ่งประเภทชัดเจน: **PM สีเขียว 🟢** และ **CM สีส้ม 🟠**
  4. ผูกระบบ Real-time Refresh: เมื่อกดเปิดใบงาน CM สำเร็จในแท็บ 2 ระบบจะสั่งรีเฟรชประวัติในแท็บ History ให้อัตโนมัติทันที

### [2026-10-10] แก้ไขปัญหาบันทึกประวัติ CM ลงไฟล์ท้องถิ่น (Config.BASE_DIR AttributeError & ดึง W/O #2351500)
- **ปัญหาที่พบ:** ผู้ใช้งานเปิดใบงานแจ้งซ่อมด่วน CM สำหรับรถ `TLM-MP-004` สำเร็จ ได้รับเลข W/O #`2351500` แต่ในแท็บ "ประวัติใบงานทั้งหมด (History)" ไม่แสดงรายการนี้
- **สาเหตุ (Root Cause):**
  1. ใน `scraper/gse_wo_creator.py` ฟังก์ชัน `log_to_google_sheet` เรียก `Config.BASE_DIR` แต่ใน `class Config` ไม่มี attribute นี้ และขาด `import json` ทำให้เกิด `AttributeError` และไม่บันทึกลง `data/work_order_history.json`
  2. แม้ใบงานจะถูกส่งเข้า Google Sheet สำเร็จ แต่แท็บ History ในเว็บแอปอ่านจากไฟล์ประวัติท้องถิ่น จึงไม่พบรายการใหม่
- **การแก้ไข:**
  1. เพิ่ม `BASE_DIR = BASE_DIR` ใน `class Config` (`scraper/config.py`) และเพิ่ม `import json` ใน `scraper/gse_wo_creator.py` พร้อม fallback path
  2. ปรับปรุง `/api/create-single` ใน `web_app.py` ให้บันทึกประวัติลง `data/work_order_history.json` ทันทีแบบ Synchronous ก่อนส่ง response
  3. บันทึกข้อมูลใบงาน CM ล่าสุด (`2351500`, GSE: `TLM-MP-004`, S/N: `TLM-MP-004`, อาการ: `HYDRAULIC OIL LEAK.`, ผู้เปิด: `TL248006`, เวลา: `2026-10-10 13:57:42`) ลงใน `data/work_order_history.json` ครบถ้วน ยอดสะสมเป็น 193 รายการ
  4. ทดสอบเรียก API `/api/history?type=CM` พบรายการ `2351500` แสดงอยู่อันดับ 1 บนสุดเรียบร้อย

---

## 📋 3. รายชื่อบัญชี eMRO ที่ผูกในระบบปัจจุบัน

| รหัสพนักงาน (ID) | สถานะ eMRO | รหัสผ่าน eMRO | 2FA Secret Key | หมายเหตุ |
| :--- | :---: | :---: | :---: | :--- |
| **TL248005** | 🟢 เชื่อมต่อแล้ว | <REDACTED> | `<REDACTED - see .env>` | บัญชีหลักปัจจุบัน |
| **TL248006** | 🟢 เชื่อมต่อแล้ว | TL248006 | `<REDACTED - see .env>` | บัญชีสำรอง |
| **TL186205** | 🔴 ยังไม่ผูก | - | - | บล็อกการเปิดใบงาน |
| **TL206992** | 🔴 ยังไม่ผูก | - | - | บล็อกการเปิดใบงาน |
| **TL248007** | 🔴 ยังไม่ผูก | - | - | บล็อกการเปิดใบงาน |
| **TL260005** | 🔴 ยังไม่ผูก | - | - | บล็อกการเปิดใบงาน |
| **TL260006** | 🔴 ยังไม่ผูก | - | - | บล็อกการเปิดใบงาน |

---

## 📌 4. ข้อกำหนดสำหรับ AI Assistant ในการทำงานถัดไป
> **คำสั่งบังคับ (Mandatory Instruction):**  
> ในการทำงานครั้งต่อไป เมื่อผู้ใช้งานสั่งให้แก้ไข, เพิ่มฟีเจอร์, แก้บัก หรือปรับแต่งระบบใด ๆ:  
> 1. ต้องเข้ามาอัปเดตรายละเอียดสิ่งที่แก้ไข สาเหตุ และผลการทำงาน ลงในไฟล์ `PROJECT_NOTES.md` นี้ทุกครั้ง  
> 2. บันทึกวันเวลาและหัวข้อการแก้ไขให้ชัดเจน เพื่อเป็นประวัติเตือนความจำของโปรเจกต์


---

## 🛡️ 2026-10-10 — Audit Fixes (Phase 0–3)

**Phase 0 – Safety net**
- Full backup: `D:\Project dashboard_backup_20261010`; history backup in `data/backup/`.
- `git init` + `.gitignore` (excludes `.env`, `data/*` runtime files, `*.exe`, logs).

**Phase 1 – History integrity (C3, C4 + duplicate bug)**
- New `scraper/history_store.py` = the ONLY writer/reader of `data/work_order_history.json`:
  thread lock, dedup by W/O number, refuses to overwrite an unreadable file, atomic write (`.tmp` + `os.replace`), `.bak` copy.
- `web_app.py` (`/api/create-single`, `/api/history`) and `GSEWorkOrderCreator.log_to_google_sheet` now use it.
- Bug confirmed & fixed: CM W/O were saved twice (web_app + log_to_google_sheet). `2351505`, `2351506` deduplicated (197 → 195). Pre-dedup copy: `data/backup/work_order_history_before_dedup.json`.
- Tests: `tests/test_history_store.py` (4 passed: dedup, skip failed, 100 concurrent writers, corrupt-file protection).

**Phase 2 – Security (password change / 2FA reset skipped by user decision)**
- Removed hardcoded eMRO passwords & TOTP secrets from `scraper/config.py` → read only from `.env`. Redacted them from this notes file.
- `FLASK_SECRET_KEY` added to `.env` (random 64 hex); no hardcoded default.
- Session cookie `HttpOnly` + `SameSite=Lax` (blocks cross-site POST / CSRF).
- Removed `"TL248005"` fallback user in `/api/start-batch` and `/api/create-single`.
- ⚠️ Still open: web login passwords = employee IDs (`VALID_USERS`), and old TOTP secrets should be reset by eMRO admin.

**Phase 3 – Stability**
- `os.chdir(Config.BASE_DIR)` at startup → relative paths work from any launch folder.
- File logging: `data/logs/web_app.log` (rotating 5MB × 5).
- Server now runs on `waitress` (16 threads); PID written to `data/web_app.pid`.
- `start_online.bat` no longer kills every `python.exe` — only the PID in `data/web_app.pid` + cloudflared.
- `requirements.txt`: added `flask`, `waitress`; pinned all versions.

---

## 👤 2026-10-11 — Per-User eMRO Session Isolation & Removed Startup TL248005 Prewarm

**ปัญหาที่พบ:**
1. ตอนรัน `start_online.bat` จะมีหน้าต่าง Chromium เด้งขึ้นมาบนจอ และล็อกอินเข้า eMRO ด้วยรหัส `TL248005` ค้างไว้ (Standby) เนื่องจากใน `web_app.py` มีฟังก์ชัน `prewarm_worker()` ที่ Hardcode สั่งให้ล็อกอิน `TL248005` และฝืน `headless=False`
2. หากมีผู้ใช้งานคนอื่น เช่น `TL248006` ล็อกอินเข้าใช้งานผ่านหน้าเว็บเพื่อเปิดใบงาน เซสชันในเบราว์เซอร์จะยังค้างหรือปะปนกับ `TL248005` ทำให้ในระบบ eMRO บันทึกชื่อผู้เปิดใบงานผิดคน (Created by: TL248005 แทนที่จะเป็น TL248006) เสียระบบ Audit Trail และ accountability

**การแก้ไขที่ดำเนินการ:**
1. **ลบ `prewarm_worker()` ออกจากการเปิดเซิร์ฟเวอร์:**
   - เมื่อรัน `start_online.bat` ระบบจะสตาร์ทเฉพาะ Web Server และ Cloudflare Tunnel ทันที (บูตเร็วใน 1 วินาที)
   - ไม่มีการเด้งหน้าต่างเบราว์เซอร์ eMRO ขึ้นมากวนหน้าจอ และไม่มีการล็อกอินค้างเป็นใครไว้ล่วงหน้า
2. **ระบบ On-Demand Per-User Session:**
   - เบราว์เซอร์ eMRO จะเริ่มทำงานเมื่อผู้ใช้กดสั่งเปิดใบงานจริงบนเว็บเท่านั้น
   - แยกพื้นที่จัดเก็บโปรไฟล์เบราว์เซอร์/คุกกี้ตามรหัสผู้ใช้เป็นสัดส่วนชัดเจน: `data/browser_session/<USER>` เช่น `TL248005` และ `TL248006` ไม่ปะปนกัน
   - `GSEWorker.get_creator(user)`: ตรวจสอบความตรงกันของผู้ใช้ หากเซสชันที่เปิดอยู่ไม่ใช่ของผู้ใช้คนปัจจุบัน ระบบจะทำการปิดเซสชันเดิมอย่างสมบูรณ์ และเปิดเซสชันใหม่ด้วย Credentials/2FA ของผู้ใช้คนนั้นโดยเฉพาะ
3. **รองรับ Headless ตาม `.env`:**
   - ปรับ `web_app.py` และ `scraper/gse_wo_creator.py` ให้ใช้ `headless=Config.HEADLESS` (ตามค่าใน `.env` ซึ่งปัจจุบันตั้งไว้เป็น `HEADLESS=true`)
   - ระบบทำงานในแบ็กกราวด์อย่างเงียบๆ ไม่เด้งหน้าต่างกวนหน้าจอ แต่ยังสามารถดูหน้าจอ Live Screen ผ่านหน้าเว็บ Dashboard ได้ 100% ตามปกติ
4. **ลบ Default TL248005 ทุกจุด:**
   - ปรับ `run_batch_thread` และ `create_single_wo` ให้รับค่า `user` จาก Session ของผู้ที่ล็อกอินจริงเสมอ


---

## 🌐 2026-10-21 — Auto-Sync Online URL to Google Sheet (Free Solution for Outside Network Users)

**ปัญหาที่พบ:**
1. คอมพิวเตอร์ที่อยู่นอกเครือข่ายออฟฟิศ (เช่น ทำงานจากที่บ้าน, มือถือ 4G/5G, หรืออยู่นอกวง Wi-Fi) ไม่สามารถเข้าใช้งานผ่าน Local IP (`http://172.21.1.111:8000`) ได้ เนื่องจากเป็น Private LAN IP
2. ลิงก์ภายนอกของ Cloudflare Quick Tunnel (`*.trycloudflare.com`) จะเปลี่ยน URL ทุกครั้งที่มีการรีสตาร์ท ทำให้คนที่อยู่นอกเครือข่ายไม่ทราบลิงก์ปัจจุบัน และลิงก์เดิมที่เคยบันทึกไว้จะหมดอายุ

**การแก้ไขที่ดำเนินการ (แบบฟรี 100%):**
1. **สร้างโมดูล `scraper/sheet_url_sync.py`:**
   - ทำหน้าที่ส่ง URL ออนไลน์ล่าสุด (Cloudflare) และ LAN IP ขึ้นไปอัปเดตลง Google Sheet ของแผนก (`1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs`) โดยอัตโนมัติ
   - แสดงผลในแท็บ **`Live Transactions`** พร้อมบอกประเภทการเชื่อมต่อ, วันที่-เวลาที่อัปเดต และสถานะ `ONLINE`
2. **ผูกระบบ Auto-Sync ในตัวเรียกใช้งาน:**
   - ใน `run_system.py` (Desktop shortcut `Start_GSE_Work_Order.bat`): เมื่อตรวจพบ Cloudflare URL จะยิงซิงก์ขึ้น Google Sheet ในเบื้องหลังทันที
   - ใน `start_online.bat`: เพิ่มคำสั่งส่ง URL ขึ้น Google Sheet ทันทีหลังเชื่อมต่อ Tunnel สำเร็จ
   - ใน `web_app.py`: เพิ่ม endpoint `/api/sync-online-url` สำหรับสั่งกดซิงก์ซ้ำได้ตลอดเวลา
3. **ผลลัพธ์:**
   - ผู้ใช้งานนอกเครือข่ายเพียงแค่เปิด Google Sheet แผ่นงาน GSE ที่ใช้งานอยู่ประจำ จะเห็นลิงก์ออนไลน์ล่าสุดของวันนั้นทันที สามารถคลิกเข้าใช้งานได้จากทุกที่ ทุกอุปกรณ์ โดยไม่ต้องคอยถามลิงก์ใหม่จากผู้เปิดเครื่อง


---

## ⚠️ 2026-10-25 — eMRO Host 502 Bad Gateway Outage & Error Handling Enhancement

**ปัญหาที่พบ:**
1. ผู้ใช้งานจากอีกเครื่องหนึ่งเปิดหน้าเว็บแล้วกดเปิดใบงาน CM (TLM-BU-027 / WATER PUMP LEAKING) แต่ขึ้นหน้าต่างเตือน:
   `Failed: Worker error: Login to eMRO as TL248006 failed: Dashboard (Favorites) not found after authentication.`
2. เมื่อตรวจสอบภาพบันทึกหน้าจอขณะเกิดเหตุ (`login_failure_TL248006.png` เวลา 08:54:51) และยิงทดสอบไปยัง `https://emro.lionair.com/emro/Home.trax` พบว่า **เซิร์ฟเวอร์ระบบ eMRO ของ Thai Lion Air ต้นทางล่มอยู่ (HTTP Error 502: Bad Gateway / Host Error)** จากฝั่งผู้ให้บริการระบบของสายการบินเอง ไม่ใช่ปัญหาจากระบบ Dashboard ของเรา
3. โค้ดเดิมยังไม่มีการดักจับข้อผิดพลาดระดับเซิร์ฟเวอร์ (502/503/504) อย่างชัดเจน ทำให้ระบบส่งข้อความแจ้งเตือนเป็น generic error ("Dashboard not found") ทำให้ผู้ใช้งานเข้าใจผิดว่าระบบเปิดใบงานเสีย

**การแก้ไขที่ดำเนินการ:**
1. **เพิ่มการดักจับสถานะ HTTP 502/503/504 และ Cloudflare Error ใน `scraper/gse_wo_creator.py`:**
   - เมื่อระบบเรียก `page.goto` ไปยัง eMRO แล้วพบว่าเซิร์ฟเวอร์ต้นทางส่งสถานะ HTTP >= 500 หรือมีข้อความ "502 Bad Gateway", "Host Error" ระบบจะหยุดรอและแจ้งเตือนผู้ใช้งานเป็นภาษาไทยชัดเจนทันที:
     `"เซิร์ฟเวอร์ระบบ eMRO ของ Thai Lion Air (emro.lionair.com) ขัดข้องชั่วคราว (HTTP 502 Bad Gateway / Host Error) ไม่สามารถเปิดหน้าเว็บ eMRO ได้ในขณะนี้ กรุณารอสักครู่ให้ทางระบบ eMRO กลับมาทำงาน แล้วลองใหม่อีกครั้ง"`
2. **แก้ไขการตรวจสอบ Session ใน `web_app.py`:**
   - แก้ไขเงื่อนไข `getattr(self.creator, "user", None) != user_clean` ไม่ให้เช็ค `current_user` ซ้ำซ้อน ซึ่งก่อนหน้านี้จะสั่งปิดและเปิดเบราว์เซอร์ใหม่โดยไม่จำเป็นหากผู้ใช้คนเดิมยังล็อกอินไม่เสร็จ
3. **ปรับปรุงข้อความแจ้งเตือน Error ทั่วไปให้เป็นภาษาไทยเข้าใจง่าย:**
   - หากเข้าสู่ระบบไม่สำเร็จและมีข้อความเตือนจาก eMRO ระบบจะดึงข้อความนั้นมาแสดงให้ผู้ใช้ทราบทันที


---

## ✈️ 2026-10-25 — Integration of emro.lionairthai.com & Redundant Failover

**การดำเนินการ:**
1. ผู้ใช้งานแจ้งโดเมนสำรองของสายการบินในเครือเดียวกัน: `https://emro.lionairthai.com/emro/Home.trax`
2. ทดสอบพบว่า `emro.lionairthai.com` ทำงานได้รวดเร็ว สถานะ HTTP 200 ปกติสมบูรณ์ โครงสร้างแบบฟอร์ม eMRO (TRAX) เหมือนกัน 100%
3. **อัปเดตการตั้งค่าระบบ:**
   - `.env`: ตั้ง `EMRO_URL=https://emro.lionairthai.com/emro/Home.trax` เป็น Primary URL และ `EMRO_FALLBACK_URL=https://emro.lionair.com/emro/Home.trax` เป็นสำรอง
   - `scraper/config.py`: รองรับทั้ง `EMRO_URL` และ `EMRO_FALLBACK_URL`
   - `scraper/gse_wo_creator.py`: รองรับการเปิดหน้าเว็บทั้งสองโดเมน พร้อมระบบสลับ URL อัตโนมัติ (Failover) หากโดเมนใดโดเมนหนึ่งล่ม จะสลับไปอีกลิงก์ให้อัตโนมัติทันที
4. **ทดสอบเปิดใบงานจริง:**
   - ทดสอบเปิดใบงาน Ad-Hoc CM ให้กับรถ **`TLM-BU-027`** (อาการ: `WATER PUMP LEAKING.`, ผู้เปิด: `TL248006`)
   - **สำเร็จสมบูรณ์ 100%!** ได้รับเลขที่ใบงาน **W/O #`2362438`** (S/N: `YS4K4X20001842240`) บันทึกลงระบบประวัติเรียบร้อย
