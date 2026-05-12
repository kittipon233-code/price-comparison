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

if "shops" not in st.session_state:
    st.session_state["shops"] = ["บริษัท A", "บริษัท B", "บริษัท C"]
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

with st.sidebar:
    st.header("⚙️ ตั้งค่าเอกสาร")
    st.session_state["doc_title"] = st.text_input("ชื่อเอกสาร", st.session_state["doc_title"])
    st.session_state["project_name"] = st.text_input("ชื่อโครงการ", st.session_state["project_name"])
    doc_date = st.date_input("วันที่", value=date.today())
    st.session_state["vat_rate"] = st.number_input(
        "อัตรา VAT (%)", value=st.session_state["vat_rate"],
        min_value=0.0, max_value=30.0, step=0.5)

    st.divider()
    st.subheader("🏪 ร้านค้า / บริษัท")
    new_shops = []
    for i, s in enumerate(st.session_state["shops"]):
        new_shops.append(st.text_input(f"ร้านที่ {i+1}", s, key=f"shop_{i}"))
    st.session_state["shops"] = new_shops
    c1, c2 = st.columns(2)
    if c1.button("➕ เพิ่มร้าน"):
        st.session_state["shops"].append(f"บริษัท {chr(65+len(st.session_state['shops']))}")
        st.rerun()
    if c2.button("➖ ลบร้าน") and len(st.session_state["shops"]) > 2:
        st.session_state["shops"].pop()
        st.rerun()

    st.divider()
    st.subheader("🎁 Special Discount (฿)")
    st.caption("ส่วนลดพิเศษรวมทั้งใบจากแต่ละร้าน")
    for s in st.session_state["shops"]:
        cur = float(st.session_state["shop_discounts"].get(s, 0.0))
        st.session_state["shop_discounts"][s] = st.number_input(
            f"{s}", value=cur, min_value=0.0, step=1.0, key=f"sd_{s}")

def calc(price, qty, vat_rate, disc=0.0):
    subtotal = price * qty
    after_disc = subtotal - disc
    vat_amt = after_disc * vat_rate / 100
    total = after_disc + vat_amt
    return subtotal, vat_amt, total, after_disc

tab1, tab2 = st.tabs(["✏️ กรอกข้อมูล", "📊 ตารางเปรียบเทียบ"])

