import streamlit as st
import pypdf
import re
import math
import tempfile
import os

st.set_page_config(layout="wide")
st.title("Roof Estimator Pro - DEBUG MODE")

TAX_RATE = 0.06

uploaded_file = st.file_uploader("Upload GAF PDF report", type="pdf")

if uploaded_file is not None:
    st.write(f"**File uploaded:** {uploaded_file.name}")
    
    if st.button("Generate Estimate"):
        st.info("Step 1: Button clicked. Saving temporary file...")
        
        try:
            # Save the file physically to the cloud server
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_file_path = tmp_file.name
            
            st.success("Step 1 Complete! File saved to server.")
            st.info("Step 2: Opening PDF with PyPDF...")
            
            reader = pypdf.PdfReader(tmp_file_path)
            
            st.success(f"Step 2 Complete! Found {len(reader.pages)} pages.")
            st.info("Step 3: Checking page count...")
            
            if len(reader.pages) < 7:
                st.error("The uploaded file is not a valid 7+ page GAF report.")
                st.stop()
            
            st.success("Step 3 Complete! Page count is good.")
            st.info("Step 4: Extracting text from Page 1 and Page 7...")
            
            p1 = reader.pages[0].extract_text() or ""
            p7 = reader.pages[6].extract_text() or ""
            
            # Clean up the file
            os.remove(tmp_file_path)
            
            st.success("Step 4 Complete! Text extracted successfully.")
            st.info("Step 5: Running math and identifying state tax...")
            
            # State Detection for Tax
            state_match = re.search(r",\s*(PA|MD|NJ)\s+\d{5}", p1, re.IGNORECASE)
            tax_multiplier = (1 + TAX_RATE) if bool(state_match) else 1.0
            
            def get_p7_val(label, txt):
                pattern = rf"(?m)^\s*{re.escape(label)}\s+([\d\.]+)"
                m = re.search(pattern, txt, re.IGNORECASE)
                return float(m.group(1)) if m else 0.0

            # Measurements
            eaves = get_p7_val("Eaves", p7)
            hips = get_p7_val("Hips", p7)
            ridges = get_p7_val("Ridges", p7)
            rakes = get_p7_val("Rakes", p7)
            valleys = get_p7_val("Valleys", p7)
            
            waste_match = re.search(r"Squares\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+([\d\.]+)", p7)
            waste_sq = float(waste_match.group(1)) if waste_match else 0.0

            mats = {
                "HDZ": {"shingle": 41.33, "iw": 89.88, "start": 56.70, "cap": 61.95, "vent": 18.00, "u_name": "Tigerpaw", "u_price": 159.60},
                "UHDZ": {"shingle": 46.33, "iw": 89.88, "start": 56.70, "cap": 77.95, "vent": 18.00, "u_name": "Tigerpaw", "u_price": 159.60},
                "TAMKO": {"shingle": 36.33, "iw": 68.30, "start": 70.50, "cap": 72.66, "vent": 12.55, "u_name": "Proguard", "u_price": 82.69}
            }

            st.success("Step 5 Complete! Generating tables...")
            
            # --- START DISPLAY ---
            st.write(f"### PROPERTY SUMMARY")
            st.write(f"**Waste Squares:** {waste_sq:.2f} | **Tax Applied:** {'Yes (6%)' if tax_multiplier > 1 else 'No'}")
            st.write(f"**Geometry:** Eaves: {eaves} | Hips: {hips} | Ridges: {ridges} | Rakes: {rakes} | Valleys: {valleys}")
            st.markdown("---")
            
            for tier, d in mats.items():
                s_base = (waste_sq * 3) * d['shingle']
                i_base = math.ceil((eaves + valleys) / 66) * d['iw']
                st_base = math.ceil((eaves + rakes) / 120) * d['start']
                c_base = math.ceil((ridges + hips) / 25) * d['cap']
                v_base = math.ceil(ridges / 4) * d['vent']
                drip_pieces = math.ceil((eaves + rakes) / 10)
                drip_base = drip_pieces * 8.00
                u_rolls = math.ceil(waste_sq / 10)
                u_base = u_rolls * d['u_price']
                gp_base = (waste_sq * 9.00) if tier in ["HDZ", "UHDZ"] else 0
                boot_base = 3 * 10.20
                con_base = 150.00

                s_m, i_m, st_m = s_base * tax_multiplier, i_base * tax_multiplier, st_base * tax_multiplier
                c_m, v_m = c_base * tax_multiplier, v_base * tax_multiplier
                drip_m, u_m = drip_base * tax_multiplier, u_base * tax_multiplier
                gp_m, boot_m, con_m = gp_base * tax_multiplier, boot_base * tax_multiplier, con_base * tax_multiplier
                
                total_mat_base = s_base + i_base + st_base + c_base + v_base + drip_base + u_base + gp_base + boot_base + con_base
                total_tax_amount = total_mat_base * TAX_RATE if tax_multiplier > 1 else 0.0
                
                mt = f"{'Item':<15} | {'Qty':<8} | {'Unit Price':<10} | {'Material $':<10} | {'Labor $':<10}\n"
                mt += "-"*70 + "\n"
                mt += f"{'Shingles':<15} | {waste_sq*3:.0f} bndl | ${d['shingle']:.2f} | ${s_m:<8,.0f} | $1,890\n"
                mt += f"{'I&W':<15} | {math.ceil((eaves+valleys)/66)} roll | ${d['iw']:.2f} | ${i_m:<8,.0f} | $0\n"
                mt += f"{'Starter':<15} | {math.ceil((eaves+rakes)/120)} roll | ${d['start']:.2f} | ${st_m:<8,.0f} | $0\n"
                mt += f"{d['u_name']:<15} | {u_rolls} roll | ${d['u_price']:.2f} | ${u_m:<8,.0f} | $0\n"
                mt += f"{'Caps':<15} | {math.ceil((ridges+hips)/25)} box | ${d['cap']:.2f} | ${c_m:<8,.0f} | $4\n"
                mt += f"{'Ridge Vent':<15} | {math.ceil(ridges/4)} pc | ${d['vent']:.2f} | ${v_m:<8,.0f} | $102\n"
                mt += f"{'Drip Edge':<15} | {drip_pieces} pc | $8.00 | ${drip_m:<8,.0f} | $0\n"
                mt += f"{'Pipe Boots':<15} | 3 pc | $10.20 | ${boot_m:<8,.0f} | $0\n"
                mt += f"{'Consumables':<15} | 1 lot | $150.00 | ${con_m:<8,.0f} | $0\n"
                if gp_m > 0: mt += f"{'Golden Pledge':<15} | {waste_sq:.0f} sq | $9.00 | ${gp_m:<8,.0f} | $0\n"

                st_str = f"\n{'Scenario':<12} | {'Margin %':<8} | {'Total Price':<12} | {'Prod Cost':<10} | {'Dumpster $':<10} | {'Profit $':<10} | {'Price/Sq':<10}\n"
                st_str += "-"*115 + "\n"
                for rate, name in [(105, "1L Walk"), (125, "1L Unwalk"), (125, "2L Walk"), (140, "2L Unwalk")]:
                    tear_off_sq = waste_sq * 2 if "2L" in name else waste_sq
                    dump_cost = 286.00 + (tear_off_sq * 15.33)
                    p_cost = (waste_sq * rate) + 1890 + s_m + i_m + st_m + u_m + c_m + v_m + drip_m + boot_m + con_m + dump_cost + gp_m
                    for m in [0.30, 0.33, 0.35, 0.37, 0.40, 0.45]:
                        total = p_cost / (1-m)
                        st_str += f"{name:<12} | {m*100:>7.0f}% | ${total:>10,.0f} | ${p_cost:>10,.0f} | ${dump_cost:>10,.0f} | ${total-p_cost:>10,.0f} | ${total/waste_sq:>10,.0f}\n"
                    st_str += "-"*115 + "\n"

                st.subheader(f"{tier} Estimate")
                st.write(f"**Total Material Tax for {tier}:** ${total_tax_amount:,.2f}")
                st.markdown(f"<div style='overflow-x: auto; font-family:monospace; font-size:12px; line-height:1.2; white-space:pre;'>{mt}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='overflow-x: auto; font-family:monospace; font-size:12px; line-height:1.2; white-space:pre;'>{st_str}</div>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"CRITICAL ERROR: {e}")
