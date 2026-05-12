import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime
import io
import json

st.set_page_config(page_title="เปรียบเทียบราคา", page_icon="🛒", layout="wide")

st.markdown("""
<style>
.main-title{font-size:26px;font-weight:700;color:#1D9E75}
.subtitle{color:#6b7280;font-size:14px;margin-bottom:1rem}
</style>
""", unsafe_allow_html=True)

# ===== Google Sheets =====
@st.cache_resource
def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds  = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["SPREADSHEET_ID"])
    existing = [ws.title for ws in sh.worksheets()]
    if "projects" not in existing:
        ws = sh.add_worksheet("projects", 1000, 20)
        ws.append_row(["id","title","project_name","date","vat_rate",
                       "shops","shop_discounts","items","created_by","created_at"])
    return sh

def get_ws(name):
    return get_sheet().worksheet(name)

def load_projects():
    try:    return get_ws("projects").get_all_records()
    except: return []

def save_project(data, created_by, project_id=None):
    ws  = get_ws("projects")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        project_id or "",
        data["title"], data["project_name"], data["date"], data["vat_rate"],
        json.dumps(data["shops"],          ensure_ascii=False),
        json.dumps(data["shop_discounts"], ensure_ascii=False),
        json.dumps(data["items"],          ensure_ascii=False),
        created_by, now
    ]
    if project_id:
        records = ws.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("id")) == str(project_id):
                ws.update(f"A{i+2}:J{i+2}", [row])
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

def parse_project(r):
    try:    shops = json.loads(r.get("shops","[]"))
    except: shops = ["บริษัท A","บริษัท B","บริษัท C"]
    try:    shop_discounts = json.loads(r.get("shop_discounts","{}"))
    except: shop_discounts = {}
    try:    items = json.loads(r.get("items","[]"))
    except: items = []
    return shops, shop_discounts, items

# ===== คำนวณ (ใช้ TOTAL (INC. VAT) หลังหักส่วนลดแล้วเปรียบเทียบ) =====
def calc_summary(items_data, shops, vat_rate, shop_disc):
    grand_sub = {s: 0.0 for s in shops}
    for it in items_data:
        qty = float(it["qty"])
        for s in shops:
            grand_sub[s] += float(it["prices"].get(s, 0)) * qty
    grand_disc       = {s: float(shop_disc.get(s, 0))                  for s in shops}
    grand_after_disc = {s: grand_sub[s] - grand_disc[s]                 for s in shops}
    grand_vat        = {s: max(grand_after_disc[s],0)*vat_rate/100      for s in shops}
    grand_total      = {s: max(grand_after_disc[s],0)+grand_vat[s]      for s in shops}
    return grand_sub, grand_disc, grand_after_disc, grand_vat, grand_total

# ===== LOGIN =====
for k, v in [("logged_in",False),("username",""),("display_name","")]:
    if k not in st.session_state: st.session_state[k] = v

if not st.session_state["logged_in"]:
    st.markdown("<div class='main-title' style='text-align:center;margin-top:2rem'>🛒 ระบบเปรียบเทียบราคา</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle' style='text-align:center'>กรุณา Login ก่อนใช้งาน</div>", unsafe_allow_html=True)
    col = st.columns([1,1.2,1])[1]
    with col:
        with st.form("login_form"):
            st.markdown("### 🔐 เข้าสู่ระบบ")
            username  = st.text_input("Username")
            password  = st.text_input("Password", type="password")
            submitted = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)
            if submitted:
                users = st.secrets.get("users", {})
                if username in users and users[username]["password"] == password:
                    st.session_state.update({
                        "logged_in":True,
                        "username":username,
                        "display_name":users[username]["name"]
                    })
                    st.rerun()
                else:
                    st.error("Username หรือ Password ไม่ถูกต้อง")
    st.stop()