with tab1:
    if st.button("➕ เพิ่มรายการสินค้า"):
        st.session_state["items_list"].append({
            "name": "สินค้าใหม่", "unit": "set", "qty": 1.0,
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
                st.session_state["items_list"][idx]["name"] = ca.text_input("ชื่อสินค้า", it["name"], key=f"n_{idx}")
                st.session_state["items_list"][idx]["unit"] = cb.text_input("หน่วย", it["unit"], key=f"u_{idx}")
                st.session_state["items_list"][idx]["qty"] = cc.number_input("จำนวน", value=float(it["qty"]), min_value=0.0, step=1.0, key=f"q_{idx}")
                if cd.button("🗑 ลบ", key=f"d_{idx}"):
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
                    total_before_disc = price * qty
                    scols[si].markdown(f"Total: **฿{total_before_disc:,.2f}**")
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
        # คำนวณยอดรวมแต่ละร้าน
        grand_subtotal = {s: 0.0 for s in shops}
        for it in items_data:
            qty = float(it["qty"])
            for s in shops:
                grand_subtotal[s] += float(it["prices"].get(s, 0)) * qty

        grand_after_disc = {s: grand_subtotal[s] - float(shop_disc.get(s, 0)) for s in shops}
        grand_vat        = {s: grand_after_disc[s] * vat / 100 for s in shops}
        net_total        = {s: grand_after_disc[s] + grand_vat[s] for s in shops}
        valid_net        = {k: v for k, v in net_total.items() if grand_subtotal[k] > 0}

        if valid_net:
            best = min(valid_net, key=valid_net.get)
            save = max(valid_net.values()) - min(valid_net.values())
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🏆 ร้านถูกสุด", best)
            m2.metric("💰 ยอดสุทธิถูกสุด", f"฿{valid_net[best]:,.2f}")
            m3.metric("✂️ ประหยัดได้", f"฿{save:,.2f}")
            m4.metric("📋 จำนวนรายการ", len(items_data))

        st.divider()

        # ตารางแบบ item rows
        header = ["Item", "Detail", "Q'TY", "Unit"]
        for s in shops:
            header += [f"{s}\nUnit Price", f"{s}\nTotal"]
        tbl_rows = []
        for i, it in enumerate(items_data):
            qty = float(it["qty"])
            row = [i+1, it["name"], int(qty), it["unit"]]
            for s in shops:
                price = float(it["prices"].get(s, 0))
                row += [price, price * qty]
            tbl_rows.append(row)

        df_tbl = pd.DataFrame(tbl_rows, columns=header)
        fmt = {c: "฿{:,.2f}" for c in df_tbl.columns if "Unit Price" in str(c) or "Total" in str(c)}

        def hi(row):
            tot_cols = [c for c in row.index if "Total" in str(c)]
            styles = [""] * len(row)
            vals = {c: float(row[c]) for c in tot_cols if float(row[c]) > 0}
            if not vals: return styles
            mn = min(vals.values())
            for i, col in enumerate(row.index):
                if col in tot_cols and float(row[col]) == mn and float(row[col]) > 0:
                    styles[i] = "background-color:#bbf7d0;font-weight:bold;color:#064e3b"
                elif col in tot_cols and float(row[col]) > mn:
                    styles[i] = "color:#dc2626"
            return styles

        st.dataframe(df_tbl.style.apply(hi, axis=1).format(fmt), use_container_width=True, hide_index=True)

        # สรุปแถวล่าง
        st.divider()
        sum_labels = ["SPECIAL DISCOUNT", f"TOTAL (EXC. VAT)", f"VAT {vat:.0f}%", "TOTAL (INC. VAT)"]
        sum_data = {}
        for s in shops:
            disc = float(shop_disc.get(s, 0))
            sum_data[s] = [
                disc,
                grand_after_disc[s],
                grand_vat[s],
                net_total[s],
            ]

        sum_cols = st.columns([1] + [1]*len(shops))
        sum_cols[0].markdown("**รายการ**")
        for si, s in enumerate(shops):
            lbl = "🏆 " if valid_net and s == best else ""
            sum_cols[si+1].markdown(f"**{lbl}{s}**")

        for ri, label in enumerate(sum_labels):
            row_cols = st.columns([1] + [1]*len(shops))
            row_cols[0].markdown(f"**{label}**")
            for si, s in enumerate(shops):
                val = sum_data[s][ri]
                if label == "TOTAL (INC. VAT)" and valid_net and s == best:
                    row_cols[si+1].success(f"**฿{val:,.2f}**")
                else:
                    row_cols[si+1].markdown(f"฿{val:,.2f}")

        # ===== Export Excel =====
        st.divider()

        def export_excel():
            from openpyxl import Workbook
            from openpyxl.styles import (Font, PatternFill, Alignment,
                                          Border, Side, GradientFill)
            from openpyxl.utils import get_column_letter
            from openpyxl.styles.numbers import FORMAT_NUMBER_COMMA_SEP1

            wb = Workbook()
            ws = wb.active
            ws.title = "เปรียบเทียบราคา"

            # สี
            GREEN      = "1D9E75"
            GREEN_LITE = "E1F5EE"
            BLUE_LITE  = "E8F4FD"
            AMBER_LITE = "FEF9C3"
            GRAY_HDR   = "F1F5F9"
            BEST_GREEN = "BBFFD9"
            WHITE      = "FFFFFF"
            DARK       = "1E293B"

            thin = Side(style="thin", color="CBD5E1")
            med  = Side(style="medium", color="94A3B8")
            bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)
            bdr_med = Border(left=med, right=med, top=med, bottom=med)

            def cell_style(ws, r, c, value="", bold=False, color=DARK, bg=None,
                           align="left", fmt=None, border=None, size=11, wrap=False):
                cell = ws.cell(row=r, column=c, value=value)
                cell.font = Font(bold=bold, color=color, size=size, name="Tahoma")
                if bg:
                    cell.fill = PatternFill("solid", fgColor=bg)
                cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
                if fmt:
                    cell.number_format = fmt
                cell.border = border or bdr
                return cell

            shops_n = st.session_state["shops"]
            n_shops = len(shops_n)
            vat_r   = st.session_state["vat_rate"]

            # คอลัมน์: Item(1) Detail(2) QTY(3) Unit(4) แล้ว Unit Price+Total ต่อร้าน
            COL_ITEM   = 1
            COL_DETAIL = 2
            COL_QTY    = 3
            COL_UNIT   = 4
            SHOP_START = 5

            total_cols = SHOP_START + n_shops * 2 - 1

            # ---- แถว 1: ชื่อเอกสาร ----
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
            t = ws.cell(row=1, column=1,
                        value=f"เปรียบเทียบราคา {st.session_state['project_name']}")
            t.font = Font(bold=True, size=16, color=GREEN, name="Tahoma")
            t.alignment = Alignment(horizontal="center", vertical="center")
            t.fill = PatternFill("solid", fgColor=WHITE)
            ws.row_dimensions[1].height = 30

            # ---- แถว 2: วันที่ ----
            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
            d = ws.cell(row=2, column=1,
                        value=f"วันที่ {doc_date.strftime('%d/%m/%Y')}    VAT {vat_r:.0f}%    เอกสาร: {st.session_state['doc_title']}")
            d.font = Font(size=10, color="64748B", name="Tahoma")
            d.alignment = Alignment(horizontal="center")
            ws.row_dimensions[2].height = 18

            # ---- แถว 3: ว่าง ----
            ws.row_dimensions[3].height = 8

            # ---- แถว 4-5: Header ----
            # merge Item/Detail/QTY/Unit แนวตั้ง
            for c, label in [(COL_ITEM,"Item"),(COL_DETAIL,"Detail"),(COL_QTY,"Q'TY"),(COL_UNIT,"Unit")]:
                ws.merge_cells(start_row=4, start_column=c, end_row=5, end_column=c)
                cell_style(ws, 4, c, label, bold=True, color=WHITE, bg=GREEN,
                           align="center", border=bdr_med, size=10, wrap=True)

            # merge ชื่อร้านแนวนอน + Unit Price/Total แถว 5
            shop_colors = [BLUE_LITE, AMBER_LITE, "F0FDF4", "FFF7ED", "F5F3FF"]
            for si, shop in enumerate(shops_n):
                col_up = SHOP_START + si * 2
                col_tot = col_up + 1
                col_bg = ["1D6B9A","B45309","166534","9A3412","6D28D9"][si % 5]
                ws.merge_cells(start_row=4, start_column=col_up, end_row=4, end_column=col_tot)
                cell_style(ws, 4, col_up, shop, bold=True, color=WHITE,
                           bg=col_bg, align="center", border=bdr_med, size=10, wrap=True)
                cell_style(ws, 5, col_up,  "Unit Price", bold=True, color=DARK,
                           bg=shop_colors[si%5], align="center", border=bdr, size=9)
                cell_style(ws, 5, col_tot, "Total",      bold=True, color=DARK,
                           bg=shop_colors[si%5], align="center", border=bdr, size=9)

            ws.row_dimensions[4].height = 22
            ws.row_dimensions[5].height = 18

            # ---- แถว Data ----
            row = 6
            stripe_bg = ["FFFFFF", "F8FAFC"]
            for i, it in enumerate(items_data):
                qty  = float(it["qty"])
                bg   = stripe_bg[i % 2]
                cell_style(ws, row, COL_ITEM,   i+1,          align="center", bg=bg)
                cell_style(ws, row, COL_DETAIL,  it["name"],   align="left",   bg=bg, wrap=True)
                cell_style(ws, row, COL_QTY,     int(qty),     align="center", bg=bg)
                cell_style(ws, row, COL_UNIT,    it["unit"],   align="center", bg=bg)

                best_price = None
                price_vals = []
                for s in shops_n:
                    p = float(it["prices"].get(s, 0))
                    price_vals.append(p * qty)
                valid_pv = [v for v in price_vals if v > 0]
                if valid_pv:
                    best_price = min(valid_pv)

                for si, shop in enumerate(shops_n):
                    col_up  = SHOP_START + si * 2
                    col_tot = col_up + 1
                    price = float(it["prices"].get(shop, 0))
                    total_val = price * qty
                    is_best = (best_price and total_val == best_price and total_val > 0)

                    cell_bg = BEST_GREEN if is_best else bg
                    cell_style(ws, row, col_up,  price,     align="right", bg=cell_bg,
                               fmt='#,##0.00', bold=is_best)
                    cell_style(ws, row, col_tot, total_val, align="right", bg=cell_bg,
                               fmt='#,##0.00', bold=is_best)

                ws.row_dimensions[row].height = 20
                row += 1

            # ---- แถว Summary ----
            sum_labels_ex = [
                ("SPECIAL DISCOUNT", "disc"),
                ("TOTAL (EXC. VAT)", "exc"),
                (f"VAT {vat_r:.0f}%", "vat"),
                ("TOTAL (INC. VAT)", "inc"),
            ]
            sum_bg = [AMBER_LITE, GRAY_HDR, GRAY_HDR, GREEN_LITE]
            sum_bold = [False, True, False, True]

            best_shop_idx = None
            if valid_net:
                best_shop_idx = shops_n.index(best)

            for li, (label, key) in enumerate(sum_labels_ex):
                # merge label
                ws.merge_cells(start_row=row, start_column=COL_ITEM, end_row=row, end_column=COL_UNIT)
                cell_style(ws, row, COL_ITEM, label, bold=sum_bold[li],
                           align="right", bg=sum_bg[li], size=10)

                for si, shop in enumerate(shops_n):
                    col_up  = SHOP_START + si * 2
                    col_tot = col_up + 1
                    disc_v  = float(shop_disc.get(shop, 0))
                    sub_v   = grand_subtotal[shop]
                    exc_v   = grand_after_disc[shop]
                    vat_v   = grand_vat[shop]
                    inc_v   = net_total[shop]
                    vals    = {"disc": disc_v, "exc": exc_v, "vat": vat_v, "inc": inc_v}
                    v       = vals[key]

                    is_best_shop = (key == "inc" and si == best_shop_idx)
                    bg_cell = BEST_GREEN if is_best_shop else sum_bg[li]

                    ws.merge_cells(start_row=row, start_column=col_up,
                                   end_row=row, end_column=col_tot)
                    cell_style(ws, row, col_up, v, bold=sum_bold[li] or is_best_shop,
                               align="right", bg=bg_cell, fmt='#,##0.00', size=10)

                ws.row_dimensions[row].height = 18
                row += 1

            # ---- ปรับขนาดคอลัมน์ ----
            ws.column_dimensions[get_column_letter(COL_ITEM)].width   = 6
            ws.column_dimensions[get_column_letter(COL_DETAIL)].width = 36
            ws.column_dimensions[get_column_letter(COL_QTY)].width    = 7
            ws.column_dimensions[get_column_letter(COL_UNIT)].width   = 8
            for si in range(n_shops):
                col_up  = SHOP_START + si * 2
                ws.column_dimensions[get_column_letter(col_up)].width   = 13
                ws.column_dimensions[get_column_letter(col_up+1)].width = 13

            # freeze panes
            ws.freeze_panes = "E6"

            out = io.BytesIO()
            wb.save(out)
            out.seek(0)
            return out.getvalue()

        excel_data = export_excel()
        st.download_button(
            "📊 ดาวน์โหลด Excel (ฟอร์แมตทางการ)",
            data=excel_data,
            file_name=f"{st.session_state['doc_title']}_{doc_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
