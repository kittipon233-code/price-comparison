import streamlit as st
import pandas as pd
from datetime import date
import io

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
if "shop_discounts" not in st.session_state:
    st.session_state["shop_discounts"] = {}

# ===== SIDEBAR =====
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    st.session_state["doc_title"] = st.text_input("ชื่อเอกสาร", st.session_state["doc_title"])
    doc_date = st.date_input("วันที่", value=date.today())
    st.session_state["vat_rate"] = st.number_input(
        "อัตรา VAT (%)", value=st.session_state["vat_rate"],
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

    st.divider()
    st.subheader("🎁 ส่วนลดรวมจากร้าน (฿)")
    st.caption("ส่วนลดพิเศษที่ร้านให้รวมทั้งใบ")
    for s in st.session_state["shops"]:
        cur = st.session_state["shop_discounts"].get(s, 0.0)
        st.session_state["shop_discounts"][s] = st.number_input(
            f"ส่วนลดจาก {s} (฿)",
            value=float(cur), min_value=0.0, step=1.0, key=f"shopdisc_{s}")

# ===== helper =====
def calc(price, qty, vat_rate):
    subtotal = price * qty
    vat_amt = subtotal * vat_rate / 100
    total = subtotal + vat_amt
    return subtotal, vat_amt, total

# ===== TABS =====
tab1, tab2 = st.tabs(["✏️ กรอกข้อมูล", "📊 ตารางเปรียบเทียบ"])

with tab1:
    if st.button("➕ เพิ่มรายการสินค้า"):
        st.session_state["items_list"].append({
            "name": "สินค้าใหม่",
            "unit": "ชิ้น",
            "qty": 1.0,
            "prices": {s: 0.0 for s in st.session_state["shops"]},
        })
        st.rerun()

    n = len(st.session_state["items_list"])
    if n == 0:
        st.info("กด '➕ เพิ่มรายการสินค้า' เพื่อเริ่มกรอกข้อมูลครับ")
    else:
        to_del = None
        shops = st.session_state["shops"]
        vat = st.session_state["vat_rate"]

        for idx in range(n):
            it = st.session_state["items_list"][idx]
            if "prices" not in it:
                it["prices"] = {s: 0.0 for s in shops}

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

                # หัวคอลัมน์ร้าน
                hcols = st.columns(len(shops))
                for si, shop in enumerate(shops):
                    hcols[si].markdown(f"**{shop}**")

                # ราคา/หน่วย (ก่อน VAT)
                pcols = st.columns(len(shops))
                for si, shop in enumerate(shops):
                    cur = float(it["prices"].get(shop, 0))
                    val = pcols[si].number_input(
                        "ราคา/หน่วย (ก่อน VAT) ฿",
                        value=cur, min_value=0.0, step=1.0, key=f"p_{idx}_{si}")
                    st.session_state["items_list"][idx]["prices"][shop] = val

                # สรุปคำนวณต่อรายการ
                st.markdown("---")
                scols = st.columns(len(shops))
                qty = float(st.session_state["items_list"][idx]["qty"])
                for si, shop in enumerate(shops):
                    price = float(st.session_state["items_list"][idx]["prices"].get(shop, 0))
                    subtotal, vat_amt, total = calc(price, qty, vat)
                    scols[si].markdown(
                        f"ยอดก่อน VAT: **฿{subtotal:,.2f}**  \n"
                        f"VAT {vat:.0f}%: ฿{vat_amt:,.2f}  \n"
                        f"รวม: **฿{total:,.2f}**"
                    )

        if to_del is not None:
            st.session_state["items_list"].pop(to_del)
            st.rerun()

with tab2:
    items_data = st.session_state["items_list"]
    shops = st.session_state["shops"]
    vat = st.session_state["vat_rate"]
    shop_disc = st.session_state["shop_discounts"]

    if len(items_data) == 0:
        st.info("ยังไม่มีข้อมูล — กรอกข้อมูลในแท็บ 'กรอกข้อมูล' ก่อนครับ")
    else:
        rows = []
        grand_before = {s: 0.0 for s in shops}
        grand_vat    = {s: 0.0 for s in shops}
        grand_total  = {s: 0.0 for s in shops}

        for it in items_data:
            qty = float(it["qty"])
            row = {"ลำดับ": len(rows)+1, "รายการ": it["name"],
                   "หน่วย": it["unit"], "จำนวน": int(qty)}
            for s in shops:
                price = float(it["prices"].get(s, 0))
                subtotal, vat_amt, total = calc(price, qty, vat)
                row[f"{s}\nราคา/หน่วย"] = price
                row[f"{s}\nยอดก่อน VAT"] = round(subtotal, 2)
                row[f"{s}\nVAT {vat:.0f}%"] = round(vat_amt, 2)
                row[f"{s}\nยอดรวม"] = round(total, 2)
                grand_before[s] += subtotal
                grand_vat[s]    += vat_amt
                grand_total[s]  += total
            rows.append(row)

        df = pd.DataFrame(rows)

        # ยอดรวมสุทธิหลังหักส่วนลดรวม
        net_total = {s: grand_total[s] - float(shop_disc.get(s, 0)) for s in shops}
        valid_net = {k: v for k, v in net_total.items() if grand_total[k] > 0}

        if valid_net:
            best = min(valid_net, key=valid_net.get)
            save = max(valid_net.values()) - min(valid_net.values())
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🏆 ร้านถูกสุด", best)
            m2.metric("💰 ยอดสุทธิถูกสุด", f"฿{valid_net[best]:,.2f}")
            m3.metric("✂️ ประหยัดได้", f"฿{save:,.2f}")
            m4.metric("📋 จำนวนรายการ", len(items_data))

        st.divider()

        # ตารางรายการ
        def hi(row):
            tc = [c for c in row.index if "ยอดรวม" in str(c)]
            styles = [""] * len(row)
            vals = {c: row[c] for c in tc if c in row.index and float(row[c]) > 0}
            if not vals: return styles
            mn = min(vals.values())
            for i, col in enumerate(row.index):
                if col in tc and float(row[col]) == mn and float(row[col]) > 0:
                    styles[i] = "background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                elif col in tc and float(row[col]) > mn:
                    styles[i] = "color:#dc2626"
            return styles

        fmt = {c: "฿{:,.2f}" for c in df.columns
               if any(x in str(c) for x in ["ราคา/หน่วย","ก่อน VAT","VAT","ยอดรวม"])}
        st.dataframe(df.style.apply(hi, axis=1).format(fmt),
                     use_container_width=True, hide_index=True)

        st.divider()

        # ตารางสรุปยอดรวมทุกร้าน
        st.subheader("📋 สรุปยอดรวมทั้งหมด")
        sum_cols = st.columns(len(shops))
        for si, s in enumerate(shops):
            disc = float(shop_disc.get(s, 0))
            net = net_total[s]
            label = "🏆 " if valid_net and s == best else ""
            with sum_cols[si]:
                st.markdown(f"**{label}{s}**")
                st.markdown(
                    f"ยอดก่อน VAT: ฿{grand_before[s]:,.2f}  \n"
                    f"VAT {vat:.0f}%: ฿{grand_vat[s]:,.2f}  \n"
                    f"ยอดรวม: ฿{grand_total[s]:,.2f}  \n"
                    f"ส่วนลดจากร้าน: -฿{disc:,.2f}  \n"
                )
                if s == best and valid_net:
                    st.success(f"**ยอดสุทธิ: ฿{net:,.2f}** ✓ ถูกสุด")
                else:
                    st.info(f"**ยอดสุทธิ: ฿{net:,.2f}**")

        # ===== ส่งออก Excel แบบมีฟอร์แมต =====
        st.divider()
        st.subheader("📥 ส่งออกเอกสาร")

        def export_excel():
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # --- Sheet 1: รายละเอียด ---
                detail_rows = []
                for it in items_data:
                    qty = float(it["qty"])
                    r = {"รายการ": it["name"], "หน่วย": it["unit"], "จำนวน": int(qty)}
                    for s in shops:
                        price = float(it["prices"].get(s, 0))
                        sub, vat_a, tot = calc(price, qty, vat)
                        r[f"{s} ราคา/หน่วย"] = round(price, 2)
                        r[f"{s} ยอดก่อน VAT"] = round(sub, 2)
                        r[f"{s} VAT"] = round(vat_a, 2)
                        r[f"{s} ยอดรวม"] = round(tot, 2)
                    detail_rows.append(r)

                df_detail = pd.DataFrame(detail_rows)

                # แถวสรุป
                sum_row = {"รายการ": "รวมทั้งหมด", "หน่วย": "", "จำนวน": ""}
                for s in shops:
                    sum_row[f"{s} ราคา/หน่วย"] = ""
                    sum_row[f"{s} ยอดก่อน VAT"] = round(grand_before[s], 2)
                    sum_row[f"{s} VAT"] = round(grand_vat[s], 2)
                    sum_row[f"{s} ยอดรวม"] = round(grand_total[s], 2)
                disc_row = {"รายการ": "ส่วนลดจากร้าน", "หน่วย": "", "จำนวน": ""}
                net_row  = {"รายการ": "ยอดสุทธิ", "หน่วย": "", "จำนวน": ""}
                for s in shops:
                    disc_row[f"{s} ราคา/หน่วย"] = ""
                    disc_row[f"{s} ยอดก่อน VAT"] = ""
                    disc_row[f"{s} VAT"] = ""
                    disc_row[f"{s} ยอดรวม"] = -round(float(shop_disc.get(s,0)), 2)
                    net_row[f"{s} ราคา/หน่วย"] = ""
                    net_row[f"{s} ยอดก่อน VAT"] = ""
                    net_row[f"{s} VAT"] = ""
                    net_row[f"{s} ยอดรวม"] = round(net_total[s], 2)

                df_full = pd.concat([
                    df_detail,
                    pd.DataFrame([sum_row, disc_row, net_row])
                ], ignore_index=True)

                df_full.to_excel(writer, sheet_name="รายละเอียด", index=False, startrow=3)

                ws = writer.sheets["รายละเอียด"]
                title = st.session_state["doc_title"]
                ws["A1"] = title
                ws["A2"] = f"วันที่: {doc_date.strftime('%d/%m/%Y')}    VAT: {vat:.0f}%"

                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                ws["A1"].font = Font(bold=True, size=14, color="1D9E75")
                ws["A2"].font = Font(size=11, color="6B7280")

                green_fill = PatternFill("solid", fgColor="1D9E75")
                white_font = Font(bold=True, color="FFFFFF")
                thin = Side(style="thin", color="D1D5DB")
                border = Border(left=thin, right=thin, top=thin, bottom=thin)

                # หัวตาราง (แถว 4)
                for cell in ws[4]:
                    cell.fill = green_fill
                    cell.font = white_font
                    cell.alignment = Alignment(horizontal="center", wrap_text=True)
                    cell.border = border

                # ปรับความกว้างคอลัมน์
                for col in ws.columns:
                    max_len = max((len(str(c.value or "")) for c in col), default=8)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 20)

                # สีแถวสลับ + border
                light = PatternFill("solid", fgColor="F9FAFB")
                green_light = PatternFill("solid", fgColor="E1F5EE")
                red_font = Font(color="DC2626")

                last_data_row = 4 + len(df_detail)
                for row_idx, row in enumerate(ws.iter_rows(min_row=5, max_row=ws.max_row), start=0):
                    is_summary = row_idx >= len(df_detail)
                    for cell in row:
                        cell.border = border
                        cell.alignment = Alignment(horizontal="right" if isinstance(cell.value, (int,float)) else "left")
                        if is_summary:
                            cell.fill = green_light
                            cell.font = Font(bold=True)
                        elif row_idx % 2 == 1:
                            cell.fill = light

                # ไฮไลต์ยอดสุทธิถูกสุด
                if valid_net:
                    best_col_key = f"{best} ยอดรวม"
                    headers = [cell.value for cell in ws[4]]
                    if best_col_key in headers:
                        best_col_idx = headers.index(best_col_key) + 1
                        net_row_idx = 4 + len(df_detail) + 3
                        if net_row_idx <= ws.max_row:
                            cell = ws.cell(row=net_row_idx, column=best_col_idx)
                            cell.fill = PatternFill("solid", fgColor="BBFFD9")
                            cell.font = Font(bold=True, color="064E3B")

            output.seek(0)
            return output.getvalue()

        excel_data = export_excel()
        st.download_button(
            "📊 ดาวน์โหลด Excel (มีฟอร์แมต พร้อมพิมพ์)",
            data=excel_data,
            file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
