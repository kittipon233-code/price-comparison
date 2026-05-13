import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json
from datetime import datetime
import io

# ===== Google Services =====
@st.cache_resource
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["SPREADSHEET_ID"])
    _init_sheets(sh)
    return sh

def get_drive_service():
    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return build("drive", "v3", credentials=creds)

def _init_sheets(sh):
    existing = [ws.title for ws in sh.worksheets()]
    sheet_defs = {
        "projects":  ["id","title","project_name","date","vat_rate","shops","shop_discounts","groups","tags","status","created_by","created_at","updated_at"],
        "shops_db":  ["id","name","contact","phone","email","address","payment_terms","notes","created_by","created_at"],
        "templates": ["id","name","category","items","created_by","created_at"],
        "settings":  ["key","value"],
    }
    for name, headers in sheet_defs.items():
        if name not in existing:
            ws = sh.add_worksheet(name, 1000, len(headers))
            ws.append_row(headers)

def get_ws(name):
    return get_sheet().worksheet(name)

# ===== Projects =====
def load_projects():
    try:
        return get_ws("projects").get_all_records()
    except:
        return []

def save_project(data, created_by, project_id=None):
    ws  = get_ws("projects")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        project_id or "",
        data["title"], data["project_name"], data["date"], data["vat_rate"],
        json.dumps(data["shops"],          ensure_ascii=False),
        json.dumps(data["shop_discounts"], ensure_ascii=False),
        json.dumps(data["groups"],         ensure_ascii=False),
        json.dumps(data.get("tags", []),   ensure_ascii=False),
        data.get("status", "กำลังดำเนินการ"),
        created_by, now, now
    ]
    if project_id:
        records = ws.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("id")) == str(project_id):
                row[11] = r.get("created_at", now)  # keep original created_at
                ws.update(f"A{i+2}:M{i+2}", [row])
                return project_id
    records = ws.get_all_records()
    new_id  = len(records) + 1
    row[0]  = new_id
    ws.append_row(row)
    return new_id

def delete_project(project_id):
    ws = get_ws("projects")
    for i, r in enumerate(ws.get_all_records()):
        if str(r.get("id")) == str(project_id):
            ws.delete_rows(i + 2)
            return True
    return False

def duplicate_project(project_id, created_by):
    ws = get_ws("projects")
    records = ws.get_all_records()
    for r in records:
        if str(r.get("id")) == str(project_id):
            shops, shop_discounts, groups = parse_project(r)
            data = {
                "title":          f"[สำเนา] {r.get('title','')}",
                "project_name":   r.get("project_name",""),
                "date":           datetime.now().strftime("%Y-%m-%d"),
                "vat_rate":       float(r.get("vat_rate", 7.0)),
                "shops":          shops,
                "shop_discounts": shop_discounts,
                "groups":         groups,
                "tags":           json.loads(r.get("tags","[]")) if r.get("tags") else [],
                "status":         "กำลังดำเนินการ",
            }
            return save_project(data, created_by)
    return None

def parse_project(r):
    try:    shops = json.loads(r.get("shops","[]"))
    except: shops = ["บริษัท A","บริษัท B","บริษัท C"]
    try:    shop_discounts = json.loads(r.get("shop_discounts","{}"))
    except: shop_discounts = {}
    try:
        groups = json.loads(r.get("groups","[]"))
        if not groups:
            old_items = json.loads(r.get("items","[]"))
            groups = [{"name":"กลุ่มที่ 1","items": old_items if old_items else []}]
    except:
        groups = [{"name":"กลุ่มที่ 1","items":[]}]
    return shops, shop_discounts, groups

# ===== Shops DB =====
def load_shops_db():
    try:    return get_ws("shops_db").get_all_records()
    except: return []

def save_shop_db(data, created_by, shop_id=None):
    ws  = get_ws("shops_db")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        shop_id or "",
        data["name"], data.get("contact",""), data.get("phone",""),
        data.get("email",""), data.get("address",""),
        data.get("payment_terms",""), data.get("notes",""),
        created_by, now
    ]
    if shop_id:
        records = ws.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("id")) == str(shop_id):
                ws.update(f"A{i+2}:J{i+2}", [row])
                return shop_id
    records = ws.get_all_records()
    new_id  = len(records) + 1
    row[0]  = new_id
    ws.append_row(row)
    return new_id