st.markdown(f"<div class='main-title'>🛒 ระบบเปรียบเทียบราคา</div>", unsafe_allow_html=True)
st.markdown(f"<div class='subtitle'>ยินดีต้อนรับ <b>{st.session_state['display_name']}</b></div>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"👤 **{st.session_state['display_name']}**")
    if st.button("🚪 ออกจากระบบ"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()
    st.divider()

for k, v in [("mode","list"),("current_project_id",None),
             ("shops",["บริษัท A","บริษัท B","บริษัท C"]),
             ("items_list",[]),("doc_title","เปรียบเทียบราคา"),
             ("project_name",""),("vat_rate",7.0),
             ("shop_discounts",{}),("doc_date",date.today())]:
    if k not in st.session_state: st.session_state[k] = v

def load_into_session(r):
    shops, shop_discounts, items = parse_project(r)
    st.session_state.update({
        "doc_title":r.get("title",""),
        "project_name":r.get("project_name",""),
        "vat_rate":float(r.get("vat_rate",7.0)),
        "shops":shops,"shop_discounts":shop_discounts,"items_list":items
    })
    try:    st.session_state["doc_date"] = datetime.strptime(r.get("date",""),"%Y-%m-%d").date()
    except: st.session_state["doc_date"] = date.today()

# ===================================================
# MODE: LIST
# ===================================================
if st.session_state["mode"] == "list":
    c1,c2 = st.columns([3,1])
    c1.markdown("## 📋 รายการเปรียบเทียบราคาทั้งหมด")
    if c2.button("➕ สร้างรายการใหม่", type="primary"):
        st.session_state.update({
            "mode":"new","current_project_id":None,
            "shops":["บริษัท A","บริษัท B","บริษัท C"],
            "items_list":[],"doc_title":"เปรียบเทียบราคา",
            "project_name":"","vat_rate":7.0,
            "shop_discounts":{},"doc_date":date.today()
        })
        st.rerun()

    with st.spinner("กำลังโหลดข้อมูล..."):
        projects = load_projects()

    if not projects:
        st.info("ยังไม่มีรายการ — กด 'สร้างรายการใหม่' เพื่อเริ่มต้นครับ")
    else:
        for r in reversed(projects):
            shops, _, items = parse_project(r)
            ca,cb,cc,cd = st.columns([3,1,1,1])
            ca.markdown(f"**{r.get('title','')}**  \n📁 {r.get('project_name','')}  \n🗓 {r.get('date','')} | 👤 {r.get('created_by','')}")
            cb.markdown(f"**{len(items)}** รายการ")
            cc.markdown(f"**{len(shops)}** ร้าน")
            with cd:
                if st.button("✏️ แก้ไข", key=f"e_{r['id']}"):
                    load_into_session(r)
                    st.session_state.update({"mode":"edit","current_project_id":r["id"]})
                    st.rerun()
                if st.button("🗑 ลบ", key=f"d_{r['id']}"):
                    delete_project(r["id"]); st.rerun()
            st.divider()

# ===================================================
# MODE: NEW / EDIT
# ===================================================
elif st.session_state["mode"] in ["new","edit"]:
    is_edit = st.session_state["mode"] == "edit"
    c1,c2   = st.columns([3,1])
    c1.markdown(f"## {'✏️ แก้ไขรายการ' if is_edit else '➕ สร้างรายการใหม่'}")
    if c2.button("← กลับ"):
        st.session_state["mode"] = "list"; st.rerun()

    with st.sidebar:
        st.header("⚙️ ตั้งค่าเอกสาร")
        st.session_state["doc_title"]    = st.text_input("ชื่อเอกสาร",  st.session_state["doc_title"])
        st.session_state["project_name"] = st.text_input("ชื่อโครงการ", st.session_state["project_name"])
        st.session_state["doc_date"]     = st.date_input("วันที่",       value=st.session_state["doc_date"])
        st.session_state["vat_rate"]     = st.number_input("VAT (%)",    value=st.session_state["vat_rate"],
                                                            min_value=0.0, max_value=30.0, step=0.5)
        st.divider()
        st.subheader("🏪 ร้านค้า / บริษัท")
        new_shops = []
        for i,s in enumerate(st.session_state["shops"]):
            new_shops.append(st.text_input(f"ร้านที่ {i+1}", s, key=f"shop_{i}"))
        st.session_state["shops"] = new_shops
        c1s,c2s = st.columns(2)
        if c1s.button("➕ เพิ่มร้าน"):
            st.session_state["shops"].append(f"บริษัท {chr(65+len(st.session_state['shops']))}"); st.rerun()
        if c2s.button("➖ ลบร้าน") and len(st.session_state["shops"]) > 2:
            st.session_state["shops"].pop(); st.rerun()
        st.divider()
        st.subheader("🎁 Special Discount (฿)")
        st.caption("หักก่อนคำนวณ VAT — ระบบเปรียบเทียบจาก TOTAL (INC. VAT) หลังหักส่วนลดแล้ว")
        for s in st.session_state["shops"]:
            cur = float(st.session_state["shop_discounts"].get(s,0.0))
            st.session_state["shop_discounts"][s] = st.number_input(
                f"{s}", value=cur, min_value=0.0, step=1.0, key=f"sd_{s}")

    tab1, tab2 = st.tabs(["✏️ กรอกข้อมูล","📊 ตารางเปรียบเทียบ"])

    # --- Tab 1 ---
    with tab1:
        if st.button("➕ เพิ่มรายการสินค้า"):
            st.session_state["items_list"].append({
                "name":"สินค้าใหม่","unit":"set","qty":1.0,
                "prices":{s:0.0 for s in st.session_state["shops"]},
                "notes":{s:"" for s in st.session_state["shops"]}
            })
            st.rerun()

        shops = st.session_state["shops"]
        vat   = st.session_state["vat_rate"]
        n     = len(st.session_state["items_list"])

        if n == 0:
            st.info("กด '➕ เพิ่มรายการสินค้า' เพื่อเริ่มกรอกข้อมูลครับ")
        else:
            to_del = None
            for idx in range(n):
                it = st.session_state["items_list"][idx]
                if "prices" not in it: it["prices"] = {s:0.0 for s in shops}
                if "notes"  not in it: it["notes"]  = {s:"" for s in shops}

                with st.expander(f"{idx+1}. {it['name']}", expanded=True):
                    ca,cb,cc,cd = st.columns([3,1,1,0.6])
                    st.session_state["items_list"][idx]["name"] = ca.text_input("ชื่อสินค้า", it["name"], key=f"n_{idx}")
                    st.session_state["items_list"][idx]["unit"] = cb.text_input("หน่วย",      it["unit"], key=f"u_{idx}")
                    st.session_state["items_list"][idx]["qty"]  = cc.number_input("จำนวน",
                        value=float(it["qty"]), min_value=0.0, step=1.0, key=f"q_{idx}")
                    if cd.button("🗑", key=f"d_{idx}"): to_del = idx

                    # หัวร้าน
                    hcols = st.columns(len(shops))
                    for si,s in enumerate(shops): hcols[si].markdown(f"**{s}**")

                    # ราคา
                    pcols = st.columns(len(shops))
                    for si,s in enumerate(shops):
                        cur = float(it["prices"].get(s,0))
                        val = pcols[si].number_input("Unit Price (฿)", value=cur,
                                                     min_value=0.0, step=1.0, key=f"p_{idx}_{si}")
                        st.session_state["items_list"][idx]["prices"][s] = val

                    # หมายเหตุ / เงื่อนไขพิเศษ
                    st.markdown("**📝 หมายเหตุ / เงื่อนไขพิเศษ**")
                    ncols = st.columns(len(shops))
                    for si,s in enumerate(shops):
                        cur_note = it["notes"].get(s,"")
                        val_note = ncols[si].text_area(
                            f"หมายเหตุ ({s})", value=cur_note,
                            placeholder="เช่น รับประกัน 1 ปี, ส่งฟรี, ราคารวมติดตั้ง",
                            height=80, key=f"note_{idx}_{si}")
                        st.session_state["items_list"][idx]["notes"][s] = val_note

                    # สรุปยอดต่อรายการ
                    st.markdown("---")
                    scols = st.columns(len(shops))
                    qty   = float(st.session_state["items_list"][idx]["qty"])
                    for si,s in enumerate(shops):
                        price    = float(st.session_state["items_list"][idx]["prices"].get(s,0))
                        subtotal = price * qty
                        scols[si].markdown(f"ยอดรวม: **฿{subtotal:,.2f}**")

            if to_del is not None:
                st.session_state["items_list"].pop(to_del); st.rerun()

        st.divider()
        if st.button("💾 บันทึกลง Google Sheets", type="primary"):
            project_data = {
                "title":st.session_state["doc_title"],
                "project_name":st.session_state["project_name"],
                "date":st.session_state["doc_date"].strftime("%Y-%m-%d"),
                "vat_rate":st.session_state["vat_rate"],
                "shops":st.session_state["shops"],
                "shop_discounts":st.session_state["shop_discounts"],
                "items":st.session_state["items_list"],
            }
            with st.spinner("กำลังบันทึก..."):
                pid = save_project(project_data, st.session_state["display_name"],
                                   st.session_state["current_project_id"])
                st.session_state.update({"current_project_id":pid,"mode":"edit"})
            st.success("✅ บันทึกเรียบร้อยแล้วครับ!")
            st.rerun()

    # --- Tab 2 ---
    with tab2:
        items_data = st.session_state["items_list"]
        shops      = st.session_state["shops"]
        vat        = st.session_state["vat_rate"]
        shop_disc  = st.session_state["shop_discounts"]
        doc_date   = st.session_state["doc_date"]

        if not items_data:
            st.info("ยังไม่มีข้อมูล — กรอกข้อมูลในแท็บ 'กรอกข้อมูล' ก่อนครับ")
        else:
            grand_sub, grand_disc, grand_after_disc, grand_vat, grand_total = calc_summary(
                items_data, shops, vat, shop_disc)

            # เปรียบเทียบจาก TOTAL (INC. VAT) หลังหักส่วนลดแล้ว
            valid = {s: grand_total[s] for s in shops if grand_sub[s] > 0}

            if valid:
                best = min(valid, key=valid.get)
                save = max(valid.values()) - min(valid.values())
                m1,m2,m3,m4 = st.columns(4)
                m1.metric("🏆 ร้านถูกสุด (หลังส่วนลด)", best)
                m2.metric("💰 ยอดสุทธิถูกสุด",           f"฿{valid[best]:,.2f}")
                m3.metric("✂️ ประหยัดได้",               f"฿{save:,.2f}")
                m4.metric("📋 จำนวนรายการ",              len(items_data))

            st.divider()

            # ตารางรายการ — เปรียบเทียบจากยอดรวมรายการ (ก่อนส่วนลด)
            rows = []
            for i,it in enumerate(items_data):
                qty = float(it["qty"])
                row = {"Item":i+1,"Detail":it["name"],"Q'TY":int(qty),"Unit":it["unit"]}
                tot_vals = []
                for s in shops:
                    price = float(it["prices"].get(s,0))
                    total = price * qty
                    row[f"{s} Unit Price"] = price
                    row[f"{s} Total"]      = round(total,2)
                    note = it.get("notes",{}).get(s,"")
                    row[f"{s} หมายเหตุ"]  = note
                    tot_vals.append(total)
                valid_tv = [v for v in tot_vals if v > 0]
                if valid_tv:
                    row["ถูกสุด(ก่อนส่วนลด)"] = shops[tot_vals.index(min(valid_tv))]
                rows.append(row)

            df = pd.DataFrame(rows)
            price_cols = [c for c in df.columns if "Unit Price" in str(c) or ("Total" in str(c) and "หมายเหตุ" not in str(c))]

            def hi(row):
                tc = [c for c in row.index if "Total" in str(c) and "หมายเหตุ" not in str(c)]
                styles = [""]*len(row)
                vals = {c:float(row[c]) for c in tc if float(row[c])>0}
                if not vals: return styles
                mn = min(vals.values())
                for i,col in enumerate(row.index):
                    if col in tc and float(row[col])==mn and float(row[col])>0:
                        styles[i]="background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                    elif col in tc and float(row[col])>mn:
                        styles[i]="color:#dc2626"
                return styles

            fmt = {c:"฿{:,.2f}" for c in df.columns if "Price" in str(c) or ("Total" in str(c) and "หมายเหตุ" not in str(c))}
            st.dataframe(df.style.apply(hi,axis=1).format(fmt),
                         use_container_width=True, hide_index=True)

            st.divider()

            # สรุปยอดรวม
            st.subheader("📋 สรุปยอดรวม (เปรียบเทียบจาก TOTAL INC. VAT หลังหักส่วนลด)")
            sum_rows = [
                ("ยอดรวมก่อนส่วนลด",  grand_sub,        False),
                ("SPECIAL DISCOUNT (-)",grand_disc,       True),
                ("TOTAL (EXC. VAT)",   grand_after_disc, False),
                (f"VAT {vat:.0f}%",    grand_vat,        False),
                ("TOTAL (INC. VAT)",   grand_total,      False),
            ]
            hcols = st.columns([2]+[1]*len(shops))
            hcols[0].markdown("**รายการ**")
            for si,s in enumerate(shops):
                lbl = "🏆 " if valid and s==best else ""
                hcols[si+1].markdown(f"**{lbl}{s}**")

            for label,vals,is_disc in sum_rows:
                rcols = st.columns([2]+[1]*len(shops))
                rcols[0].markdown(f"**{label}**")
                for si,s in enumerate(shops):
                    v       = vals.get(s,0)
                    is_best = label=="TOTAL (INC. VAT)" and valid and s==best
                    disp    = f"-฿{v:,.2f}" if is_disc else f"฿{v:,.2f}"
                    if is_best: rcols[si+1].success(f"**{disp}**")
                    else:       rcols[si+1].markdown(disp)

            st.divider()

            # ===== Export Excel =====
            def export_excel():
                from openpyxl import Workbook
                from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
                from openpyxl.utils import get_column_letter

                wb = Workbook(); ws = wb.active; ws.title="เปรียบเทียบราคา"
                GREEN="1D9E75"; GL="E1F5EE"; WHITE="FFFFFF"; DARK="1E293B"
                BEST="BBFFD9"; AMBER="FEF9C3"; GRAY="F1F5F9"; NOTE_BG="FFFBEB"
                shop_colors=[("1D6B9A","E8F4FD"),("B45309","FEF9C3"),
                             ("166534","F0FDF4"),("9A3412","FFF7ED"),("6D28D9","F5F3FF")]
                thin=Side(style="thin",color="CBD5E1")
                med =Side(style="medium",color="94A3B8")
                bdr =Border(left=thin,right=thin,top=thin,bottom=thin)
                bdr_med=Border(left=med,right=med,top=med,bottom=med)

                def cs(r,c,val="",bold=False,color=DARK,bg=None,align="left",
                       fmt=None,border=None,size=11,wrap=False):
                    cell=ws.cell(row=r,column=c,value=val)
                    cell.font=Font(bold=bold,color=color,size=size,name="Tahoma")
                    if bg: cell.fill=PatternFill("solid",fgColor=bg)
                    cell.alignment=Alignment(horizontal=align,vertical="center",wrap_text=wrap)
                    if fmt: cell.number_format=fmt
                    cell.border=border or bdr
                    return cell

                n_shops=len(shops)
                # คอลัมน์: Item(1) Detail(2) QTY(3) Unit(4) แล้ว Unit Price+Total+หมายเหตุ ต่อร้าน
                SHOP_START=5
                COLS_PER_SHOP=3  # Unit Price, Total, หมายเหตุ
                total_cols=SHOP_START+n_shops*COLS_PER_SHOP-1

                # แถว 1
                ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=total_cols)
                t=ws.cell(row=1,column=1,value=f"เปรียบเทียบราคา {st.session_state['project_name']}")
                t.font=Font(bold=True,size=16,color=GREEN,name="Tahoma")
                t.alignment=Alignment(horizontal="center",vertical="center")
                ws.row_dimensions[1].height=30

                # แถว 2
                ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=total_cols)
                d=ws.cell(row=2,column=1,
                          value=f"วันที่ {doc_date.strftime('%d/%m/%Y')}    VAT {vat:.0f}%    เอกสาร: {st.session_state['doc_title']}")
                d.font=Font(size=10,color="64748B",name="Tahoma")
                d.alignment=Alignment(horizontal="center")
                ws.row_dimensions[2].height=18
                ws.row_dimensions[3].height=8

                # header row 4-5
                for c,label in [(1,"Item"),(2,"Detail"),(3,"Q'TY"),(4,"Unit")]:
                    ws.merge_cells(start_row=4,start_column=c,end_row=5,end_column=c)
                    cs(4,c,label,bold=True,color=WHITE,bg=GREEN,align="center",border=bdr_med,size=10,wrap=True)

                for si,shop in enumerate(shops):
                    col_up  = SHOP_START+si*COLS_PER_SHOP
                    col_tot = col_up+1
                    col_note= col_up+2
                    hc,lc   = shop_colors[si%5]
                    ws.merge_cells(start_row=4,start_column=col_up,end_row=4,end_column=col_note)
                    cs(4,col_up,shop,bold=True,color=WHITE,bg=hc,align="center",border=bdr_med,size=10,wrap=True)
                    cs(5,col_up,  "Unit Price", bold=True,color=DARK,bg=lc,align="center",border=bdr,size=9)
                    cs(5,col_tot, "Total",      bold=True,color=DARK,bg=lc,align="center",border=bdr,size=9)
                    cs(5,col_note,"หมายเหตุ",  bold=True,color=DARK,bg=lc,align="center",border=bdr,size=9)

                ws.row_dimensions[4].height=22; ws.row_dimensions[5].height=18

                # data rows
                row=6; stripe=["FFFFFF","F8FAFC"]
                for i,it in enumerate(items_data):
                    qty=float(it["qty"]); bg=stripe[i%2]
                    cs(row,1,i+1,align="center",bg=bg)
                    cs(row,2,it["name"],align="left",bg=bg,wrap=True)
                    cs(row,3,int(qty),align="center",bg=bg)
                    cs(row,4,it["unit"],align="center",bg=bg)

                    tot_vals=[float(it["prices"].get(s,0))*qty for s in shops]
                    valid_tv=[v for v in tot_vals if v>0]
                    best_p=min(valid_tv) if valid_tv else None

                    for si,shop in enumerate(shops):
                        col_up  = SHOP_START+si*COLS_PER_SHOP
                        col_tot = col_up+1
                        col_note= col_up+2
                        price=float(it["prices"].get(shop,0)); total=price*qty
                        note=it.get("notes",{}).get(shop,"")
                        is_b=best_p and total==best_p and total>0
                        cell_bg=BEST if is_b else bg
                        cs(row,col_up, price,align="right",bg=cell_bg,fmt='#,##0.00',bold=is_b)
                        cs(row,col_tot,total,align="right",bg=cell_bg,fmt='#,##0.00',bold=is_b)
                        cs(row,col_note,note,align="left",bg=NOTE_BG if note else bg,wrap=True,size=9)

                    ws.row_dimensions[row].height=20; row+=1

                # summary
                best_idx=shops.index(best) if valid else None
                sum_defs=[
                    ("ยอดรวมก่อนส่วนลด", grand_sub,        GRAY, False, False),
                    ("SPECIAL DISCOUNT",  grand_disc,       AMBER,False, True),
                    ("TOTAL (EXC. VAT)",  grand_after_disc, GRAY, True,  False),
                    (f"VAT {vat:.0f}%",   grand_vat,        GRAY, False, False),
                    ("TOTAL (INC. VAT)",  grand_total,      GL,   True,  False),
                ]
                for label,vals,sbg,sbold,is_disc in sum_defs:
                    ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=4)
                    cs(row,1,label,bold=sbold,align="right",bg=sbg,size=10)
                    for si,shop in enumerate(shops):
                        col_up  = SHOP_START+si*COLS_PER_SHOP
                        col_end = col_up+COLS_PER_SHOP-1
                        v=vals.get(shop,0)
                        is_b=label=="TOTAL (INC. VAT)" and si==best_idx
                        cell_bg=BEST if is_b else sbg
                        disp=-v if is_disc else v
                        ws.merge_cells(start_row=row,start_column=col_up,end_row=row,end_column=col_end)
                        cs(row,col_up,disp,bold=sbold or is_b,align="right",bg=cell_bg,fmt='#,##0.00',size=10)
                    ws.row_dimensions[row].height=18; row+=1

                # column widths
                ws.column_dimensions[get_column_letter(1)].width=6
                ws.column_dimensions[get_column_letter(2)].width=36
                ws.column_dimensions[get_column_letter(3)].width=7
                ws.column_dimensions[get_column_letter(4)].width=8
                for si in range(n_shops):
                    base=SHOP_START+si*COLS_PER_SHOP
                    ws.column_dimensions[get_column_letter(base)].width=13
                    ws.column_dimensions[get_column_letter(base+1)].width=13
                    ws.column_dimensions[get_column_letter(base+2)].width=22
                ws.freeze_panes="E6"

                out=io.BytesIO(); wb.save(out); out.seek(0)
                return out.getvalue()

            # ===== Export PDF (via HTML print) =====
            def export_pdf_html():
                shop_headers = ""
                for s in shops:
                    shop_headers += f'<th colspan="3">{s}</th>'

                sub_headers = ""
                for s in shops:
                    sub_headers += "<th>Unit Price</th><th>Total</th><th>หมายเหตุ</th>"

                item_rows = ""
                for i,it in enumerate(items_data):
                    qty=float(it["qty"])
                    tot_vals=[float(it["prices"].get(s,0))*qty for s in shops]
                    valid_tv=[v for v in tot_vals if v>0]
                    best_p=min(valid_tv) if valid_tv else None
                    bg = "#f9fafb" if i%2==1 else "#ffffff"
                    cols = f'<td style="text-align:center">{i+1}</td>'
                    cols += f'<td>{it["name"]}</td>'
                    cols += f'<td style="text-align:center">{int(qty)}</td>'
                    cols += f'<td style="text-align:center">{it["unit"]}</td>'
                    for s in shops:
                        price=float(it["prices"].get(s,0))
                        total=price*qty
                        note=it.get("notes",{}).get(s,"")
                        is_b=best_p and total==best_p and total>0
                        cell_style='style="background:#bbf7d0;font-weight:bold"' if is_b else ''
                        cols += f'<td {cell_style} style="text-align:right">฿{price:,.2f}</td>'
                        cols += f'<td {cell_style} style="text-align:right">฿{total:,.2f}</td>'
                        cols += f'<td style="font-size:10px;color:#555">{note}</td>'
                    item_rows += f'<tr style="background:{bg}">{cols}</tr>'

                sum_section = ""
                sum_defs2 = [
                    ("ยอดรวมก่อนส่วนลด", grand_sub,        False, False),
                    ("SPECIAL DISCOUNT",  grand_disc,       True,  False),
                    ("TOTAL (EXC. VAT)",  grand_after_disc, False, True),
                    (f"VAT {vat:.0f}%",   grand_vat,        False, False),
                    ("TOTAL (INC. VAT)",  grand_total,      False, True),
                ]
                best_idx2 = shops.index(best) if valid else None
                for label,vals,is_disc,is_bold in sum_defs2:
                    row_html = f'<td colspan="4" style="text-align:right;padding:6px 8px;font-weight:{"bold" if is_bold else "normal"}">{label}</td>'
                    for si,s in enumerate(shops):
                        v=vals.get(s,0)
                        disp=f"-฿{v:,.2f}" if is_disc else f"฿{v:,.2f}"
                        is_b=label=="TOTAL (INC. VAT)" and si==best_idx2
                        cell_style="background:#bbf7d0;font-weight:bold;color:#064e3b" if is_b else ""
                        row_html += f'<td colspan="3" style="text-align:right;padding:6px 8px;{cell_style};font-weight:{"bold" if is_bold else "normal"}">{disp}</td>'
                    sum_section += f"<tr>{row_html}</tr>"

                html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{st.session_state['doc_title']}</title>
