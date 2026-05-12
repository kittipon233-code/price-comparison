import streamlit as st
import google.generativeai as genai
import json, re, io, base64
from PIL import Image
import pandas as pd

st.set_page_config(page_title="เปรียบเทียบราคา AI", page_icon="🛒", layout="wide")

st.markdown("""
<style>
  .main-title { font-size: 26px; font-weight: 700; color: #1D9E75; }
  .subtitle { color: #6b7280; font-size: 14px; margin-bottom: 1rem; }
  .win { background:#E1F5EE; color:#0F6E56; padding:2px 10px;
         border-radius:20px; font-size:12px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🛒 ระบบเปรียบเทียบราคา AI</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>อัปโหลดใบเสนอราคา PDF หรือรูปภาพ แล้ว AI กรอกข้อมูลให้อัตโนมัติ</div>", unsafe_allow_html=True)

# --- Session State ---
if "shops" not in st.session_state:
    st.session_state.shops = ["ร้าน A", "ร้าน B", "ร้าน C"]
if "items" not in st.session_state:
    st.session_state.items = []
if "doc_title" not in st.session_state:
    st.session_state.doc_title = "เปรียบเทียบราคา"

# ===== SIDEBAR =====
with st.sidebar:
    st.header("🔑 API Key")
    api_key = st.text_input("Gemini API Key", type="password",
                             help="รับฟรีที่ https://aistudio.google.com/app/apikey")
    if api_key:
        st.success("✅ API Key พร้อมใช้")

    st.divider()
    st.header("📁 อัปโหลดไฟล์")
    uploaded = st.file_uploader(
        "ใบเสนอราคา (PDF หรือรูปภาพ)",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    if uploaded:
        st.success(f"เลือก {len(uploaded)} ไฟล์แล้ว")
        for f in uploaded:
            st.caption(f"📄 {f.name}")

    if st.button("🤖 ให้ AI วิเคราะห์", type="primary",
                 disabled=not uploaded or not api_key):
        with st.spinner("AI กำลังอ่านไฟล์..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")

                content_parts = []
                for f in uploaded:
                    data = f.read()
                    if f.type == "application/pdf":
                        try:
                            from pdf2image import convert_from_bytes
                            pages = convert_from_bytes(data, dpi=150)
                            for page in pages[:4]:
                                buf = io.BytesIO()
                                page.save(buf, format="JPEG")
                                content_parts.append({
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": base64.b64encode(buf.getvalue()).decode()
                                    }
                                })
                        except Exception:
                            import PyPDF2
                            reader = PyPDF2.PdfReader(io.BytesIO(data))
                            text = "\n".join(p.extract_text() or "" for p in reader.pages)
                            content_parts.append(f"ข้อความจาก PDF:\n{text}")
                    else:
                        content_parts.append({
                            "inline_data": {
                                "mime_type": f.type,
                                "data": base64.b64encode(data).decode()
                            }
                        })

                prompt = """วิเคราะห์ใบเสนอราคาเหล่านี้แล้วตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{
  "shops": ["ชื่อร้าน1", "ชื่อร้าน2"],
  "items": [
    {
      "name": "ชื่อสินค้า",
      "unit": "หน่วย",
      "qty": 1,
      "prices": {"ชื่อร้าน1": ราคาต่อหน่วย, "ชื่อร้าน2": ราคาต่อหน่วย}
    }
  ]
}
ถ้าไม่พบราคาให้ใส่ 0"""
                content_parts.append(prompt)

                resp = model.generate_content(content_parts)
                raw = re.sub(r"```json|```", "", resp.text).strip()
                parsed = json.loads(raw)

                if parsed.get("shops"):
                    st.session_state.shops = parsed["shops"]
                if parsed.get("items"):
                    new_items = []
                    for it in parsed["items"]:
                        prices = {}
                        for s in st.session_state.shops:
                            prices[s] = float(it.get("prices", {}).get(s, 0) or 0)
                        new_items.append({
                            "name": it.get("name", ""),
                            "unit": it.get("unit", "ชิ้น"),
                            "qty": float(it.get("qty", 1) or 1),
                            "prices": prices
                        })
                    st.session_state.items = new_items
                st.success(f"✅ พบ {len(st.session_state.items)} รายการ!")
                st.rerun()
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาด: {e}")

    st.divider()
    st.header("⚙️ ตั้งค่า")
    st.session_state.doc_title = st.text_input("ชื่อเอกสาร", st.session_state.doc_title)
    vat = st.checkbox("คำนวณ VAT 7%")

    st.subheader("ชื่อร้านค้า")
    new_shops = []
    for i, s in enumerate(st.session_state.shops):
        new_shops.append(st.text_input(f"ร้านที่ {i+1}", s, key=f"shop_{i}"))
    st.session_state.shops = new_shops

    col1, col2 = st.columns(2)
    if col1.button("➕ เพิ่มร้าน"):
        st.session_state.shops.append(f"ร้าน {chr(65+len(st.session_state.shops))}")
        st.rerun()
    if col2.button("➖ ลบร้าน") and len(st.session_state.shops) > 2:
        st.session_state.shops.pop()
        st.rerun()

# ===== MAIN TABS =====
tab1, tab2 = st.tabs(["✏️ แก้ไขข้อมูล", "📊 ตารางเปรียบเทียบ"])

with tab1:
    if st.button("➕ เพิ่มรายการสินค้า"):
        st.session_state.items.append({
            "name": "สินค้าใหม่", "unit": "ชิ้น", "qty": 1.0,
            "prices": {s: 0.0 for s in st.session_state.shops}
        })
        st.rerun()

    if not st.session_state.items:
        st.info("ยังไม่มีรายการ — อัปโหลดไฟล์ทางซ้าย หรือกด 'เพิ่มรายการสินค้า'")
    else:
        to_delete = None
        num_items = len(st.session_state.items)

        for idx in range(num_items):
            item = st.session_state.items[idx]
            with st.expander(f"{idx+1}. {item['name']}", expanded=True):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 0.6])
                st.session_state.items[idx]["name"] = c1.text_input(
                    "ชื่อสินค้า", item["name"], key=f"n_{idx}")
                st.session_state.items[idx]["unit"] = c2.text_input(
                    "หน่วย", item["unit"], key=f"u_{idx}")
                st.session_state.items[idx]["qty"] = c3.number_input(
                    "จำนวน", value=float(item["qty"]), min_value=0.0, step=1.0, key=f"q_{idx}")
                if c4.button("🗑 ลบ", key=f"del_{idx}"):
                    to_delete = idx

                shops_now = st.session_state.shops
                pcols = st.columns(len(shops_now))
                for si, shop in enumerate(shops_now):
                    cur_price = float(st.session_state.items[idx]["prices"].get(shop, 0))
                    new_price = pcols[si].number_input(
                        f"ราคา/หน่วย ({shop})",
                        value=cur_price,
                        min_value=0.0, step=1.0,
                        key=f"p_{idx}_{si}"
                    )
                    st.session_state.items[idx]["prices"][shop] = new_price

        if to_delete is not None:
            st.session_state.items.pop(to_delete)
            st.rerun()

with tab2:
    if not st.session_state.items:
        st.info("ยังไม่มีข้อมูล — กรอกข้อมูลในแท็บ 'แก้ไขข้อมูล' ก่อนครับ")
    else:
        shops = st.session_state.shops
        rows = []
        for item in st.session_state.items:
            row = {"รายการ": item["name"], "หน่วย": item["unit"], "จำนวน": int(item["qty"])}
            totals = {}
            for s in shops:
                price = float(item["prices"].get(s, 0))
                total = price * item["qty"]
                if vat:
                    total *= 1.07
                row[f"{s} (รวม ฿)"] = round(total, 2)
                totals[s] = total
            valid = {k: v for k, v in totals.items() if v > 0}
            if valid:
                winner = min(valid, key=valid.get)
                saving = max(valid.values()) - min(valid.values())
                row["ร้านถูกสุด"] = winner
                row["ประหยัดได้ ฿"] = round(saving, 2)
            rows.append(row)

        df = pd.DataFrame(rows)

        # สรุป metrics
        grand = {s: df[f"{s} (รวม ฿)"].sum() for s in shops if f"{s} (รวม ฿)" in df.columns}
        valid_grand = {k: v for k, v in grand.items() if v > 0}
        if valid_grand:
            best = min(valid_grand, key=valid_grand.get)
            total_save = max(valid_grand.values()) - min(valid_grand.values())
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🏆 ร้านถูกสุดโดยรวม", best)
            m2.metric("💰 ราคารวมถูกสุด", f"฿{valid_grand[best]:,.2f}")
            m3.metric("✂️ ประหยัดได้", f"฿{total_save:,.2f}")
            m4.metric("📋 จำนวนรายการ", len(st.session_state.items))

        st.divider()

        # ไฮไลต์ราคาถูกสุด
        def highlight_min(row):
            price_cols = [c for c in row.index if "(รวม ฿)" in str(c)]
            styles = [""] * len(row)
            if not price_cols:
                return styles
            vals = {c: row[c] for c in price_cols if row[c] > 0}
            if not vals:
                return styles
            mn = min(vals.values())
            for i, col in enumerate(row.index):
                if col in price_cols and row[col] == mn and row[col] > 0:
                    styles[i] = "background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                elif col in price_cols and row[col] > mn:
                    styles[i] = "color:#dc2626"
            return styles

        price_fmt = {c: "฿{:,.2f}" for c in df.columns if "(รวม ฿)" in str(c) or "ประหยัด" in str(c)}
        st.dataframe(
            df.style.apply(highlight_min, axis=1).format(price_fmt),
            use_container_width=True, hide_index=True
        )

        st.divider()
        # ดาวน์โหลด CSV
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ ดาวน์โหลด CSV (เปิดใน Excel ได้)",
            data=csv.encode("utf-8-sig"),
            file_name=f"{st.session_state.doc_title}.csv",
            mime="text/csv"
        )