def delete_shop_db(shop_id):
    ws = get_ws("shops_db")
    for i, r in enumerate(ws.get_all_records()):
        if str(r.get("id")) == str(shop_id):
            ws.delete_rows(i + 2)
            return True
    return False

# ===== Templates =====
def load_templates():
    try:    return get_ws("templates").get_all_records()
    except: return []

def save_template(data, created_by, tmpl_id=None):
    ws  = get_ws("templates")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        tmpl_id or "",
        data["name"], data.get("category","ทั่วไป"),
        json.dumps(data["items"], ensure_ascii=False),
        created_by, now
    ]
    if tmpl_id:
        records = ws.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("id")) == str(tmpl_id):
                ws.update(f"A{i+2}:F{i+2}", [row])
                return tmpl_id
    records = ws.get_all_records()
    new_id  = len(records) + 1
    row[0]  = new_id
    ws.append_row(row)
    return new_id

def delete_template(tmpl_id):
    ws = get_ws("templates")
    for i, r in enumerate(ws.get_all_records()):
        if str(r.get("id")) == str(tmpl_id):
            ws.delete_rows(i + 2)
            return True
    return False

# ===== Google Drive Upload =====
def upload_to_drive(file_bytes, filename, mime_type):
    try:
        service     = get_drive_service()
        folder_id   = st.secrets.get("DRIVE_FOLDER_ID","")
        file_meta   = {"name": filename, "parents": [folder_id] if folder_id else []}
        media       = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type)
        uploaded    = service.files().create(body=file_meta, media_body=media, fields="id,webViewLink").execute()
        service.permissions().create(fileId=uploaded["id"],
                                     body={"role":"reader","type":"anyone"}).execute()
        return uploaded.get("webViewLink","")
    except Exception as e:
        return None

# ===== Calculation =====
def calc_group(items_data, shops, vat_rate, shop_disc):
    grand_sub = {s: 0.0 for s in shops}
    for it in items_data:
        qty = float(it.get("qty", 1))
        for s in shops:
            price = float(it["prices"].get(s, 0))
            # ส่วนลดต่อรายการ (%)
            item_disc_pct = float(it.get("item_discounts", {}).get(s, 0))
            price_after   = price * (1 - item_disc_pct / 100)
            grand_sub[s] += price_after * qty
    grand_disc       = {s: float(shop_disc.get(s, 0))               for s in shops}
    grand_after_disc = {s: max(grand_sub[s] - grand_disc[s], 0)      for s in shops}
    grand_vat        = {s: grand_after_disc[s] * vat_rate / 100      for s in shops}
    grand_total      = {s: grand_after_disc[s] + grand_vat[s]        for s in shops}
    return grand_sub, grand_disc, grand_after_disc, grand_vat, grand_total

# ===== Helpers =====
def new_group(idx):
    return {"name": f"กลุ่มที่ {idx}", "items": [], "discounts": {}}

def new_item(shops):
    return {
        "name": "สินค้าใหม่", "unit": "set", "qty": 1.0, "category": "วัสดุ",
        "prices":         {s: 0.0 for s in shops},
        "item_discounts": {s: 0.0 for s in shops},
        "notes":          {s: ""  for s in shops},
        "file_links":     {s: ""  for s in shops},
    }

STATUS_OPTIONS  = ["กำลังดำเนินการ","รออนุมัติ","อนุมัติแล้ว","ยกเลิก"]
STATUS_COLORS   = {"กำลังดำเนินการ":"#E6F1FB","รออนุมัติ":"#FAEEDA","อนุมัติแล้ว":"#E1F5EE","ยกเลิก":"#FCEBEB"}
STATUS_TEXT     = {"กำลังดำเนินการ":"#185FA5","รออนุมัติ":"#633806","อนุมัติแล้ว":"#085041","ยกเลิก":"#A32D2D"}
ITEM_CATEGORIES = ["วัสดุ/อุปกรณ์","ค่าแรง","ค่าขนส่ง","ค่าติดตั้ง","ค่าบริการ","อื่นๆ"]