<style>
  body{{font-family:Tahoma,sans-serif;font-size:12px;color:#1e293b;margin:20px}}
  h1{{font-size:18px;color:#1D9E75;text-align:center;margin-bottom:4px}}
  .sub{{text-align:center;color:#6b7280;font-size:11px;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse;margin-top:8px}}
  th{{background:#1D9E75;color:white;padding:7px 8px;font-size:11px}}
  td{{padding:6px 8px;border-bottom:1px solid #e2e8f0}}
  .sum-table th{{background:#f1f5f9;color:#1e293b}}
  @media print{{body{{margin:10px}}button{{display:none}}}}
</style></head><body>
<h1>เปรียบเทียบราคา {st.session_state['project_name']}</h1>
<div class="sub">วันที่ {doc_date.strftime('%d/%m/%Y')} &nbsp;|&nbsp; VAT {vat:.0f}% &nbsp;|&nbsp; เอกสาร: {st.session_state['doc_title']}</div>
<table>
  <thead>
    <tr><th rowspan="2">Item</th><th rowspan="2">Detail</th>
        <th rowspan="2">Q'TY</th><th rowspan="2">Unit</th>{shop_headers}</tr>
    <tr>{sub_headers}</tr>
  </thead>
  <tbody>{item_rows}</tbody>
</table>
<br>
<table class="sum-table">
  <thead><tr><th colspan="4">รายการ</th>
  {"".join(f'<th colspan="3">{s}</th>' for s in shops)}</tr></thead>
  <tbody>{sum_section}</tbody>
</table>
<br>
<button onclick="window.print()" style="padding:8px 20px;background:#1D9E75;color:white;border:none;border-radius:6px;cursor:pointer;font-size:13px">🖨️ พิมพ์ / บันทึก PDF</button>
</body></html>"""
                return html.encode("utf-8")

            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                excel_data = export_excel()
                st.download_button(
                    "📊 ดาวน์โหลด Excel",
                    data=excel_data,
                    file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col_ex2:
                pdf_html = export_pdf_html()
                st.download_button(
                    "🖨️ ดาวน์โหลด HTML → พิมพ์เป็น PDF",
                    data=pdf_html,
                    file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.html",
                    mime="text/html",
                    use_container_width=True
                )
                st.caption("เปิดไฟล์ในเบราว์เซอร์ → กดปุ่ม 'พิมพ์' → เลือก Save as PDF")
