import streamlit as st
import pandas as pd
from datetime import date, datetime
import io, json
from utils import (
    load_projects, save_project, delete_project, duplicate_project,
    parse_project, load_shops_db, save_shop_db, delete_shop_db,
    load_templates, save_template, delete_template,
    calc_group, new_group, new_item,
    STATUS_OPTIONS, STATUS_COLORS, STATUS_TEXT, ITEM_CATEGORIES
)

st.set_page_config(page_title="เปรียบเทียบราคา", page_icon="💼", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
.block-container{padding:1.5rem 2rem 3rem;max-width:1400px}
[data-testid="stSidebar"]{background:linear-gradient(160deg,#0f2027,#203a43,#2c5364)!important}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,[data-testid="stSidebar"] div{color:#e2e8f0!important}
[data-testid="stSidebar"] input,[data-testid="stSidebar"] select,
[data-testid="stSidebar"] textarea{color:#1e293b!important}
[data-testid="stSidebar"] .stRadio label{
  background:rgba(255,255,255,.07);border-radius:10px;
  padding:10px 14px;margin-bottom:6px;display:block;cursor:pointer}
[data-testid="stSidebar"] .stRadio label:hover{background:rgba(255,255,255,.15)}
.stButton>button{border-radius:8px!important;font-size:13px!important;font-weight:500!important}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#1D9E75,#0F6E56)!important;
  color:white!important;border-color:transparent!important}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-radius:10px;padding:4px;border:none}
.stTabs [data-baseweb="tab"]{
  border-radius:8px!important;font-size:13px!important;
  font-weight:500!important;padding:6px 16px!important;border:none!important}
.stTabs [aria-selected="true"]{
  background:white!important;color:#1D9E75!important;
  box-shadow:0 1px 4px rgba(0,0,0,.12)!important}
.streamlit-expanderHeader{font-weight:500!important;font-size:14px!important}
</style>
""", unsafe_allow_html=True)

# ===== LOGIN =====
for k,v in [("logged_in",False),("username",""),("display_name","")]:
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state["logged_in"]:
    st.markdown("<div style='text-align:center;padding-top:3rem'><span style='font-size:48px'>💼</span><h2 style='margin:.5rem 0 0'>ระบบเปรียบเทียบราคา</h2><p style='color:gray'>Price Comparison System</p></div>", unsafe_allow_html=True)
    col=st.columns([1,1,1])[1]
    with col:
        with st.form("login"):
            st.markdown("**เข้าสู่ระบบ**")
            u=st.text_input("Username")
            p=st.text_input("Password",type="password")
            if st.form_submit_button("เข้าสู่ระบบ",type="primary",use_container_width=True):
                users=st.secrets.get("users",{})
                if u in users and users[u]["password"]==p:
                    st.session_state.update({"logged_in":True,"username":u,"display_name":users[u]["name"]})
                    st.rerun()
                else: st.error("Username หรือ Password ไม่ถูกต้อง")
    st.stop()

# ===== SIDEBAR =====
with st.sidebar:
    init=(st.session_state["display_name"][:2]).upper()
    st.markdown(f"<div style='background:rgba(255,255,255,.1);border-radius:10px;padding:10px 14px;margin-bottom:12px;display:flex;align-items:center;gap:10px'><div style='width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#1D9E75,#0F6E56);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:white;flex-shrink:0'>{init}</div><div><div style='font-size:13px;font-weight:600'>{st.session_state['display_name']}</div><div style='font-size:11px;opacity:.7'>ผู้ใช้งาน</div></div></div>",unsafe_allow_html=True)
    menu=st.radio("",["📋  โครงการ","🏪  ร้านค้า","📦  Templates"],label_visibility="collapsed")
    st.markdown("---")
    if st.button("ออกจากระบบ",use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# ===== SESSION =====
for k,v in [("mode","list"),("current_project_id",None),
            ("shops",["บริษัท A","บริษัท B","บริษัท C"]),
            ("groups",[{"name":"กลุ่มที่ 1","items":[],"discounts":{}}]),
            ("doc_title","เปรียบเทียบราคา"),("project_name",""),
            ("vat_rate",7.0),("shop_discounts",{}),("doc_date",date.today()),
            ("tags",[]),("status","กำลังดำเนินการ")]:
    if k not in st.session_state: st.session_state[k]=v

def load_into_session(r):
    shops,shop_discounts,groups=parse_project(r)
    try: tags=json.loads(r.get("tags","[]"))
    except: tags=[]
    st.session_state.update({
        "doc_title":r.get("title",""),"project_name":r.get("project_name",""),
        "vat_rate":float(r.get("vat_rate",7.0)),"shops":shops,
        "shop_discounts":shop_discounts,"groups":groups,
        "tags":tags,"status":r.get("status","กำลังดำเนินการ")})
    try: st.session_state["doc_date"]=datetime.strptime(r.get("date",""),"%Y-%m-%d").date()
    except: st.session_state["doc_date"]=date.today()

def do_save(show_msg=True):
    pid=save_project({
        "title":st.session_state["doc_title"],"project_name":st.session_state["project_name"],
        "date":st.session_state["doc_date"].strftime("%Y-%m-%d"),"vat_rate":st.session_state["vat_rate"],
        "shops":st.session_state["shops"],"shop_discounts":st.session_state["shop_discounts"],
        "groups":st.session_state["groups"],"tags":st.session_state["tags"],
        "status":st.session_state["status"]},
        st.session_state["display_name"],st.session_state["current_project_id"])
    st.session_state.update({"current_project_id":pid,"mode":"edit"})
    if show_msg: st.success("✅ บันทึกเรียบร้อย!")

# ============================================================
# MENU: โครงการ
# ============================================================
if "📋" in menu:

    if st.session_state["mode"]=="list":
        st.markdown("## 📋 รายการโครงการ")
        c1,c2=st.columns([3,1])
        with c2:
            if st.button("➕ สร้างโครงการใหม่",type="primary",use_container_width=True):
                st.session_state.update({
                    "mode":"new","current_project_id":None,
                    "shops":["บริษัท A","บริษัท B","บริษัท C"],
                    "groups":[{"name":"กลุ่มที่ 1","items":[],"discounts":{}}],
                    "doc_title":"เปรียบเทียบราคา","project_name":"",
                    "vat_rate":7.0,"shop_discounts":{},"doc_date":date.today(),
                    "tags":[],"status":"กำลังดำเนินการ"})
                st.rerun()
        with c1:
            sc1,sc2,sc3=st.columns([2,1,1])
            sq=sc1.text_input("",placeholder="🔍 ค้นหา...",label_visibility="collapsed")
            fs=sc2.selectbox("",["ทั้งหมด"]+STATUS_OPTIONS,label_visibility="collapsed")
            sb=sc3.selectbox("",["ใหม่สุด","เก่าสุด","ชื่อ A-Z"],label_visibility="collapsed")

        with st.spinner(""):
            projects=load_projects()

        if sq: projects=[p for p in projects if sq.lower() in p.get("title","").lower() or sq.lower() in p.get("project_name","").lower()]
        if fs!="ทั้งหมด": projects=[p for p in projects if p.get("status","")==fs]
        if sb=="ใหม่สุด": projects=list(reversed(projects))
        elif sb=="ชื่อ A-Z": projects=sorted(projects,key=lambda x:x.get("title",""))

        if not projects:
            st.info("ยังไม่มีโครงการ — กด 'สร้างโครงการใหม่' เพื่อเริ่มต้นครับ")
        else:
            for r in projects:
                _,_,gr=parse_project(r)
                total_items=sum(len(g.get("items",[])) for g in gr)
                try: tags=json.loads(r.get("tags","[]"))
                except: tags=[]
                status=r.get("status","กำลังดำเนินการ")
                ca,cb=st.columns([5,2])
                with ca:
                    tag_txt="  ".join(f"`{t}`" for t in tags) if tags else ""
                    st.markdown(f"**{r.get('title','')}** &nbsp; `{status}` &nbsp; {tag_txt}")
                    st.caption(f"📁 {r.get('project_name','')}  ·  🗓 {r.get('date','')}  ·  👤 {r.get('created_by','')}  ·  {len(gr)} กลุ่ม · {total_items} รายการ")
                with cb:
                    ba,bb,bc=st.columns(3)
                    if ba.button("✏️",key=f"e_{r['id']}",use_container_width=True,help="แก้ไข"):
                        load_into_session(r); st.session_state.update({"mode":"edit","current_project_id":r["id"]}); st.rerun()
                    if bb.button("📋",key=f"dup_{r['id']}",use_container_width=True,help="สำเนา"):
                        duplicate_project(r["id"],st.session_state["display_name"]); st.rerun()
                    if bc.button("🗑",key=f"d_{r['id']}",use_container_width=True,help="ลบ"):
                        delete_project(r["id"]); st.rerun()
                st.divider()

    elif st.session_state["mode"] in ["new","edit"]:
        is_edit=st.session_state["mode"]=="edit"
        c1,c2,c3=st.columns([4,1,1])
        c1.markdown(f"## {'✏️ แก้ไขโครงการ' if is_edit else '➕ สร้างโครงการใหม่'}")
        if c2.button("💾 บันทึก",type="primary",use_container_width=True): do_save(); st.rerun()
        if c3.button("← กลับ",use_container_width=True): st.session_state["mode"]="list"; st.rerun()
        st.divider()

        with st.sidebar:
            st.markdown("**⚙️ ตั้งค่า**")
            st.session_state["doc_title"]=st.text_input("ชื่อเอกสาร",st.session_state["doc_title"])
            st.session_state["project_name"]=st.text_input("ชื่อโครงการ",st.session_state["project_name"])
            st.session_state["doc_date"]=st.date_input("วันที่",value=st.session_state["doc_date"])
            cv,cs2=st.columns(2)
            st.session_state["vat_rate"]=cv.number_input("VAT %",value=st.session_state["vat_rate"],min_value=0.0,max_value=30.0,step=0.5)
            st.session_state["status"]=cs2.selectbox("สถานะ",STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(st.session_state["status"]) if st.session_state["status"] in STATUS_OPTIONS else 0)
            tag_in=st.text_input("Tags",", ".join(st.session_state["tags"]),placeholder="เช่น IT, ก่อสร้าง")
            st.session_state["tags"]=[t.strip() for t in tag_in.split(",") if t.strip()]
            st.divider()
            st.markdown("**🏪 ร้านค้า**")
            shops_db=load_shops_db()
            if shops_db:
                sel_db=st.multiselect("เลือกจากฐานข้อมูล",[s["name"] for s in shops_db],
                                      label_visibility="collapsed",placeholder="เลือกร้าน...")
                if sel_db and st.button("+ เพิ่มร้านที่เลือก",use_container_width=True):
                    for sn in sel_db:
                        if sn not in st.session_state["shops"]: st.session_state["shops"].append(sn)
                    st.rerun()
            del_idx=None
            for i,s in enumerate(st.session_state["shops"]):
                ci,cd=st.columns([4,.7])
                st.session_state["shops"][i]=ci.text_input(f"ร้านที่ {i+1}",s,key=f"shop_name_{i}")
                if len(st.session_state["shops"])>2:
                    if cd.button("🗑",key=f"del_shop_btn_{i}",help=f"ลบร้านที่ {i+1}"): del_idx=i
            if del_idx is not None:
                st.session_state["shops"].pop(del_idx)
                for j in range(len(st.session_state["shops"]),len(st.session_state["shops"])+5):
                    if f"shop_name_{j}" in st.session_state: del st.session_state[f"shop_name_{j}"]
                st.rerun()
            if st.button("➕ เพิ่มร้านค้า",use_container_width=True):
                st.session_state["shops"].append(f"บริษัท {chr(65+len(st.session_state['shops']))}"); st.rerun()
            st.divider()
            st.markdown("**🎁 Special Discount (฿)**")
            for gi,grp in enumerate(st.session_state["groups"]):
                if "discounts" not in grp: grp["discounts"]={}
                if len(st.session_state["groups"])>1: st.caption(grp["name"])
                for s in st.session_state["shops"]:
                    grp["discounts"][s]=st.number_input(s,value=float(grp["discounts"].get(s,0.0)),
                                                         min_value=0.0,step=1.0,key=f"disc_{gi}_{s}")

        shops=st.session_state["shops"]
        vat=st.session_state["vat_rate"]
        tab1,tab2=st.tabs(["✏️  กรอกข้อมูล","📊  ตารางเปรียบเทียบ"])

        # ===== TAB 1 =====
        with tab1:
            ca2,cb2=st.columns([1,3])
            if ca2.button("➕ เพิ่มกลุ่มสินค้า"):
                st.session_state["groups"].append(new_group(len(st.session_state["groups"])+1)); st.rerun()
            templates=load_templates()
            if templates:
                tn=["-- เลือก Template --"]+[t["name"] for t in templates]
                sel_t=cb2.selectbox("",tn,label_visibility="collapsed")
                if sel_t!="-- เลือก Template --":
                    tmpl=next((t for t in templates if t["name"]==sel_t),None)
                    if tmpl and st.button(f"➕ โหลด '{sel_t}'"):
                        try:
                            for it in json.loads(tmpl["items"]):
                                ni=new_item(shops); ni.update({"name":it.get("name",""),"unit":it.get("unit","set"),"qty":float(it.get("qty",1)),"category":it.get("category","วัสดุ/อุปกรณ์")})
                                st.session_state["groups"][0]["items"].append(ni)
                            st.rerun()
                        except: pass

            gnames=[f"{i+1}. {g['name']}" for i,g in enumerate(st.session_state["groups"])]
            stabs=st.tabs(gnames)
            for gi,stab in enumerate(stabs):
                with stab:
                    grp=st.session_state["groups"][gi]
                    if "items" not in grp: grp["items"]=[]
                    if "discounts" not in grp: grp["discounts"]={}
                    gc1,gc2,gc3=st.columns([3,1,1])
                    grp["name"]=gc1.text_input("ชื่อกลุ่ม",grp["name"],key=f"gname_{gi}")
                    if gc2.button("➕ เพิ่มสินค้า",key=f"gadd_{gi}",use_container_width=True):
                        grp["items"].append(new_item(shops)); st.rerun()
                    if gc3.button("🗑 ลบกลุ่ม",key=f"gdel_{gi}",use_container_width=True) and len(st.session_state["groups"])>1:
                        st.session_state["groups"].pop(gi); st.rerun()
                    if grp["items"] and st.button(f"💾 บันทึกกลุ่มนี้เป็น Template",key=f"st_{gi}"):
                        save_template({"name":f"{grp['name']} ({datetime.now().strftime('%d/%m/%y')})","category":"ทั่วไป",
                                       "items":[{"name":it["name"],"unit":it["unit"],"qty":it["qty"],"category":it.get("category","")} for it in grp["items"]]},
                                      st.session_state["display_name"]); st.success("บันทึก Template แล้ว!")
                    n=len(grp["items"])
                    if n==0: st.info("กด '➕ เพิ่มสินค้า' เพื่อเพิ่มรายการ")
                    else:
                        to_del=None
                        for idx in range(n):
                            it=grp["items"][idx]
                            for key in ["prices","item_discounts","notes"]:
                                if key not in it: it[key]={}
                            for s in shops:
                                if s not in it["prices"]: it["prices"][s]=0.0
                                if s not in it["item_discounts"]: it["item_discounts"][s]=0.0
                                if s not in it["notes"]: it["notes"][s]=""
                            with st.expander(f"{idx+1}. {it['name']}  [{it.get('category','')}]",expanded=True):
                                ca3,cb3,cc3,cd3,ce3=st.columns([2.5,1,.8,1.5,.5])
                                it["name"]=ca3.text_input("ชื่อสินค้า/บริการ",it["name"],key=f"n_{gi}_{idx}")
                                it["unit"]=cb3.text_input("หน่วย",it["unit"],key=f"u_{gi}_{idx}")
                                it["qty"]=cc3.number_input("จำนวน",value=float(it["qty"]),min_value=0.0,step=1.0,key=f"q_{gi}_{idx}")
                                it["category"]=cd3.selectbox("ประเภท",ITEM_CATEGORIES,
                                    index=ITEM_CATEGORIES.index(it.get("category","วัสดุ/อุปกรณ์")) if it.get("category") in ITEM_CATEGORIES else 0,
                                    key=f"cat_{gi}_{idx}")
                                if ce3.button("🗑",key=f"d_{gi}_{idx}"): to_del=idx
                                hc=st.columns(len(shops))
                                for si,s in enumerate(shops): hc[si].markdown(f"**{s}**")
                                pc=st.columns(len(shops))
                                for si,s in enumerate(shops):
                                    it["prices"][s]=pc[si].number_input("ราคา/หน่วย (฿)",value=float(it["prices"].get(s,0)),min_value=0.0,step=1.0,key=f"p_{gi}_{idx}_{si}")
                                dc=st.columns(len(shops))
                                for si,s in enumerate(shops):
                                    it["item_discounts"][s]=dc[si].number_input("ส่วนลด/หน่วย (฿)",value=float(it["item_discounts"].get(s,0)),min_value=0.0,step=1.0,key=f"id_{gi}_{idx}_{si}")
                                st.markdown("**หมายเหตุ**")
                                nc=st.columns(len(shops))
                                for si,s in enumerate(shops):
                                    it["notes"][s]=nc[si].text_area(f"({s})",value=it["notes"].get(s,""),placeholder="เช่น รับประกัน 1 ปี",height=60,key=f"note_{gi}_{idx}_{si}",label_visibility="collapsed")
                                st.markdown("---")
                                sc4=st.columns(len(shops))
                                qty=float(it["qty"])
                                for si,s in enumerate(shops):
                                    price=float(it["prices"].get(s,0)); disc=float(it["item_discounts"].get(s,0))
                                    sub=max(price-disc,0)*qty
                                    dtxt=f" (ลด ฿{disc:,.0f})" if disc>0 else ""
                                    sc4[si].markdown(f"ยอดรวม{dtxt}  \n**฿{sub:,.2f}**")
                        if to_del is not None: grp["items"].pop(to_del); st.rerun()
            st.divider()
            if st.button("💾 บันทึกลง Google Sheets",type="primary"): do_save(); st.rerun()

        # ===== TAB 2 =====
        with tab2:
            doc_date=st.session_state["doc_date"]
            groups=st.session_state["groups"]
            if not any(g.get("items") for g in groups):
                st.info("ยังไม่มีข้อมูล — กรอกข้อมูลในแท็บ 'กรอกข้อมูล' ก่อนครับ")
            else:
                all_totals={s:0.0 for s in shops}
                for grp in groups:
                    if not grp.get("items"): continue
                    _,_,_,_,gt=calc_group(grp["items"],shops,vat,grp.get("discounts",{}))
                    for s in shops: all_totals[s]+=gt[s]

                data_groups=[(i,g) for i,g in enumerate(groups) if g.get("items")]
                tlabels=[f"{i+1}. {g['name']}" for i,g in data_groups]
                if len(data_groups)>1: tlabels.append("📊 สรุปรวม")
                stabs2=st.tabs(tlabels)

                for ti,(gi2,grp) in enumerate(data_groups):
                    with stabs2[ti]:
                        items_data=grp.get("items",[]); shop_disc=grp.get("discounts",{})
                        gs,gd,gad,gv,gt2=calc_group(items_data,shops,vat,shop_disc)
                        valid={s:gt2[s] for s in shops if gs[s]>0}
                        best=min(valid,key=valid.get) if valid else None
                        if valid and best:
                            sa=max(valid.values())-min(valid.values())
                            m1,m2,m3,m4=st.columns(4)
                            m1.metric("ร้านถูกสุด",best)
                            m2.metric("ยอดสุทธิ",f"฿{valid[best]:,.2f}")
                            m3.metric("ประหยัดได้",f"฿{sa:,.2f}")
                            m4.metric("รายการ",len(items_data))
                        cats=list(dict.fromkeys(it.get("category","วัสดุ/อุปกรณ์") for it in items_data))
                        for cat in cats:
                            citems=[it for it in items_data if it.get("category","วัสดุ/อุปกรณ์")==cat]
                            st.markdown(f"**{cat}**")
                            rows=[]
                            for i,it in enumerate(citems):
                                qty=float(it["qty"]); row={"#":i+1,"รายการ":it["name"],"จำนวน":int(qty),"หน่วย":it["unit"]}
                                tv=[]
                                for s in shops:
                                    price=float(it["prices"].get(s,0)); disc=float(it["item_discounts"].get(s,0))
                                    total=max(price-disc,0)*qty
                                    row[f"{s} Unit Price"]=price
                                    row[f"{s} ส่วนลด(฿)"]=disc if disc>0 else ""
                                    row[f"{s} Total"]=round(total,2); tv.append(total)
                                vtv=[v for v in tv if v>0]
                                if vtv: row["ถูกสุด"]=shops[tv.index(min(vtv))]
                                rows.append(row)
                            df=pd.DataFrame(rows)
                            def hi(row):
                                tc=[c for c in row.index if "Total" in str(c)]
                                styles=[""]*len(row)
                                vals={c:float(row[c]) for c in tc if str(row[c]) not in ["","0.0","0"]}
                                if not vals: return styles
                                mn=min(vals.values())
                                for i2,col in enumerate(row.index):
                                    if col in tc and str(row[col]) not in ["","0"] and float(row[col])==mn:
                                        styles[i2]="background-color:#D1FAE5;font-weight:600;color:#065F46"
                                    elif col in tc and str(row[col]) not in ["","0"] and float(row[col])>mn:
                                        styles[i2]="color:#DC2626"
                                return styles
                            def fmt_d(v):
                                if v=="" or v is None: return ""
                                try: return f"฿{float(v):,.2f}"
                                except: return ""
                            fmt={c:"฿{:,.2f}" for c in df.columns if "Total" in str(c) or "Price" in str(c)}
                            dc2=[c for c in df.columns if "ส่วนลด" in str(c)]
                            styled=df.style.apply(hi,axis=1).format(fmt)
                            for dcc in dc2: styled=styled.format(fmt_d,subset=[dcc])
                            st.dataframe(styled,use_container_width=True,hide_index=True)
                        st.markdown("**สรุปยอด**")
                        sr=[("ยอดรวมก่อนส่วนลด",gs,False),("SPECIAL DISCOUNT (-)",gd,True),
                            ("TOTAL (EXC. VAT)",gad,False),(f"VAT {vat:.0f}%",gv,False),("TOTAL (INC. VAT)",gt2,False)]
                        hcols=st.columns([2]+[1]*len(shops))
                        hcols[0].markdown("**รายการ**")
                        for si,s in enumerate(shops):
                            hcols[si+1].markdown(f"**{'🏆 ' if valid and s==best else ''}{s}**")
                        for label,vals,is_disc in sr:
                            rcols=st.columns([2]+[1]*len(shops))
                            rcols[0].markdown(f"**{label}**")
                            for si,s in enumerate(shops):
                                v=vals.get(s,0); is_b=label=="TOTAL (INC. VAT)" and valid and s==best
                                disp=f"-฿{v:,.2f}" if is_disc else f"฿{v:,.2f}"
                                if is_b: rcols[si+1].success(f"**{disp}**")
                                else: rcols[si+1].markdown(disp)
                        has_notes=any(it.get("notes",{}).get(s,"").strip() for it in items_data for s in shops)
                        if has_notes:
                            st.divider(); st.markdown("**หมายเหตุ**")
                            nc2=st.columns(len(shops))
                            for si,s in enumerate(shops):
                                lbl="🏆 " if valid and s==best else ""
                                with nc2[si]:
                                    st.markdown(f"**{lbl}{s}**")
                                    for it in items_data:
                                        note=it.get("notes",{}).get(s,"").strip()
                                        if note: st.markdown(f"**· {it['name']}**  \n{note}")

                if len(data_groups)>1:
                    with stabs2[-1]:
                        va2={s:all_totals[s] for s in shops if all_totals[s]>0}
                        if va2:
                            ba2=min(va2,key=va2.get); sv2=max(va2.values())-min(va2.values())
                            m1,m2,m3=st.columns(3)
                            m1.metric("ร้านถูกสุดโดยรวม",ba2)
                            m2.metric("ยอดรวมถูกสุด",f"฿{va2[ba2]:,.2f}")
                            m3.metric("ประหยัดได้รวม",f"฿{sv2:,.2f}")
                        sr2=[]
                        for gi3,grp2 in enumerate(groups):
                            if not grp2.get("items"): continue
                            _,_,_,_,gt3=calc_group(grp2["items"],shops,vat,grp2.get("discounts",{}))
                            r2={"กลุ่ม":f"กลุ่ม {gi3+1}: {grp2['name']}"}
                            for s in shops: r2[f"{s} TOTAL"]=round(gt3[s],2)
                            sr2.append(r2)
                        tr2={"กลุ่ม":"รวมทั้งหมด"}
                        for s in shops: tr2[f"{s} TOTAL"]=round(all_totals[s],2)
                        sr2.append(tr2)
                        df2=pd.DataFrame(sr2)
                        def hi2(row):
                            tc=[c for c in row.index if "TOTAL" in str(c)]; styles=[""]*len(row)
                            vals={c:float(row[c]) for c in tc if float(row[c])>0}
                            if not vals: return styles
                            mn=min(vals.values())
                            for i3,col in enumerate(row.index):
                                if col in tc and float(row[col])==mn and float(row[col])>0: styles[i3]="background-color:#D1FAE5;font-weight:600;color:#065F46"
                                elif col in tc and float(row[col])>mn: styles[i3]="color:#DC2626"
                            return styles
                        f2={c:"฿{:,.2f}" for c in df2.columns if "TOTAL" in str(c)}
                        st.dataframe(df2.style.apply(hi2,axis=1).format(f2),use_container_width=True,hide_index=True)

                st.divider()

                def export_excel():
                    from openpyxl import Workbook
                    from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
                    from openpyxl.utils import get_column_letter
                    wb=Workbook(); ws=wb.active; ws.title="เปรียบเทียบราคา"
                    # สีขาวสะอาด ไฮไลต์เฉพาะจุด
                    GRN="1D9E75"; WIN="D1FAE5"; WINT="065F46"; WINS="059669"
                    DSC="FFFBEB"; DSCT="92400E"; SUM="F9FAFB"
                    TOT="ECFDF5"; TOTT="065F46"; WHT="FFFFFF"
                    TXT="111827"; MUT="6B7280"; BDR="E5E7EB"; HDR="F3F4F6"
                    thin=Side(style="thin",color=BDR)
                    bdr=Border(left=thin,right=thin,top=thin,bottom=thin)
                    def cs(r,c,val="",bold=False,color=TXT,bg=None,align="left",fmt=None,size=10,wrap=False,italic=False):
                        cell=ws.cell(row=r,column=c,value=val)
                        cell.font=Font(bold=bold,color=color,size=size,name="Calibri",italic=italic)
                        if bg: cell.fill=PatternFill("solid",fgColor=bg)
                        cell.alignment=Alignment(horizontal=align,vertical="center",wrap_text=wrap)
                        if fmt: cell.number_format=fmt
                        cell.border=bdr
                        return cell
                    n_shops=len(shops); SS=5; TC=SS+n_shops*2-1
                    # แถว 1-2
                    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=TC)
                    t=ws.cell(row=1,column=1,value=f"เปรียบเทียบราคา  —  {st.session_state['project_name']}")
                    t.font=Font(bold=True,size=14,color=TXT,name="Calibri")
                    t.alignment=Alignment(horizontal="left",vertical="center")
                    t.border=Border(); ws.row_dimensions[1].height=26
                    ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=TC)
                    d=ws.cell(row=2,column=1,value=f"วันที่ {doc_date.strftime('%d/%m/%Y')}   |   VAT {vat:.0f}%   |   {st.session_state['doc_title']}")
                    d.font=Font(size=9,color=MUT,name="Calibri")
                    d.alignment=Alignment(horizontal="left",vertical="center")
                    d.border=Border(); ws.row_dimensions[2].height=16; ws.row_dimensions[3].height=8
                    cur=4
                    for gi4,grp in enumerate(groups):
                        items_data=grp.get("items",[]); shop_disc=grp.get("discounts",{})
                        if not items_data: continue
                        gs2,gd2,gad2,gv2,gt4=calc_group(items_data,shops,vat,shop_disc)
                        valid2={s:gt4[s] for s in shops if gs2[s]>0}
                        bi=shops.index(min(valid2,key=valid2.get)) if valid2 else None
                        # หัวกลุ่ม — เส้นเขียวซ้าย + bg เขียวอ่อนมาก
                        ws.merge_cells(start_row=cur,start_column=1,end_row=cur,end_column=TC)
                        g2=ws.cell(row=cur,column=1,value=f"กลุ่ม {gi4+1}  :  {grp['name']}")
                        g2.font=Font(bold=True,size=11,color=GRN,name="Calibri")
                        g2.fill=PatternFill("solid",fgColor="F0FDF4")
                        g2.alignment=Alignment(horizontal="left",vertical="center",indent=1)
                        g2.border=Border(bottom=Side(style="medium",color=GRN))
                        ws.row_dimensions[cur].height=22; cur+=1
                        # header
                        for c2,lbl,w in [(1,"#",5),(2,"รายการ",38),(3,"จำนวน",8),(4,"หน่วย",8)]:
                            ws.merge_cells(start_row=cur,start_column=c2,end_row=cur+1,end_column=c2)
                            cs(cur,c2,lbl,bold=True,color=TXT,bg=HDR,align="center",size=9)
                            ws.column_dimensions[get_column_letter(c2)].width=w
                        for si2,shop in enumerate(shops):
                            cu=SS+si2*2; ct=cu+1
                            ib=si2==bi; sh_bg="ECFDF5" if ib else HDR; sh_t=WINS if ib else TXT
                            ws.merge_cells(start_row=cur,start_column=cu,end_row=cur,end_column=ct)
                            cs(cur,cu,("★ " if ib else "")+shop,bold=ib,color=sh_t,bg=sh_bg,align="center",size=9)
                            cs(cur+1,cu,"Unit Price",color=MUT,bg=HDR,align="center",size=8)
                            cs(cur+1,ct,"Total",color=MUT,bg=HDR,align="center",size=8)
                            ws.column_dimensions[get_column_letter(cu)].width=13
                            ws.column_dimensions[get_column_letter(ct)].width=13
                        ws.row_dimensions[cur].height=20; ws.row_dimensions[cur+1].height=15; cur+=2
                        # data
                        for i2,it in enumerate(items_data):
                            qty=float(it["qty"])
                            rt=[float(it["prices"].get(s,0))*qty for s in shops]
                            dt=[float(it.get("item_discounts",{}).get(s,0))*qty for s in shops]
                            at=[max(rt[si3]-dt[si3],0) for si3 in range(len(shops))]
                            vtv2=[v for v in at if v>0]; bp=min(vtv2) if vtv2 else None
                            cs(cur,1,i2+1,align="center",bg=WHT,size=9,color=MUT)
                            cs(cur,2,f"[{it.get('category','')}] {it['name']}",align="left",bg=WHT,wrap=True,size=10,bold=True)
                            cs(cur,3,int(qty),align="center",bg=WHT,size=9)
                            cs(cur,4,it["unit"],align="center",bg=WHT,size=9)
                            for si3,shop in enumerate(shops):
                                cu2=SS+si3*2; ct2=cu2+1
                                price=float(it["prices"].get(shop,0)); raw=rt[si3]
                                ib2=bp and at[si3]==bp and at[si3]>0
                                cb2=WIN if ib2 else WHT; ct3=WINT if ib2 else TXT
                                cs(cur,cu2,price,align="right",bg=cb2,fmt="#,##0.00",size=10,color=ct3)
                                cs(cur,ct2,raw,align="right",bg=cb2,fmt="#,##0.00",size=10,bold=ib2,color=ct3)
                            ws.row_dimensions[cur].height=18; cur+=1
                            hd=any(float(it.get("item_discounts",{}).get(s,0))>0 for s in shops)
                            if hd:
                                ws.merge_cells(start_row=cur,start_column=1,end_row=cur,end_column=4)
                                cs(cur,1,f"  ส่วนลด  {it['name']}",align="right",bg=DSC,size=8,color=DSCT,italic=True)
                                for si3,shop in enumerate(shops):
                                    cu2=SS+si3*2; ct2=cu2+1; dtt=dt[si3]
                                    ws.merge_cells(start_row=cur,start_column=cu2,end_row=cur,end_column=ct2)
                                    cs(cur,cu2,-dtt if dtt>0 else "",align="right",bg=DSC,fmt="#,##0.00",size=8,color=DSCT)
                                ws.row_dimensions[cur].height=14; cur+=1
                        # summary
                        for lbl2,vals2,sbg2,sb2,isd2,stx2 in [
                            ("SPECIAL DISCOUNT",gd2,DSC,False,True,DSCT),
                            ("TOTAL (EXC. VAT)",gad2,SUM,True,False,TXT),
                            (f"VAT {vat:.0f}%",gv2,SUM,False,False,MUT),
                            ("TOTAL (INC. VAT)",gt4,TOT,True,False,TOTT)]:
                            ws.merge_cells(start_row=cur,start_column=1,end_row=cur,end_column=4)
                            cs(cur,1,lbl2,bold=sb2,align="right",bg=sbg2,size=9,color=stx2)
                            for si3,shop in enumerate(shops):
                                cu2=SS+si3*2; ct2=cu2+1; v2=vals2.get(shop,0)
                                ib3=lbl2=="TOTAL (INC. VAT)" and si3==bi
                                cb3=WIN if ib3 else sbg2; ct4=WINT if ib3 else stx2
                                disp2=-v2 if isd2 else v2
                                ws.merge_cells(start_row=cur,start_column=cu2,end_row=cur,end_column=ct2)
                                cs(cur,cu2,disp2,bold=sb2 or ib3,align="right",bg=cb3,fmt="#,##0.00",size=10,color=ct4)
                            ws.row_dimensions[cur].height=18; cur+=1
                        cur+=2
                    # สรุปรวม
                    if len([g for g in groups if g.get("items")])>1:
                        ws.merge_cells(start_row=cur,start_column=1,end_row=cur,end_column=TC)
                        sg2=ws.cell(row=cur,column=1,value="สรุปรวมทุกกลุ่ม  —  TOTAL (INC. VAT)")
                        sg2.font=Font(bold=True,size=11,color=TOTT,name="Calibri")
                        sg2.fill=PatternFill("solid",fgColor=TOT)
                        sg2.alignment=Alignment(horizontal="left",vertical="center",indent=1)
                        sg2.border=Border(bottom=Side(style="medium",color=GRN))
                        ws.row_dimensions[cur].height=22; cur+=1
                        va3={s:all_totals[s] for s in shops if all_totals[s]>0}
                        bai=shops.index(min(va3,key=va3.get)) if va3 else None
                        ws.merge_cells(start_row=cur,start_column=1,end_row=cur,end_column=4)
                        cs(cur,1,"",bg=TOT)
                        for si3,shop in enumerate(shops):
                            cu2=SS+si3*2; ct2=cu2+1; v3=all_totals[shop]; ib4=si3==bai
                            ws.merge_cells(start_row=cur,start_column=cu2,end_row=cur,end_column=ct2)
                            cs(cur,cu2,v3,bold=ib4,align="right",bg=WIN if ib4 else TOT,fmt="#,##0.00",size=12,color=WINT if ib4 else TOTT)
                        ws.row_dimensions[cur].height=24
                    ws.freeze_panes="E4"
                    out=io.BytesIO(); wb.save(out); out.seek(0); return out.getvalue()

                def export_pdf():
                    from reportlab.lib.pagesizes import A4,landscape
                    from reportlab.lib import colors
                    from reportlab.lib.styles import ParagraphStyle
                    from reportlab.lib.units import mm
                    from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer
                    from reportlab.pdfbase import pdfmetrics
                    from reportlab.pdfbase.ttfonts import TTFont
                    import urllib.request,os
                    fp="/tmp/SarabunR.ttf"; fb="/tmp/SarabunB.ttf"
                    if not os.path.exists(fp): urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Regular.ttf",fp)
                    if not os.path.exists(fb): urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Bold.ttf",fb)
                    try: pdfmetrics.registerFont(TTFont("TH",fp)); pdfmetrics.registerFont(TTFont("THB",fb)); F,FB="TH","THB"
                    except: F=FB="Helvetica"
                    buf=io.BytesIO()
                    doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=15*mm,rightMargin=15*mm,topMargin=15*mm,bottomMargin=15*mm)
                    story=[]
                    def p(txt,bold=False,size=10,color=colors.HexColor("#111827"),align="LEFT"):
                        s=ParagraphStyle("s",fontName=FB if bold else F,fontSize=size,textColor=color,
                                         alignment={"LEFT":0,"CENTER":1,"RIGHT":2}.get(align,0),leading=size*1.4)
                        return Paragraph(str(txt or ""),s)
                    GRN=colors.HexColor("#1D9E75"); WIN2=colors.HexColor("#D1FAE5"); WINT2=colors.HexColor("#065F46")
                    DSC2=colors.HexColor("#FFFBEB"); DSCT2=colors.HexColor("#92400E")
                    SUM2=colors.HexColor("#F9FAFB"); TOT2=colors.HexColor("#ECFDF5"); TOTT2=colors.HexColor("#065F46")
                    WHT2=colors.white; MUT2=colors.HexColor("#6B7280"); HDR2=colors.HexColor("#F3F4F6")
                    story.append(p(f"เปรียบเทียบราคา — {st.session_state['project_name']}",bold=True,size=15))
                    story.append(p(f"วันที่ {doc_date.strftime('%d/%m/%Y')}   |   VAT {vat:.0f}%   |   {st.session_state['doc_title']}",size=9,color=MUT2))
                    story.append(Spacer(1,6*mm))
                    pw=landscape(A4)[0]-30*mm; fw=pw*.32; sw=(pw-fw)/len(shops)
                    cws=[fw*.07,fw*.45,fw*.10,fw*.10]+[sw*.5,sw*.5]*len(shops)
                    for gi4,grp in enumerate(groups):
                        items_data=grp.get("items",[]); shop_disc=grp.get("discounts",{})
                        if not items_data: continue
                        gs3,gd3,gad3,gv3,gt5=calc_group(items_data,shops,vat,shop_disc)
                        valid3={s:gt5[s] for s in shops if gs3[s]>0}
                        bs2=min(valid3,key=valid3.get) if valid3 else None
                        tdata=[]; cmds=[("GRID",(0,0),(-1,-1),.5,colors.HexColor("#E5E7EB")),
                                        ("FONTSIZE",(0,0),(-1,-1),9),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]
                        tdata.append([p(f"กลุ่ม {gi4+1}  :  {grp['name']}",bold=True,size=10,color=GRN)]+[""]*(3+len(shops)*2))
                        cmds+=[("SPAN",(0,0),(-1,0)),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F0FDF4"))]
                        h1=[p("#",bold=True,align="CENTER"),p("รายการ",bold=True),p("จำนวน",bold=True,align="CENTER"),p("หน่วย",bold=True,align="CENTER")]
                        h2=["","","",""]
                        for si2,s in enumerate(shops):
                            ib5=s==bs2; sh2="ECFDF5" if ib5 else "F3F4F6"; st5=WINT2 if ib5 else colors.HexColor("#111827")
                            h1+=[p(("★ " if ib5 else "")+s,bold=ib5,color=st5,align="CENTER"),""]
                            h2+=[p("Unit Price",size=8,color=MUT2,align="CENTER"),p("Total",size=8,color=MUT2,align="CENTER")]
                            cmds+=[("SPAN",(4+si2*2,1),(5+si2*2,1)),("BACKGROUND",(4+si2*2,1),(5+si2*2,2),colors.HexColor(sh2))]
                        tdata+=[h1,h2]
                        for c3 in range(4): cmds.append(("SPAN",(c3,1),(c3,2)))
                        cmds+=[ ("BACKGROUND",(0,1),(-1,2),HDR2),("SPAN",(0,0),(-1,0))]
                        ri=3
                        for i2,it in enumerate(items_data):
                            qty=float(it["qty"])
                            rt2=[float(it["prices"].get(s,0))*qty for s in shops]
                            dt2=[float(it.get("item_discounts",{}).get(s,0))*qty for s in shops]
                            at2=[max(rt2[si3]-dt2[si3],0) for si3 in range(len(shops))]
                            vtv3=[v for v in at2 if v>0]; bp2=min(vtv3) if vtv3 else None
                            bg2=WHT2 if i2%2==0 else SUM2
                            dr=[p(str(i2+1),align="CENTER"),p(f"[{it.get('category','')}] {it['name']}",bold=True),p(str(int(qty)),align="CENTER"),p(it["unit"],align="CENTER")]
                            for si3,s in enumerate(shops):
                                ib6=bp2 and at2[si3]==bp2 and at2[si3]>0
                                cb4=WIN2 if ib6 else bg2; ct5=WINT2 if ib6 else colors.HexColor("#111827")
                                dr+=[p(f"฿{rt2[si3]/qty:,.2f}",align="RIGHT",color=ct5),p(f"฿{rt2[si3]:,.2f}",bold=ib6,align="RIGHT",color=ct5)]
                                cmds.append(("BACKGROUND",(4+si3*2,ri),(5+si3*2,ri),cb4))
                            tdata.append(dr); cmds.append(("BACKGROUND",(0,ri),(3,ri),bg2)); ri+=1
                            hd2=any(float(it.get("item_discounts",{}).get(s,0))>0 for s in shops)
                            if hd2:
                                drow=["","","",p(f"ส่วนลด {it['name']}",size=8,color=DSCT2,align="RIGHT")]
                                for si3,s in enumerate(shops):
                                    dtt2=dt2[si3]; drow+=["",p(f"-฿{dtt2:,.2f}" if dtt2>0 else "",size=8,color=DSCT2,align="RIGHT")]
                                    cmds.append(("BACKGROUND",(4+si3*2,ri),(5+si3*2,ri),DSC2))
                                tdata.append(drow); cmds.append(("BACKGROUND",(0,ri),(3,ri),DSC2)); ri+=1
                        for lbl3,vals3,sbg3,sb3,isd3,stx3 in [
                            ("SPECIAL DISCOUNT",gd3,DSC2,False,True,DSCT2),
                            ("TOTAL (EXC. VAT)",gad3,SUM2,True,False,colors.HexColor("#111827")),
                            (f"VAT {vat:.0f}%",gv3,SUM2,False,False,MUT2),
                            ("TOTAL (INC. VAT)",gt5,TOT2,True,False,TOTT2)]:
                            srow=["","","",p(lbl3,bold=sb3,align="RIGHT",color=stx3)]
                            for si3,s in enumerate(shops):
                                v4=vals3.get(s,0); ib7=lbl3=="TOTAL (INC. VAT)" and s==bs2
                                cb5=WIN2 if ib7 else sbg3; ct6=WINT2 if ib7 else stx3
                                disp3=f"-฿{v4:,.2f}" if isd3 else f"฿{v4:,.2f}"
                                srow+=["",p(disp3,bold=sb3 or ib7,align="RIGHT",color=ct6)]
                                cmds.append(("BACKGROUND",(4+si3*2,ri),(5+si3*2,ri),cb5))
                            tdata.append(srow); cmds+=[("BACKGROUND",(0,ri),(3,ri),sbg3),("SPAN",(0,ri),(3,ri))]
                            for si3 in range(len(shops)): cmds.append(("SPAN",(4+si3*2,ri),(5+si3*2,ri)))
                            ri+=1
                        t2=Table(tdata,colWidths=cws,repeatRows=3); t2.setStyle(TableStyle(cmds))
                        story.append(t2); story.append(Spacer(1,8*mm))
                    doc.build(story); buf.seek(0); return buf.getvalue()

                ce1,ce2=st.columns(2)
                with ce1:
                    st.download_button("📊 ดาวน์โหลด Excel",data=export_excel(),
                        file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
                with ce2:
                    try:
                        st.download_button("📄 ดาวน์โหลด PDF",data=export_pdf(),
                            file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",use_container_width=True)
                    except Exception as e:
                        st.error(f"PDF error: {e}")

# ============================================================
# MENU: ร้านค้า
# ============================================================
elif "🏪" in menu:
    st.markdown("## 🏪 ฐานข้อมูลร้านค้า")
    with st.expander("➕ เพิ่มร้านค้าใหม่",expanded=False):
        with st.form("add_shop"):
            sc1,sc2=st.columns(2)
            sn=sc1.text_input("ชื่อบริษัท / ร้านค้า *"); sco=sc2.text_input("ผู้ติดต่อ")
            sc3,sc4=st.columns(2); sp=sc3.text_input("เบอร์โทร"); se=sc4.text_input("อีเมล")
            sa=st.text_area("ที่อยู่",height=60)
            sc5,sc6=st.columns(2)
            spt=sc5.selectbox("เงื่อนไขชำระ",["เงินสด","โอน","เครดิต 30 วัน","เครดิต 60 วัน","อื่นๆ"]); snt=sc6.text_input("หมายเหตุ")
            if st.form_submit_button("บันทึก",type="primary"):
                if sn: save_shop_db({"name":sn,"contact":sco,"phone":sp,"email":se,"address":sa,"payment_terms":spt,"notes":snt},st.session_state["display_name"]); st.success(f"เพิ่ม '{sn}' แล้ว!"); st.rerun()
                else: st.error("กรุณาใส่ชื่อร้านค้า")
    shops_db=load_shops_db()
    if not shops_db: st.info("ยังไม่มีร้านค้า")
    else:
        sq2=st.text_input("",placeholder="🔍 ค้นหา...",label_visibility="collapsed")
        if sq2: shops_db=[s for s in shops_db if sq2.lower() in s.get("name","").lower() or sq2 in s.get("phone","")]
        for s in shops_db:
            sid=s.get("id") or s.get("ID","")
            with st.expander(f"**{s.get('name','')}**  ·  {s.get('contact','')}  ·  {s.get('phone','')}",expanded=False):
                c1,c2,c3,c4=st.columns(4)
                c1.markdown(f"📞 {s.get('phone','—')}"); c2.markdown(f"✉️ {s.get('email','—')}")
                c3.markdown(f"💳 {s.get('payment_terms','—')}"); c4.markdown(f"📝 {s.get('notes','—')}")
                if s.get("address"): st.markdown(f"📍 {s.get('address')}")
                if sid and st.button("🗑 ลบ",key=f"dshop_{sid}"): delete_shop_db(sid); st.rerun()

# ============================================================
# MENU: Templates
# ============================================================
elif "📦" in menu:
    st.markdown("## 📦 Template สินค้า")
    with st.expander("➕ สร้าง Template ใหม่",expanded=False):
        tc1,tc2=st.columns(2)
        tn2=tc1.text_input("ชื่อ Template *",key="tnm"); tcat=tc2.selectbox("หมวดหมู่",["ทั่วไป","ก่อสร้าง","IT/Network","ไฟฟ้า","ประปา","อื่นๆ"],key="tcat")
        if "tmpl_draft" not in st.session_state: st.session_state["tmpl_draft"]=[{"name":"","unit":"set","qty":1.0,"category":"วัสดุ/อุปกรณ์"}]
        tdel=None
        for ti,dit in enumerate(st.session_state["tmpl_draft"]):
            ta,tb,tc3,td,te=st.columns([3,1,1,1.5,.5])
            dit["name"]=ta.text_input("ชื่อสินค้า",dit["name"],key=f"tin_{ti}")
            dit["unit"]=tb.text_input("หน่วย",dit["unit"],key=f"tiu_{ti}")
            dit["qty"]=tc3.number_input("จำนวน",value=float(dit["qty"]),min_value=0.0,step=1.0,key=f"tiq_{ti}")
            dit["category"]=td.selectbox("ประเภท",ITEM_CATEGORIES,index=ITEM_CATEGORIES.index(dit.get("category","วัสดุ/อุปกรณ์")) if dit.get("category") in ITEM_CATEGORIES else 0,key=f"tic_{ti}")
            if te.button("🗑",key=f"tid_{ti}") and len(st.session_state["tmpl_draft"])>1: tdel=ti
        if tdel is not None: st.session_state["tmpl_draft"].pop(tdel); st.rerun()
        ca4,cb4=st.columns([1,2])
        if ca4.button("➕ เพิ่มรายการ"): st.session_state["tmpl_draft"].append({"name":"","unit":"set","qty":1.0,"category":"วัสดุ/อุปกรณ์"}); st.rerun()
        if cb4.button("💾 บันทึก Template",type="primary"):
            if tn2:
                vi=[it for it in st.session_state["tmpl_draft"] if it["name"].strip()]
                if vi:
                    save_template({"name":tn2,"category":tcat,"items":vi},st.session_state["display_name"])
                    st.session_state["tmpl_draft"]=[{"name":"","unit":"set","qty":1.0,"category":"วัสดุ/อุปกรณ์"}]
                    st.success(f"บันทึก '{tn2}' แล้ว!"); st.rerun()
                else: st.error("กรุณาใส่รายการสินค้าอย่างน้อย 1 รายการ")
            else: st.error("กรุณาใส่ชื่อ Template")
    templates=load_templates()
    if not templates: st.info("ยังไม่มี Template")
    else:
        for t in templates:
            try: il=json.loads(t.get("items","[]"))
            except: il=[]
            tid2=t.get("id") or t.get("ID","")
            with st.expander(f"**{t.get('name','')}**  [{t.get('category','')}]  —  {len(il)} รายการ",expanded=False):
                for it in il: st.markdown(f"- **{it.get('name','')}**  {it.get('unit','')} × {it.get('qty','')}  [{it.get('category','')}]")
                st.caption(f"สร้างโดย {t.get('created_by','')}  ·  {t.get('created_at','')}")
                if tid2 and st.button("🗑 ลบ",key=f"dt_{tid2}"): delete_template(tid2); st.rerun()
