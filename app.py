import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
import json
import re
from utils import (
    get_sheet, load_projects, save_project, delete_project, duplicate_project,
    parse_project, load_shops_db, save_shop_db, delete_shop_db,
    load_templates, save_template, delete_template,
    upload_to_drive, calc_group, new_group, new_item,
    STATUS_OPTIONS, STATUS_COLORS, STATUS_TEXT, ITEM_CATEGORIES
)

st.set_page_config(page_title="เปรียบเทียบราคา", page_icon="🛒", layout="wide")
st.markdown("""
<style>
.main-title{font-size:26px;font-weight:700;color:#1D9E75}
.subtitle{color:#6b7280;font-size:14px;margin-bottom:1rem}
.status-badge{font-size:11px;padding:3px 10px;border-radius:20px;font-weight:500;display:inline-block}
.group-hdr{font-size:15px;font-weight:600;color:#1D9E75;padding:6px 0;border-bottom:2px solid #1D9E75;margin-bottom:10px}
</style>
""", unsafe_allow_html=True)

# ===== LOGIN =====
for k,v in [("logged_in",False),("username",""),("display_name","")]:
    if k not in st.session_state: st.session_state[k] = v

if not st.session_state["logged_in"]:
    st.markdown("<div class='main-title' style='text-align:center;margin-top:2rem'>🛒 ระบบเปรียบเทียบราคา</div>", unsafe_allow_html=True)
    col = st.columns([1,1.2,1])[1]
    with col:
        with st.form("login_form"):
            st.markdown("### 🔐 เข้าสู่ระบบ")
            username  = st.text_input("Username")
            password  = st.text_input("Password", type="password")
            submitted = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)
            if submitted:
                users = st.secrets.get("users",{})
                if username in users and users[username]["password"] == password:
                    st.session_state.update({"logged_in":True,"username":username,
                                             "display_name":users[username]["name"]})
                    st.rerun()
                else:
                    st.error("Username หรือ Password ไม่ถูกต้อง")
    st.stop()

# ===== HEADER =====
st.markdown(f"<div class='main-title'>🛒 ระบบเปรียบเทียบราคา</div>", unsafe_allow_html=True)
st.markdown(f"<div class='subtitle'>ยินดีต้อนรับ <b>{st.session_state['display_name']}</b></div>", unsafe_allow_html=True)

