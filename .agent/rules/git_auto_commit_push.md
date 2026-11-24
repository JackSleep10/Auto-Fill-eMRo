# Git Auto Commit & Push Rule

- **Always Commit & Push Every Change**: ทุกครั้งที่มีการแก้ไขงาน ปรับปรุงโค้ด เพิ่มฟีเจอร์ หรือแก้ไขบั๊กในโปรเจกต์ `D:\Project dashboard` (`Auto-Fill-eMRo`) ต้องทำการ `git add`, `git commit` และ `git push` ขึ้น GitHub (`https://github.com/JackSleep10/Auto-Fill-eMRo.git` บน branch `main`) ตลอดเสมอ
- **Sync `D:\Project inventory`**: เมื่อมีการแก้ไขงานใน `D:\Project inventory` ให้คัดลอกเฉพาะไฟล์ซอร์สโค้ด (ยกเว้น `.env`, `data/`, `__pycache__/`) มาที่ `D:\Project dashboard\project_inventory\` ก่อนทำการ `git add`, `git commit` และ `git push origin main` ทุกครั้ง
- **Verify Before Commit**: ตรวจสอบ `git status` และ `git diff` ให้แน่ใจว่าไม่มีไฟล์ความลับ (`.env`), ข้อมูล runtime หรือ cache ปะปนเข้าไป (ยึดตาม `.gitignore`)
- **Clear Commit Messages**: เขียน commit message ให้สื่อความหมายของการแก้ไขอย่างชัดเจน และส่งคำสั่ง `git push origin main` หลัง commit เสร็จสิ้นทุกครั้ง
