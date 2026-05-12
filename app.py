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
.login-box{max-width:400px;margin:80px auto;padding:2rem;
           border:1px solid #e5e7eb;border-radius:16px;
           background:white;box-shadow:0 4px 24px rgba(0,0,0,0.08)}
</style>
""", unsafe_allow_html=True)

# ===== Google Sheets Connection =====
@st.cache_resource
def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["SPREADSHEET_ID"])

    # สร้าง worksheets ถ้ายังไม่มี
    existing = [ws.title for ws in sh.worksheets()]
    if "projects" not in existing:
        ws = sh.add_worksheet("projects", 1000, 20)
        ws.append_row(["id","title","project_name","date","vat_rate",
                        "shops","shop_discounts","items","created_by","created_at"])
    return sh

def get_ws(name):
    sh = get_sheet()
    return sh.worksheet(name)

def load_projects():
    try:
        ws = get_ws("projects")
        data = ws.get_all_records()
        return data
    except:
        return []

def save_project(project_data, created_by, project_id=None):
    ws = get_ws("projects")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if project_id:
        # update
        records = ws.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("id")) == str(project_id):
                row_num = i + 2
                ws.update(f"A{row_num}:J{row_num}", [[
                    project_id,
                    project_data["title"],
                    project_data["project_name"],
                    project_data["date"],
                    project_data["vat_rate"],
                    json.dumps(project_data["shops"], ensure_ascii=False),
                    json.dumps(project_data["shop_discounts"], ensure_ascii=False),
                    json.dumps(project_data["items"], ensure_ascii=False),
                    created_by,
                    now
                ]])
                return project_id
    else:
        # new
        all_data = ws.get_all_records()
        new_id = len(all_data) + 1
        ws.append_row([
            new_id,
            project_data["title"],
            project_data["project_name"],
            project_data["date"],
            project_data["vat_rate"],
            json.dumps(project_data["shops"], ensure_ascii=False),
            json.dumps(project_data["shop_discounts"], ensure_ascii=False),
            json.dumps(project_data["items"], ensure_ascii=False),
            created_by,
            now
        ])
        return new_id

def delete_project(project_id):
    ws = get_ws("projects")
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if str(r.get("id")) == str(project_id):
            ws.delete_rows(i + 2)
            return True
    return False

def parse_project(r):
    try:
        shops = json.loads(r.get("shops","[]"))
    except:
        shops = ["ร้าน A","ร้าน B","ร้าน C"]
    try:
        shop_discounts = json.loads(r.get("shop_discounts","{}"))
    except:
        shop_discounts = {}
    try:
        items = json.loads(r.get("items","[]"))
    except:
        items = []
    return shops, shop_discounts, items

# ===== LOGIN =====
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "display_name" not in st.session_state:
    st.session_state["display_name"] = ""

if not st.session_state["logged_in"]:
    st.markdown("<div class='main-title' style='text-align:center;margin-top:2rem'>🛒 ระบบเปรียบเทียบราคา</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle' style='text-align:center'>กรุณา Login ก่อนใช้งาน</div>", unsafe_allow_html=True)

    col = st.columns([1,1.2,1])[1]
    with col:
        with st.form("login_form"):
            st.markdown("### 🔐 เข้าสู่ระบบ")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)

            if submitted:
                users = st.secrets.get("users", {})
                if username in users and users[username]["password"] == password:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.session_state["display_name"] = users[username]["name"]
                    st.rerun()
                else:
                    st.error("Username หรือ Password ไม่ถูกต้อง")
    st.stop()

# ===== MAIN APP (หลัง login) =====
st.markdown(f"<div class='main-title'>🛒 ระบบเปรียบเทียบราคา</div>", unsafe_allow_html=True)
st.markdown(f"<div class='subtitle'>ยินดีต้อนรับ <b>{st.session_state['display_name']}</b></div>", unsafe_allow_html=True)

# logout
with st.sidebar:
    st.markdown(f"👤 **{st.session_state['display_name']}**")
    if st.button("🚪 ออกจากระบบ"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.divider()

# ===== Session State =====
if "mode" not in st.session_state:
    st.session_state["mode"] = "list"  # list / edit / new
if "current_project_id" not in st.session_state:
    st.session_state["current_project_id"] = None
if "shops" not in st.session_state:
    st.session_state["shops"] = ["บริษัท A","บริษัท B","บริษัท C"]
if "items_list" not in st.session_state:
    st.session_state["items_list"] = []
if "doc_title" not in st.session_state:
    st.session_state["doc_title"] = "เปรียบเทียบราคา"
if "project_name" not in st.session_state:
    st.session_state["project_name"] = ""
if "vat_rate" not in st.session_state:
    st.session_state["vat_rate"] = 7.0
if "shop_discounts" not in st.session_state:
    st.session_state["shop_discounts"] = {}
if "doc_date" not in st.session_state:
    st.session_state["doc_date"] = date.today()

def calc(price, qty, vat_rate):
    subtotal = price * qty
    vat_amt  = subtotal * vat_rate / 100
    return subtotal, vat_amt, subtotal + vat_amt

def load_into_session(r):
    shops, shop_discounts, items = parse_project(r)
    st.session_state["doc_title"]       = r.get("title","")
    st.session_state["project_name"]    = r.get("project_name","")
    st.session_state["vat_rate"]        = float(r.get("vat_rate", 7.0))
    st.session_state["shops"]           = shops
    st.session_state["shop_discounts"]  = shop_discounts
    st.session_state["items_list"]      = items
    try:
        st.session_state["doc_date"] = datetime.strptime(r.get("date",""), "%Y-%m-%d").date()
    except:
        st.session_state["doc_date"] = date.today()

# ===== MODE: LIST =====
if st.session_state["mode"] == "list":
    col1, col2 = st.columns([3,1])
    col1.markdown("## 📋 รายการเปรียบเทียบราคาทั้งหมด")
    if col2.button("➕ สร้างรายการใหม่", type="primary"):
        st.session_state["mode"] = "new"
        st.session_state["current_project_id"] = None
        st.session_state["shops"] = ["บริษัท A","บริษัท B","บริษัท C"]
        st.session_state["items_list"] = []
        st.session_state["doc_title"] = "เปรียบเทียบราคา"
        st.session_state["project_name"] = ""
        st.session_state["vat_rate"] = 7.0
        st.session_state["shop_discounts"] = {}
        st.session_state["doc_date"] = date.today()
        st.rerun()

    with st.spinner("กำลังโหลดข้อมูล..."):
        projects = load_projects()

    if not projects:
        st.info("ยังไม่มีรายการ — กด 'สร้างรายการใหม่' เพื่อเริ่มต้นครับ")
    else:
        for r in reversed(projects):
            shops, _, items = parse_project(r)
            with st.container():
                ca, cb, cc, cd = st.columns([3,1,1,1])
                ca.markdown(f"**{r.get('title','')}**  \n📁 {r.get('project_name','')}  \n🗓 {r.get('date','')} | 👤 {r.get('created_by','')}")
                cb.markdown(f"**{len(items)}** รายการ")
                cc.markdown(f"**{len(shops)}** ร้าน")
                with cd:
                    if st.button("✏️ แก้ไข", key=f"edit_{r['id']}"):
                        load_into_session(r)
                        st.session_state["mode"] = "edit"
                        st.session_state["current_project_id"] = r["id"]
                        st.rerun()
                    if st.button("🗑 ลบ", key=f"del_{r['id']}"):
                        delete_project(r["id"])
                        st.rerun()
                st.divider()

# ===== MODE: NEW / EDIT =====
elif st.session_state["mode"] in ["new","edit"]:
    is_edit = st.session_state["mode"] == "edit"
    title_text = "✏️ แก้ไขรายการ" if is_edit else "➕ สร้างรายการใหม่"

    col1, col2 = st.columns([3,1])
    col1.markdown(f"## {title_text}")
    if col2.button("← กลับ"):
        st.session_state["mode"] = "list"
        st.rerun()

    # Sidebar settings
    with st.sidebar:
        st.header("⚙️ ตั้งค่าเอกสาร")
        st.session_state["doc_title"]    = st.text_input("ชื่อเอกสาร", st.session_state["doc_title"])
        st.session_state["project_name"] = st.text_input("ชื่อโครงการ", st.session_state["project_name"])
        st.session_state["doc_date"]     = st.date_input("วันที่", value=st.session_state["doc_date"])
        st.session_state["vat_rate"]     = st.number_input("VAT (%)", value=st.session_state["vat_rate"],
                                                            min_value=0.0, max_value=30.0, step=0.5)
        st.divider()
        st.subheader("🏪 ร้านค้า / บริษัท")
        new_shops = []
        for i, s in enumerate(st.session_state["shops"]):
            new_shops.append(st.text_input(f"ร้านที่ {i+1}", s, key=f"shop_{i}"))
        st.session_state["shops"] = new_shops
        c1, c2 = st.columns(2)
        if c1.button("➕"):
            st.session_state["shops"].append(f"บริษัท {chr(65+len(st.session_state['shops']))}")
            st.rerun()
        if c2.button("➖") and len(st.session_state["shops"]) > 2:
            st.session_state["shops"].pop()
            st.rerun()

        st.divider()
        st.subheader("🎁 Special Discount (฿)")
        for s in st.session_state["shops"]:
            cur = float(st.session_state["shop_discounts"].get(s, 0.0))
            st.session_state["shop_discounts"][s] = st.number_input(
                f"{s}", value=cur, min_value=0.0, step=1.0, key=f"sd_{s}")

    tab1, tab2 = st.tabs(["✏️ กรอกข้อมูล","📊 ตารางเปรียบเทียบ"])

    with tab1:
        sa, sb = st.columns([1,4])
        if sa.button("➕ เพิ่มรายการ"):
            st.session_state["items_list"].append({
                "name":"สินค้าใหม่","unit":"set","qty":1.0,
                "prices":{s:0.0 for s in st.session_state["shops"]}
            })
            st.rerun()

        n = len(st.session_state["items_list"])
        if n == 0:
            st.info("กด '➕ เพิ่มรายการ' เพื่อเริ่มกรอกข้อมูลครับ")
        else:
            to_del = None
            shops = st.session_state["shops"]
            vat   = st.session_state["vat_rate"]
            for idx in range(n):
                it = st.session_state["items_list"][idx]
                if "prices" not in it:
                    it["prices"] = {s:0.0 for s in shops}
                with st.expander(f"{idx+1}. {it['name']}", expanded=True):
                    ca,cb,cc,cd = st.columns([3,1,1,0.6])
                    st.session_state["items_list"][idx]["name"] = ca.text_input("ชื่อสินค้า", it["name"], key=f"n_{idx}")
                    st.session_state["items_list"][idx]["unit"] = cb.text_input("หน่วย", it["unit"], key=f"u_{idx}")
                    st.session_state["items_list"][idx]["qty"]  = cc.number_input("จำนวน", value=float(it["qty"]), min_value=0.0, step=1.0, key=f"q_{idx}")
                    if cd.button("🗑", key=f"d_{idx}"):
                        to_del = idx

                    hcols = st.columns(len(shops))
                    for si, shop in enumerate(shops):
                        hcols[si].markdown(f"**{shop}**")

                    pcols = st.columns(len(shops))
                    for si, shop in enumerate(shops):
                        cur = float(it["prices"].get(shop, 0))
                        val = pcols[si].number_input("Unit Price (฿)", value=cur, min_value=0.0, step=1.0, key=f"p_{idx}_{si}")
                        st.session_state["items_list"][idx]["prices"][shop] = val

                    st.markdown("---")
                    scols = st.columns(len(shops))
                    qty = float(st.session_state["items_list"][idx]["qty"])
                    for si, shop in enumerate(shops):
                        price = float(st.session_state["items_list"][idx]["prices"].get(shop, 0))
                        sub, vat_a, total = calc(price, qty, vat)
                        scols[si].markdown(
                            f"ก่อน VAT: **฿{sub:,.2f}**  \n"
                            f"VAT {vat:.0f}%: ฿{vat_a:,.2f}  \n"
                            f"รวม: **฿{total:,.2f}**"
                        )
            if to_del is not None:
                st.session_state["items_list"].pop(to_del)
                st.rerun()

        st.divider()
        # ปุ่ม Save
        if st.button("💾 บันทึกลง Google Sheets", type="primary"):
            project_data = {
                "title":          st.session_state["doc_title"],
                "project_name":   st.session_state["project_name"],
                "date":           st.session_state["doc_date"].strftime("%Y-%m-%d"),
                "vat_rate":       st.session_state["vat_rate"],
                "shops":          st.session_state["shops"],
                "shop_discounts": st.session_state["shop_discounts"],
                "items":          st.session_state["items_list"],
            }
            with st.spinner("กำลังบันทึก..."):
                pid = save_project(project_data, st.session_state["display_name"],
                                   st.session_state["current_project_id"])
                st.session_state["current_project_id"] = pid
                st.session_state["mode"] = "edit"
            st.success("✅ บันทึกเรียบร้อยแล้วครับ!")
            st.rerun()

    with tab2:
        items_data  = st.session_state["items_list"]
        shops       = st.session_state["shops"]
        vat         = st.session_state["vat_rate"]
        shop_disc   = st.session_state["shop_discounts"]
        doc_date    = st.session_state["doc_date"]

        if len(items_data) == 0:
            st.info("ยังไม่มีข้อมูล")
        else:
            grand_sub  = {s:0.0 for s in shops}
            for it in items_data:
                qty = float(it["qty"])
                for s in shops:
                    grand_sub[s] += float(it["prices"].get(s,0)) * qty

            grand_vat   = {s: grand_sub[s] * vat/100 for s in shops}
            grand_tot   = {s: grand_sub[s] + grand_vat[s] for s in shops}
            grand_disc  = {s: float(shop_disc.get(s,0)) for s in shops}
            net_total   = {s: grand_tot[s] - grand_disc[s] for s in shops}
            valid_net   = {k:v for k,v in net_total.items() if grand_sub[k]>0}

            if valid_net:
                best = min(valid_net, key=valid_net.get)
                save = max(valid_net.values()) - min(valid_net.values())
                m1,m2,m3,m4 = st.columns(4)
                m1.metric("🏆 ร้านถูกสุด", best)
                m2.metric("💰 ยอดสุทธิถูกสุด", f"฿{valid_net[best]:,.2f}")
                m3.metric("✂️ ประหยัดได้", f"฿{save:,.2f}")
                m4.metric("📋 รายการ", len(items_data))

            st.divider()

            # ตารางรายการ
            rows = []
            for i, it in enumerate(items_data):
                qty = float(it["qty"])
                row = {"Item":i+1,"Detail":it["name"],"Q'TY":int(qty),"Unit":it["unit"]}
                tot_vals = []
                for s in shops:
                    price = float(it["prices"].get(s,0))
                    sub, _, total = calc(price, qty, vat)
                    row[f"{s} Unit Price"] = price
                    row[f"{s} Total"]      = round(total, 2)
                    tot_vals.append(total)
                valid_tv = [v for v in tot_vals if v>0]
                if valid_tv:
                    row["ถูกสุด"] = shops[tot_vals.index(min(valid_tv))]
                rows.append(row)

            df = pd.DataFrame(rows)

            def hi(row):
                tc = [c for c in row.index if "Total" in str(c)]
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

            fmt = {c:"฿{:,.2f}" for c in df.columns if "Price" in str(c) or "Total" in str(c)}
            st.dataframe(df.style.apply(hi,axis=1).format(fmt),
                         use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("📋 สรุปยอดรวม")
            sum_rows = [
                ("SPECIAL DISCOUNT", grand_disc),
                ("TOTAL (EXC. VAT)", grand_sub),
                (f"VAT {vat:.0f}%",  grand_vat),
                ("TOTAL (INC. VAT)", grand_tot),
                ("NET TOTAL",        net_total),
            ]
            hcols = st.columns([2]+[1]*len(shops))
            hcols[0].markdown("**รายการ**")
            for si,s in enumerate(shops):
                lbl = "🏆 " if valid_net and s==best else ""
                hcols[si+1].markdown(f"**{lbl}{s}**")

            for label, vals in sum_rows:
                rcols = st.columns([2]+[1]*len(shops))
                rcols[0].markdown(f"**{label}**")
                for si,s in enumerate(shops):
                    v = vals.get(s,0)
                    is_best = label=="NET TOTAL" and valid_net and s==best
                    if is_best:
                        rcols[si+1].success(f"**฿{v:,.2f}**")
                    else:
                        rcols[si+1].markdown(f"฿{v:,.2f}")

            # Export Excel
            st.divider()
            def export_excel():
                from openpyxl import Workbook
                from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
                from openpyxl.utils import get_column_letter

                wb  = Workbook()
                ws  = wb.active
                ws.title = "เปรียบเทียบราคา"

                GREEN="1D9E75"; GL="E1F5EE"; WHITE="FFFFFF"; DARK="1E293B"
                BEST="BBFFD9"; AMBER="FEF9C3"; GRAY="F1F5F9"
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
                SHOP_START=5
                total_cols=SHOP_START+n_shops*2-1

                # แถว 1: ชื่อ
                ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=total_cols)
                t=ws.cell(row=1,column=1,
                           value=f"เปรียบเทียบราคา {st.session_state['project_name']}")
                t.font=Font(bold=True,size=16,color=GREEN,name="Tahoma")
                t.alignment=Alignment(horizontal="center",vertical="center")
                ws.row_dimensions[1].height=30

                # แถว 2: วันที่
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
                    col_up=SHOP_START+si*2; col_tot=col_up+1
                    hc,lc=shop_colors[si%5]
                    ws.merge_cells(start_row=4,start_column=col_up,end_row=4,end_column=col_tot)
                    cs(4,col_up,shop,bold=True,color=WHITE,bg=hc,align="center",border=bdr_med,size=10,wrap=True)
                    cs(5,col_up,"Unit Price",bold=True,color=DARK,bg=lc,align="center",border=bdr,size=9)
                    cs(5,col_tot,"Total",bold=True,color=DARK,bg=lc,align="center",border=bdr,size=9)

                ws.row_dimensions[4].height=22
                ws.row_dimensions[5].height=18

                # data rows
                row=6
                stripe=["FFFFFF","F8FAFC"]
                for i,it in enumerate(items_data):
                    qty=float(it["qty"]); bg=stripe[i%2]
                    cs(row,1,i+1,align="center",bg=bg)
                    cs(row,2,it["name"],align="left",bg=bg,wrap=True)
                    cs(row,3,int(qty),align="center",bg=bg)
                    cs(row,4,it["unit"],align="center",bg=bg)

                    tot_vals=[float(it["prices"].get(s,0))*qty for s in shops]
                    valid_tv=[v for v in tot_vals if v>0]
                    best_price=min(valid_tv) if valid_tv else None

                    for si,shop in enumerate(shops):
                        col_up=SHOP_START+si*2; col_tot=col_up+1
                        price=float(it["prices"].get(shop,0)); total=price*qty
                        is_b=best_price and total==best_price and total>0
                        cell_bg=BEST if is_b else bg
                        cs(row,col_up,price,align="right",bg=cell_bg,fmt='#,##0.00',bold=is_b)
                        cs(row,col_tot,total,align="right",bg=cell_bg,fmt='#,##0.00',bold=is_b)
                    ws.row_dimensions[row].height=20
                    row+=1

                # summary rows
                sum_defs=[
                    ("SPECIAL DISCOUNT",grand_disc,AMBER,False),
                    ("TOTAL (EXC. VAT)",grand_sub,GRAY,True),
                    (f"VAT {vat:.0f}%",grand_vat,GRAY,False),
                    ("TOTAL (INC. VAT)",grand_tot,GRAY,True),
                    ("NET TOTAL",net_total,GL,True),
                ]
                best_idx=shops.index(best) if valid_net else None
                for label,vals,sbg,sbold in sum_defs:
                    ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=4)
                    cs(row,1,label,bold=sbold,align="right",bg=sbg,size=10)
                    for si,shop in enumerate(shops):
                        col_up=SHOP_START+si*2; col_tot=col_up+1
                        v=vals.get(shop,0)
                        is_b=label=="NET TOTAL" and si==best_idx
                        cell_bg=BEST if is_b else sbg
                        ws.merge_cells(start_row=row,start_column=col_up,end_row=row,end_column=col_tot)
                        cs(row,col_up,v,bold=sbold or is_b,align="right",bg=cell_bg,fmt='#,##0.00',size=10)
                    ws.row_dimensions[row].height=18
                    row+=1

                # column widths
                ws.column_dimensions[get_column_letter(1)].width=6
                ws.column_dimensions[get_column_letter(2)].width=36
                ws.column_dimensions[get_column_letter(3)].width=7
                ws.column_dimensions[get_column_letter(4)].width=8
                for si in range(n_shops):
                    col_up=SHOP_START+si*2
                    ws.column_dimensions[get_column_letter(col_up)].width=13
                    ws.column_dimensions[get_column_letter(col_up+1)].width=13
                ws.freeze_panes="E6"

                out=io.BytesIO(); wb.save(out); out.seek(0)
                return out.getvalue()

            excel_data=export_excel()
            st.download_button(
                "📊 ดาวน์โหลด Excel (ฟอร์แมตทางการ)",
                data=excel_data,
                file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