# ===== SIDEBAR =====
with st.sidebar:
    st.markdown(f"👤 **{st.session_state['display_name']}**")
    if st.button("🚪 ออกจากระบบ"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()
    st.divider()
    st.markdown("**เมนูหลัก**")
    menu = st.radio("", ["📋 โครงการ","🏪 ฐานข้อมูลร้านค้า","📦 Template สินค้า"], label_visibility="collapsed")

# ===== SESSION DEFAULTS =====
for k,v in [("mode","list"),("current_project_id",None),
            ("shops",["บริษัท A","บริษัท B","บริษัท C"]),
            ("groups",[{"name":"กลุ่มที่ 1","items":[],"discounts":{}}]),
            ("doc_title","เปรียบเทียบราคา"),("project_name",""),
            ("vat_rate",7.0),("shop_discounts",{}),("doc_date",date.today()),
            ("tags",[]),("status","กำลังดำเนินการ"),
            ("autosave_pending",False)]:
    if k not in st.session_state: st.session_state[k] = v

def load_into_session(r):
    shops, shop_discounts, groups = parse_project(r)
    try:    tags = json.loads(r.get("tags","[]"))
    except: tags = []
    st.session_state.update({
        "doc_title":      r.get("title",""),
        "project_name":   r.get("project_name",""),
        "vat_rate":       float(r.get("vat_rate",7.0)),
        "shops":          shops,
        "shop_discounts": shop_discounts,
        "groups":         groups,
        "tags":           tags,
        "status":         r.get("status","กำลังดำเนินการ"),
    })
    try:    st.session_state["doc_date"] = datetime.strptime(r.get("date",""),"%Y-%m-%d").date()
    except: st.session_state["doc_date"] = date.today()

def do_save(show_msg=True):
    project_data = {
        "title":          st.session_state["doc_title"],
        "project_name":   st.session_state["project_name"],
        "date":           st.session_state["doc_date"].strftime("%Y-%m-%d"),
        "vat_rate":       st.session_state["vat_rate"],
        "shops":          st.session_state["shops"],
        "shop_discounts": st.session_state["shop_discounts"],
        "groups":         st.session_state["groups"],
        "tags":           st.session_state["tags"],
        "status":         st.session_state["status"],
    }
    pid = save_project(project_data, st.session_state["display_name"],
                       st.session_state["current_project_id"])
    st.session_state.update({"current_project_id":pid,"mode":"edit","autosave_pending":False})
    if show_msg: st.success("✅ บันทึกเรียบร้อย!")

# ============================================================
# MENU: โครงการ
# ============================================================
if "📋" in menu:

    # ===== LIST =====
    if st.session_state["mode"] == "list":
        c1,c2 = st.columns([3,1])
        c1.markdown("## 📋 รายการโครงการทั้งหมด")
        if c2.button("➕ สร้างโครงการใหม่", type="primary"):
            st.session_state.update({
                "mode":"new","current_project_id":None,
                "shops":["บริษัท A","บริษัท B","บริษัท C"],
                "groups":[{"name":"กลุ่มที่ 1","items":[],"discounts":{}}],
                "doc_title":"เปรียบเทียบราคา","project_name":"",
                "vat_rate":7.0,"shop_discounts":{},"doc_date":date.today(),
                "tags":[],"status":"กำลังดำเนินการ",
            })
            st.rerun()

        # ค้นหา + กรอง
        with st.expander("🔍 ค้นหาและกรอง", expanded=False):
            sc1,sc2,sc3 = st.columns([2,1,1])
            search_q    = sc1.text_input("ค้นหา", placeholder="ชื่อโครงการ หรือชื่อเอกสาร...")
            filter_status = sc2.selectbox("สถานะ", ["ทั้งหมด"] + STATUS_OPTIONS)
            sort_by     = sc3.selectbox("เรียงตาม", ["ใหม่สุด","เก่าสุด","ชื่อ A-Z"])

        with st.spinner("กำลังโหลด..."):
            projects = load_projects()

        # กรอง
        if search_q:
            projects = [p for p in projects if
                        search_q.lower() in p.get("title","").lower() or
                        search_q.lower() in p.get("project_name","").lower()]
        if filter_status != "ทั้งหมด":
            projects = [p for p in projects if p.get("status","") == filter_status]
        if sort_by == "ใหม่สุด":   projects = list(reversed(projects))
        elif sort_by == "ชื่อ A-Z": projects = sorted(projects, key=lambda x: x.get("title",""))

        if not projects:
            st.info("ไม่พบโครงการ — ลองเปลี่ยนคำค้นหา หรือกด 'สร้างโครงการใหม่'")
        else:
            for r in projects:
                _, _, groups = parse_project(r)
                total_items = sum(len(g.get("items",[])) for g in groups)
                try: tags = json.loads(r.get("tags","[]"))
                except: tags = []
                status = r.get("status","กำลังดำเนินการ")
                sbg    = STATUS_COLORS.get(status,"#f1f5f9")
                stxt   = STATUS_TEXT.get(status,"#1e293b")

                with st.container():
                    ca,cb,cc = st.columns([4,1,1])
                    with ca:
                        st.markdown(
                            f"**{r.get('title','')}**  \n"
                            f"📁 {r.get('project_name','')} &nbsp;|&nbsp; "
                            f"🗓 {r.get('date','')} &nbsp;|&nbsp; 👤 {r.get('created_by','')}  \n"
                            f"<span class='status-badge' style='background:{sbg};color:{stxt}'>{status}</span>"
                            + ("".join(f" `{t}`" for t in tags)),
                            unsafe_allow_html=True
                        )
                        st.caption(f"{len(groups)} กลุ่ม | {total_items} รายการ")
                    with cb:
                        if st.button("✏️ แก้ไข", key=f"e_{r['id']}"):
                            load_into_session(r)
                            st.session_state.update({"mode":"edit","current_project_id":r["id"]})
                            st.rerun()
                        if st.button("📋 Duplicate", key=f"dup_{r['id']}"):
                            with st.spinner("กำลัง duplicate..."):
                                duplicate_project(r["id"], st.session_state["display_name"])
                            st.rerun()
                    with cc:
                        if st.button("🗑 ลบ", key=f"d_{r['id']}"):
                            delete_project(r["id"]); st.rerun()
                    st.divider()

    # ===== NEW / EDIT =====
    elif st.session_state["mode"] in ["new","edit"]:
        is_edit = st.session_state["mode"] == "edit"
        c1,c2,c3 = st.columns([3,1,1])
        c1.markdown(f"## {'✏️ แก้ไขโครงการ' if is_edit else '➕ สร้างโครงการใหม่'}")
        if c2.button("💾 บันทึก", type="primary"):
            do_save()
            st.rerun()
        if c3.button("← กลับ"):
            st.session_state["mode"] = "list"; st.rerun()

        # Sidebar settings
        with st.sidebar:
            st.header("⚙️ ตั้งค่าโครงการ")
            st.session_state["doc_title"]    = st.text_input("ชื่อเอกสาร",  st.session_state["doc_title"])
            st.session_state["project_name"] = st.text_input("ชื่อโครงการ", st.session_state["project_name"])
            st.session_state["doc_date"]     = st.date_input("วันที่",       value=st.session_state["doc_date"])
            st.session_state["vat_rate"]     = st.number_input("VAT (%)",    value=st.session_state["vat_rate"],
                                                                min_value=0.0,max_value=30.0,step=0.5)
            st.session_state["status"]       = st.selectbox("สถานะ", STATUS_OPTIONS,
                                                             index=STATUS_OPTIONS.index(st.session_state["status"])
                                                             if st.session_state["status"] in STATUS_OPTIONS else 0)
            # Tags
            tag_input = st.text_input("Tags (คั่นด้วยจุลภาค)", ", ".join(st.session_state["tags"]))
            st.session_state["tags"] = [t.strip() for t in tag_input.split(",") if t.strip()]

            st.divider()
            st.subheader("🏪 ร้านค้า / บริษัท")

            # เลือกจากฐานข้อมูลร้านค้า
            shops_db = load_shops_db()
            if shops_db:
                shop_names_db = [s["name"] for s in shops_db]
                selected_from_db = st.multiselect("เลือกจากฐานข้อมูล", shop_names_db)
                if selected_from_db and st.button("+ เพิ่มร้านที่เลือก"):
                    for sn in selected_from_db:
                        if sn not in st.session_state["shops"]:
                            st.session_state["shops"].append(sn)
                    st.rerun()

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
            st.caption("หักก่อนคำนวณ VAT แยกต่างหากต่อกลุ่ม")
            for g_idx, grp in enumerate(st.session_state["groups"]):
                if "discounts" not in grp: grp["discounts"] = {}
                st.markdown(f"**{grp['name']}**")
                for s in st.session_state["shops"]:
                    cur = float(grp["discounts"].get(s,0.0))
                    grp["discounts"][s] = st.number_input(
                        f"{s}", value=cur, min_value=0.0, step=1.0, key=f"disc_{g_idx}_{s}")
                if g_idx < len(st.session_state["groups"])-1: st.markdown("---")

        # Main tabs
        tab1, tab2, tab3 = st.tabs(["✏️ กรอกข้อมูล","📊 ตารางเปรียบเทียบ","📎 ไฟล์แนบ"])

        shops = st.session_state["shops"]
        vat   = st.session_state["vat_rate"]

        # ===== TAB 1: กรอกข้อมูล =====
        with tab1:
            ba,bb = st.columns([1,3])
            if ba.button("➕ เพิ่มกลุ่มสินค้า"):
                st.session_state["groups"].append(new_group(len(st.session_state["groups"])+1))
                st.rerun()

            # Load template
            templates = load_templates()
            if templates:
                tmpl_names = ["-- เลือก Template --"] + [t["name"] for t in templates]
                sel_tmpl = bb.selectbox("โหลด Template สินค้า", tmpl_names)
                if sel_tmpl != "-- เลือก Template --":
                    tmpl = next((t for t in templates if t["name"]==sel_tmpl), None)
                    if tmpl and st.button(f"➕ โหลด '{sel_tmpl}' ไปยังกลุ่มที่เลือก"):
                        try:
                            tmpl_items = json.loads(tmpl["items"])
                            if st.session_state["groups"]:
                                for it in tmpl_items:
                                    new_it = new_item(shops)
                                    new_it["name"]     = it.get("name","")
                                    new_it["unit"]     = it.get("unit","set")
                                    new_it["qty"]      = float(it.get("qty",1))
                                    new_it["category"] = it.get("category","วัสดุ/อุปกรณ์")
                                    st.session_state["groups"][0]["items"].append(new_it)
                                st.rerun()
                        except: pass

            group_names = [f"กลุ่ม {i+1}: {g['name']}" for i,g in enumerate(st.session_state["groups"])]
            sub_tabs = st.tabs(group_names)

            for g_idx, sub_tab in enumerate(sub_tabs):
                with sub_tab:
                    grp = st.session_state["groups"][g_idx]
                    if "items"     not in grp: grp["items"]     = []
                    if "discounts" not in grp: grp["discounts"]  = {}

                    gc1,gc2,gc3 = st.columns([3,1,1])
                    grp["name"] = gc1.text_input("ชื่อกลุ่ม", grp["name"], key=f"gname_{g_idx}")
                    if gc2.button("➕ เพิ่มสินค้า", key=f"gadd_{g_idx}"):
                        grp["items"].append(new_item(shops)); st.rerun()
                    if gc3.button("🗑 ลบกลุ่ม", key=f"gdel_{g_idx}") and len(st.session_state["groups"]) > 1:
                        st.session_state["groups"].pop(g_idx); st.rerun()

                    # บันทึกกลุ่มนี้เป็น template
                    if grp["items"] and st.button(f"💾 บันทึกกลุ่มนี้เป็น Template", key=f"save_tmpl_{g_idx}"):
                        tmpl_data = {
                            "name":     f"{grp['name']} ({datetime.now().strftime('%d/%m/%y')})",
                            "category": "ทั่วไป",
                            "items":    [{"name":it["name"],"unit":it["unit"],"qty":it["qty"],"category":it.get("category","")} for it in grp["items"]]
                        }
                        save_template(tmpl_data, st.session_state["display_name"])
                        st.success("บันทึก Template แล้ว!")

                    n = len(grp["items"])
                    if n == 0:
                        st.info("กด '➕ เพิ่มสินค้า' เพื่อเพิ่มรายการ")
                    else:
                        to_del = None
                        for idx in range(n):
                            it = grp["items"][idx]
                            for key,default in [("prices",{}),("item_discounts",{}),("notes",{}),("file_links",{})]:
                                if key not in it: it[key] = {}
                            for s in shops:
                                for key,default in [("prices",0.0),("item_discounts",0.0),("notes",""),("file_links","")]:
                                    if s not in it[key]: it[key][s] = default

                            with st.expander(f"{idx+1}. {it['name']} [{it.get('category','วัสดุ/อุปกรณ์')}]", expanded=True):
                                ca,cb,cc,cd,ce = st.columns([2.5,1,0.8,0.8,0.5])
                                it["name"]     = ca.text_input("ชื่อสินค้า/บริการ", it["name"], key=f"n_{g_idx}_{idx}")
                                it["unit"]     = cb.text_input("หน่วย", it["unit"], key=f"u_{g_idx}_{idx}")
                                it["qty"]      = cc.number_input("จำนวน", value=float(it["qty"]), min_value=0.0, step=1.0, key=f"q_{g_idx}_{idx}")
                                it["category"] = cd.selectbox("ประเภท", ITEM_CATEGORIES,
                                                              index=ITEM_CATEGORIES.index(it.get("category","วัสดุ/อุปกรณ์"))
                                                              if it.get("category") in ITEM_CATEGORIES else 0,
                                                              key=f"cat_{g_idx}_{idx}")
                                if ce.button("🗑", key=f"d_{g_idx}_{idx}"): to_del = idx

                                # หัวร้าน
                                hcols = st.columns(len(shops))
                                for si,s in enumerate(shops): hcols[si].markdown(f"**{s}**")

                                # Unit Price
                                pcols = st.columns(len(shops))
                                for si,s in enumerate(shops):
                                    it["prices"][s] = pcols[si].number_input(
                                        "ราคา/หน่วย (฿)", value=float(it["prices"].get(s,0)),
                                        min_value=0.0, step=1.0, key=f"p_{g_idx}_{idx}_{si}")

                                # ส่วนลดต่อรายการ
                                dcols = st.columns(len(shops))
                                for si,s in enumerate(shops):
                                    it["item_discounts"][s] = dcols[si].number_input(
                                        "ส่วนลดต่อรายการ (%)", value=float(it["item_discounts"].get(s,0)),
                                        min_value=0.0, max_value=100.0, step=0.5, key=f"id_{g_idx}_{idx}_{si}")

                                # หมายเหตุ
                                st.markdown("**หมายเหตุ / เงื่อนไขพิเศษ**")
                                ncols = st.columns(len(shops))
                                for si,s in enumerate(shops):
                                    it["notes"][s] = ncols[si].text_area(
                                        f"หมายเหตุ ({s})", value=it["notes"].get(s,""),
                                        placeholder="เช่น รับประกัน 1 ปี, ส่งฟรี",
                                        height=60, key=f"note_{g_idx}_{idx}_{si}")

                                # สรุปยอดต่อรายการ
                                st.markdown("---")
                                scols = st.columns(len(shops))
                                qty   = float(it["qty"])
                                for si,s in enumerate(shops):
                                    price     = float(it["prices"].get(s,0))
                                    disc_pct  = float(it["item_discounts"].get(s,0))
                                    price_aft = price * (1 - disc_pct/100)
                                    subtotal  = price_aft * qty
                                    disc_txt  = f" (-{disc_pct:.0f}%)" if disc_pct > 0 else ""
                                    scols[si].markdown(f"ยอดรวม{disc_txt}: **฿{subtotal:,.2f}**")

                        if to_del is not None:
                            grp["items"].pop(to_del); st.rerun()

            st.divider()
            col_save, col_info = st.columns([1,3])
            if col_save.button("💾 บันทึกลง Google Sheets", type="primary"):
                do_save(); st.rerun()
            col_info.caption("ระบบจะบันทึกอัตโนมัติเมื่อกด 'บันทึก' ด้านบน")

        # ===== TAB 2: ตารางเปรียบเทียบ =====
        with tab2:
            doc_date = st.session_state["doc_date"]
            groups   = st.session_state["groups"]

            if not any(g.get("items") for g in groups):
                st.info("ยังไม่มีข้อมูล")
            else:
                all_totals = {s:0.0 for s in shops}
                for grp in groups:
                    if not grp.get("items"): continue
                    _,_,_,_,gt = calc_group(grp["items"],shops,vat,grp.get("discounts",{}))
                    for s in shops: all_totals[s] += gt[s]

                data_groups = [(i,g) for i,g in enumerate(groups) if g.get("items")]
                tab_labels  = [f"กลุ่ม {i+1}: {g['name']}" for i,g in data_groups]
                if len(data_groups) > 1: tab_labels.append("📊 สรุปรวม")
                sub_tabs2 = st.tabs(tab_labels)

                for tab_i,(g_idx,grp) in enumerate(data_groups):
                    with sub_tabs2[tab_i]:
                        items_data = grp.get("items",[])
                        shop_disc  = grp.get("discounts",{})
                        grand_sub, grand_disc, grand_after_disc, grand_vat, grand_total = calc_group(
                            items_data, shops, vat, shop_disc)

                        valid = {s:grand_total[s] for s in shops if grand_sub[s]>0}
                        best  = min(valid,key=valid.get) if valid else None

                        if valid and best:
                            save_amt = max(valid.values())-min(valid.values())
                            m1,m2,m3,m4 = st.columns(4)
                            m1.metric("ร้านถูกสุด (หลังส่วนลด)", best)
                            m2.metric("ยอดสุทธิถูกสุด", f"฿{valid[best]:,.2f}")
                            m3.metric("ประหยัดได้", f"฿{save_amt:,.2f}")
                            m4.metric("รายการ", len(items_data))

                        # กราฟ
                        if valid:
                            chart_data = pd.DataFrame({
                                "ร้านค้า": list(valid.keys()),
                                "ยอดรวม (฿)": list(valid.values())
                            })
                            st.bar_chart(chart_data.set_index("ร้านค้า"))

                        # ตารางรายการ — แยกตามประเภท
                        categories = list(dict.fromkeys(it.get("category","วัสดุ/อุปกรณ์") for it in items_data))
                        for cat in categories:
                            cat_items = [it for it in items_data if it.get("category","วัสดุ/อุปกรณ์")==cat]
                            st.markdown(f"**{cat}**")
                            rows = []
                            for i,it in enumerate(cat_items):
                                qty = float(it["qty"])
                                row = {"Item":i+1,"Detail":it["name"],"Q'TY":int(qty),"Unit":it["unit"]}
                                tot_vals = []
                                for s in shops:
                                    price    = float(it["prices"].get(s,0))
                                    disc_pct = float(it["item_discounts"].get(s,0))
                                    p_aft    = price*(1-disc_pct/100)
                                    total    = p_aft*qty
                                    row[f"{s} Unit Price"] = price
                                    row[f"{s} Disc%"]      = disc_pct if disc_pct>0 else ""
                                    row[f"{s} Total"]      = round(total,2)
                                    tot_vals.append(total)
                                valid_tv = [v for v in tot_vals if v>0]
                                if valid_tv: row["ถูกสุด"] = shops[tot_vals.index(min(valid_tv))]
                                rows.append(row)

                            df = pd.DataFrame(rows)
                            def hi(row):
                                tc=[c for c in row.index if "Total" in str(c)]
                                styles=[""]*len(row)
                                vals={c:float(row[c]) for c in tc if str(row[c]) not in ["","0.0","0"]}
                                if not vals: return styles
                                mn=min(vals.values())
                                for i,col in enumerate(row.index):
                                    if col in tc and str(row[col]) not in ["","0"] and float(row[col])==mn:
                                        styles[i]="background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                                    elif col in tc and str(row[col]) not in ["","0"] and float(row[col])>mn:
                                        styles[i]="color:#dc2626"
                                return styles
                            fmt={c:"฿{:,.2f}" for c in df.columns if "Total" in str(c) or "Price" in str(c)}
                            st.dataframe(df.style.apply(hi,axis=1).format(fmt),
                                         use_container_width=True,hide_index=True)

                        # สรุปยอด
                        st.markdown("**สรุปยอดรวม**")
                        sum_rows = [
                            ("ยอดรวมก่อนส่วนลด",   grand_sub,        False),
                            ("SPECIAL DISCOUNT (-)", grand_disc,       True),
                            ("TOTAL (EXC. VAT)",    grand_after_disc, False),
                            (f"VAT {vat:.0f}%",     grand_vat,        False),
                            ("TOTAL (INC. VAT)",    grand_total,      False),
                        ]
                        hcols=st.columns([2]+[1]*len(shops))
                        hcols[0].markdown("**รายการ**")
                        for si,s in enumerate(shops):
                            lbl="🏆 " if valid and s==best else ""
                            hcols[si+1].markdown(f"**{lbl}{s}**")
                        for label,vals,is_disc in sum_rows:
                            rcols=st.columns([2]+[1]*len(shops))
                            rcols[0].markdown(f"**{label}**")
                            for si,s in enumerate(shops):
                                v=vals.get(s,0)
                                is_b=label=="TOTAL (INC. VAT)" and valid and s==best
                                disp=f"-฿{v:,.2f}" if is_disc else f"฿{v:,.2f}"
                                if is_b: rcols[si+1].success(f"**{disp}**")
                                else:    rcols[si+1].markdown(disp)

                        # หมายเหตุ
                        has_notes=any(it.get("notes",{}).get(s,"").strip() for it in items_data for s in shops)
                        if has_notes:
                            st.divider()
                            st.markdown("**หมายเหตุ / เงื่อนไขพิเศษ**")
                            ncols=st.columns(len(shops))
                            for si,s in enumerate(shops):
                                lbl="🏆 " if valid and s==best else ""
                                with ncols[si]:
                                    st.markdown(f"**{lbl}{s}**")
                                    for it in items_data:
                                        note=it.get("notes",{}).get(s,"").strip()
                                        if note:
                                            st.markdown(f"**· {it['name']}**")
                                            st.markdown(f"&nbsp;&nbsp;{note}")

                # Tab สรุปรวม
                if len(data_groups) > 1:
                    with sub_tabs2[-1]:
                        valid_all={s:all_totals[s] for s in shops if all_totals[s]>0}
                        if valid_all:
                            best_all=min(valid_all,key=valid_all.get)
                            save_all=max(valid_all.values())-min(valid_all.values())
                            m1,m2,m3=st.columns(3)
                            m1.metric("ร้านถูกสุดโดยรวม", best_all)
                            m2.metric("ยอดรวมถูกสุด",     f"฿{valid_all[best_all]:,.2f}")
                            m3.metric("ประหยัดได้รวม",     f"฿{save_all:,.2f}")

                            # กราฟรวม
                            chart_data2 = pd.DataFrame({
                                "ร้านค้า":    list(valid_all.keys()),
                                "ยอดรวม (฿)": list(valid_all.values())
                            })
                            st.bar_chart(chart_data2.set_index("ร้านค้า"))

                        sum_rows2=[]
                        for g_idx2,grp2 in enumerate(groups):
                            if not grp2.get("items"): continue
                            _,_,_,_,gt=calc_group(grp2["items"],shops,vat,grp2.get("discounts",{}))
                            row2={"กลุ่ม":f"กลุ่ม {g_idx2+1}: {grp2['name']}"}
                            for s in shops: row2[f"{s} TOTAL"]=round(gt[s],2)
                            sum_rows2.append(row2)
                        total_row2={"กลุ่ม":"รวมทั้งหมด"}
                        for s in shops: total_row2[f"{s} TOTAL"]=round(all_totals[s],2)
                        sum_rows2.append(total_row2)
                        df2=pd.DataFrame(sum_rows2)
                        def hi2(row):
                            tc=[c for c in row.index if "TOTAL" in str(c)]
                            styles=[""]*len(row)
                            vals={c:float(row[c]) for c in tc if float(row[c])>0}
                            if not vals: return styles
                            mn=min(vals.values())
                            for i,col in enumerate(row.index):
                                if col in tc and float(row[col])==mn and float(row[col])>0:
                                    styles[i]="background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                                elif col in tc and float(row[col])>mn:
                                    styles[i]="color:#dc2626"
                            return styles
                        fmt2={c:"฿{:,.2f}" for c in df2.columns if "TOTAL" in str(c)}
                        st.dataframe(df2.style.apply(hi2,axis=1).format(fmt2),
                                     use_container_width=True,hide_index=True)

                st.divider()
                # Export Excel
                def export_excel():
                    from openpyxl import Workbook
                    from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
                    from openpyxl.utils import get_column_letter
                    wb=Workbook(); ws=wb.active; ws.title="เปรียบเทียบราคา"
                    GREEN="1D9E75"; GL="E1F5EE"; WHITE="FFFFFF"; DARK="1E293B"
                    BEST="BBFFD9"; AMBER="FEF9C3"; GRAY="F1F5F9"; NOTE_BG="FFFDE7"
                    shop_colors=[("1D6B9A","E8F4FD"),("B45309","FEF9C3"),("166534","F0FDF4"),
                                 ("9A3412","FFF7ED"),("6D28D9","F5F3FF")]
                    thin=Side(style="thin",color="CBD5E1"); med=Side(style="medium",color="94A3B8")
                    bdr=Border(left=thin,right=thin,top=thin,bottom=thin)
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
                    n_shops=len(shops); SHOP_START=5; total_cols=SHOP_START+n_shops*2-1
                    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=total_cols)
                    t=ws.cell(row=1,column=1,value=f"เปรียบเทียบราคา {st.session_state['project_name']}")
                    t.font=Font(bold=True,size=16,color=GREEN,name="Tahoma")
                    t.alignment=Alignment(horizontal="center",vertical="center")
                    ws.row_dimensions[1].height=30
                    ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=total_cols)
                    d=ws.cell(row=2,column=1,value=f"วันที่ {doc_date.strftime('%d/%m/%Y')}    VAT {vat:.0f}%    เอกสาร: {st.session_state['doc_title']}")
                    d.font=Font(size=10,color="64748B",name="Tahoma")
                    d.alignment=Alignment(horizontal="center")
                    ws.row_dimensions[2].height=18; ws.row_dimensions[3].height=10
                    current_row=4
                    for g_idx,grp in enumerate(groups):
                        items_data=grp.get("items",[]); shop_disc=grp.get("discounts",{})
                        if not items_data: continue
                        grand_sub,grand_disc,grand_after_disc,grand_vat,grand_total=calc_group(
                            items_data,shops,vat,shop_disc)
                        valid={s:grand_total[s] for s in shops if grand_sub[s]>0}
                        best_idx=shops.index(min(valid,key=valid.get)) if valid else None
                        ws.merge_cells(start_row=current_row,start_column=1,end_row=current_row,end_column=total_cols)
                        g=ws.cell(row=current_row,column=1,value=f"กลุ่ม {g_idx+1}: {grp['name']}")
                        g.font=Font(bold=True,size=12,color=WHITE,name="Tahoma")
                        g.fill=PatternFill("solid",fgColor=GREEN)
                        g.alignment=Alignment(horizontal="left",vertical="center")
                        ws.row_dimensions[current_row].height=22; current_row+=1
                        for c,label in [(1,"Item"),(2,"Detail"),(3,"Q'TY"),(4,"Unit")]:
                            ws.merge_cells(start_row=current_row,start_column=c,end_row=current_row+1,end_column=c)
                            cs(current_row,c,label,bold=True,color=WHITE,bg=GREEN,align="center",border=bdr_med,size=10,wrap=True)
                        for si,shop in enumerate(shops):
                            col_up=SHOP_START+si*2; col_tot=col_up+1
                            hc,lc=shop_colors[si%5]
                            ws.merge_cells(start_row=current_row,start_column=col_up,end_row=current_row,end_column=col_tot)
                            lbl=("* " if si==best_idx else "")+shop
                            cs(current_row,col_up,lbl,bold=True,color=WHITE,bg=hc,align="center",border=bdr_med,size=10,wrap=True)
                            cs(current_row+1,col_up,"Unit Price",bold=True,color=DARK,bg=lc,align="center",border=bdr,size=9)
                            cs(current_row+1,col_tot,"Total",bold=True,color=DARK,bg=lc,align="center",border=bdr,size=9)
                        ws.row_dimensions[current_row].height=22; ws.row_dimensions[current_row+1].height=16; current_row+=2
                        stripe=["FFFFFF","F8FAFC"]
                        for i,it in enumerate(items_data):
                            qty=float(it["qty"]); bg=stripe[i%2]
                            cs(current_row,1,i+1,align="center",bg=bg)
                            cs(current_row,2,f"[{it.get('category','')}] {it['name']}",align="left",bg=bg,wrap=True)
                            cs(current_row,3,int(qty),align="center",bg=bg)
                            cs(current_row,4,it["unit"],align="center",bg=bg)
                            tot_vals=[float(it["prices"].get(s,0))*(1-float(it.get("item_discounts",{}).get(s,0))/100)*qty for s in shops]
                            valid_tv=[v for v in tot_vals if v>0]
                            best_p=min(valid_tv) if valid_tv else None
                            for si,shop in enumerate(shops):
                                col_up=SHOP_START+si*2; col_tot=col_up+1
                                price=float(it["prices"].get(shop,0)); total=tot_vals[si]
                                is_b=best_p and total==best_p and total>0
                                cell_bg=BEST if is_b else bg
                                cs(current_row,col_up,price,align="right",bg=cell_bg,fmt='#,##0.00',bold=is_b)
                                cs(current_row,col_tot,total,align="right",bg=cell_bg,fmt='#,##0.00',bold=is_b)
                            ws.row_dimensions[current_row].height=20; current_row+=1
                        sum_defs=[
                            ("SPECIAL DISCOUNT",grand_disc,AMBER,False,True),
                            ("TOTAL (EXC. VAT)",grand_after_disc,GRAY,True,False),
                            (f"VAT {vat:.0f}%",grand_vat,GRAY,False,False),
                            ("TOTAL (INC. VAT)",grand_total,GL,True,False),
                        ]
                        for label,vals,sbg,sbold,is_disc in sum_defs:
                            ws.merge_cells(start_row=current_row,start_column=1,end_row=current_row,end_column=4)
                            cs(current_row,1,label,bold=sbold,align="right",bg=sbg,size=10)
                            for si,shop in enumerate(shops):
                                col_up=SHOP_START+si*2; col_tot=col_up+1
                                v=vals.get(shop,0)
                                is_b=label=="TOTAL (INC. VAT)" and si==best_idx
                                cell_bg=BEST if is_b else sbg; disp=-v if is_disc else v
                                ws.merge_cells(start_row=current_row,start_column=col_up,end_row=current_row,end_column=col_tot)
                                cs(current_row,col_up,disp,bold=sbold or is_b,align="right",bg=cell_bg,fmt='#,##0.00',size=10)
                            ws.row_dimensions[current_row].height=18; current_row+=1
                        current_row+=2
                    if len([g for g in groups if g.get("items")])>1:
                        ws.merge_cells(start_row=current_row,start_column=1,end_row=current_row,end_column=total_cols)
                        g=ws.cell(row=current_row,column=1,value="สรุปรวมทุกกลุ่ม")
                        g.font=Font(bold=True,size=12,color=WHITE,name="Tahoma")
                        g.fill=PatternFill("solid",fgColor="0F6E56")
                        g.alignment=Alignment(horizontal="left",vertical="center")
                        ws.row_dimensions[current_row].height=22; current_row+=1
                        valid_all2={s:all_totals[s] for s in shops if all_totals[s]>0}
                        best_all_idx=shops.index(min(valid_all2,key=valid_all2.get)) if valid_all2 else None
                        ws.merge_cells(start_row=current_row,start_column=1,end_row=current_row,end_column=4)
                        cs(current_row,1,"ยอดรวม TOTAL (INC. VAT) ทุกกลุ่ม",bold=True,align="right",bg=GL,size=10)
                        for si,shop in enumerate(shops):
                            col_up=SHOP_START+si*2; col_tot=col_up+1
                            v=all_totals[shop]; is_b=si==best_all_idx
                            ws.merge_cells(start_row=current_row,start_column=col_up,end_row=current_row,end_column=col_tot)
                            cs(current_row,col_up,v,bold=is_b,align="right",bg=BEST if is_b else GL,fmt='#,##0.00',size=11)
                        ws.row_dimensions[current_row].height=22
                    ws.column_dimensions[get_column_letter(1)].width=6
                    ws.column_dimensions[get_column_letter(2)].width=36
                    ws.column_dimensions[get_column_letter(3)].width=7
                    ws.column_dimensions[get_column_letter(4)].width=8
                    for si in range(n_shops):
                        base=SHOP_START+si*2
                        ws.column_dimensions[get_column_letter(base)].width=13
                        ws.column_dimensions[get_column_letter(base+1)].width=13
                    ws.freeze_panes="E4"
                    out=io.BytesIO(); wb.save(out); out.seek(0)
                    return out.getvalue()

                st.download_button(
                    "📊 ดาวน์โหลด Excel (ฟอร์แมตทางการ)",
                    data=export_excel(),
                    file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        # ===== TAB 3: ไฟล์แนบ =====
        with tab3:
            st.markdown("### 📎 แนบไฟล์ใบเสนอราคา")
            st.caption("อัปโหลดไฟล์ใบเสนอราคาของแต่ละร้าน ไฟล์จะเก็บใน Google Drive")
            if not any(g.get("items") for g in st.session_state["groups"]):
                st.info("กรอกข้อมูลโครงการก่อนแล้วค่อยแนบไฟล์ครับ")
            else:
                for g_idx,grp in enumerate(st.session_state["groups"]):
                    if not grp.get("items"): continue
                    st.markdown(f"**กลุ่ม {g_idx+1}: {grp['name']}**")
                    for idx,it in enumerate(grp["items"]):
                        if "file_links" not in it: it["file_links"] = {}
                        with st.expander(f"{it['name']}", expanded=False):
                            fcols = st.columns(len(shops))
                            for si,s in enumerate(shops):
                                with fcols[si]:
                                    st.markdown(f"**{s}**")
                                    existing_link = it["file_links"].get(s,"")
                                    if existing_link:
                                        st.markdown(f"[ดูไฟล์ที่แนบ]({existing_link})")
                                    uploaded_file = st.file_uploader(
                                        "อัปโหลดไฟล์", type=["pdf","png","jpg","jpeg"],
                                        key=f"file_{g_idx}_{idx}_{si}")
                                    if uploaded_file:
                                        with st.spinner("กำลังอัปโหลด..."):
                                            link = upload_to_drive(
                                                uploaded_file.read(),
                                                f"{it['name']}_{s}_{uploaded_file.name}",
                                                uploaded_file.type
                                            )
                                        if link:
                                            it["file_links"][s] = link
                                            st.success("อัปโหลดสำเร็จ!")
                                            st.markdown(f"[ดูไฟล์]({link})")
                                        else:
                                            st.error("อัปโหลดไม่สำเร็จ")
                    st.divider()

# ============================================================
# MENU: ฐานข้อมูลร้านค้า
# ============================================================
elif "🏪" in menu:
    st.markdown("## 🏪 ฐานข้อมูลร้านค้า")
    with st.expander("➕ เพิ่มร้านค้าใหม่", expanded=False):
        with st.form("add_shop_form"):
            sc1,sc2 = st.columns(2)
            shop_name    = sc1.text_input("ชื่อบริษัท/ร้านค้า *")
            shop_contact = sc2.text_input("ชื่อผู้ติดต่อ")
            sc3,sc4 = st.columns(2)
            shop_phone   = sc3.text_input("เบอร์โทร")
            shop_email   = sc4.text_input("อีเมล")
            shop_address = st.text_area("ที่อยู่", height=60)
            sc5,sc6 = st.columns(2)
            shop_payment = sc5.selectbox("เงื่อนไขการชำระ", ["เงินสด","โอน","เครดิต 30 วัน","เครดิต 60 วัน","อื่นๆ"])
            shop_notes   = sc6.text_input("หมายเหตุ")
            if st.form_submit_button("บันทึกร้านค้า", type="primary"):
                if shop_name:
                    save_shop_db({
                        "name":shop_name,"contact":shop_contact,"phone":shop_phone,
                        "email":shop_email,"address":shop_address,
                        "payment_terms":shop_payment,"notes":shop_notes
                    }, st.session_state["display_name"])
                    st.success(f"เพิ่ม '{shop_name}' แล้วครับ!")
                    st.rerun()
                else:
                    st.error("กรุณาใส่ชื่อร้านค้า")

    with st.spinner("กำลังโหลด..."):
        shops_db = load_shops_db()

    if not shops_db:
        st.info("ยังไม่มีร้านค้าในฐานข้อมูล")
    else:
        search_shop = st.text_input("ค้นหาร้านค้า", placeholder="ชื่อ หรือเบอร์โทร...")
        if search_shop:
            shops_db = [s for s in shops_db if
                        search_shop.lower() in s.get("name","").lower() or
                        search_shop in s.get("phone","")]
        for s in shops_db:
            with st.expander(f"**{s.get('name','')}** — {s.get('contact','')} {s.get('phone','')}", expanded=False):
                c1,c2,c3,c4 = st.columns(4)
                c1.markdown(f"**เบอร์:** {s.get('phone','—')}")
                c2.markdown(f"**อีเมล:** {s.get('email','—')}")
                c3.markdown(f"**เงื่อนไข:** {s.get('payment_terms','—')}")
                c4.markdown(f"**หมายเหตุ:** {s.get('notes','—')}")
                if s.get("address"):
                    st.markdown(f"**ที่อยู่:** {s.get('address')}")
                if st.button("🗑 ลบร้านค้านี้", key=f"dshop_{s['id']}"):
                    delete_shop_db(s["id"]); st.rerun()

# ============================================================
# MENU: Template สินค้า
# ============================================================
elif "📦" in menu:
    st.markdown("## 📦 Template สินค้า")
    st.caption("Template คือรายการสินค้าที่ใช้บ่อย บันทึกไว้แล้วเรียกใช้ในโครงการได้เลย")

    with st.expander("➕ สร้าง Template ใหม่", expanded=False):
        with st.form("add_tmpl_form"):
            tc1,tc2 = st.columns(2)
            tmpl_name = tc1.text_input("ชื่อ Template *")
            tmpl_cat  = tc2.selectbox("หมวดหมู่", ["ทั่วไป","ก่อสร้าง","IT/Network","ไฟฟ้า","ประปา","อื่นๆ"])
            st.markdown("**รายการสินค้าใน Template**")
            tmpl_items_raw = st.text_area(
                "กรอกรายการ (แต่ละบรรทัด = 1 รายการ รูปแบบ: ชื่อ, หน่วย, จำนวน)",
                placeholder="Access Point, set, 1\nSwitch 8 Port, เครื่อง, 2\nสายแลน Cat6, เมตร, 100",
                height=120
            )
            if st.form_submit_button("บันทึก Template", type="primary"):
                if tmpl_name and tmpl_items_raw:
                    items_parsed = []
                    for line in tmpl_items_raw.strip().split("\n"):
                        parts = [p.strip() for p in line.split(",")]
                        items_parsed.append({
                            "name":     parts[0] if len(parts)>0 else "",
                            "unit":     parts[1] if len(parts)>1 else "ชิ้น",
                            "qty":      float(parts[2]) if len(parts)>2 else 1,
                            "category": "วัสดุ/อุปกรณ์"
                        })
                    save_template({
                        "name":tmpl_name,"category":tmpl_cat,"items":items_parsed
                    }, st.session_state["display_name"])
                    st.success(f"บันทึก Template '{tmpl_name}' แล้วครับ!")
                    st.rerun()
                else:
                    st.error("กรุณาใส่ชื่อและรายการสินค้า")

    with st.spinner("กำลังโหลด..."):
        templates = load_templates()

    if not templates:
        st.info("ยังไม่มี Template — สร้างได้จากปุ่มด้านบน หรือบันทึกจากกลุ่มสินค้าในโครงการ")
    else:
        for t in templates:
            try:    items_list = json.loads(t.get("items","[]"))
            except: items_list = []
            with st.expander(f"**{t.get('name','')}** [{t.get('category','')}] — {len(items_list)} รายการ", expanded=False):
                for it in items_list:
                    st.markdown(f"- {it.get('name','')} ({it.get('unit','')}) x{it.get('qty','')}")
                st.caption(f"สร้างโดย: {t.get('created_by','')} เมื่อ {t.get('created_at','')}")
                if st.button("🗑 ลบ Template นี้", key=f"dtmpl_{t['id']}"):
                    delete_template(t["id"]); st.rerun()
