/**
 * LOG eMRO W/O — Google Apps Script
 * สำหรับใส่ใน Google Sheets "LOG eMRO W/O"
 * 
 * วิธีใช้:
 * 1. กดปุ่ม 'เรียกใช้' (Run ▶️) ที่ฟังก์ชัน initAndImportAllLogs ด้านบน
 *    ข้อมูลประวัติ 192 รายการพร้อมหัวตารางจะปรากฏบนชีตทันที!
 * 2. หากต้องการให้ระบบส่งใบงานใหม่เข้าชีตนี้อัตโนมัติ:
 *    กดปุ่ม 'ทำให้ใช้งานได้' (Deploy) -> 'การทำให้ใช้งานได้ใหม่' (New deployment)
 *    เลือกประเภท: เว็บแอป (Web app) -> ให้สิทธิ์: ทุกคน (Anyone) -> Deploy
 */

var INITIAL_LOGS = [
  [
    "2026-10-04 15:40:13",
    "TL248005",
    "TLM-BC-009",
    "TLM-BC-009",
    "2346666",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:40:27",
    "TL248005",
    "TLM-BC-014",
    "TLM-BC-014",
    "2346667",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:40:37",
    "TL248005",
    "TLM-BC-015",
    "TLM-BC-015",
    "2346668",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:40:46",
    "TL248005",
    "TLM-BC-024",
    "TLM-BC-024",
    "2346669",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:40:55",
    "TL248005",
    "TLM-BC-025",
    "TLM-BC-025",
    "2346670",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:41:13",
    "TL248005",
    "TLM-BC-026",
    "TLM-BC-026",
    "2346671",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:41:22",
    "TL248005",
    "TLM-BC-032",
    "TLM-BC-032",
    "2346672",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:41:32",
    "TL248005",
    "TLM-BC-034",
    "TLM-BC-034",
    "2346673",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:41:40",
    "TL248005",
    "TLM-BC-056",
    "TLM-BC-056",
    "2346674",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:41:49",
    "TL248005",
    "TLM-BC-060",
    "TLM-BC-060",
    "2346675",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:42:06",
    "TL248005",
    "TLM-BC-062",
    "TLM-BC-062",
    "2346676",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:42:15",
    "TL248005",
    "TLM-BC-063",
    "TLM-BC-063",
    "2346677",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:42:25",
    "TL248005",
    "TLM-BC-064",
    "TLM-BC-064",
    "2346678",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:42:34",
    "TL248005",
    "TLM-BC-065",
    "TLM-BC-065",
    "2346679",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:42:45",
    "TL248005",
    "TLM-BC-066",
    "TLM-BC-066",
    "2346680",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:42:55",
    "TL248005",
    "TLM-BC-079",
    "TLM-BC-079",
    "2346681",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:43:04",
    "TL248005",
    "TLM-BC-268",
    "TLM-BC-268",
    "2346682",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:43:15",
    "TL248005",
    "TLM-BC-080",
    "TLM-BC-080",
    "2346683",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:43:27",
    "TL248005",
    "TLM-BC-081",
    "TLM-BC-081",
    "2346684",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:43:38",
    "TL248005",
    "TLM-BC-082",
    "TLM-BC-082",
    "2346685",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:43:47",
    "TL248005",
    "TLM-BC-329",
    "TLM-BC-329",
    "2346686",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:43:58",
    "TL248005",
    "TLM-BC-083",
    "TLM-BC-083",
    "2346687",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:44:09",
    "TL248005",
    "TLM-BC-084",
    "TLM-BC-084",
    "2346688",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:44:20",
    "TL248005",
    "TLM-BC-085",
    "TLM-BC-085",
    "2346689",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:44:41",
    "TL248005",
    "TLM-BC-086",
    "TLM-BC-086",
    "2346690",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:44:52",
    "TL248005",
    "TLM-BC-103",
    "TLM-BC-103",
    "2346691",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:45:15",
    "TL248005",
    "TLM-BC-107",
    "TLM-BC-107",
    "2346692",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:45:27",
    "TL248005",
    "TLM-BC-108",
    "TLM-BC-108",
    "2346693",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:45:43",
    "TL248005",
    "TLM-BC-109",
    "TLM-BC-109",
    "2346694",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:45:54",
    "TL248005",
    "TLM-BC-110",
    "TLM-BC-110",
    "2346695",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:46:23",
    "TL248005",
    "TLM-BC-111",
    "TLM-BC-111",
    "2346696",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:46:33",
    "TL248005",
    "TLM-BC-112",
    "TLM-BC-112",
    "2346697",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:46:51",
    "TL248005",
    "TLM-BC-113",
    "TLM-BC-113",
    "2346698",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:47:09",
    "TL248005",
    "TLM-BC-114",
    "TLM-BC-114",
    "2346699",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:47:18",
    "TL248005",
    "TLM-BC-115",
    "TLM-BC-115",
    "2346700",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:47:27",
    "TL248005",
    "TLM-BC-116",
    "TLM-BC-116",
    "2346701",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:47:46",
    "TL248005",
    "TLM-BC-117",
    "TLM-BC-117",
    "2346702",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:48:11",
    "TL248005",
    "TLM-BC-118",
    "TLM-BC-118",
    "2346703",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:48:27",
    "TL248005",
    "TLM-BC-120",
    "TLM-BC-120",
    "2346704",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:48:45",
    "TL248005",
    "TLM-BC-121",
    "TLM-BC-121",
    "2346705",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:48:57",
    "TL248005",
    "TLM-BC-122",
    "TLM-BC-122",
    "2346706",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:49:08",
    "TL248005",
    "TLM-BC-124",
    "TLM-BC-124",
    "2346707",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:49:19",
    "TL248005",
    "TLM-BC-125",
    "TLM-BC-125",
    "2346708",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:49:29",
    "TL248005",
    "TLM-BC-126",
    "TLM-BC-126",
    "2346709",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:49:42",
    "TL248005",
    "TLM-BC-128",
    "TLM-BC-128",
    "2346710",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:49:52",
    "TL248005",
    "TLM-BC-129",
    "TLM-BC-129",
    "2346711",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:50:11",
    "TL248005",
    "TLM-BC-131",
    "TLM-BC-131",
    "2346712",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:50:21",
    "TL248005",
    "TLM-BC-132",
    "TLM-BC-132",
    "2346713",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:50:30",
    "TL248005",
    "TLM-BC-330",
    "TLM-BC-330",
    "2346714",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:50:42",
    "TL248005",
    "TLM-BC-133",
    "TLM-BC-133",
    "2346715",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:50:55",
    "TL248005",
    "TLM-BC-135",
    "TLM-BC-135",
    "2346716",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:51:05",
    "TL248005",
    "TLM-BC-331",
    "TLM-BC-331",
    "2346717",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:51:17",
    "TL248005",
    "TLM-BC-332",
    "TLM-BC-332",
    "2346718",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:51:30",
    "TL248005",
    "TLM-BC-333",
    "TLM-BC-333",
    "2346719",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:51:42",
    "TL248005",
    "TLM-BC-136",
    "TLM-BC-136",
    "2346720",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:51:53",
    "TL248005",
    "TLM-BC-137",
    "TLM-BC-136",
    "2346721",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:52:13",
    "TL248005",
    "TLM-BC-334",
    "TLM-BC-334",
    "2346722",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:52:22",
    "TL248005",
    "TLM-BC-138",
    "TLM-BC-138",
    "2346723",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:52:31",
    "TL248005",
    "TLM-BC-139",
    "TLM-BC-139",
    "2346724",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:52:40",
    "TL248005",
    "TLM-BC-140",
    "TLM-BC-140",
    "2346725",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:52:59",
    "TL248005",
    "TLM-BC-146",
    "TLM-BC-146",
    "2346726",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:53:08",
    "TL248005",
    "TLM-BC-335",
    "TLM-BC-335",
    "2346727",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:53:17",
    "TL248005",
    "TLM-BC-147",
    "TLM-BC-147",
    "2346728",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:53:26",
    "TL248005",
    "TLM-BC-148",
    "TLM-BC-148",
    "2346729",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:53:35",
    "TL248005",
    "TLM-BC-151",
    "TLM-BC-151",
    "2346730",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:53:43",
    "TL248005",
    "TLM-BC-152",
    "TLM-BC-152",
    "2346731",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:53:52",
    "TL248005",
    "TLM-BC-336",
    "TLM-BC-336",
    "2346732",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:54:12",
    "TL248005",
    "TLM-BC-153",
    "TLM-BC-153",
    "2346733",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:54:30",
    "TL248005",
    "TLM-BC-154",
    "TLM-BC-154",
    "2346734",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:54:40",
    "TL248005",
    "TLM-BC-155",
    "TLM-BC-155",
    "2346735",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:54:49",
    "TL248005",
    "TLM-BC-337",
    "TLM-BC-337",
    "2346736",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:55:07",
    "TL248005",
    "TLM-BC-156",
    "TLM-BC-156",
    "2346737",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:55:18",
    "TL248005",
    "TLM-BC-157",
    "TLM-BC-157",
    "2346738",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:55:28",
    "TL248005",
    "TLM-BC-338",
    "TLM-BC-338",
    "2346739",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:55:38",
    "TL248005",
    "TLM-BC-158",
    "TLM-BC-158",
    "2346740",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:55:47",
    "TL248005",
    "TLM-BC-159",
    "TLM-BC-159",
    "2346741",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:55:56",
    "TL248005",
    "TLM-BC-161",
    "TLM-BC-161",
    "2346742",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:56:05",
    "TL248005",
    "TLM-BC-162",
    "TLM-BC-162",
    "2346743",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:56:13",
    "TL248005",
    "TLM-BC-339",
    "TLM-BC-339",
    "2346744",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:56:22",
    "TL248005",
    "TLM-BC-340",
    "TLM-BC-340",
    "2346745",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:56:31",
    "TL248005",
    "TLM-BC-163",
    "TLM-BC-163",
    "2346746",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:56:39",
    "TL248005",
    "TLM-BC-164",
    "TLM-BC-164",
    "2346747",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:56:56",
    "TL248005",
    "TLM-BC-341",
    "TLM-BC-341",
    "2346748",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:57:08",
    "TL248005",
    "TLM-BC-342",
    "TLM-BC-342",
    "2346749",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:57:18",
    "TL248005",
    "TLM-BC-343",
    "TLM-BC-343",
    "2346750",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:57:28",
    "TL248005",
    "TLM-BC-344",
    "TLM-BC-344",
    "2346751",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:57:38",
    "TL248005",
    "TLM-BC-345",
    "TLM-BC-345",
    "2346752",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:57:49",
    "TL248005",
    "TLM-BC-346",
    "TLM-BC-346",
    "2346753",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:58:00",
    "TL248005",
    "TLM-BC-347",
    "TLM-BC-347",
    "2346754",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:58:10",
    "TL248005",
    "TLM-BC-348",
    "TLM-BC-348",
    "2346755",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:58:19",
    "TL248005",
    "TLM-BC-349",
    "TLM-BC-349",
    "2346756",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:58:30",
    "TL248005",
    "TLM-BC-350",
    "TLM-BC-350",
    "2346757",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:58:39",
    "TL248005",
    "TLM-BC-351",
    "TLM-BC-351",
    "2346758",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:58:49",
    "TL248005",
    "TLM-BC-352",
    "TLM-BC-352",
    "2346759",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:59:05",
    "TL248005",
    "TLM-BC-353",
    "TLM-BC-353",
    "2346760",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:59:15",
    "TL248005",
    "TLM-BC-354",
    "TLM-BC-354",
    "2346761",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:59:25",
    "TL248005",
    "TLM-BC-355",
    "TLM-BC-355",
    "2346762",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:59:35",
    "TL248005",
    "TLM-BC-356",
    "TLM-BC-356",
    "2346763",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:59:44",
    "TL248005",
    "TLM-BC-357",
    "TLM-BC-357",
    "2346764",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 15:59:54",
    "TL248005",
    "TLM-BC-358",
    "TLM-BC-358",
    "2346765",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:00:03",
    "TL248005",
    "TLM-BC-359",
    "TLM-BC-359",
    "2346766",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:00:12",
    "TL248005",
    "TLM-BC-360",
    "TLM-BC-360",
    "2346767",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:00:20",
    "TL248005",
    "TLM-BC-361",
    "TLM-BC-361",
    "2346768",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:00:30",
    "TL248005",
    "TLM-BC-362",
    "TLM-BC-362",
    "2346769",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:00:39",
    "TL248005",
    "TLM-BC-363",
    "TLM-BC-363",
    "2346770",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:00:48",
    "TL248005",
    "TLM-BC-364",
    "TLM-BC-364",
    "2346771",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:01:07",
    "TL248005",
    "TLM-BC-365",
    "TLM-BC-365",
    "2346772",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:01:30",
    "TL248005",
    "TLM-BC-366",
    "TLM-BC-366",
    "2346773",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:01:40",
    "TL248005",
    "TLM-BC-367",
    "TLM-BC-367",
    "2346774",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:01:50",
    "TL248005",
    "TLM-BC-368",
    "TLM-BC-368",
    "2346775",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:01:59",
    "TL248005",
    "TLM-BC-369",
    "TLM-BC-369",
    "2346776",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:02:09",
    "TL248005",
    "TLM-BC-370",
    "TLM-BC-370",
    "2346777",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:27:38",
    "TL248005",
    "TLM-BC-371",
    "TLM-BC-371",
    "2346867",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:02:45",
    "TL248005",
    "TLM-BC-372",
    "TLM-BC-372",
    "2346780",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:03:09",
    "TL248005",
    "TLM-BC-373",
    "TLM-BC-373",
    "2346782",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:03:32",
    "TL248005",
    "TLM-BC-374",
    "TLM-BC-374",
    "2346784",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:03:47",
    "TL248005",
    "TLM-BC-375",
    "TLM-BC-375",
    "2346785",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:04:00",
    "TL248005",
    "TLM-BC-376",
    "TLM-BC-376",
    "2346787",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:04:14",
    "TL248005",
    "TLM-BC-377",
    "TLM-BC-377",
    "2346788",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:04:28",
    "TL248005",
    "TLM-BC-378",
    "TLM-BC-378",
    "2346790",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:04:42",
    "TL248005",
    "TLM-BC-379",
    "TLM-BC-379",
    "2346791",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:04:57",
    "TL248005",
    "TLM-BC-380",
    "TLM-BC-380",
    "2346793",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:05:12",
    "TL248005",
    "TLM-BC-381",
    "TLM-BC-381",
    "2346795",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:05:26",
    "TL248005",
    "TLM-BC-165",
    "TLM-BC-165",
    "2346797",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:05:54",
    "TL248005",
    "TLM-BC-166",
    "TLM-BC-166",
    "2346799",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:06:08",
    "TL248005",
    "TLM-BC-167",
    "TLM-BC-167",
    "2346800",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:06:22",
    "TL248005",
    "TLM-BC-193",
    "TLM-BC-193",
    "2346801",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:06:36",
    "TL248005",
    "TLM-BC-194",
    "TLM-BC-194",
    "2346802",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:06:50",
    "TL248005",
    "TLM-BC-195",
    "TLM-BC-195",
    "2346803",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:07:04",
    "TL248005",
    "TLM-BC-196",
    "TLM-BC-196",
    "2346804",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:07:19",
    "TL248005",
    "TLM-BC-197",
    "TLM-BC-197",
    "2346805",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:07:33",
    "TL248005",
    "TLM-BC-198",
    "TLM-BC-198",
    "2346806",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:07:45",
    "TL248005",
    "TLM-BC-199",
    "TLM-BC-199",
    "2346807",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:07:58",
    "TL248005",
    "TLM-BC-213",
    "TLM-BC-213",
    "2346808",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:08:10",
    "TL248005",
    "TLM-BC-214",
    "TLM-BC-214",
    "2346809",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:08:22",
    "TL248005",
    "TLM-BC-215",
    "TLM-BC-215",
    "2346810",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:08:43",
    "TL248005",
    "TLM-BC-217",
    "TLM-BC-217",
    "2346811",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:08:55",
    "TL248005",
    "TLM-BC-227",
    "TLM-BC-227",
    "2346812",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:09:07",
    "TL248005",
    "TLM-BC-228",
    "TLM-BC-228",
    "2346813",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:09:20",
    "TL248005",
    "TLM-BC-230",
    "TLM-BC-230",
    "2346814",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:09:32",
    "TL248005",
    "TLM-BC-232",
    "TLM-BC-232",
    "2346815",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:09:43",
    "TL248005",
    "TLM-BC-233",
    "TLM-BC-233",
    "2346816",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:09:55",
    "TL248005",
    "TLM-BC-234",
    "TLM-BC-234",
    "2346817",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:10:07",
    "TL248005",
    "TLM-BC-235",
    "TLM-BC-235",
    "2346818",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:10:18",
    "TL248005",
    "TLM-BC-241",
    "TLM-BC-241",
    "2346819",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:10:30",
    "TL248005",
    "TLM-BC-257",
    "TLM-BC-257",
    "2346820",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:10:42",
    "TL248005",
    "TLM-BC-262",
    "TLM-BC-262",
    "2346821",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:10:54",
    "TL248005",
    "TLM-BC-263",
    "TLM-BC-263",
    "2346822",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:11:05",
    "TL248005",
    "TLM-BC-266",
    "TLM-BC-266",
    "2346823",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:11:18",
    "TL248005",
    "TLM-BC-267",
    "TLM-BC-267",
    "2346824",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:11:30",
    "TL248005",
    "TLM-BC-270",
    "TLM-BC-270",
    "2346825",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:11:42",
    "TL248005",
    "TLM-BC-271",
    "TLM-BC-271",
    "2346826",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:11:54",
    "TL248005",
    "TLM-BC-272",
    "TLM-BC-272",
    "2346827",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:12:06",
    "TL248005",
    "TLM-BC-273",
    "TLM-BC-273",
    "2346828",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:12:19",
    "TL248005",
    "TLM-BC-283",
    "TLM-BC-283",
    "2346830",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:12:32",
    "TL248005",
    "TLM-BC-284",
    "TLM-BC-284",
    "2346831",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:12:44",
    "TL248005",
    "TLM-BC-285",
    "TLM-BC-285",
    "2346832",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:12:56",
    "TL248005",
    "TLM-BC-286",
    "TLM-BC-286",
    "2346833",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:13:09",
    "TL248005",
    "TLM-BC-288",
    "TLM-BC-288",
    "2346834",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:13:21",
    "TL248005",
    "TLM-BC-289",
    "TLM-BC-289",
    "2346835",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:13:33",
    "TL248005",
    "TLM-BC-290",
    "TLM-BC-290",
    "2346836",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:13:45",
    "TL248005",
    "TLM-BC-291",
    "TLM-BC-291",
    "2346837",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:13:57",
    "TL248005",
    "TLM-BC-292",
    "TLM-BC-292",
    "2346838",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:14:09",
    "TL248005",
    "TLM-BC-293",
    "TLM-BC-293",
    "2346839",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:14:20",
    "TL248005",
    "TLM-BC-302",
    "TLM-BC-302",
    "2346840",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:14:32",
    "TL248005",
    "TLM-BC-303",
    "TLM-BC-303",
    "2346841",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:14:44",
    "TL248005",
    "TLM-BC-304",
    "TLM-BC-304",
    "2346842",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:14:56",
    "TL248005",
    "TLM-BC-305",
    "TLM-BC-305",
    "2346843",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:15:16",
    "TL248005",
    "TLM-BC-306",
    "TLM-BC-306",
    "2346844",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:15:29",
    "TL248005",
    "TLM-BC-307",
    "TLM-BC-307",
    "2346845",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:15:40",
    "TL248005",
    "TLM-BC-308",
    "TLM-BC-308",
    "2346846",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:15:54",
    "TL248005",
    "TLM-BC-309",
    "TLM-BC-309",
    "2346847",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:16:14",
    "TL248005",
    "TLM-BC-310",
    "TLM-BC-310",
    "2346848",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:16:27",
    "TL248005",
    "TLM-BC-311",
    "TLM-BC-311",
    "2346849",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:16:40",
    "TL248005",
    "TLM-BC-312",
    "TLM-BC-312",
    "2346850",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:16:52",
    "TL248005",
    "TLM-BC-313",
    "TLM-BC-313",
    "2346851",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:17:04",
    "TL248005",
    "TLM-BC-314",
    "TLM-BC-314",
    "2346852",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:17:16",
    "TL248005",
    "TLM-BC-315",
    "TLM-BC-315",
    "2346853",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:17:28",
    "TL248005",
    "TLM-BC-316",
    "TLM-BC-316",
    "2346854",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:17:40",
    "TL248005",
    "TLM-BC-317",
    "TLM-BC-317",
    "2346855",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:17:52",
    "TL248005",
    "TLM-BC-318",
    "TLM-BC-318",
    "2346856",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:18:05",
    "TL248005",
    "TLM-BC-319",
    "TLM-BC-319",
    "2346857",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:18:17",
    "TL248005",
    "TLM-BC-320",
    "TLM-BC-320",
    "2346858",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:18:30",
    "TL248005",
    "TLM-BC-321",
    "TLM-BC-321",
    "2346859",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:18:42",
    "TL248005",
    "TLM-BC-322",
    "TLM-BC-322",
    "2346860",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:18:54",
    "TL248005",
    "TLM-BC-323",
    "TLM-BC-323",
    "2346861",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:19:07",
    "TL248005",
    "TLM-BC-324",
    "TLM-BC-324",
    "2346862",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:19:19",
    "TL248005",
    "TLM-BC-325",
    "TLM-BC-325",
    "2346863",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:19:44",
    "TL248005",
    "TLM-BC-326",
    "TLM-BC-326",
    "2346864",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:20:05",
    "TL248005",
    "TLM-BC-327",
    "TLM-BC-327",
    "2346865",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 16:20:16",
    "TL248005",
    "TLM-BC-328",
    "TLM-BC-328",
    "2346866",
    "PM",
    "PM NOV",
    "SUCCESS"
  ],
  [
    "2026-10-04 19:13:07",
    "TL248006",
    "TLM-TR-031",
    "132110",
    "2346873",
    "CM",
    "OIL LEAKED TEST 2FA",
    "SUCCESS"
  ]
];

