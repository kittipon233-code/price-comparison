import streamlit as st
import google.generativeai as genai
import json, re, io, base64
import pandas as pd

st.set_page_config(page_title="เปรียบเทียบราคา AI", page_icon="🛒", layout="wide")

st.markdown("""
<style>
.main-title{font-size:26px;font-weight:700;color:#1D9E75}
.subtitle{color:#6b7280;font-size:14px;margin-bottom:1rem}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🛒 ระบบเปรียบเทียบราคา AI</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>อัปโหลดใบเสนอราคา PDF หรือรูปภาพ แล้ว AI กรอกข้อมูลให้อัตโนมัติ</div>", unsafe_allow_html=True)

# --- Session State ---
if "shops" not in st.session_state:
    st.session_state["shops"] = ["ร้าน A", "ร้าน B", "ร้าน C"]
if "items_list" not in st.session_state:
    st.session_state["items_list"] = []
if "doc_title" not in st.session_state:
    st.session_state["doc_title"] = "เปรียบเทียบราคา"
if "vat" not in st.session_state:
    st.session_state["vat"] = False

# ===== SIDEBAR =====
with st.sidebar:
    st.header("🔑 API Key")
    api_key = st.text_input("Gemini API Key", type="password",
                             help="รับฟรีที่ https://aistudio.google.com/app/apikey")
    if api_key:
        st.success("✅ พร้อมใช้")

    st.divider()
    st.header("📁 อัปโหลดไฟล์")
    uploaded = st.file_uploader(
        "ใบเสนอราคา",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )
    if uploaded:
        st.success(f"เลือก {len(uploaded)} ไฟล์")

    run_ai = st.button("🤖 ให้ AI วิเคราะห์", type="primary",
                       disabled=(not uploaded or not api_key))

    if run_ai:
        with st.spinner("AI กำลังอ่านไฟล์..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                parts = []

                for f in uploaded:
                    raw = f.read()
                    if f.type == "application/pdf":
                        try:
                            from pdf2image import convert_from_bytes
                            pages = convert_from_bytes(raw, dpi=150)
                            for page in pages[:4]:
                                buf = io.BytesIO()
                                page.save(buf, format="JPEG")
                                parts.append({"inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": base64.b64encode(buf.getvalue()).decode()
                                }})
                        except Exception:
                            import PyPDF2
                            reader = PyPDF2.PdfReader(io.BytesIO(raw))
                            text = "\n".join(p.extract_text() or "" for p in reader.pages)
                            parts.append(f"ข้อความจาก PDF:\n{text}")
                    else:
                        parts.append({"inline_data": {
                            "mime_type": f.type,
                            "data": base64.b64encode(raw).decode()
                        }})

                parts.append("""วิเคราะห์ใบเสนอราคาเหล่านี้แล้วตอบเป็น JSON เท่านั้น:
{
  "shops": ["ชื่อร้าน1","ชื่อร้าน2"],
  "items": [{"name":"ชื่อสินค้า","unit":"หน่วย","qty":1,
             "prices":{"ชื่อร้าน1":ราคา,"ชื่อร้าน2":ราคา}}]
}
ถ้าไม่พบราคาใส่ 0 ตอบ JSON อย่างเดียวห้ามมี backtick""")

                resp = model.generate_content(parts)
                raw_text = re.sub(r"```json|```", "", resp.text).strip()
                parsed = json.loads(raw_text)

                if parsed.get("shops"):
                    st.session_state["shops"] = parsed["shops"]

                new_list = []
                for it in parsed.get("items", []):
                    prices = {}
                    for s in st.session_state["shops"]:
                        prices[s] = float(it.get("prices", {}).get(s, 0) or 0)
                    new_list.append({
                        "name": str(it.get("name", "")),
                        "unit": str(it.get("unit", "ชิ้น")),
                        "qty": float(it.get("qty", 1) or 1),
                        "prices": prices
                    })
                st.session_state["items_list"] = new_list
                st.success(f"✅ พบ {len(new_list)} รายการ!")
                st.rerun()
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาด: {e}")

    st.divider()
    st.header("⚙️ ตั้งค่า")
    st.session_state["doc_title"] = st.text_input("ชื่อเอกสาร", st.session_state["doc_title"])
    st.session_state["vat"] = st.checkbox("คำนวณ VAT 7%", st.session_state["vat"])

    st.subheader("ชื่อร้านค้า")
    new_shops = []
    for i, s in enumerate(st.session_state["shops"]):
        new_shops.append(st.text_input(f"ร้านที่ {i+1}", s, key=f"shop_{i}"))
    st.session_state["shops"] = new_shops

    c1, c2 = st.columns(2)
    if c1.button("➕ ร้าน"):
        st.session_state["shops"].append(f"ร้าน {chr(65+len(st.session_state['shops']))}")
        st.rerun()
    if c2.button("➖ ร้าน") and len(st.session_state["shops"]) > 2:
        st.session_state["shops"].pop()
        st.rerun()

# ===== TABS =====
tab1, tab2 = st.tabs(["✏️ แก้ไขข้อมูล", "📊 ตารางเปรียบเทียบ"])

with tab1:
    if st.button("➕ เพิ่มรายการสินค้า"):
        st.session_state["items_list"].append({
            "name": "สินค้าใหม่",
            "unit": "ชิ้น",
            "qty": 1.0,
            "prices": {s: 0.0 for s in st.session_state["shops"]}
        })
        st.rerun()

    n = len(st.session_state["items_list"])
    if n == 0:
        st.info("ยังไม่มีรายการ — อัปโหลดไฟล์ทางซ้าย หรือกด '➕ เพิ่มรายการสินค้า'")
    else:
        to_del = None
        for idx in range(n):
            it = st.session_state["items_list"][idx]
            with st.expander(f"{idx+1}. {it['name']}", expanded=True):
                ca, cb, cc, cd = st.columns([3, 1, 1, 0.6])
                st.session_state["items_list"][idx]["name"] = ca.text_input(
                    "ชื่อสินค้า", it["name"], key=f"n_{idx}")
                st.session_state["items_list"][idx]["unit"] = cb.text_input(
                    "หน่วย", it["unit"], key=f"u_{idx}")
                st.session_state["items_list"][idx]["qty"] = cc.number_input(
                    "จำนวน", value=float(it["qty"]), min_value=0.0, step=1.0, key=f"q_{idx}")
                if cd.button("🗑", key=f"d_{idx}"):
                    to_del = idx

                pcols = st.columns(len(st.session_state["shops"]))
                for si, shop in enumerate(st.session_state["shops"]):
                    cur = float(st.session_state["items_list"][idx]["prices"].get(shop, 0))
                    val = pcols[si].number_input(
                        f"{shop} (฿/หน่วย)", value=cur,
                        min_value=0.0, step=1.0, key=f"p_{idx}_{si}")
                    st.session_state["items_list"][idx]["prices"][shop] = val

        if to_del is not None:
            st.session_state["items_list"].pop(to_del)
            st.rerun()

with tab2:
    items_data = st.session_state["items_list"]
    shops = st.session_state["shops"]

    if len(items_data) == 0:
        st.info("ยังไม่มีข้อมูล")
    else:
        rows = []
        for it in items_data:
            row = {"รายการ": it["name"], "หน่วย": it["unit"], "จำนวน": int(it["qty"])}
            totals = {}
            for s in shops:
                p = float(it["prices"].get(s, 0))
                total = p * float(it["qty"])
                if st.session_state["vat"]:
                    total *= 1.07
                row[f"{s} (฿รวม)"] = round(total, 2)
                totals[s] = total
            valid = {k: v for k, v in totals.items() if v > 0}
            if valid:
                winner = min(valid, key=valid.get)
                row["ถูกสุด"] = winner
                row["ประหยัด ฿"] = round(max(valid.values()) - min(valid.values()), 2)
            rows.append(row)

        df = pd.DataFrame(rows)

        grand = {s: df[f"{s} (฿รวม)"].sum() for s in shops if f"{s} (฿รวม)" in df.columns}
        vg = {k: v for k, v in grand.items() if v > 0}
        if vg:
            best = min(vg, key=vg.get)
            save = max(vg.values()) - min(vg.values())
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🏆 ร้านถูกสุด", best)
            m2.metric("💰 รวมถูกสุด", f"฿{vg[best]:,.2f}")
            m3.metric("✂️ ประหยัดได้", f"฿{save:,.2f}")
            m4.metric("📋 รายการ", len(items_data))

        st.divider()

        def hi(row):
            pc = [c for c in row.index if "(฿รวม)" in str(c)]
            styles = [""] * len(row)
            vals = {c: row[c] for c in pc if row[c] > 0}
            if not vals:
                return styles
            mn = min(vals.values())
            for i, col in enumerate(row.index):
                if col in pc and row[col] == mn and row[col] > 0:
                    styles[i] = "background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                elif col in pc and row[col] > mn:
                    styles[i] = "color:#dc2626"
            return styles

        fmt = {c: "฿{:,.2f}" for c in df.columns if "(฿รวม)" in str(c) or "ประหยัด" in str(c)}
        st.dataframe(df.style.apply(hi, axis=1).format(fmt),
                     use_container_width=True, hide_index=True)

        st.divider()
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("⬇️ ดาวน์โหลด CSV",
                           data=csv.encode("utf-8-sig"),
                           file_name=f"{st.session_state['doc_title']}.csv",
                           mime="text/csv")
