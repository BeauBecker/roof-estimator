import streamlit as st
import pypdf
import re
import math
import tempfile
import os
import pandas as pd

st.set_page_config(page_title="Roof Estimator Pro", layout="wide")
st.title("Roof Estimator Pro")
st.markdown("Upload a GAF PDF report and generate a material and pricing estimate for HDZ, UHDZ, and TAMKO scenarios.")

TAX_RATE = 0.06

uploaded_file = st.file_uploader("Upload GAF PDF report", type="pdf")

with st.expander("Optional add-on work and costs", expanded=True):
    st.markdown("**Task-based pricing options**")
    waste_percent = st.number_input(
        "Waste percentage",
        min_value=0.0,
        value=20.0,
        step=0.1,
        format="%.1f",
        help="Override the report waste percentage used to calculate total squares for materials.",
    )
    skylight_replacement = st.checkbox("Skylight Replacement — Labor $160.00 per skylight")
    skylight_count = st.number_input(
        "Skylight quantity",
        min_value=0,
        value=0,
        step=1,
        disabled=not skylight_replacement,
    )
    step_flasher = st.checkbox("Replace Step Flashing — Labor $60.00 per section")
    step_flashing_sections = st.number_input(
        "Step flashing sections",
        min_value=0,
        value=0,
        step=1,
        disabled=not step_flasher,
    )
    plywood_replacement = st.checkbox("Plywood Replacement — Labor $20.00 + Material $12.50 per sheet")
    plywood_sheets = st.number_input(
        "Plywood sheets",
        min_value=0,
        value=0,
        step=1,
        disabled=not plywood_replacement,
    )
    chimney_flasher = st.checkbox("Chimney Flashing — Labor $160.00 per chimney")
    chimney_flashing_count = st.number_input(
        "Chimney flashing quantity",
        min_value=0,
        value=0,
        step=1,
        disabled=not chimney_flasher,
    )
    smart_vent_replacement = st.checkbox("Smart Vent Replacement — Labor $4.00/ft, Material $4.20/ft")
    smart_vent_feet = st.number_input(
        "Smart vent length (ft)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.1f",
        disabled=not smart_vent_replacement,
    )

    gutter_5k_white = st.checkbox("5k Gutters White — $6.00 per foot")
    gutter_5k_white_length = st.number_input(
        "5k Gutters White length (ft)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.1f",
        disabled=not gutter_5k_white,
    )
    gutter_6k_white = st.checkbox("6k Gutters White — $8.00 per foot")
    gutter_6k_white_length = st.number_input(
        "6k Gutters White length (ft)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.1f",
        disabled=not gutter_6k_white,
    )
    gutter_6k_colored = st.checkbox("6k Gutters Colored — $10.00 per foot")
    gutter_6k_colored_length = st.number_input(
        "6k Gutters Colored length (ft)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.1f",
        disabled=not gutter_6k_colored,
    )
    attic_fan_install = st.checkbox("Attic Fan Install — $120.00")

    st.markdown("**Custom extra costs**")
    extra_material_enabled = st.checkbox("Include extra materials")
    extra_material_cost = st.number_input(
        "Extra material cost ($)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        format="%.2f",
        disabled=not extra_material_enabled,
    ) if extra_material_enabled else 0.0

    extra_labor_enabled = st.checkbox("Include extra labor")
    extra_labor_cost = st.number_input(
        "Extra labor cost ($)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        format="%.2f",
        disabled=not extra_labor_enabled,
    ) if extra_labor_enabled else 0.0

    extra_other_enabled = st.checkbox("Include other additional costs")
    extra_other_cost = st.number_input(
        "Other additional cost ($)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        format="%.2f",
        disabled=not extra_other_enabled,
    ) if extra_other_enabled else 0.0

    permit_fees_enabled = st.checkbox("Include permit fees")
    permit_fees_cost = st.number_input(
        "Permit fee cost ($)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        format="%.2f",
        disabled=not permit_fees_enabled,
    ) if permit_fees_enabled else 0.0