function initAndImportAllLogs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheets()[0];
  
  var headers = [
    "วันที่-เวลา (Timestamp)",
    "ผู้เปิดใบงาน (User)",
    "รหัสรถ (GSE NO.)",
    "หมายเลขตัวถัง (S/N)",
    "เลขที่ W/O",
    "ประเภท (Type)",
    "อาการ / รายละเอียด (Description)",
    "สถานะ (Status)"
  ];

  sheet.clearContents();
  sheet.appendRow(headers);

  // สไตล์หัวตาราง Dark Slate
  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setFontWeight("bold");
  headerRange.setBackground("#0F172A");
  headerRange.setFontColor("#F8FAFC");
  headerRange.setHorizontalAlignment("center");
  headerRange.setVerticalAlignment("middle");
  sheet.setRowHeight(1, 38);
  sheet.setFrozenRows(1);

  // ใส่ข้อมูลทั้ง 192 รายการ
  if (INITIAL_LOGS.length > 0) {
    sheet.getRange(2, 1, INITIAL_LOGS.length, headers.length).setValues(INITIAL_LOGS);

    // จัด Alignment และสี
    sheet.getRange(2, 1, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 2, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 3, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 4, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 5, INITIAL_LOGS.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
    sheet.getRange(2, 6, INITIAL_LOGS.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
    sheet.getRange(2, 8, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");

    // แบ่งสี CM / PM
    for (var i = 0; i < INITIAL_LOGS.length; i++) {
      var pType = INITIAL_LOGS[i][5];
      var cell = sheet.getRange(i + 2, 6);
      if (pType === "CM") {
        cell.setFontColor("#D97706");
      } else {
        cell.setFontColor("#059669");
      }
    }
  }

  // ปรับความกว้างคอลัมน์ให้อ่านง่าย
  for (var c = 1; c <= headers.length; c++) {
    sheet.autoResizeColumn(c);
  }
  SpreadsheetApp.flush();
}

// รับข้อมูลใบงานใหม่ในอนาคตแบบอัตโนมัติ
function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);
    var contents = e.postData.contents;
    var data = JSON.parse(contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheets()[0];

    if (data.items && data.items.length > 0) {
      var now = new Date();
      var nowStr = Utilities.formatDate(now, "Asia/Bangkok", "dd/MM/yyyy HH:mm:ss");
      var newRows = [];

      data.items.forEach(function(item) {
        if (!item.success && !item.wo_number) return;
        var prio = (item.priority === "SCHED" || item.priority === "PM") ? "PM" : "CM";
        newRows.push([
          item.created_at || nowStr,
          item.user || "TL248006",
          item.gse || "-",
          item.sn || "-",
          item.wo_number || "-",
          prio,
          item.description || "-",
          item.success ? "SUCCESS" : ("FAILED: " + (item.error || ""))
        ]);
      });

      if (newRows.length > 0) {
        var startRow = sheet.getLastRow() + 1;
        sheet.getRange(startRow, 1, newRows.length, 8).setValues(newRows);
        sheet.getRange(startRow, 1, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 2, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 3, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 4, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 5, newRows.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
        sheet.getRange(startRow, 6, newRows.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
        sheet.getRange(startRow, 8, newRows.length, 1).setHorizontalAlignment("center");
      }
    }

    return ContentService.createTextOutput(JSON.stringify({ status: "success" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
