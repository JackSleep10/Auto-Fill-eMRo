# Web Form & Grid Scraper Isolation Guardrails

- **Strict Container Boundary**: เมื่อทำการ parse ข้อมูลจากตารางหรือฟอร์มที่มีโครงสร้างแบบ Grid/Responsive (เช่น PrimeFaces `.ui-g`, Bootstrap `.col-*`, Flexbox, หรือ `<td>`) ต้องจำกัดการค้นหา Input/Textarea ให้อยู่เฉพาะภายใน Column Container เดียวกันกับ Label เท่านั้น
- **Never Unbounded Search**: ห้ามใช้การค้นหาแบบเปิดกว้างข้ามโดม เช่น `find_all_next(...)` หรือ `find_next(...)` ไปยังฟิลด์อื่น เมื่อฟิลด์นั้นไม่มีค่าในคอนเทนเนอร์ของตนเอง
- **Preserve Empty Values**: "อันไหนที่ไม่มีให้เว้นว่างไว้" — หากฟิลด์ไม่มี Input หรือไม่มีค่า (`value=""`) ให้คงค่าว่าง `""` เสมอ ห้าม fallback ไปดึงค่าจากฟิลด์ใกล้เคียง
- **Action Keyword Exclusion**: กรองค่าปุ่มหรือ action text เช่น `"Select"`, `"View"`, `"Edit"`, `"Find"` ออกจากค่าข้อมูลเสมอ