skylight_count = skylight_count if skylight_replacement else 0
skylight_cost = skylight_count * 160.00
step_flasher_cost = step_flashing_sections * 60.00 if step_flasher else 0.0
plywood_labor_cost = plywood_sheets * 20.00 if plywood_replacement else 0.0
plywood_material_cost = plywood_sheets * 12.50 if plywood_replacement else 0.0
chimney_cost = chimney_flashing_count * 160.00 if chimney_flasher else 0.0
smart_vent_labor_cost = smart_vent_feet * 4.00 if smart_vent_replacement else 0.0
smart_vent_material_cost = smart_vent_feet * 4.20 if smart_vent_replacement else 0.0

gutter_5k_white_cost = gutter_5k_white_length * 6.00 if gutter_5k_white else 0.0
        
gutter_6k_white_cost = gutter_6k_white_length * 8.00 if gutter_6k_white else 0.0
        
gutter_6k_colored_cost = gutter_6k_colored_length * 10.00 if gutter_6k_colored else 0.0
        
attic_fan_cost = 120.00 if attic_fan_install else 0.0

extra_cost_total = (
    skylight_cost
    + step_flasher_cost
    + plywood_labor_cost
    + plywood_material_cost
    + chimney_cost
    + smart_vent_labor_cost
    + smart_vent_material_cost    + gutter_5k_white_cost
    + gutter_6k_white_cost
    + gutter_6k_colored_cost
    + attic_fan_cost    + extra_material_cost
    + extra_labor_cost
    + extra_other_cost
    + permit_fees_cost
)


