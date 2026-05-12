import streamlit as st
import pandas as pd

st.set_page_config(page_title="เปรียบเทียบราคา", page_icon="🛒", layout="wide")

st.markdown("""
<style>
.main-title{font-size:26px;font-weight:700;color:#1D9E75}
.subtitle{color:#6b7280;font-size:14px;margin-bottom:1rem}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🛒 ระบบเปรียบเทียบราคา</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>กรอกราคาสินค้าของแต่ละร้าน ระบบคำนวณ VAT ส่วนลด และเปรียบเทียบให้อัตโนมัติ</div>", unsafe_allow_html=True)

# --- Session State ---
if "shops" not in st.session_state:
    st.session_state["shops"] = ["ร้าน A", "ร้าน B", "ร้าน C"]
if "items_list" not in st.session_state:
    st.session_state["items_list"] = []
if "doc_title" not in st.session_state:
    st.session_state["doc_title"] = "เปรียบเทียบราคา"
if "vat_rate" not in st.session_state:
    st.session_state["vat_rate"] = 7.0

# ===== SIDEBAR =====
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    st.session_state["doc_title"] = st.text_input("ชื่อเอกสาร", st.session_state["doc_title"])
    st.session_state["vat_rate"] = st.number_input("อัตรา VAT (%)", value=st.session_state["vat_rate"],
                                                    min_value=0.0, max_value=30.0, step=0.5)

    st.divider()
    st.subheader("🏪 ร้านค้า")
    new_shops = []
    for i, s in enumerate(st.session_state["shops"]):
        new_shops.append(st.text_input(f"ร้านที่ {i+1}", s, key=f"shop_{i}"))
    st.session_state["shops"] = new_shops

    c1, c2 = st.columns(2)
    if c1.button("➕ เพิ่มร้าน"):
        st.session_state["shops"].append(f"ร้าน {chr(65+len(st.session_state['shops']))}")
        st.rerun()
    if c2.button("➖ ลบร้าน") and len(st.session_state["shops"]) > 2:
        st.session_state["shops"].pop()
        st.rerun()

# ===== TABS =====
tab1, tab2 = st.tabs(["✏️ กรอกข้อมูล", "📊 ตารางเปรียบเทียบ"])

with tab1:
    if st.button("➕ เพิ่มรายการสินค้า"):
        st.session_state["items_list"].append({
            "name": "สินค้าใหม่",
            "unit": "ชิ้น",
            "qty": 1.0,
            "prices": {s: 0.0 for s in st.session_state["shops"]},
            "discounts": {s: 0.0 for s in st.session_state["shops"]},
        })
        st.rerun()

    n = len(st.session_state["items_list"])
    if n == 0:
        st.info("กด '➕ เพิ่มรายการสินค้า' เพื่อเริ่มกรอกข้อมูลครับ")
    else:
        to_del = None
        for idx in range(n):
            it = st.session_state["items_list"][idx]

            # เพิ่ม key ใหม่ถ้ายังไม่มี
            if "discounts" not in it:
                it["discounts"] = {s: 0.0 for s in st.session_state["shops"]}

            with st.expander(f"{idx+1}. {it['name']}", expanded=True):
                ca, cb, cc, cd = st.columns([3, 1, 1, 0.6])
                st.session_state["items_list"][idx]["name"] = ca.text_input(
                    "ชื่อสินค้า", it["name"], key=f"n_{idx}")
                st.session_state["items_list"][idx]["unit"] = cb.text_input(
                    "หน่วย", it["unit"], key=f"u_{idx}")
                st.session_state["items_list"][idx]["qty"] = cc.number_input(
                    "จำนวน", value=float(it["qty"]), min_value=0.0, step=1.0, key=f"q_{idx}")
                if cd.button("🗑 ลบ", key=f"d_{idx}"):
                    to_del = idx

                shops = st.session_state["shops"]
                vat = st.session_state["vat_rate"]

                # หัวคอลัมน์
                header_cols = st.columns(len(shops))
                for si, shop in enumerate(shops):
                    header_cols[si].markdown(f"**{shop}**")

                # แถวราคาก่อน VAT
                price_cols = st.columns(len(shops))
                for si, shop in enumerate(shops):
                    cur = float(it["prices"].get(shop, 0))
                    val = price_cols[si].number_input(
                        f"ราคา/หน่วย (ก่อน VAT)",
                        value=cur, min_value=0.0, step=1.0, key=f"p_{idx}_{si}")
                    st.session_state["items_list"][idx]["prices"][shop] = val

                # แถวส่วนลด
                disc_cols = st.columns(len(shops))
                for si, shop in enumerate(shops):
                    cur_d = float(it["discounts"].get(shop, 0))
                    val_d = disc_cols[si].number_input(
                        f"ส่วนลด (%)",
                        value=cur_d, min_value=0.0, max_value=100.0, step=0.5, key=f"disc_{idx}_{si}")
                    st.session_state["items_list"][idx]["discounts"][shop] = val_d

                # แสดงสรุปคำนวณ
                st.markdown("---")
                sum_cols = st.columns(len(shops))
                qty = float(it["qty"])
                for si, shop in enumerate(shops):
                    price = float(st.session_state["items_list"][idx]["prices"].get(shop, 0))
                    disc_pct = float(st.session_state["items_list"][idx]["discounts"].get(shop, 0))
                    subtotal = price * qty
                    disc_amt = subtotal * disc_pct / 100
                    after_disc = subtotal - disc_amt
                    vat_amt = after_disc * vat / 100
                    total = after_disc + vat_amt
                    sum_cols[si].markdown(
                        f"ก่อน VAT: **฿{after_disc:,.2f}**\n\n"
                        f"VAT {vat:.0f}%: ฿{vat_amt:,.2f}\n\n"
                        f"รวมทั้งสิ้น: **฿{total:,.2f}**"
                    )

        if to_del is not None:
            st.session_state["items_list"].pop(to_del)
            st.rerun()

with tab2:
    items_data = st.session_state["items_list"]
    shops = st.session_state["shops"]
    vat = st.session_state["vat_rate"]

    if len(items_data) == 0:
        st.info("ยังไม่มีข้อมูล — กรอกข้อมูลในแท็บ 'กรอกข้อมูล' ก่อนครับ")
    else:
        rows = []
        for it in items_data:
            qty = float(it["qty"])
            row = {"รายการ": it["name"], "หน่วย": it["unit"], "จำนวน": int(qty)}
            totals = {}
            for s in shops:
                price = float(it["prices"].get(s, 0))
                disc_pct = float(it.get("discounts", {}).get(s, 0))
                subtotal = price * qty
                disc_amt = subtotal * disc_pct / 100
                after_disc = subtotal - disc_amt
                vat_amt = after_disc * vat / 100
                total = after_disc + vat_amt
                row[f"{s} ก่อน VAT"] = round(after_disc, 2)
                row[f"{s} VAT"] = round(vat_amt, 2)
                row[f"{s} รวม"] = round(total, 2)
                totals[s] = total
            valid = {k: v for k, v in totals.items() if v > 0}
            if valid:
                row["ถูกสุด"] = min(valid, key=valid.get)
                row["ประหยัด ฿"] = round(max(valid.values()) - min(valid.values()), 2)
            rows.append(row)

        df = pd.DataFrame(rows)

        # สรุปยอดรวมทุกร้าน
        grand = {s: df[f"{s} รวม"].sum() for s in shops if f"{s} รวม" in df.columns}
        vg = {k: v for k, v in grand.items() if v > 0}
        if vg:
            best = min(vg, key=vg.get)
            save = max(vg.values()) - min(vg.values())
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🏆 ร้านถูกสุด", best)
            m2.metric("💰 ยอดรวมถูกสุด", f"฿{vg[best]:,.2f}")
            m3.metric("✂️ ประหยัดได้", f"฿{save:,.2f}")
            m4.metric("📋 รายการ", len(items_data))

        st.divider()

        # ไฮไลต์ราคาถูกสุด
        def hi(row):
            tc = [c for c in row.index if c.endswith(" รวม") and c != "ประหยัด ฿"]
            styles = [""] * len(row)
            vals = {c: row[c] for c in tc if c in row.index and row[c] > 0}
            if not vals:
                return styles
            mn = min(vals.values())
            for i, col in enumerate(row.index):
                if col in tc and row[col] == mn and row[col] > 0:
                    styles[i] = "background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                elif col in tc and row[col] > mn:
                    styles[i] = "color:#dc2626"
            return styles

        fmt = {c: "฿{:,.2f}" for c in df.columns
               if any(x in str(c) for x in ["ก่อน VAT", "VAT", "รวม", "ประหยัด"])}
        st.dataframe(df.style.apply(hi, axis=1).format(fmt),
                     use_container_width=True, hide_index=True)

        # ยอดรวมทุกร้าน
        st.divider()
        st.subheader("📋 สรุปยอดรวมทั้งหมด")
        sum_cols = st.columns(len(shops))
        for si, s in enumerate(shops):
            if f"{s} ก่อน VAT" in df.columns:
                total_before = df[f"{s} ก่อน VAT"].sum()
                total_vat = df[f"{s} VAT"].sum()
                total_all = df[f"{s} รวม"].sum()
                label = "🏆 " if s == best else ""
                sum_cols[si].metric(
                    f"{label}{s}",
                    f"฿{total_all:,.2f}",
                    delta=f"VAT ฿{total_vat:,.2f}"
                )

        st.divider()
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ ดาวน์โหลด CSV (เปิดใน Excel ได้)",
            data=csv.encode("utf-8-sig"),
            file_name=f"{st.session_state['doc_title']}.csv",
            mime="text/csv"
        )