def get_p7_val(label: str, txt: str) -> float:
    pattern = rf"(?m)^\s*{re.escape(label)}\s+([\d\.]+)"
    m = re.search(pattern, txt, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def parse_report(pdf_path: str) -> tuple[str, str]:
    reader = pypdf.PdfReader(pdf_path)
    if len(reader.pages) < 7:
        raise ValueError("The uploaded file is not a valid 7+ page GAF report.")

    p1 = reader.pages[0].extract_text() or ""
    p7 = reader.pages[6].extract_text() or ""
    return p1, p7


def get_property_address(p1: str) -> str:
    # First try labels and common oneline address formats.
    address_match = re.search(
        r"Address[:\s]*([0-9]+[A-Za-z0-9 .#\-/]+?,\s*[A-Za-z .]+,\s*(?:PA|MD|NJ)\s+\d{5})",
        p1,
        re.IGNORECASE,
    )
    if address_match:
        return address_match.group(1).strip()

    address_match = re.search(
        r"([0-9]+[A-Za-z0-9 .#\-/]+?,\s*[A-Za-z .]+,\s*(?:PA|MD|NJ)\s+\d{5})",
        p1,
    )
    if address_match:
        return address_match.group(1).strip()

    # Try multi-line street + city/state/zip formats.
    address_match = re.search(
        r"([0-9]+[A-Za-z0-9 .#\-/]+?)\s*[\n\r]+([A-Za-z .]+?,\s*(?:PA|MD|NJ)\s+\d{5})",
        p1,
        re.MULTILINE,
    )
    if address_match:
        return f"{address_match.group(1).strip()}, {address_match.group(2).strip()}"

    # Last fallback: any street address with state + zip on the same line.
    address_match = re.search(
        r"([0-9]+[A-Za-z0-9 .#\-/]+\s+(?:PA|MD|NJ)\s+\d{5})",
        p1,
    )
    if address_match:
        return address_match.group(1).strip()

    return "Unknown"


def extract_metrics(p7: str) -> dict[str, float]:
    metrics = {
        "Eaves": get_p7_val("Eaves", p7),
        "Hips": get_p7_val("Hips", p7),
        "Ridges": get_p7_val("Ridges", p7),
        "Rakes": get_p7_val("Rakes", p7),
        "Valleys": get_p7_val("Valleys", p7),
        "RoofSq": 0.0,
    }

    squares_line = re.search(r"Squares\s+([\d\.]+(?:\s+[\d\.]+)+)", p7)
    if squares_line:
        values = [float(v) for v in re.findall(r"[\d\.]+", squares_line.group(1))]
        if values:
            metrics["RoofSq"] = values[0]
        if len(values) >= 1:
            metrics["Waste"] = values[-1]
        else:
            metrics["Waste"] = 0.0
    else:
        metrics["Waste"] = 0.0

    return metrics


def build_tables(waste_sq: float, eaves: float, hips: float, ridges: float, rakes: float, valleys: float, tax_multiplier: float, extra_cost_total: float, extra_material_cost: float = 0.0, extra_labor_cost: float = 0.0, extra_other_cost: float = 0.0, permit_fees_cost: float = 0.0) -> dict[str, dict[str, str]]:
    mats = {
        "HDZ": {"shingle": 41.33, "iw": 89.88, "start": 56.70, "cap": 61.95, "vent": 18.00, "u_name": "Tigerpaw", "u_price": 159.60},
        "UHDZ": {"shingle": 46.33, "iw": 89.88, "start": 56.70, "cap": 77.95, "vent": 18.00, "u_name": "Tigerpaw", "u_price": 159.60},
        "TAMKO": {"shingle": 36.33, "iw": 68.30, "start": 70.50, "cap": 72.66, "vent": 12.55, "u_name": "Proguard", "u_price": 82.69},
    }

    result = {}

    for tier, d in mats.items():
        shingle_bundles = math.ceil(waste_sq * 3)
        s_base = shingle_bundles * d["shingle"]
        i_base = math.ceil((eaves + valleys) / 66) * d["iw"]
        st_base = math.ceil((eaves + rakes) / 120) * d["start"]
        c_base = math.ceil((ridges + hips) / 25) * d["cap"]
        v_base = math.ceil(ridges / 4) * d["vent"]
        drip_pieces = math.ceil((eaves + rakes) / 10)
        drip_base = drip_pieces * 8.00
        u_rolls = math.ceil(waste_sq / 10)
        u_base = u_rolls * d["u_price"]
        gp_base = (waste_sq * 9.00) if tier in ["HDZ", "UHDZ"] else 0
        boot_base = 3 * 10.20
        con_base = 150.00

        s_m = s_base * tax_multiplier
        i_m = i_base * tax_multiplier
        st_m = st_base * tax_multiplier
        c_m = c_base * tax_multiplier
        v_m = v_base * tax_multiplier
        drip_m = drip_base * tax_multiplier
        u_m = u_base * tax_multiplier
        gp_m = gp_base * tax_multiplier
        boot_m = boot_base * tax_multiplier
        con_m = con_base * tax_multiplier

        total_mat_base = s_base + i_base + st_base + c_base + v_base + drip_base + u_base + gp_base + boot_base + con_base
        total_tax_amount = total_mat_base * TAX_RATE if tax_multiplier > 1 else 0.0

        mt = f"{'Item':<15} | {'Qty':<8} | {'Unit Price':<10} | {'Material $':<12} | {'Labor $':<8}\n"
        mt += "-" * 70 + "\n"
        mt += f"{'Shingles':<15} | {shingle_bundles} bndl | ${d['shingle']:.2f} | ${s_m:<10,.0f} | $1,890\n"
        mt += f"{'I&W':<15} | {math.ceil((eaves + valleys) / 66)} roll | ${d['iw']:.2f} | ${i_m:<10,.0f} | $0\n"
        mt += f"{'Starter':<15} | {math.ceil((eaves + rakes) / 120)} roll | ${d['start']:.2f} | ${st_m:<10,.0f} | $0\n"
        mt += f"{d['u_name']:<15} | {u_rolls} roll | ${d['u_price']:.2f} | ${u_m:<10,.0f} | $0\n"
        mt += f"{'Caps':<15} | {math.ceil((ridges + hips) / 25)} box | ${d['cap']:.2f} | ${c_m:<10,.0f} | $4\n"
        mt += f"{'Ridge Vent':<15} | {math.ceil(ridges / 4)} pc | ${d['vent']:.2f} | ${v_m:<10,.0f} | $102\n"
        mt += f"{'Drip Edge':<15} | {drip_pieces} pc | $8.00 | ${drip_m:<10,.0f} | $0\n"
        mt += f"{'Pipe Boots':<15} | 3 pc | $10.20 | ${boot_m:<10,.0f} | $0\n"
        mt += f"{'Consumables':<15} | 1 lot | $150.00 | ${con_m:<10,.0f} | $0\n"
        if gp_m > 0:
            mt += f"{'Golden Pledge':<15} | {waste_sq:.0f} sq | $9.00 | ${gp_m:<10,.0f} | $0\n"

        st_str = f"{ 'Scenario':<12 } | {'Margin %':<8} | {'Total Price':<12} | {'Prod Cost':<10} | {'Dumpster $':<10} | {'Material $':<12} | {'Profit $':<10} | {'Price/Sq':<10}\n"
        st_str += "-" * 115 + "\n"
        comp_frames = []
        for rate, name in [(105, "1L Walk"), (125, "1L Unwalk"), (125, "2L Walk"), (140, "2L Unwalk")]:
            tear_off_sq = waste_sq * 2 if "2L" in name else waste_sq
            dump_cost = 286.00 + (tear_off_sq * 15.33)
            # separate production (labor), material, dumpster and extras
            production_labor = (waste_sq * rate) + extra_labor_cost
            material_total = s_m + i_m + st_m + u_m + c_m + v_m + drip_m + boot_m + con_m + gp_m + extra_material_cost
            other_extras = extra_other_cost + permit_fees_cost
            p_cost = production_labor + dump_cost + material_total + other_extras
            # Build a short dataframe for a simple component chart
            comp_df = pd.DataFrame(
                {
                    "Production Labour": [production_labor],
                    "Dumpster": [dump_cost],
                    "Materials": [material_total],
                },
                index=[name],
            )
            comp_frames.append(comp_df)
            for m in [0.30, 0.33, 0.35, 0.37, 0.40, 0.45]:
                total = p_cost / (1 - m)
                st_str += f"{name:<12} | {m * 100:>7.0f}% | ${total:>10,.0f} | ${production_labor:>10,.0f} | ${dump_cost:>10,.0f} | ${material_total:>12,.0f} | ${total - p_cost:>10,.0f} | ${total / waste_sq:>10,.0f}\n"
            st_str += "-" * 115 + "\n"
        comp_all = pd.concat(comp_frames) if comp_frames else pd.DataFrame()
        result[tier] = {
            "material_table": mt,
            "scenario_table": st_str,
            "tax_amount": total_tax_amount,
            "component_df": comp_all,
        }

    return result


if uploaded_file is not None:
    st.info(f"File uploaded: {uploaded_file.name}")

    if st.button("Generate Estimate"):
        with st.spinner("Processing PDF and building estimate..."):
            tmp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_file_path = tmp_file.name

                p1, p7 = parse_report(tmp_file_path)
                metrics = extract_metrics(p7)
                property_address = get_property_address(p1)
                waste_sq = metrics["RoofSq"] * (1 + waste_percent / 100.0) if metrics["RoofSq"] > 0 else metrics["Waste"]

                state_match = re.search(r",\s*(PA|MD|NJ)\s+\d{5}", p1, re.IGNORECASE)
                tax_multiplier = 1 + TAX_RATE if bool(state_match) else 1.0

                st.success("PDF parsed successfully.")
                st.write("---")

                st.subheader("Property Summary")
                st.write(f"**Property Address:** {property_address}")
                st.write(f"**Waste Squares:** {waste_sq:.2f}")
                st.write(f"**Waste percentage:** {waste_percent:.1f}%")
                st.write(f"**Tax Applied:** {'Yes (6%)' if tax_multiplier > 1 else 'No'}")
                st.write(f"**Geometry:** Eaves: {metrics['Eaves']} | Hips: {metrics['Hips']} | Ridges: {metrics['Ridges']} | Rakes: {metrics['Rakes']} | Valleys: {metrics['Valleys']}")
                st.write("---")
                st.write("**Task Add-on Costs**")
                if skylight_cost > 0:
                    st.write(f"Skylight Replacement: {skylight_count} skylight(s) — ${skylight_cost:.2f}")
                if step_flasher_cost > 0:
                    st.write(f"Replace Step Flashing: ${step_flasher_cost:.2f}")
                if plywood_labor_cost > 0:
                    st.write(f"Plywood Replacement Labor: ${plywood_labor_cost:.2f}")
                if plywood_material_cost > 0:
                    st.write(f"Plywood Replacement Material: ${plywood_material_cost:.2f}")
                if chimney_cost > 0:
                    st.write(f"Chimney Flashing: {chimney_flashing_count} unit(s) — ${chimney_cost:.2f}")
                if smart_vent_labor_cost > 0:
                    st.write(f"Smart Vent Labor: ${smart_vent_labor_cost:.2f}")
                if smart_vent_material_cost > 0:
                    st.write(f"Smart Vent Material: ${smart_vent_material_cost:.2f}")
                if gutter_5k_white_cost > 0:
                    st.write(f"5k Gutters White: ${gutter_5k_white_cost:.2f}")
                if gutter_6k_white_cost > 0:
                    st.write(f"6k Gutters White: ${gutter_6k_white_cost:.2f}")
                if gutter_6k_colored_cost > 0:
                    st.write(f"6k Gutters Colored: ${gutter_6k_colored_cost:.2f}")
                if attic_fan_cost > 0:
                    st.write(f"Attic Fan Install: ${attic_fan_cost:.2f}")
                if extra_material_cost > 0:
                    st.write(f"Custom extra material cost: ${extra_material_cost:.2f}")
                if extra_labor_cost > 0:
                    st.write(f"Custom extra labor cost: ${extra_labor_cost:.2f}")
                if extra_other_cost > 0:
                    st.write(f"Custom other add-on cost: ${extra_other_cost:.2f}")
                if permit_fees_cost > 0:
                    st.write(f"Permit fees: ${permit_fees_cost:.2f}")
                st.write(f"**Total Add-on Cost:** ${extra_cost_total:.2f}")
                st.write("---")

                waste_sq = metrics["RoofSq"] * (1 + waste_percent / 100.0) if metrics["RoofSq"] > 0 else metrics["Waste"]
                estimates = build_tables(
                    waste_sq=waste_sq,
                    eaves=metrics["Eaves"],
                    hips=metrics["Hips"],
                    ridges=metrics["Ridges"],
                    rakes=metrics["Rakes"],
                    valleys=metrics["Valleys"],
                    tax_multiplier=tax_multiplier,
                    extra_cost_total=extra_cost_total,
                    extra_material_cost=extra_material_cost,
                    extra_labor_cost=extra_labor_cost,
                    extra_other_cost=extra_other_cost,
                    permit_fees_cost=permit_fees_cost,
                )

                for tier, data in estimates.items():
                    st.subheader(f"{tier} Estimate")
                    st.write(f"**Total Material Tax for {tier}:** ${data['tax_amount']:,.2f}")
                    st.markdown(
                        f"<div style='overflow-x:auto; font-family:monospace; font-size:12px; line-height:1.2; white-space:pre;'>{data['material_table']}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div style='overflow-x:auto; font-family:monospace; font-size:12px; line-height:1.2; white-space:pre;'>{data['scenario_table']}</div>",
                        unsafe_allow_html=True,
                    )
                    # Show a simple bar chart of Production (labor), Dumpster, and Materials components
                    if not data.get("component_df", pd.DataFrame()).empty:
                        st.write("**Component breakdown (Production labour vs Dumpster vs Materials)**")
                        st.bar_chart(data["component_df"])
            except Exception as e:
                st.error(f"CRITICAL ERROR: {e}")
            finally:
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)
