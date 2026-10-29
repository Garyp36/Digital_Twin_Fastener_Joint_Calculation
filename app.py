from __future__ import annotations

import math
import csv
import io
import re
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------
# Geometry values are keyed by nominal metric thread size. The Fine/Medium/
# Coarse field in the form is recorded for the workflow and does not alter
# screw geometry or the agreed hole-size formulas.
#
# Sources/labels agreed for this demo:
#   Flanged hex screw: TS 17130
#   Square weld nut with collar: TS 17426
#
# Fastener preload/torque and proof-stress tables below are carried forward
# from the supplied prototype. Replace these constants with controlled,
# revisioned data when the approved database is connected.

SCREW_GEOMETRY: dict[str, dict[str, float]] = {
    "M6":  {"d": 6.0,  "s": 10.0, "e": 11.05, "dc": 14.0, "k": 6.0,  "c": 0.8},
    "M8":  {"d": 8.0,  "s": 12.0, "e": 13.25, "dc": 17.5, "k": 8.0,  "c": 1.0},
    "M10": {"d": 10.0, "s": 14.0, "e": 15.51, "dc": 21.0, "k": 10.0, "c": 1.2},
    "M12": {"d": 12.0, "s": 17.0, "e": 18.90, "dc": 25.0, "k": 11.5, "c": 1.4},
}

SQUARE_WELD_NUT_DB: dict[str, dict[str, float]] = {
    "M6":  {"d1": 6.0,  "d4": 9.1,  "s": 10.0, "e": 13.0, "m_above_panel": 3.2, "h2": 1.8},
    "M8":  {"d1": 8.0,  "d4": 12.8, "s": 14.0, "e": 18.0, "m_above_panel": 4.5, "h2": 2.0},
    "M10": {"d1": 10.0, "d4": 15.6, "s": 17.0, "e": 22.0, "m_above_panel": 5.8, "h2": 2.2},
    "M12": {"d1": 12.0, "d4": 17.4, "s": 19.0, "e": 25.0, "m_above_panel": 6.5, "h2": 3.0},
}

# Thread variants are offered only where the supplied prototype has matching
# preload/torque data. The M10 x 1.25 geometry variant is not offered because
# the supplied performance table contains M10 x 1.0, which is a different
# pitch and must not be substituted.
THREAD_OPTIONS: dict[str, dict[str, Any]] = {
    "M6": {"base": "M6", "pitch": 1.0, "performance_key": "M6", "thread_type": "Coarse"},
    "M8": {"base": "M8", "pitch": 1.25, "performance_key": "M8", "thread_type": "Coarse"},
    "M8x1": {"base": "M8", "pitch": 1.0, "performance_key": "M8x1", "thread_type": "Fine"},
    "M10": {"base": "M10", "pitch": 1.5, "performance_key": "M10", "thread_type": "Coarse"},
    "M12": {"base": "M12", "pitch": 1.75, "performance_key": "M12", "thread_type": "Coarse"},
    "M12x1.5": {"base": "M12", "pitch": 1.5, "performance_key": "M12x1.5", "thread_type": "Fine"},
}

PREFERRED_LENGTH_RANGE: dict[str, tuple[float, float]] = {
    "M6": (25.0, 60.0),
    "M8": (30.0, 80.0),
    "M10": (40.0, 100.0),
    "M12": (45.0, 120.0),
}

SURFACE_PROTECTION: dict[str, str] = {
    "Phosphated (SS9400)": "Phosphated",
    "Zinc plated (SS8451 / SS8451S2)": "Zinc_Plated",
}

# Database values from the supplied prototype. P is kgf; T is kgf.m.
FASTENER_PERFORMANCE: dict[str, dict[str, dict[str, dict[str, float]]]] = {
    "M6": {
        "Phosphated": {
            "8.8": {"P_kgf": 900, "T_kgfm": 1.0},
            "10.9": {"P_kgf": 1260, "T_kgfm": 1.4},
            "12.9": {"P_kgf": 1510, "T_kgfm": 1.7},
        },
        "Zinc_Plated": {
            "8.8": {"P_kgf": 925, "T_kgfm": 0.95},
            "10.9": {"P_kgf": 1300, "T_kgfm": 1.3},
            "12.9": {"P_kgf": 1560, "T_kgfm": 1.6},
        },
    },
    "M8": {
        "Phosphated": {
            "8.8": {"P_kgf": 1650, "T_kgfm": 2.5},
            "10.9": {"P_kgf": 2320, "T_kgfm": 3.5},
            "12.9": {"P_kgf": 2790, "T_kgfm": 4.1},
        },
        "Zinc_Plated": {
            "8.8": {"P_kgf": 1700, "T_kgfm": 2.3},
            "10.9": {"P_kgf": 2390, "T_kgfm": 3.2},
            "12.9": {"P_kgf": 2870, "T_kgfm": 3.9},
        },
    },
    "M10": {
        "Phosphated": {
            "8.8": {"P_kgf": 2620, "T_kgfm": 4.9},
            "10.9": {"P_kgf": 3690, "T_kgfm": 6.9},
            "12.9": {"P_kgf": 4430, "T_kgfm": 8.3},
        },
        "Zinc_Plated": {
            "8.8": {"P_kgf": 2710, "T_kgfm": 4.6},
            "10.9": {"P_kgf": 3800, "T_kgfm": 6.4},
            "12.9": {"P_kgf": 4570, "T_kgfm": 7.7},
        },
    },
    "M12": {
        "Phosphated": {
            "8.8": {"P_kgf": 3830, "T_kgfm": 8.6},
            "10.9": {"P_kgf": 5400, "T_kgfm": 12.0},
            "12.9": {"P_kgf": 6450, "T_kgfm": 14.5},
        },
        "Zinc_Plated": {
            "8.8": {"P_kgf": 3950, "T_kgfm": 8.0},
            "10.9": {"P_kgf": 5550, "T_kgfm": 11.0},
            "12.9": {"P_kgf": 6670, "T_kgfm": 13.5},
        },
    },
}

FINE_THREAD_PERFORMANCE: dict[str, dict[str, dict[str, dict[str, float]]]] = {
    "M8x1": {
        "Phosphated": {
            "8.8": {"P_kgf": 1810, "T_kgfm": 2.7},
            "10.9": {"P_kgf": 2550, "T_kgfm": 3.8},
            "12.9": {"P_kgf": 3060, "T_kgfm": 4.5},
        },
        "Zinc_Plated": {
            "8.8": {"P_kgf": 1860, "T_kgfm": 2.5},
            "10.9": {"P_kgf": 2620, "T_kgfm": 3.5},
            "12.9": {"P_kgf": 3150, "T_kgfm": 4.2},
        },
    },
    "M12x1.5": {
        "Phosphated": {
            "8.8": {"P_kgf": 4070, "T_kgfm": 9.0},
            "10.9": {"P_kgf": 5700, "T_kgfm": 12.5},
            "12.9": {"P_kgf": 6850, "T_kgfm": 15.0},
        },
        "Zinc_Plated": {
            "8.8": {"P_kgf": 4190, "T_kgfm": 8.3},
            "10.9": {"P_kgf": 5900, "T_kgfm": 11.5},
            "12.9": {"P_kgf": 7050, "T_kgfm": 14.0},
        },
    },
}

BOLT_PROPERTIES: dict[str, dict[str, float]] = {
    "8.8": {"proof_mpa": 600.0, "yield_mpa": 640.0},
    "10.9": {"proof_mpa": 830.0, "yield_mpa": 900.0},
    "12.9": {"proof_mpa": 970.0, "yield_mpa": 1080.0},
}

NUT_PROOF_STRESS_MPA: dict[str, float] = {
    "8": 800.0,
    "10": 1040.0,
    "12": 1200.0,
}

HOLE_CLASSES = ("Fine", "Medium", "Coarse")
BOLT_GRADES = ("8.8", "10.9", "12.9")
NUT_CLASSES = ("8", "10", "12")


# ---------------------------------------------------------------------------
# Engineering calculations
# ---------------------------------------------------------------------------

def performance_table_for(thread_label: str) -> dict[str, dict[str, dict[str, float]]]:
    thread = THREAD_OPTIONS[thread_label]
    key = thread["performance_key"]
    if key in FINE_THREAD_PERFORMANCE:
        return FINE_THREAD_PERFORMANCE[key]
    return FASTENER_PERFORMANCE[key]


def circle_intersection_area(r1: float, r2: float, distance: float) -> float:
    """Area shared by two circles."""
    r1, r2, distance = abs(r1), abs(r2), abs(distance)
    if r1 <= 0.0 or r2 <= 0.0:
        return 0.0
    if distance >= r1 + r2:
        return 0.0
    if distance <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2

    cos1 = max(-1.0, min(1.0, (distance**2 + r1**2 - r2**2) / (2.0 * distance * r1)))
    cos2 = max(-1.0, min(1.0, (distance**2 + r2**2 - r1**2) / (2.0 * distance * r2)))
    alpha = math.acos(cos1)
    beta = math.acos(cos2)
    triangle = 0.5 * math.sqrt(
        max(0.0, (-distance + r1 + r2) * (distance + r1 - r2)
            * (distance - r1 + r2) * (distance + r1 + r2))
    )
    return r1**2 * alpha + r2**2 * beta - triangle


def flange_bearing_area(flange_diameter: float, hole_diameter: float, radial_shift: float) -> float:
    """Flange area outside the overlapping through-hole area."""
    flange_r = flange_diameter / 2.0
    hole_r = hole_diameter / 2.0
    flange_area = math.pi * flange_r**2
    overlap = circle_intersection_area(flange_r, hole_r, radial_shift)
    return max(0.0, flange_area - overlap)


def calculate_design(inputs: dict[str, Any]) -> dict[str, Any]:
    thread_label = inputs["thread"]
    thread = THREAD_OPTIONS[thread_label]
    base_size = thread["base"]
    nut_base_size = inputs.get("nut_base_size", base_size)
    screw = SCREW_GEOMETRY[base_size]
    nut = SQUARE_WELD_NUT_DB[nut_base_size]
    diameter = screw["d"]
    pitch = float(thread["pitch"])

    panels = inputs["panels"]
    gaps = inputs["gaps"]
    weld_nut_panel = int(inputs["weld_nut_panel"])
    if not 1 <= weld_nut_panel <= len(panels):
        raise ValueError("Weld-nut panel must be one of the entered panels.")

    # Panel 1 is at the bolt-head contact side. The clamped stack ends at the
    # selected weld-nut panel; gaps after that panel are outside this stack.
    clamped_thickness = sum(p["thickness"] for p in panels[:weld_nut_panel])
    clamped_gap = sum(gaps[:max(0, weld_nut_panel - 1)])
    nut_height_above_panel = nut["m_above_panel"]
    required_screw_length = clamped_thickness + clamped_gap + nut_height_above_panel + 3.0 * pitch

    length_min, length_max = PREFERRED_LENGTH_RANGE[base_size]
    length_in_range = length_min <= required_screw_length <= length_max

    # The panel adjacent to the weld-nut panel on the bolt-head side is the
    # panel that can foul with the collar. If the weld nut is on Panel 1, use
    # the next panel as the adjacent panel for this schematic stack.
    if weld_nut_panel > 1:
        collar_neighbor_index = weld_nut_panel - 2
    else:
        collar_neighbor_index = 1 if len(panels) > 1 else None

    weld_panel_thickness = panels[weld_nut_panel - 1]["thickness"]
    special_top_panel_index = None
    if weld_panel_thickness < nut["h2"] and collar_neighbor_index is not None:
        special_top_panel_index = collar_neighbor_index

    hole_rows: list[dict[str, Any]] = []
    for i, panel in enumerate(panels):
        panel_number = i + 1
        if panel_number == weld_nut_panel:
            nominal_hole = nut["d4"] + 1.0
            rule = f"TS 17426 weld-nut panel: d4 + 1 mm = {nominal_hole:.2f} mm"
            role = "Square weld-nut panel"
        elif i == special_top_panel_index:
            nominal_hole = nut["d4"] + 2.0
            rule = (
                f"Collar extends beyond weld-nut panel (h2 {nut['h2']:.2f} mm > "
                f"panel {weld_panel_thickness:.2f} mm): d4 + 2 mm = {nominal_hole:.2f} mm"
            )
            role = "Adjacent top panel"
        else:
            nominal_hole = diameter + 2.0
            rule = f"Non-weld-nut panel: thread d + 2 mm = {nominal_hole:.2f} mm"
            role = "Non-weld-nut panel"

        minus_tol = float(panel["tol_minus"])
        plus_tol = float(panel["tol_plus"])
        minimum_hole = nominal_hole - minus_tol
        maximum_hole = nominal_hole + plus_tol

        if panel_number == weld_nut_panel:
            required_min_hole = nut["d4"]
        elif i == special_top_panel_index:
            required_min_hole = nut["d4"]
        else:
            # The user enters maximum radial shift ±e; the hole must allow the
            # screw diameter plus 2e at its minimum material condition.
            required_min_hole = diameter + 2.0 * inputs["radial_shift"]

        hole_rows.append({
            "Panel": f"Panel {panel_number}",
            "Role": role,
            "Thickness (mm)": panel["thickness"],
            "Hole rule": rule,
            "Nominal hole (mm)": nominal_hole,
            "Tol - (mm)": minus_tol,
            "Tol + (mm)": plus_tol,
            "Minimum hole (mm)": minimum_hole,
            "Maximum hole (mm)": maximum_hole,
            "Minimum required (mm)": required_min_hole,
            "Fit check": "OK" if minimum_hole + 1e-9 >= required_min_hole else "Warning",
        })

    panel1 = hole_rows[0]
    nominal_bearing = flange_bearing_area(screw["dc"], panel1["Nominal hole (mm)"], 0.0)
    worst_bearing = flange_bearing_area(
        screw["dc"],
        panel1["Maximum hole (mm)"],
        inputs["radial_shift"],
    )
    oversized_panel1 = panel1["Maximum hole (mm)"] > diameter + 2.0 + 1e-9

    stack_rows = []
    for i in range(weld_nut_panel):
        stack_rows.append({
            "Stack component": f"Panel {i + 1} thickness",
            "Value (mm)": panels[i]["thickness"],
        })
        if i < weld_nut_panel - 1:
            stack_rows.append({
                "Stack component": f"Gap {i + 1}",
                "Value (mm)": gaps[i],
            })
    stack_rows.extend([
        {"Stack component": "Nut height above panel surface", "Value (mm)": nut_height_above_panel},
        {"Stack component": "Three threads beyond nut (3 × pitch)", "Value (mm)": 3.0 * pitch},
        {"Stack component": "Calculated screw length", "Value (mm)": required_screw_length},
    ])

    perf_table = performance_table_for(thread_label)
    fastener_rows: list[dict[str, Any]] = []
    for grade in BOLT_GRADES:
        perf = perf_table[inputs["surface_key"]][grade]
        bolt_prop = BOLT_PROPERTIES[grade]
        for nut_class in NUT_CLASSES:
            nut_proof = NUT_PROOF_STRESS_MPA[nut_class]
            passes = nut_proof >= bolt_prop["proof_mpa"]
            warning_reasons = []
            if not passes:
                warning_reasons.append(
                    f"Nut class {nut_class} proof stress ({nut_proof:.0f} MPa) is below "
                    f"bolt grade {grade} proof stress ({bolt_prop['proof_mpa']:.0f} MPa)."
                )
            if not length_in_range:
                warning_reasons.append(
                    f"Calculated screw length ({required_screw_length:.2f} mm) is outside "
                    f"the {base_size} preferred range ({length_min:.0f}–{length_max:.0f} mm)."
                )
            fastener_rows.append({
                "Bolt grade": grade,
                "Bolt proof stress (MPa)": bolt_prop["proof_mpa"],
                "Bolt yield stress (MPa)": bolt_prop["yield_mpa"],
                "Nut class": nut_class,
                "Nut proof stress (MPa)": nut_proof,
                "Nut proof ≥ bolt proof": "OK" if passes else "Warning",
                "Database preload (kgf)": perf["P_kgf"],
                "Database torque (kgf·m)": perf["T_kgfm"],
                "Screw length check": "OK" if length_in_range else "Warning",
                "Warning reason": " ".join(warning_reasons) if warning_reasons else "None",
            })

    return {
        "thread": thread_label,
        "base_size": base_size,
        "nut_base_size": nut_base_size,
        "thread_type": thread["thread_type"],
        "pitch": pitch,
        "screw": screw,
        "nut": nut,
        "panels": panels,
        "gaps": gaps,
        "weld_nut_panel": weld_nut_panel,
        "clamped_thickness": clamped_thickness,
        "clamped_gap": clamped_gap,
        "nut_height_above_panel": nut_height_above_panel,
        "required_screw_length": required_screw_length,
        "length_range": (length_min, length_max),
        "length_in_range": length_in_range,
        "hole_rows": hole_rows,
        "nominal_bearing": nominal_bearing,
        "worst_bearing": worst_bearing,
        "radial_shift": inputs["radial_shift"],
        "position_zone_diameter": 2.0 * inputs["radial_shift"],
        "oversized_panel1": oversized_panel1,
        "fastener_rows": fastener_rows,
        "hole_class": inputs["hole_class"],
        "surface_label": inputs["surface_label"],
        "surface_key": inputs["surface_key"],
    }


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def create_joint_cross_section(result: dict[str, Any]):
    """Draw the joint with screw head above Panel 1 and weld nut below the stack."""
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    screw = result["screw"]
    nut = result["nut"]
    panels = result["panels"]
    gaps = result["gaps"]
    weld_idx = result["weld_nut_panel"] - 1
    panel_width = max(36.0, screw["dc"] * 2.4)
    hole_rows = result["hole_rows"]

    y = 0.0
    for i in range(weld_idx + 1):
        thickness = panels[i]["thickness"]
        y0 = y
        hole_diameter = hole_rows[i]["Nominal hole (mm)"]
        hole_left = -hole_diameter / 2.0
        hole_right = hole_diameter / 2.0

        # Draw two panel sections with an open central hole. The screw shank is
        # drawn afterward, leaving the diametral clearance visible on each side.
        ax.add_patch(Rectangle(
            (-panel_width / 2.0, y0), panel_width / 2.0 + hole_left, thickness,
            facecolor="#DDE7F2", edgecolor="#4B5563", linewidth=1.1
        ))
        ax.add_patch(Rectangle(
            (hole_right, y0), panel_width / 2.0 - hole_right, thickness,
            facecolor="#DDE7F2", edgecolor="#4B5563", linewidth=1.1
        ))
        y += thickness
        if i < weld_idx:
            gap = gaps[i]
            ax.add_patch(Rectangle(
                (-panel_width / 2.0, y), panel_width, gap,
                facecolor="#FFFFFF", edgecolor="#9CA3AF",
                linewidth=0.8, linestyle="--"
            ))
            y += gap

    stack_bottom = y
    total_head_height = screw["k"]
    flange_thickness = screw["c"]
    head_body_height = max(0.0, total_head_height - flange_thickness)
    nut_body_height = nut["m_above_panel"]
    protrusion = 3.0 * result["pitch"]

    # The total head height k includes the flange thickness c. Draw the main
    # head body and the wider flange as two separate rectangles.
    ax.add_patch(Rectangle(
        (-screw["s"] / 2.0, -total_head_height), screw["s"], head_body_height,
        facecolor="#9CA3AF", edgecolor="#374151", linewidth=1.2
    ))
    ax.add_patch(Rectangle(
        (-screw["dc"] / 2.0, -flange_thickness), screw["dc"], flange_thickness,
        facecolor="#858D98", edgecolor="#374151", linewidth=1.2
    ))

    # Draw the screw shank through the stack and nut, with three pitches of
    # protrusion below the nut.
    ax.add_patch(Rectangle(
        (-screw["d"] / 2.0, 0.0), screw["d"],
        stack_bottom + nut_body_height + protrusion,
        facecolor="#6B7280", edgecolor="#374151", linewidth=0.8,
        zorder=3
    ))

    # Collar enters upward into the weld-nut panel from the bottom surface.
    collar_bottom = stack_bottom - nut["h2"]
    ax.add_patch(Rectangle(
        (-nut["d4"] / 2.0, collar_bottom), nut["d4"], nut["h2"],
        facecolor="#E9B95F", edgecolor="#7C5B21", linewidth=1.1,
        zorder=4
    ))
    # Use the weld nut across-corners dimension for its visible body width in
    # this schematic; the across-flats s dimension remains in the data table.
    nut_body_width = nut["e"]
    ax.add_patch(Rectangle(
        (-nut_body_width / 2.0, stack_bottom), nut_body_width, nut_body_height,
        facecolor="#F2C879", edgecolor="#7C5B21", linewidth=1.2,
        zorder=2
    ))
    # Re-draw the threaded portion visible through the nut and its protrusion.
    ax.add_patch(Rectangle(
        (-screw["d"] / 2.0, stack_bottom), screw["d"],
        nut_body_height + protrusion,
        facecolor="#6B7280", edgecolor="#374151", linewidth=0.8,
        zorder=5
    ))
    ax.set_title("Joint cross-section", fontsize=10, pad=8)
    ax.set_xlim(-panel_width / 2.0 - 2.0, panel_width / 2.0 + 2.0)
    ax.set_ylim(stack_bottom + nut_body_height + protrusion + 2.0,
                -total_head_height - 2.0)
    # Keep equal scale on both axes so head height, flange thickness, panel
    # holes, and weld-nut width retain their physical proportions.
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.tight_layout()
    return fig


def create_bearing_figure(result: dict[str, Any], worst_case: bool):
    """Draw one bearing-area plan view with the supported area hatched."""
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    screw = result["screw"]
    panel1 = result["hole_rows"][0]
    flange_r = screw["dc"] / 2.0

    if worst_case:
        hole_diameter = panel1["Maximum hole (mm)"]
        shift = result["radial_shift"]
        bearing_area = result["worst_bearing"]
        title = f"Worst case\nBearing area: {bearing_area:.2f} mm²"
    else:
        hole_diameter = panel1["Nominal hole (mm)"]
        shift = 0.0
        bearing_area = result["nominal_bearing"]
        title = f"Nominal\nBearing area: {bearing_area:.2f} mm²"

    hole_r = hole_diameter / 2.0
    # The flange footprint is hatched; the hole is drawn white over it. The
    # remaining hatch is the flange material supporting Panel 1.
    ax.add_patch(Circle(
        (0.0, 0.0), flange_r,
        facecolor="#D7E8F7", edgecolor="#1F4E79", hatch="///",
        linewidth=1.5, zorder=1
    ))
    ax.add_patch(Circle(
        (shift, 0.0), hole_r,
        facecolor="white", edgecolor="#C0392B", linewidth=1.8,
        zorder=2
    ))

    if shift > 0.0:
        ax.annotate(
            "", xy=(shift, 0.0), xytext=(0.0, 0.0),
            arrowprops={"arrowstyle": "<->", "lw": 1.2, "color": "#7F1D1D"},
            zorder=5
        )

    extent = max(flange_r, hole_r + shift) + 2.0
    ax.set_xlim(-extent, extent)
    ax.set_ylim(extent, -extent)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title, fontsize=10, pad=8)
    ax.axis("off")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Verification calculations and demo PLM records
# ---------------------------------------------------------------------------

DEMO_PLM_SCENARIOS: dict[str, dict[str, Any]] = {
    "Compatible M8 joint": {
        "bolt_part_number": "DEMO-TS17130-M8X35-8.8-ZN",
        "nut_part_number": "DEMO-TS17426-M8-SQUARE-CL8",
        "thread": "M8",
        "nut_thread": "M8",
        "grade": "8.8",
        "nut_class": "8",
        "surface_label": "Zinc plated (SS8451 / SS8451S2)",
        "screw_length": 35.0,
        "weld_nut_panel": 3,
        "radial_shift": 0.5,
        "panels": [
            {"part_number": "DEMO-PANEL-M8-01", "thickness": 2.0, "hole": 10.0, "tol_plus": 0.2, "tol_minus": 0.0},
            {"part_number": "DEMO-PANEL-M8-02", "thickness": 2.0, "hole": 10.0, "tol_plus": 0.2, "tol_minus": 0.0},
            {"part_number": "DEMO-PANEL-M8-03", "thickness": 2.5, "hole": 13.8, "tol_plus": 0.1, "tol_minus": 0.1},
        ],
        "gaps": [0.2, 0.2],
    },
    "Proof-stress mismatch M10 joint": {
        "bolt_part_number": "DEMO-TS17130-M10X50-12.9-PH",
        "nut_part_number": "DEMO-TS17426-M10-SQUARE-CL8",
        "thread": "M10",
        "nut_thread": "M10",
        "grade": "12.9",
        "nut_class": "8",
        "surface_label": "Phosphated (SS9400)",
        "screw_length": 50.0,
        "weld_nut_panel": 3,
        "radial_shift": 0.5,
        "panels": [
            {"part_number": "DEMO-PANEL-M10-01", "thickness": 2.0, "hole": 12.0, "tol_plus": 0.2, "tol_minus": 0.0},
            {"part_number": "DEMO-PANEL-M10-02", "thickness": 2.0, "hole": 12.0, "tol_plus": 0.2, "tol_minus": 0.0},
            {"part_number": "DEMO-PANEL-M10-03", "thickness": 3.0, "hole": 16.6, "tol_plus": 0.1, "tol_minus": 0.1},
        ],
        "gaps": [0.2, 0.2],
    },
}


def calculate_verification(inputs: dict[str, Any]) -> dict[str, Any]:
    """Compare actual entered geometry/specs with the agreed demo rules."""
    screw_thread = inputs["thread"]
    nut_thread = inputs["nut_thread"]
    screw_spec = THREAD_OPTIONS[screw_thread]
    nut_spec = THREAD_OPTIONS[nut_thread]

    geometry_inputs = {
        "thread": screw_thread,
        "nut_base_size": nut_spec["base"],
        "surface_label": inputs["surface_label"],
        "surface_key": SURFACE_PROTECTION[inputs["surface_label"]],
        "hole_class": inputs["hole_class"],
        "panels": inputs["panels"],
        "gaps": inputs["gaps"],
        "weld_nut_panel": inputs["weld_nut_panel"],
        "radial_shift": inputs["radial_shift"],
    }
    design_geometry = calculate_design(geometry_inputs)
    actual_hole_rows: list[dict[str, Any]] = []

    for i, panel in enumerate(inputs["panels"]):
        target = design_geometry["hole_rows"][i]
        actual_nominal = float(panel["actual_hole"])
        actual_minimum = actual_nominal - float(panel["tol_minus"])
        actual_maximum = actual_nominal + float(panel["tol_plus"])
        required_minimum = target["Minimum required (mm)"]
        target_nominal = target["Nominal hole (mm)"]

        if actual_minimum + 1e-9 < required_minimum:
            check = "NOK"
            reason = (
                f"Minimum actual hole {actual_minimum:.2f} mm is below the "
                f"required minimum {required_minimum:.2f} mm."
            )
        else:
            warnings = []
            if abs(actual_nominal - target_nominal) > 1e-6:
                warnings.append(
                    f"Entered nominal hole {actual_nominal:.2f} mm differs from "
                    f"the rule target {target_nominal:.2f} mm."
                )
            screw_diameter = SCREW_GEOMETRY[design_geometry["base_size"]]["d"]
            if (
                target["Role"] == "Non-weld-nut panel"
                and actual_maximum > screw_diameter + 2.0 + 1e-9
            ):
                oversize_reason = (
                    f"Maximum hole {actual_maximum:.2f} mm exceeds thread diameter + 2 mm "
                    f"(>{screw_diameter + 2.0:.2f} mm)."
                )
                if i == 0:
                    oversize_reason += " Review the calculated Panel 1 bearing areas."
                warnings.append(oversize_reason)
            check = "Warning" if warnings else "OK"
            reason = " ".join(warnings) if warnings else (
                "Entered hole size satisfies the rule target and minimum clearance check."
            )

        actual_hole_rows.append({
            "Panel": f"Panel {i + 1}",
            "Part number": panel.get("part_number", ""),
            "Role": target["Role"],
            "Thickness (mm)": panel["thickness"],
            "Rule / target": target["Hole rule"],
            "Actual nominal hole (mm)": actual_nominal,
            "Tol - (mm)": float(panel["tol_minus"]),
            "Tol + (mm)": float(panel["tol_plus"]),
            "Actual min (mm)": actual_minimum,
            "Actual max (mm)": actual_maximum,
            "Required min (mm)": required_minimum,
            "Check": check,
            "Reason": reason,
        })

    base_size = screw_spec["base"]
    screw = SCREW_GEOMETRY[base_size]
    nut = SQUARE_WELD_NUT_DB[nut_spec["base"]]
    same_thread = screw_thread == nut_thread
    used_length = float(inputs["screw_length"])
    required_length = design_geometry["required_screw_length"]
    length_min, length_max = design_geometry["length_range"]
    stack_to_nut = design_geometry["clamped_thickness"] + design_geometry["clamped_gap"] + nut["m_above_panel"]
    actual_protrusion = used_length - stack_to_nut
    required_protrusion = 3.0 * screw_spec["pitch"]
    sufficient_length = used_length + 1e-9 >= required_length
    length_in_range = length_min <= used_length <= length_max

    bolt_proof = BOLT_PROPERTIES[inputs["grade"]]["proof_mpa"]
    bolt_yield = BOLT_PROPERTIES[inputs["grade"]]["yield_mpa"]
    nut_proof = NUT_PROOF_STRESS_MPA[inputs["nut_class"]]
    proof_compatible = nut_proof >= bolt_proof

    performance = performance_table_for(screw_thread)[
        SURFACE_PROTECTION[inputs["surface_label"]]
    ][inputs["grade"]]

    geometry_checks = [
        {
            "Check": "Screw thread vs weld-nut thread",
            "Status": "OK" if same_thread else "NOK",
            "Actual / requirement": f"Screw {screw_thread}; nut {nut_thread}",
            "Reason": "Nominal size and pitch match." if same_thread else "Screw and weld-nut thread size/pitch differ.",
        },
        {
            "Check": "Used screw length vs required stack length",
            "Status": "OK" if sufficient_length else "NOK",
            "Actual / requirement": f"Used {used_length:.2f} mm; required {required_length:.2f} mm",
            "Reason": "Used length meets the stack requirement." if sufficient_length else "Used screw is shorter than the stack requirement including three-thread protrusion.",
        },
        {
            "Check": "Used screw length vs preferred range",
            "Status": "OK" if length_in_range else "Warning",
            "Actual / requirement": f"Used {used_length:.2f} mm; range {length_min:.0f}–{length_max:.0f} mm",
            "Reason": "Used length is inside the preferred range." if length_in_range else "Used length is outside the preferred range for this size.",
        },
        {
            "Check": "Actual protrusion beyond nut",
            "Status": "OK" if actual_protrusion + 1e-9 >= required_protrusion else "NOK",
            "Actual / requirement": f"{actual_protrusion:.2f} mm; minimum {required_protrusion:.2f} mm (3 × pitch)",
            "Reason": "Protrusion meets the three-thread requirement." if actual_protrusion + 1e-9 >= required_protrusion else "Actual protrusion is less than three thread pitches.",
        },
    ]

    geometry_checks.extend({
        "Check": f"{row['Panel']} hole compatibility",
        "Status": row["Check"],
        "Actual / requirement": (
            f"Actual {row['Actual min (mm)']:.2f}–{row['Actual max (mm)']:.2f} mm; "
            f"target {design_geometry['hole_rows'][i]['Nominal hole (mm)']:.2f} mm"
        ),
        "Reason": row["Reason"],
    } for i, row in enumerate(actual_hole_rows))

    spec_checks = [
        {
            "Check": "Bolt / nut proof-stress compatibility",
            "Status": "OK" if proof_compatible else "NOK",
            "Actual / requirement": f"Bolt grade {inputs['grade']}: {bolt_proof:.0f} MPa; nut class {inputs['nut_class']}: {nut_proof:.0f} MPa",
            "Reason": "Nut proof stress is at least bolt proof stress." if proof_compatible else "Nut proof stress is below bolt proof stress.",
        },
        {
            "Check": "Fastener torque / preload data",
            "Status": "Available",
            "Actual / requirement": f"Preload {performance['P_kgf']:.0f} kgf; torque {performance['T_kgfm']:.2f} kgf·m",
            "Reason": "Required values found for selected thread, surface protection, and bolt grade.",
        },
    ]

    panel1 = actual_hole_rows[0]
    nominal_bearing = flange_bearing_area(screw["dc"], panel1["Actual nominal hole (mm)"], 0.0)
    worst_bearing = flange_bearing_area(screw["dc"], panel1["Actual max (mm)"], inputs["radial_shift"])

    def overall_status(checks: list[dict[str, Any]]) -> str:
        statuses = [row["Status"] for row in checks]
        if "NOK" in statuses:
            return "NOK"
        if "Warning" in statuses:
            return "Warning"
        return "OK"

    # A copy of the design geometry result with actual hole conditions is used
    # by the shared cross-section and bearing figures.
    figure_result = dict(design_geometry)
    figure_result["hole_rows"] = [
        {
            **design_geometry["hole_rows"][i],
            "Nominal hole (mm)": actual_hole_rows[i]["Actual nominal hole (mm)"],
            "Maximum hole (mm)": actual_hole_rows[i]["Actual max (mm)"],
        }
        for i in range(len(actual_hole_rows))
    ]
    figure_result["nominal_bearing"] = nominal_bearing
    figure_result["worst_bearing"] = worst_bearing
    figure_result["radial_shift"] = inputs["radial_shift"]

    return {
        "geometry": design_geometry,
        "hole_rows": actual_hole_rows,
        "geometry_checks": geometry_checks,
        "spec_checks": spec_checks,
        "geometry_status": overall_status(geometry_checks),
        "spec_status": overall_status(spec_checks),
        "screw": screw,
        "nut": nut,
        "bolt_proof_mpa": bolt_proof,
        "bolt_yield_mpa": bolt_yield,
        "nut_proof_mpa": nut_proof,
        "preload_kgf": performance["P_kgf"],
        "torque_kgfm": performance["T_kgfm"],
        "nominal_bearing": nominal_bearing,
        "worst_bearing": worst_bearing,
        "figure_result": figure_result,
        "required_length": required_length,
        "used_length": used_length,
        "actual_protrusion": actual_protrusion,
        "required_protrusion": required_protrusion,
        "radial_shift": inputs["radial_shift"],
    }


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def render_design_mode(st) -> None:
    st.title("Fastener Joint Digital Twin — Design Mode")
    st.caption("Flanged Hex Screw: TS 17130 | Square Weld Nut with Collar: TS 17426 | Supported sizes: M6–M12")

    with st.sidebar:
        st.header("Fastener and joint")
        thread_label = st.selectbox(
            "Thread size",
            options=list(THREAD_OPTIONS.keys()),
            format_func=lambda key: f"{key}  (pitch {THREAD_OPTIONS[key]['pitch']:.2f} mm)",
        )
        selected_thread = THREAD_OPTIONS[thread_label]
        base_size = selected_thread["base"]
        surface_label = st.selectbox("Surface protection", list(SURFACE_PROTECTION.keys()))
        hole_class = st.selectbox(
            "Thread / hole class (formality)",
            HOLE_CLASSES,
            help="Recorded in the design inputs. It does not change screw geometry or the agreed hole-size formulas in this demo.",
        )

        st.header("Panel stack")
        panel_count = int(st.number_input(
            "Number of panels",
            min_value=2,
            max_value=12,
            value=3,
            step=1,
        ))
        weld_nut_panel = int(st.selectbox(
            "Panel carrying the square weld nut",
            options=list(range(1, panel_count + 1)),
            index=panel_count - 1,
        ))
        radial_shift = float(st.number_input(
            "Maximum radial position shift ±e (mm)",
            min_value=0.0,
            max_value=5.0,
            value=0.5,
            step=0.1,
            help="Shown as GD&T position zone Ø(2e). The value is the maximum center offset used for worst-case bearing.",
        ))
        st.caption(f"Equivalent GD&T position zone: Ø{2.0 * radial_shift:.2f} mm")

    screw = SCREW_GEOMETRY[base_size]
    nut = SQUARE_WELD_NUT_DB[base_size]
    panels: list[dict[str, float]] = []
    gaps: list[float] = []

    st.subheader("Panel inputs")
    st.caption("Panel 1 is the bolt-head contact panel. Enter panels in order from the bolt head toward the weld-nut panel.")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Thickness and hole tolerances**")
        for i in range(panel_count):
            default_thickness = 2.0 if i < panel_count - 1 else 2.5
            panel_cols = st.columns([1.0, 0.9, 0.9])
            with panel_cols[0]:
                thickness = float(st.number_input(
                    f"Panel {i + 1} thickness (mm)",
                    min_value=0.1,
                    max_value=50.0,
                    value=default_thickness,
                    step=0.1,
                    key=f"panel_thickness_{i}",
                ))
            with panel_cols[1]:
                tol_plus = float(st.number_input(
                    f"P{i + 1} hole tol + (mm)",
                    min_value=0.0,
                    max_value=5.0,
                    value=0.0,
                    step=0.05,
                    key=f"panel_tol_plus_{i}",
                ))
            with panel_cols[2]:
                tol_minus = float(st.number_input(
                    f"P{i + 1} hole tol - (mm)",
                    min_value=0.0,
                    max_value=5.0,
                    value=0.0,
                    step=0.05,
                    key=f"panel_tol_minus_{i}",
                ))
            panels.append({
                "thickness": thickness,
                "tol_plus": tol_plus,
                "tol_minus": tol_minus,
            })

    with cols[1]:
        st.markdown("**Gaps between adjacent panels**")
        for i in range(panel_count - 1):
            gap = float(st.number_input(
                f"Gap {i + 1} (P{i + 1} to P{i + 2}) (mm)",
                min_value=0.0,
                max_value=20.0,
                value=0.2,
                step=0.1,
                key=f"gap_{i}",
            ))
            gaps.append(gap)

        st.markdown("**Selected geometry**")
        st.write({
            "Screw geometry basis": "TS 17130 Flanged Hex Screw",
            "Square weld-nut basis": "TS 17426",
            "Screw major diameter d (mm)": screw["d"],
            "Screw pitch (mm)": selected_thread["pitch"],
            "Bolt flange diameter dc (mm)": screw["dc"],
            "Weld-nut collar diameter d4 (mm)": nut["d4"],
            "Weld-nut collar height h2 (mm)": nut["h2"],
            "Nut height above panel (mm)": nut["m_above_panel"],
        })

    inputs = {
        "thread": thread_label,
        "surface_label": surface_label,
        "surface_key": SURFACE_PROTECTION[surface_label],
        "hole_class": hole_class,
        "panels": panels,
        "gaps": gaps,
        "weld_nut_panel": weld_nut_panel,
        "radial_shift": radial_shift,
    }

    result = calculate_design(inputs)
    length_min, length_max = result["length_range"]

    st.divider()
    st.subheader("Design results")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Calculated screw length", f"{result['required_screw_length']:.2f} mm")
    r2.metric(
        "TS 17130 preferred range",
        f"{length_min:.0f}–{length_max:.0f} mm",
        "OK" if result["length_in_range"] else "Warning",
    )
    r3.metric("Nominal Panel 1 bearing area", f"{result['nominal_bearing']:.2f} mm²")
    r4.metric("Worst-case Panel 1 bearing area", f"{result['worst_bearing']:.2f} mm²")

    if result["length_in_range"]:
        st.success(
            f"Calculated length {result['required_screw_length']:.2f} mm is within the "
            f"{base_size} preferred range of {length_min:.0f}–{length_max:.0f} mm."
        )
    else:
        st.warning(
            f"Calculated length {result['required_screw_length']:.2f} mm is outside the "
            f"{base_size} preferred range of {length_min:.0f}–{length_max:.0f} mm. "
            "This demo reports the check and does not suggest or round to another length."
        )

    if result["oversized_panel1"]:
        st.warning(
            f"Panel 1 maximum hole is larger than thread diameter + 2 mm "
            f"({screw['d'] + 2.0:.2f} mm). Review the displayed bearing area."
        )

    st.markdown("#### Panel hole schedule")
    st.dataframe(result["hole_rows"], width="stretch", hide_index=True)
    st.caption(
        "Hole rules: non-weld-nut panels use d + 2 mm; the weld-nut panel uses d4 + 1 mm; "
        "the adjacent top panel uses d4 + 2 mm when collar height h2 exceeds weld-nut-panel thickness; "
        "otherwise it uses d + 2 mm. "
        "The Fine/Medium/Coarse selection is recorded as a formality."
    )

    st.markdown("#### Stack length breakdown")
    st.markdown(
        "Calculated screw length = panel thicknesses through the weld-nut panel "
        "+ gaps in that stack + nut height above the panel surface + 3 × pitch."
    )
    stack_rows = []
    for i in range(result["weld_nut_panel"]):
        stack_rows.append({"Component": f"Panel {i + 1} thickness", "Value (mm)": panels[i]["thickness"]})
        if i < result["weld_nut_panel"] - 1:
            stack_rows.append({"Component": f"Gap {i + 1}", "Value (mm)": gaps[i]})
    stack_rows.extend([
        {"Component": "Nut height above panel surface", "Value (mm)": result["nut_height_above_panel"]},
        {"Component": "3 × thread pitch", "Value (mm)": 3.0 * result["pitch"]},
        {"Component": "Calculated screw length", "Value (mm)": result["required_screw_length"]},
    ])
    st.dataframe(stack_rows, width="stretch", hide_index=True)

    st.markdown("#### Available fastener specifications")
    st.caption(
        "Preload and torque are database lookups for the selected thread, surface protection, and bolt grade. "
        "Bolt and nut proof stresses are compared directly; no engagement scaling is applied."
    )
    st.dataframe(result["fastener_rows"], width="stretch", hide_index=True)

    panel1_hole = result["hole_rows"][0]
    panel1_nominal_hole = panel1_hole["Nominal hole (mm)"]
    panel1_max_hole = panel1_hole["Maximum hole (mm)"]
    st.markdown("#### Worst-case shift and bearing-area calculation")
    st.markdown(
        "Worst case uses Panel 1's maximum hole size and the maximum radial center shift. "
        "The entered shift is e; the equivalent GD&T position zone is Ø(2e)."
    )
    st.latex(r"D_{P1,max}=D_{P1,nominal}+t_+ \qquad e_{max}=\frac{\text{position zone diameter}}{2}")
    st.latex(
        r"A_{bearing}=\pi\left(\frac{d_c}{2}\right)^2"
        r"-A_{overlap}\left(\frac{d_c}{2},\frac{D_{P1}}{2},e\right)"
    )
    shift_rows = [
        {"Calculation input/result": "Panel 1 nominal hole diameter", "Value": f"{panel1_nominal_hole:.2f} mm"},
        {"Calculation input/result": "Panel 1 positive hole tolerance", "Value": f"+{panel1_hole['Tol + (mm)']:.2f} mm"},
        {"Calculation input/result": "Panel 1 maximum hole diameter", "Value": f"{panel1_max_hole:.2f} mm"},
        {"Calculation input/result": "Maximum radial center shift e", "Value": f"±{result['radial_shift']:.2f} mm"},
        {"Calculation input/result": "Equivalent GD&T position zone", "Value": f"Ø{result['position_zone_diameter']:.2f} mm"},
        {"Calculation input/result": "Bolt flange diameter dc", "Value": f"{screw['dc']:.2f} mm"},
        {"Calculation input/result": "Nominal bearing area (nominal hole, zero shift)", "Value": f"{result['nominal_bearing']:.2f} mm²"},
        {"Calculation input/result": "Worst-case bearing area (maximum hole, shift e)", "Value": f"{result['worst_bearing']:.2f} mm²"},
    ]
    st.dataframe(shift_rows, width="stretch", hide_index=True)

    st.markdown("#### Flanged hex screw geometry")
    screw_geometry_rows = [
        {"Dimension": "Nominal thread diameter d", "Value (mm)": screw["d"]},
        {"Dimension": "Across flats s", "Value (mm)": screw["s"]},
        {"Dimension": "Across corners e", "Value (mm)": screw["e"]},
        {"Dimension": "Flange diameter dc", "Value (mm)": screw["dc"]},
        {"Dimension": "Head height k", "Value (mm)": screw["k"]},
        {"Dimension": "Flange thickness c", "Value (mm)": screw["c"]},
    ]
    nut_geometry_rows = [
        {"Dimension": "Thread size d1", "Value (mm)": nut["d1"]},
        {"Dimension": "Collar diameter d4", "Value (mm)": nut["d4"]},
        {"Dimension": "Across flats s", "Value (mm)": nut["s"]},
        {"Dimension": "Across corners e", "Value (mm)": nut["e"]},
        {"Dimension": "Nut height above panel", "Value (mm)": nut["m_above_panel"]},
        {"Dimension": "Collar height h2", "Value (mm)": nut["h2"]},
    ]
    g1, g2 = st.columns(2)
    with g1:
        st.dataframe(screw_geometry_rows, width="stretch", hide_index=True)
    with g2:
        st.dataframe(nut_geometry_rows, width="stretch", hide_index=True)

    st.markdown("#### Joint and bearing images")
    image_joint, image_nominal, image_worst = st.columns(3, gap="small")
    with image_joint:
        st.markdown("**Joint cross-section**")
        fig = create_joint_cross_section(result)
        st.pyplot(fig, clear_figure=True, width="stretch")
        plt.close(fig)
        st.caption(
            f"Head body s={screw['s']:.2f} × (k−c)={screw['k'] - screw['c']:.2f} mm; "
            f"flange dc={screw['dc']:.2f} × c={screw['c']:.2f} mm. "
            f"Weld-nut body schematic width e={nut['e']:.2f} mm (s across flats={nut['s']:.2f} mm), "
            f"height={nut['m_above_panel']:.2f} mm; collar d4={nut['d4']:.2f} × h2={nut['h2']:.2f} mm."
        )
    with image_nominal:
        st.markdown("**Nominal bearing area**")
        fig = create_bearing_figure(result, worst_case=False)
        st.pyplot(fig, clear_figure=True, width="stretch")
        plt.close(fig)
        st.caption(
            f"dc={screw['dc']:.2f} mm; Panel 1 nominal hole Ø{panel1_nominal_hole:.2f} mm; "
            "concentric condition."
        )
    with image_worst:
        st.markdown("**Worst-case bearing area**")
        fig = create_bearing_figure(result, worst_case=True)
        st.pyplot(fig, clear_figure=True, width="stretch")
        plt.close(fig)
        st.caption(
            f"Panel 1 maximum hole Ø{panel1_max_hole:.2f} mm; radial shift ±{radial_shift:.2f} mm; "
            f"GD&T position zone Ø{2.0 * radial_shift:.2f} mm."
        )


def _fetch_demo_plm_record() -> None:
    """Populate Verification widgets from a local demo record (no live PLM call)."""
    import streamlit as st

    scenario_name = st.session_state.get("verification_plm_scenario", "")
    record = DEMO_PLM_SCENARIOS.get(scenario_name)
    if record is None:
        st.session_state["verification_plm_loaded_scenario"] = scenario_name
        st.session_state["verification_plm_status"] = (
            "No demo record returned. Enter or correct the properties manually."
        )
        return

    st.session_state["verification_bolt_part_number"] = record["bolt_part_number"]
    st.session_state["verification_nut_part_number"] = record["nut_part_number"]
    st.session_state["verification_panel_count"] = len(record["panels"])
    st.session_state["verification_thread"] = record["thread"]
    st.session_state["verification_nut_thread"] = record["nut_thread"]
    st.session_state["verification_grade"] = record["grade"]
    st.session_state["verification_nut_class"] = record["nut_class"]
    st.session_state["verification_surface"] = record["surface_label"]
    st.session_state["verification_screw_length"] = record["screw_length"]
    st.session_state["verification_weld_nut_panel"] = record["weld_nut_panel"]
    st.session_state["verification_radial_shift"] = record["radial_shift"]
    st.session_state["verification_hole_class"] = "Medium"
    for i, panel in enumerate(record["panels"]):
        st.session_state[f"verification_panel_pn_{i}"] = panel["part_number"]
        st.session_state[f"verification_thickness_{i}"] = panel["thickness"]
        st.session_state[f"verification_hole_{i}"] = panel["hole"]
        st.session_state[f"verification_tol_plus_{i}"] = panel["tol_plus"]
        st.session_state[f"verification_tol_minus_{i}"] = panel["tol_minus"]
    for i, gap in enumerate(record["gaps"]):
        st.session_state[f"verification_gap_{i}"] = gap
    st.session_state["verification_plm_status"] = (
        "Demo properties loaded. Review and edit every field before checking."
    )
    st.session_state["verification_plm_loaded_scenario"] = scenario_name


def render_verification_mode(st) -> None:
    st.title("Fastener Joint Digital Twin — Verification Mode")
    st.caption(
        "Enter the parts and measured/design properties to check geometry, fastener specification, "
        "proof stress, torque, preload, and bearing area."
    )

    st.subheader("Part numbers and PLM lookup")
    st.caption(
        "This demo uses local sample records to illustrate the PLM handoff. It does not call a live PLM system; "
        "all fetched values remain editable, and a missing record can be entered manually."
    )
    scenario_names = [*DEMO_PLM_SCENARIOS, "No PLM record (manual entry)"]
    p1, p2 = st.columns([3, 1])
    with p1:
        st.selectbox("Demo PLM record", scenario_names, key="verification_plm_scenario")
    with p2:
        st.button(
            "Fetch from PLM (Demo)",
            on_click=_fetch_demo_plm_record,
            width="stretch",
        )
    if st.session_state.get("verification_plm_loaded_scenario") != st.session_state.get("verification_plm_scenario"):
        st.info("Selected sample is not loaded yet. Click **Fetch from PLM (Demo)** to populate its fields.")
    elif st.session_state.get("verification_plm_status"):
        if st.session_state["verification_plm_scenario"] == "No PLM record (manual entry)":
            st.info(st.session_state["verification_plm_status"])
        else:
            st.success(st.session_state["verification_plm_status"])

    id_cols = st.columns(3)
    with id_cols[0]:
        st.text_input("Screw part number", value="", key="verification_bolt_part_number")
    with id_cols[1]:
        st.text_input("Square weld-nut part number", value="", key="verification_nut_part_number")
    with id_cols[2]:
        panel_count = int(st.number_input(
            "Number of panels",
            min_value=2,
            max_value=12,
            value=3,
            step=1,
            key="verification_panel_count",
        ))
    st.markdown("**Panel part numbers**")
    pn_cols = st.columns(min(panel_count, 4))
    for i in range(panel_count):
        with pn_cols[i % len(pn_cols)]:
            st.text_input(
                f"Panel {i + 1} part number",
                value="",
                placeholder=f"Enter Panel {i + 1} part number",
                key=f"verification_panel_pn_{i}",
            )

    st.divider()
    st.subheader("Fastener and joint properties")
    property_cols = st.columns(4)
    with property_cols[0]:
        screw_thread = st.selectbox(
            "Screw thread",
            list(THREAD_OPTIONS),
            key="verification_thread",
        )
        grade = st.selectbox("Bolt property class", BOLT_GRADES, key="verification_grade")
    with property_cols[1]:
        nut_thread = st.selectbox(
            "Weld-nut thread",
            list(THREAD_OPTIONS),
            key="verification_nut_thread",
        )
        nut_class = st.selectbox("Nut property class", NUT_CLASSES, key="verification_nut_class")
    with property_cols[2]:
        surface_label = st.selectbox(
            "Surface protection",
            list(SURFACE_PROTECTION),
            key="verification_surface",
        )
        hole_class = st.selectbox(
            "Thread class (formality)", HOLE_CLASSES, key="verification_hole_class"
        )
    with property_cols[3]:
        screw_length = float(st.number_input(
            "Screw length (mm)",
            min_value=1.0,
            max_value=200.0,
            value=35.0,
            step=0.5,
            key="verification_screw_length",
        ))
        radial_shift = float(st.number_input(
            "Maximum radial position shift ±e (mm)",
            min_value=0.0,
            max_value=5.0,
            value=0.5,
            step=0.1,
            key="verification_radial_shift",
        ))

    if st.session_state.get("verification_weld_nut_panel", panel_count) > panel_count:
        st.session_state["verification_weld_nut_panel"] = panel_count
    weld_nut_panel = int(st.selectbox(
        "Panel carrying the square weld nut",
        list(range(1, panel_count + 1)),
        index=min(panel_count - 1, max(0, int(st.session_state.get("verification_weld_nut_panel", panel_count)) - 1)),
        key="verification_weld_nut_panel",
    ))

    st.markdown("#### Panel geometry and actual holes")
    st.caption(
        "Panel 1 is always the bolt-head contact panel. Enter panels in order from the screw head toward the weld nut. "
        "The entered position shift is treated as radial center offset e; its GD&T zone is Ø(2e)."
    )
    panel_values: list[dict[str, Any]] = []
    thickness_cols = st.columns(min(panel_count, 4))
    for i in range(panel_count):
        with thickness_cols[i % len(thickness_cols)]:
            thickness = float(st.number_input(
                f"Panel {i + 1} thickness (mm)",
                min_value=0.1,
                max_value=50.0,
                value=2.0 if i < panel_count - 1 else 2.5,
                step=0.1,
                key=f"verification_thickness_{i}",
            ))
            panel_values.append({
                "part_number": st.session_state.get(f"verification_panel_pn_{i}", ""),
                "thickness": thickness,
                "tol_plus": 0.0,
                "tol_minus": 0.0,
                "actual_hole": 10.0,
            })

    gaps: list[float] = []
    if panel_count > 1:
        gap_cols = st.columns(min(panel_count - 1, 4))
        for i in range(panel_count - 1):
            with gap_cols[i % len(gap_cols)]:
                gaps.append(float(st.number_input(
                    f"Gap {i + 1} (P{i + 1} to P{i + 2}) (mm)",
                    min_value=0.0,
                    max_value=20.0,
                    value=0.2,
                    step=0.1,
                    key=f"verification_gap_{i}",
                )))

    template_inputs = {
        "thread": screw_thread,
        "surface_label": surface_label,
        "surface_key": SURFACE_PROTECTION[surface_label],
        "hole_class": hole_class,
        "panels": panel_values,
        "gaps": gaps,
        "weld_nut_panel": weld_nut_panel,
        "radial_shift": radial_shift,
        "nut_base_size": THREAD_OPTIONS[nut_thread]["base"],
    }
    template = calculate_design(template_inputs)
    st.markdown("**Actual panel hole size and bilateral tolerances**")
    hole_header = st.columns([1.1, 1.1, 1.1, 1.1, 1.1])
    for col, label in zip(hole_header, ["Panel", "Nominal hole Ø (mm)", "Tol − (mm)", "Tol + (mm)", "Rule target Ø (mm)"]):
        col.caption(label)
    for i, panel in enumerate(panel_values):
        row = st.columns([1.1, 1.1, 1.1, 1.1, 1.1])
        row[0].markdown(f"Panel {i + 1}")
        panel["actual_hole"] = float(row[1].number_input(
            f"Panel {i + 1} actual nominal hole (mm)",
            min_value=0.1,
            max_value=100.0,
            value=float(template["hole_rows"][i]["Nominal hole (mm)"]),
            step=0.1,
            key=f"verification_hole_{i}",
            label_visibility="collapsed",
        ))
        panel["tol_minus"] = float(row[2].number_input(
            f"Panel {i + 1} hole tolerance minus (mm)",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.05,
            key=f"verification_tol_minus_{i}",
            label_visibility="collapsed",
        ))
        panel["tol_plus"] = float(row[3].number_input(
            f"Panel {i + 1} hole tolerance plus (mm)",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.05,
            key=f"verification_tol_plus_{i}",
            label_visibility="collapsed",
        ))
        row[4].markdown(f"{template['hole_rows'][i]['Nominal hole (mm)']:.2f}")

    inputs = {
        **template_inputs,
        "panels": panel_values,
        "gaps": gaps,
        "thread": screw_thread,
        "nut_thread": nut_thread,
        "grade": grade,
        "nut_class": nut_class,
        "screw_length": screw_length,
        "bolt_part_number": st.session_state.get("verification_bolt_part_number", ""),
        "nut_part_number": st.session_state.get("verification_nut_part_number", ""),
    }
    result = calculate_verification(inputs)
    performance = performance_table_for(screw_thread)[SURFACE_PROTECTION[surface_label]][grade]

    st.divider()
    st.subheader("Required torque and preload")
    torque_metric, preload_metric, torque_si, preload_si = st.columns(4)
    torque_metric.metric("Database torque", f"{performance['T_kgfm']:.2f} kgf·m")
    preload_metric.metric("Database preload", f"{performance['P_kgf']:.0f} kgf")
    torque_si.metric("Torque (SI equivalent)", f"{performance['T_kgfm'] * 9.80665:.2f} N·m")
    preload_si.metric("Preload (SI equivalent)", f"{performance['P_kgf'] * 9.80665 / 1000:.2f} kN")
    st.caption(
        f"Lookup key: {screw_thread}, {surface_label}, bolt class {grade}. "
        "Values are retrieved directly from the prototype database."
    )

    st.subheader("Compatibility summary")
    summary_cols = st.columns(2)
    with summary_cols[0]:
        st.metric("Geometric compatibility", result["geometry_status"])
    with summary_cols[1]:
        st.metric("Specification compatibility", result["spec_status"])
    st.markdown("#### Geometry checks")
    st.dataframe(result["geometry_checks"], width="stretch", hide_index=True)
    st.markdown("#### Specification checks")
    st.dataframe(result["spec_checks"], width="stretch", hide_index=True)

    st.markdown("#### Entered fastener and part data")
    st.dataframe([
        {"Item": "Screw part number", "Value": inputs["bolt_part_number"] or "Not entered"},
        {"Item": "Screw", "Value": f"{screw_thread}, class {grade}, length {screw_length:.2f} mm"},
        {"Item": "Square weld-nut part number", "Value": inputs["nut_part_number"] or "Not entered"},
        {"Item": "Square weld nut", "Value": f"TS 17426, {nut_thread}, property class {nut_class}"},
        {"Item": "Bolt proof / yield stress", "Value": f"{result['bolt_proof_mpa']:.0f} / {result['bolt_yield_mpa']:.0f} MPa"},
        {"Item": "Nut proof stress", "Value": f"{result['nut_proof_mpa']:.0f} MPa"},
    ], width="stretch", hide_index=True)

    st.markdown("#### Panel hole compatibility")
    st.dataframe(result["hole_rows"], width="stretch", hide_index=True)
    st.caption(
        "Rule targets: non-weld-nut panels use thread diameter + 2 mm; the TS 17426 weld-nut panel uses d4 + 1 mm; "
        "the adjacent top panel uses d4 + 2 mm when weld-nut collar height h2 exceeds weld-nut-panel thickness. "
        "Oversize non-weld-nut holes are flagged for bearing-area review."
    )

    summary = result["geometry"]
    st.markdown("#### Stack length and bearing results")
    st.write(
        f"Required screw length from stack: **{result['required_length']:.2f} mm**; "
        f"used length: **{result['used_length']:.2f} mm**; "
        f"available range for {THREAD_OPTIONS[screw_thread]['base']}: "
        f"**{summary['length_range'][0]:.0f}–{summary['length_range'][1]:.0f} mm**."
    )
    metrics = st.columns(4)
    metrics[0].metric("Actual protrusion", f"{result['actual_protrusion']:.2f} mm")
    metrics[1].metric("Minimum protrusion (3 × pitch)", f"{result['required_protrusion']:.2f} mm")
    metrics[2].metric("Nominal Panel 1 bearing area", f"{result['nominal_bearing']:.2f} mm²")
    metrics[3].metric("Worst-case Panel 1 bearing area", f"{result['worst_bearing']:.2f} mm²")
    st.caption(
        f"Worst case uses Panel 1's maximum hole Ø{result['hole_rows'][0]['Actual max (mm)']:.2f} mm "
        f"and radial shift ±{radial_shift:.2f} mm (GD&T position zone Ø{2 * radial_shift:.2f} mm)."
    )

    st.markdown("#### Joint and bearing images")
    image_joint, image_nominal, image_worst = st.columns(3, gap="small")
    with image_joint:
        st.markdown("**Joint cross-section**")
        fig = create_joint_cross_section(result["figure_result"])
        st.pyplot(fig, clear_figure=True, width="stretch")
        plt.close(fig)
    with image_nominal:
        st.markdown("**Nominal bearing area**")
        fig = create_bearing_figure(result["figure_result"], worst_case=False)
        st.pyplot(fig, clear_figure=True, width="stretch")
        plt.close(fig)
    with image_worst:
        st.markdown("**Worst-case bearing area**")
        fig = create_bearing_figure(result["figure_result"], worst_case=True)
        st.pyplot(fig, clear_figure=True, width="stretch")
        plt.close(fig)


def parse_rul_torque_csv(uploaded_file) -> tuple[list[dict[str, Any]], str | None]:
    """Read a MAT-number and assembly-torque CSV without requiring pandas."""
    try:
        content = uploaded_file.getvalue().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return [], "CSV needs a header row with MAT number and Torque value columns."

        normalized = {
            re.sub(r"[^a-z0-9]", "", header.lower()): header
            for header in reader.fieldnames
            if header
        }
        mat_header = next((normalized[key] for key in ("matnumber", "matno", "mat", "vehiclemat") if key in normalized), None)
        torque_header = next((normalized[key] for key in ("torquevalue", "assemblytorque", "ton", "torque") if key in normalized), None)
        if mat_header is None or torque_header is None:
            return [], "Could not identify MAT number and Torque value columns in the CSV header."

        records: list[dict[str, Any]] = []
        seen_mat: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            mat_number = str(row.get(mat_header, "")).strip()
            torque_text = str(row.get(torque_header, "")).strip()
            if not mat_number and not torque_text:
                continue
            if not mat_number or not torque_text:
                return [], f"CSV row {line_number} is missing a MAT number or torque value."
            if mat_number in seen_mat:
                return [], f"MAT number {mat_number} appears more than once; use one torque row per MAT."
            try:
                torque = float(torque_text.replace(",", "."))
            except ValueError:
                return [], f"CSV row {line_number} has a non-numeric torque value."
            if not math.isfinite(torque):
                return [], f"CSV row {line_number} torque must be a finite number."
            if torque <= 0:
                return [], f"CSV row {line_number} torque must be greater than zero."
            seen_mat.add(mat_number)
            records.append({"MAT number": mat_number, "CSV torque": torque})
        if not records:
            return [], "CSV contains no MAT torque records."
        return records, None
    except (UnicodeDecodeError, csv.Error) as exc:
        return [], f"Could not read this CSV: {exc}"


def build_rul_torque_csv_template() -> str:
    """Create a starter CSV with five replaceable MAT rows."""
    template = io.StringIO()
    writer = csv.writer(template, lineterminator="\n")
    writer.writerow(["MAT number", "Torque value"])
    for i in range(1, 6):
        writer.writerow([f"MAT-{i:03d}", ""])
    return template.getvalue()


DEMO_CAE_TREND: list[dict[str, float]] = [
    {"Cycle": 0, "Toff retention (%)": 100.0, "Preload retention (%)": 100.0},
    {"Cycle": 400, "Toff retention (%)": 98.5, "Preload retention (%)": 99.0},
    {"Cycle": 800, "Toff retention (%)": 97.0, "Preload retention (%)": 98.0},
    {"Cycle": 1200, "Toff retention (%)": 95.0, "Preload retention (%)": 97.0},
    {"Cycle": 1600, "Toff retention (%)": 93.0, "Preload retention (%)": 96.0},
    {"Cycle": 2000, "Toff retention (%)": 91.0, "Preload retention (%)": 95.0},
    {"Cycle": 2400, "Toff retention (%)": 89.0, "Preload retention (%)": 94.0},
    {"Cycle": 2800, "Toff retention (%)": 87.0, "Preload retention (%)": 93.0},
    {"Cycle": 3200, "Toff retention (%)": 85.0, "Preload retention (%)": 92.0},
]


DEMO_TEST_TREND: list[dict[str, float]] = [
    {"Cycle": 0, "Toff retention (%)": 100.0, "Preload retention (%)": 100.0},
    {"Cycle": 400, "Toff retention (%)": 97.5, "Preload retention (%)": 98.5},
    {"Cycle": 800, "Toff retention (%)": 95.0, "Preload retention (%)": 97.0},
    {"Cycle": 1200, "Toff retention (%)": 93.0, "Preload retention (%)": 95.0},
    {"Cycle": 1600, "Toff retention (%)": 90.0, "Preload retention (%)": 93.0},
    {"Cycle": 2000, "Toff retention (%)": 88.0, "Preload retention (%)": 91.0},
    {"Cycle": 2400, "Toff retention (%)": 85.0, "Preload retention (%)": 89.0},
    {"Cycle": 2800, "Toff retention (%)": 83.0, "Preload retention (%)": 87.0},
    {"Cycle": 3200, "Toff retention (%)": 80.0, "Preload retention (%)": 85.0},
]


def build_cae_rul_csv_template() -> str:
    """Create a downloadable CAE trend template with an illustrative decline curve."""
    template = io.StringIO()
    writer = csv.writer(template, lineterminator="\n")
    writer.writerow(["Cycle", "Toff retention (%)", "Preload retention (%)"])
    for row in DEMO_CAE_TREND:
        writer.writerow([row["Cycle"], row["Toff retention (%)"], row["Preload retention (%)"]])
    return template.getvalue()


def build_test_rul_csv_template() -> str:
    """Create a downloadable physical-test trend template with an illustrative decline curve."""
    template = io.StringIO()
    writer = csv.writer(template, lineterminator="\n")
    writer.writerow(["Cycle", "Toff retention (%)", "Preload retention (%)"])
    for row in DEMO_TEST_TREND:
        writer.writerow([row["Cycle"], row["Toff retention (%)"], row["Preload retention (%)"]])
    return template.getvalue()


def parse_rul_trend_csv(uploaded_file, trend_name: str = "trend") -> tuple[list[dict[str, float]], str | None]:
    """Read cycle-indexed, normalized Toff and preload retention percentages."""
    try:
        content = uploaded_file.getvalue().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return [], f"{trend_name} CSV needs a header row with Cycle, Toff retention (%), and Preload retention (%) columns."
        normalized = {
            re.sub(r"[^a-z0-9]", "", header.lower()): header
            for header in reader.fieldnames
            if header
        }
        cycle_header = next((normalized[key] for key in ("cycle", "cycles", "missioncycle") if key in normalized), None)
        toff_header = next((normalized[key] for key in ("toffretention", "toffretentionpercent", "toffpercent") if key in normalized), None)
        preload_header = next((normalized[key] for key in ("preloadretention", "preloadretentionpercent", "preloadpercent") if key in normalized), None)
        if cycle_header is None or toff_header is None or preload_header is None:
            return [], f"Could not identify Cycle, Toff retention (%), and Preload retention (%) columns in the {trend_name} CSV."

        records: list[dict[str, float]] = []
        seen_cycles: set[float] = set()
        for line_number, row in enumerate(reader, start=2):
            values = [str(row.get(header, "")).strip() for header in (cycle_header, toff_header, preload_header)]
            if not any(values):
                continue
            if any(not value for value in values):
                return [], f"{trend_name} CSV row {line_number} is missing a cycle or retention value."
            try:
                cycle, toff_retention, preload_retention = [float(value.replace(",", ".")) for value in values]
            except ValueError:
                return [], f"{trend_name} CSV row {line_number} contains a non-numeric value."
            if not all(math.isfinite(value) for value in (cycle, toff_retention, preload_retention)):
                return [], f"{trend_name} CSV row {line_number} must contain finite numeric values."
            if cycle < 0:
                return [], f"{trend_name} CSV row {line_number} cycle must be zero or greater."
            if not 0.0 <= toff_retention <= 100.0 or not 0.0 <= preload_retention <= 100.0:
                return [], f"{trend_name} CSV row {line_number} retention percentages must be between 0 and 100."
            if cycle in seen_cycles:
                return [], f"{trend_name} CSV has duplicate cycle value {cycle:g}."
            seen_cycles.add(cycle)
            records.append({
                "Cycle": cycle,
                "Toff retention (%)": toff_retention,
                "Preload retention (%)": preload_retention,
            })
        records.sort(key=lambda row: row["Cycle"])
        if len(records) < 2:
            return [], f"{trend_name} CSV must contain at least two cycle rows."
        if records[0]["Cycle"] != 0.0:
            return [], f"{trend_name} trend must start at cycle 0."
        if abs(records[0]["Toff retention (%)"] - 100.0) > 1e-6 or abs(records[0]["Preload retention (%)"] - 100.0) > 1e-6:
            return [], "At cycle 0, both Toff and preload retention must be 100%."
        return records, None
    except (UnicodeDecodeError, csv.Error) as exc:
        return [], f"Could not read this {trend_name} CSV: {exc}"


def interpolate_trend_retention(
    trend_points: list[dict[str, float]],
    cycle: float,
    retention_key: str,
) -> float:
    """Piecewise-linearly interpolate a normalized model retention series."""
    if cycle <= trend_points[0]["Cycle"]:
        return trend_points[0][retention_key]
    for left, right in zip(trend_points, trend_points[1:]):
        if left["Cycle"] <= cycle <= right["Cycle"]:
            width = right["Cycle"] - left["Cycle"]
            fraction = 0.0 if width == 0 else (cycle - left["Cycle"]) / width
            return left[retention_key] + fraction * (right[retention_key] - left[retention_key])
    return trend_points[-1][retention_key]


def calculate_trend_rul(
    *,
    thread_label: str,
    surface_label: str,
    bolt_grade: str,
    mission_cycles: int,
    mission_km: float,
    design_factor_safety: float,
    residual_percent: float,
    current_cycle: int,
    interval_cycles: int,
    torque_check_lead_km: float,
    trend_points: list[dict[str, float]],
    trend_name: str,
    csv_records: list[dict[str, Any]] | None = None,
    csv_torque_unit: str = "kgf·m",
) -> tuple[dict[str, Any] | None, str | None]:
    """Scale a normalized retention trend to each MAT and find Toff limit crossings."""
    thread = THREAD_OPTIONS[thread_label]
    performance = performance_table_for(thread_label)[SURFACE_PROTECTION[surface_label]][bolt_grade]
    database_ton = float(performance["T_kgfm"])
    database_preload = float(performance["P_kgf"])
    design_capacity = max(1, int(round(mission_cycles * design_factor_safety)))
    if trend_points[-1]["Cycle"] < design_capacity:
        return None, (
            f"{trend_name} data ends at {trend_points[-1]['Cycle']:,.0f} cycles, before the FoS horizon "
            f"of {design_capacity:,} cycles. Add {trend_name.lower()} points through the FoS horizon."
        )

    target_ratio = max(0.0, min(1.0, residual_percent / 100.0))
    km_per_cycle = mission_km / mission_cycles
    horizon_km = design_capacity * km_per_cycle
    reference_toff_initial = 0.90 * database_ton
    reference_toff_limit = reference_toff_initial * target_ratio
    reference_preload_limit = database_preload * target_ratio
    lead_km = max(0.0, torque_check_lead_km)

    # Use the uploaded model points through the FoS horizon plus an interpolated horizon point.
    model_cycles = sorted({
        0.0,
        float(design_capacity),
        *(point["Cycle"] for point in trend_points if 0.0 < point["Cycle"] < design_capacity),
    })

    def find_crossing(values: list[tuple[float, float]], threshold: float) -> float | None:
        tolerance = 1e-9
        if values[0][1] <= threshold + tolerance:
            return 0.0
        for (cycle0, value0), (cycle1, value1) in zip(values, values[1:]):
            if value0 > threshold + tolerance and value1 <= threshold + tolerance:
                if abs(value1 - value0) <= tolerance:
                    return cycle1
                fraction = (value0 - threshold) / (value0 - value1)
                return cycle0 + fraction * (cycle1 - cycle0)
        return None

    source_records = csv_records or [{"MAT number": "Joint baseline", "CSV torque": database_ton}]
    fasteners: list[dict[str, Any]] = []
    for source in source_records:
        if csv_records:
            measured_ton = float(source["CSV torque"])
            ton_kgfm = measured_ton / 9.80665 if csv_torque_unit == "N·m" else measured_ton
            initial_preload = database_preload * ton_kgfm / database_ton
            mat_number = str(source["MAT number"])
            toff_method = f"{trend_name} retention trend scaled from assembly-line Ton"
        else:
            ton_kgfm = database_ton
            initial_preload = database_preload
            mat_number = "Joint baseline"
            toff_method = f"{trend_name} retention trend scaled from database Ton"
        toff_initial = 0.90 * ton_kgfm

        toff_values = [
            (cycle, toff_initial * interpolate_trend_retention(trend_points, cycle, "Toff retention (%)") / 100.0)
            for cycle in model_cycles
        ]
        preload_values = [
            (cycle, initial_preload * interpolate_trend_retention(trend_points, cycle, "Preload retention (%)") / 100.0)
            for cycle in model_cycles
        ]
        toff_crossing = find_crossing(toff_values, reference_toff_limit)
        preload_crossing = find_crossing(preload_values, reference_preload_limit)
        if toff_crossing is not None:
            mat_crossing_cycle, crossing_basis = toff_crossing, "Toff"
            mat_crossing_km = mat_crossing_cycle * km_per_cycle
            mat_due_km = max(0.0, mat_crossing_km - lead_km)
            mat_due_cycle = mat_due_km / km_per_cycle
            effective_lead = mat_crossing_km - mat_due_km
        else:
            mat_crossing_cycle = mat_crossing_km = mat_due_km = mat_due_cycle = effective_lead = None
            crossing_basis = "None"

        current_cycle_clamped = min(current_cycle, design_capacity)
        current_toff = toff_initial * interpolate_trend_retention(trend_points, current_cycle_clamped, "Toff retention (%)") / 100.0
        current_preload = initial_preload * interpolate_trend_retention(trend_points, current_cycle_clamped, "Preload retention (%)") / 100.0
        current_km = current_cycle * km_per_cycle

        if mat_crossing_cycle is None:
            message = (
                f"Re-torquing not required within the {trend_name} horizon ({design_capacity:,} cycles / {horizon_km:,.0f} km). "
                f"Predicted Toff at the horizon is {toff_values[-1][1]:.3f} kgf·m, above the reference limit "
                f"{reference_toff_limit:.3f} kgf·m."
            )
        elif current_km >= mat_crossing_km:
            message = (
                f"Torque application required now. The predicted {crossing_basis} limit crossing was at "
                f"{mat_crossing_km:,.0f} km (cycle {mat_crossing_cycle:,.1f})."
            )
        elif current_km >= mat_due_km:
            message = (
                f"Torque application due now/by {current_km:,.0f} km. The predicted {crossing_basis} limit crossing is at "
                f"{mat_crossing_km:,.0f} km, about {mat_crossing_km - current_km:,.0f} km from now."
            )
        else:
            message = (
                f"Re-torque by {mat_due_km:,.0f} km (cycle {mat_due_cycle:,.1f}), {effective_lead:,.0f} km before the predicted "
                f"{crossing_basis} limit crossing at {mat_crossing_km:,.0f} km (cycle {mat_crossing_cycle:,.1f})."
            )

        fasteners.append({
            "MAT number": mat_number,
            "Ton (kgf·m)": ton_kgfm,
            "Estimated Toff at cycle 0 (kgf·m)": toff_initial,
            f"{trend_name} Toff retention at horizon (%)": interpolate_trend_retention(trend_points, design_capacity, "Toff retention (%)"),
            "Toff at FoS horizon (kgf·m)": toff_values[-1][1],
            "Reference Toff limit (kgf·m)": reference_toff_limit,
            "Estimated preload at cycle 0 (kgf)": initial_preload,
            f"{trend_name} preload retention at horizon (%)": interpolate_trend_retention(trend_points, design_capacity, "Preload retention (%)"),
            "Preload at FoS horizon (kgf)": preload_values[-1][1],
            "Reference preload limit (kgf)": reference_preload_limit,
            "Preload limit crossing cycle": preload_crossing,
            "Preload limit crossing km": preload_crossing * km_per_cycle if preload_crossing is not None else None,
            "Estimated Toff at current cycle (kgf·m)": current_toff,
            "Estimated preload at current cycle (kgf)": current_preload,
            "Limit crossing basis": crossing_basis,
            "Limit crossing cycle": mat_crossing_cycle,
            "Limit crossing km": mat_crossing_km,
            "Re-torque due by cycle": mat_due_cycle,
            "Re-torque due by km": mat_due_km,
            "Toff estimate method": toff_method,
            "Re-Torque Requirement as per MAT number": message,
        })

    curve = []
    for fastener in fasteners:
        mat_number = fastener["MAT number"]
        ton_kgfm = fastener["Ton (kgf·m)"]
        toff_initial = fastener["Estimated Toff at cycle 0 (kgf·m)"]
        preload_initial = fastener["Estimated preload at cycle 0 (kgf)"]
        point_set = set(model_cycles)
        point_set.add(float(mission_cycles))
        point_set.update(range(interval_cycles, design_capacity, interval_cycles))
        if 0 <= current_cycle <= design_capacity:
            point_set.add(float(current_cycle))
        if fastener["Limit crossing cycle"] is not None:
            point_set.add(float(fastener["Limit crossing cycle"]))
            point_set.add(float(fastener["Re-torque due by cycle"]))
        for cycle in sorted(point_set):
            toff_retention = interpolate_trend_retention(trend_points, cycle, "Toff retention (%)")
            preload_retention = interpolate_trend_retention(trend_points, cycle, "Preload retention (%)")
            toff = toff_initial * toff_retention / 100.0
            preload = preload_initial * preload_retention / 100.0
            curve.append({
                "MAT number": mat_number,
                "Cycle": cycle,
                "Toff retention (%)": toff_retention,
                "Preload retention (%)": preload_retention,
                "Ton (kgf·m)": ton_kgfm,
                "Toff (kgf·m)": toff,
                "Reference Toff limit (kgf·m)": reference_toff_limit,
                "Toff loss (kgf·m)": toff_initial - toff,
                "Toff (N·m)": toff * 9.80665,
                "Preload (kgf)": preload,
                "Reference preload limit (kgf)": reference_preload_limit,
                "Preload loss (kgf)": preload_initial - preload,
                "Preload (kN)": preload * 9.80665 / 1000.0,
            })

    return {
        "database_ton_kgfm": database_ton,
        "database_preload_kgf": database_preload,
        "design_capacity_cycles": design_capacity,
        "threshold_km": horizon_km,
        "reference_toff_limit": reference_toff_limit,
        "reference_preload_limit": reference_preload_limit,
        "km_per_cycle": km_per_cycle,
        "remaining_cycles": max(0, design_capacity - current_cycle),
        "remaining_km": max(0, design_capacity - current_cycle) * km_per_cycle,
        "fasteners": fasteners,
        "curve": curve,
        "trend_points": trend_points,
    }, None


def calculate_fos_rul(
    *,
    thread_label: str,
    surface_label: str,
    bolt_grade: str,
    mission_cycles: int,
    mission_km: float,
    design_factor_safety: float,
    residual_percent: float,
    current_cycle: int,
    interval_cycles: int,
    torque_check_lead_km: float,
    csv_records: list[dict[str, Any]] | None = None,
    csv_torque_unit: str = "kgf·m",
) -> dict[str, Any]:
    """Predict MAT Toff/preload crossings against a shared joint reference limit."""
    thread = THREAD_OPTIONS[thread_label]
    performance = performance_table_for(thread_label)[SURFACE_PROTECTION[surface_label]][bolt_grade]
    database_ton = float(performance["T_kgfm"])
    database_preload = float(performance["P_kgf"])
    pitch = float(thread["pitch"])
    design_capacity = max(1, int(round(mission_cycles * design_factor_safety)))
    target_ratio = max(0.0, min(1.0, residual_percent / 100.0))
    km_per_cycle = mission_km / mission_cycles
    threshold_cycle = design_capacity if target_ratio < 1.0 else 0
    threshold_km = threshold_cycle * km_per_cycle
    effective_lead_setting = max(0.0, torque_check_lead_km)
    reference_toff_initial = 0.90 * database_ton
    reference_toff_limit = reference_toff_initial * target_ratio
    reference_preload_limit = database_preload * target_ratio
    reference_check_due_km = max(0.0, threshold_km - effective_lead_setting)
    reference_effective_lead_km = max(0.0, threshold_km - reference_check_due_km)

    def crossing_cycle(initial_value: float, threshold_value: float) -> float | None:
        """Find the first cycle at/below a shared threshold on the linear curve."""
        tolerance = 1e-9
        if initial_value <= threshold_value + tolerance:
            return 0.0
        if target_ratio >= 1.0:
            return None
        endpoint_value = initial_value * target_ratio
        if endpoint_value > threshold_value + tolerance:
            return None
        fraction = (1.0 - threshold_value / initial_value) / (1.0 - target_ratio)
        return max(0.0, min(float(design_capacity), fraction * design_capacity))

    source_records = csv_records or [{"MAT number": "Joint baseline", "CSV torque": database_ton}]
    fasteners: list[dict[str, Any]] = []
    for source in source_records:
        if csv_records:
            measured_ton = float(source["CSV torque"])
            if csv_torque_unit == "N·m":
                ton_kgfm = measured_ton / 9.80665
            else:
                ton_kgfm = measured_ton
            # The vehicle's line torque scales the database preload linearly for
            # this demo. Toff uses the same 10% workflow estimate as the DB path.
            initial_preload = database_preload * ton_kgfm / database_ton
            toff_initial = 0.90 * ton_kgfm
            toff_method = "Workflow estimate: Toff is 90% of assembly-line Ton"
            mat_number = str(source["MAT number"])
        else:
            ton_kgfm = database_ton
            initial_preload = database_preload
            toff_initial = 0.90 * ton_kgfm
            toff_method = "Workflow fallback: Toff is estimated as 90% of Ton"
            mat_number = "Joint baseline"

        toff_crossing = crossing_cycle(toff_initial, reference_toff_limit)
        preload_crossing = crossing_cycle(initial_preload, reference_preload_limit)
        # Retorque timing follows the agreed Toff trigger. Preload is still
        # reported separately as a correlated output.
        mat_crossing_cycle = toff_crossing
        mat_crossing_km = mat_crossing_cycle * km_per_cycle if mat_crossing_cycle is not None else None
        mat_due_km = max(0.0, mat_crossing_km - effective_lead_setting) if mat_crossing_km is not None else None
        mat_due_cycle = mat_due_km / km_per_cycle if mat_due_km is not None else None
        mat_effective_lead_km = (
            max(0.0, mat_crossing_km - mat_due_km)
            if mat_crossing_km is not None and mat_due_km is not None
            else None
        )

        cycle_for_check = min(current_cycle, design_capacity)
        current_retention = 1.0 - (1.0 - target_ratio) * cycle_for_check / design_capacity
        expected_current_toff = toff_initial * current_retention
        expected_current_preload = initial_preload * current_retention
        current_km = current_cycle * km_per_cycle
        if mat_crossing_cycle is None:
            message = (
                f"Re-torquing not required within the modeled FOS life ({design_capacity:,} cycles / "
                f"{threshold_km:,.0f} km). Predicted Toff at the horizon is "
                f"{toff_initial * target_ratio:.3f} kgf·m, above the reference limit "
                f"{reference_toff_limit:.3f} kgf·m."
            )
        elif current_km >= mat_crossing_km:
            message = (
                f"Torque application required now. The predicted Toff limit crossing was at "
                f"{mat_crossing_km:,.0f} km (cycle {mat_crossing_cycle:,.1f})."
            )
        elif current_km >= mat_due_km:
            message = (
                f"Torque application due now/by {current_km:,.0f} km. The predicted Toff limit crossing is at "
                f"{mat_crossing_km:,.0f} km, about {mat_crossing_km - current_km:,.0f} km from now."
            )
        else:
            message = (
                f"Re-torque by {mat_due_km:,.0f} km (cycle {mat_due_cycle:,.1f}), "
                f"{mat_effective_lead_km:,.0f} km before the predicted Toff limit crossing "
                f"at {mat_crossing_km:,.0f} km (cycle {mat_crossing_cycle:,.1f})."
            )

        fasteners.append({
            "MAT number": mat_number,
            "Ton (kgf·m)": ton_kgfm,
            "Estimated Toff at cycle 0 (kgf·m)": toff_initial,
            "Toff at capacity limit (kgf·m)": toff_initial * target_ratio,
            "Reference Toff limit (kgf·m)": reference_toff_limit,
            "Database preload basis (kgf)": database_preload,
            "Estimated preload at cycle 0 (kgf)": initial_preload,
            "Preload at capacity limit (kgf)": initial_preload * target_ratio,
            "Reference preload limit (kgf)": reference_preload_limit,
            "Estimated Toff at current cycle (kgf·m)": expected_current_toff,
            "Estimated preload at current cycle (kgf)": expected_current_preload,
            "Toff limit crossing cycle": mat_crossing_cycle,
            "Toff limit crossing km": mat_crossing_km,
            "Re-torque due by cycle": mat_due_cycle,
            "Re-torque due by km": mat_due_km,
            "Current km": current_km,
            "Cycles to Toff limit": max(0.0, mat_crossing_cycle - current_cycle) if mat_crossing_cycle is not None else None,
            "Km to Toff limit": max(0.0, mat_crossing_km - current_km) if mat_crossing_km is not None else None,
            "Toff estimate method": toff_method,
            "Re-Torque Requirement as per MAT number": message,
        })

    # Build an interval table including mission life, check-due points, and
    # MAT-specific Toff/preload threshold crossings.
    curve = []
    for fastener in fasteners:
        ton_kgfm = fastener["Ton (kgf·m)"]
        toff_initial = fastener["Estimated Toff at cycle 0 (kgf·m)"]
        preload_initial = fastener["Estimated preload at cycle 0 (kgf)"]
        point_set = {0.0, float(mission_cycles), float(design_capacity)}
        point_set.update(range(interval_cycles, design_capacity, interval_cycles))
        if 0 <= current_cycle <= design_capacity:
            point_set.add(float(current_cycle))
        if fastener["Toff limit crossing cycle"] is not None:
            point_set.add(float(fastener["Toff limit crossing cycle"]))
            point_set.add(float(fastener["Re-torque due by cycle"]))
        for cycle in sorted(point_set):
            progress = min(1.0, max(0.0, cycle / design_capacity))
            retention = 1.0 - (1.0 - target_ratio) * progress
            toff = toff_initial * retention
            preload = preload_initial * retention
            curve.append({
                "MAT number": fastener["MAT number"],
                "Cycle": cycle,
                "Retention (%)": retention * 100.0,
                "Ton (kgf·m)": ton_kgfm,
                "Toff (kgf·m)": toff,
                "Toff loss (kgf·m)": toff_initial - toff,
                "Toff (N·m)": toff * 9.80665,
                "Preload (kgf)": preload,
                "Preload loss (kgf)": preload_initial - preload,
                "Preload (kN)": preload * 9.80665 / 1000.0,
                "Reference Toff limit (kgf·m)": reference_toff_limit,
                "Reference preload limit (kgf)": reference_preload_limit,
            })

    return {
        "database_ton_kgfm": database_ton,
        "database_preload_kgf": database_preload,
        "pitch_mm": pitch,
        "design_capacity_cycles": design_capacity,
        "threshold_cycle": threshold_cycle,
        "threshold_km": threshold_km,
        "reference_toff_initial": reference_toff_initial,
        "reference_toff_limit": reference_toff_limit,
        "reference_preload_limit": reference_preload_limit,
        "reference_check_due_km": reference_check_due_km,
        "reference_effective_lead_km": reference_effective_lead_km,
        "torque_check_lead_km": effective_lead_setting,
        "km_per_cycle": km_per_cycle,
        "remaining_cycles": max(0, design_capacity - current_cycle),
        "remaining_km": max(0, design_capacity - current_cycle) * km_per_cycle,
        "fasteners": fasteners,
        "curve": curve,
    }


def create_rul_figure(
    curve: list[dict[str, Any]],
    value_key: str,
    capacity: int,
    mission_cycles: int,
    threshold_value: float,
    title: str,
    ylabel: str,
    threshold_label: str,
):
    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    mat_numbers = list(dict.fromkeys(row["MAT number"] for row in curve))
    for mat_number in mat_numbers:
        rows = [row for row in curve if row["MAT number"] == mat_number]
        ax.plot(
            [row["Cycle"] for row in rows],
            [row[value_key] for row in rows],
            marker="o",
            linewidth=1.8,
            label=mat_number,
        )
    ax.axhline(
        threshold_value,
        color="#7F1D1D",
        linestyle=":",
        linewidth=1.4,
        label=threshold_label,
    )
    ax.axvline(
        mission_cycles,
        color="#B42318",
        linestyle="--",
        linewidth=1.2,
        label="Mission life / design limit",
    )
    ax.set_title(title)
    ax.set_xlabel("Working cycle (chart extends to mission life × FoS)")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, capacity)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return fig


def render_fos_rul_mode(st) -> None:
    st.title("Fastener Joint Digital Twin — RUL Mode")
    st.subheader("RUL Model 1: FOS Model")
    st.caption(
        "A simple theoretical model: Toff and preload decrease linearly from cycle 0 to the expected "
        "residual percentage at the FoS-scaled design capacity."
    )

    st.markdown("#### Case and fastener inputs")
    top = st.columns(2)
    with top[0]:
        project_name = st.text_input("Project name", key="rul_project_name")
        joint_name = st.text_input("Joint name", key="rul_joint_name")
        thread_label = st.selectbox("Thread size", list(THREAD_OPTIONS), key="rul_thread")
    with top[1]:
        surface_label = st.selectbox("Surface protection", list(SURFACE_PROTECTION), key="rul_surface")
        thread_class = st.selectbox("Thread class (Fine / Medium / Coarse)", HOLE_CLASSES, key="rul_thread_class")
        bolt_grade = st.selectbox(
            "Bolt property class for database lookup",
            BOLT_GRADES,
            key="rul_bolt_grade",
            help="Selects the existing torque and preload row; no stress values need to be entered.",
        )

    st.markdown("#### Assembly-line torque information")
    template_cols = st.columns([2.5, 1.0])
    with template_cols[0]:
        st.caption(
            "The template has five starter MAT rows. Replace the sample MAT numbers, enter one assembly torque per row, "
            "and choose the matching torque unit below."
        )
    with template_cols[1]:
        st.download_button(
            "Download CSV template",
            data=build_rul_torque_csv_template(),
            file_name="rul_fos_mat_torque_template.csv",
            mime="text/csv",
            width="stretch",
        )
    torque_source = st.radio(
        "Is assembly-line torque information available?",
        ["No — use database Ton", "Yes — upload MAT/Torque CSV"],
        horizontal=True,
        key="rul_torque_source",
    )
    csv_records: list[dict[str, Any]] | None = None
    csv_torque_unit = "kgf·m"
    if torque_source.startswith("Yes"):
        csv_cols = st.columns([1.3, 1.0])
        with csv_cols[0]:
            uploaded = st.file_uploader(
                "CSV with MAT number and Torque value columns",
                type=["csv"],
                key="rul_torque_csv",
                help="The Torque column is treated as each MAT's assembly Ton. Use one row per vehicle/fastener.",
            )
        with csv_cols[1]:
            csv_torque_unit = st.selectbox(
                "CSV torque unit",
                ["kgf·m", "N·m"],
                key="rul_torque_csv_unit",
            )
        if uploaded is not None:
            parsed, error = parse_rul_torque_csv(uploaded)
            if error:
                st.error(error)
                return
            else:
                csv_records = parsed
                st.success(f"Loaded {len(parsed)} MAT torque record(s). CSV torque is interpreted as assembly Ton.")
                st.dataframe(parsed, width="stretch", hide_index=True)
        else:
            st.info("Upload the assembly-line CSV. Until then, the database Ton is shown as a preview.")

    st.markdown("#### Mission and monitoring inputs")
    mission_cols = st.columns(5)
    with mission_cols[0]:
        mission_cycles = int(st.number_input("Mission cycles", min_value=1, max_value=10_000_000, value=1600, step=100, key="rul_mission_cycles"))
    with mission_cols[1]:
        mission_km = float(st.number_input("Mission km", min_value=1.0, max_value=100_000_000.0, value=240000.0, step=1000.0, key="rul_mission_km"))
    with mission_cols[2]:
        fos = float(st.number_input("Design factor of safety", min_value=0.1, max_value=10.0, value=2.0, step=0.1, key="rul_fos"))
    with mission_cols[3]:
        residual_percent = float(st.number_input("Expected residual Toff at design capacity (%)", min_value=1.0, max_value=100.0, value=90.0, step=1.0, key="rul_residual_percent"))
    with mission_cols[4]:
        current_cycle = int(st.number_input("Current working cycle", min_value=0, max_value=10_000_000, value=0, step=100, key="rul_current_cycle"))
    check_cols = st.columns(2)
    with check_cols[0]:
        interval_cycles = int(st.number_input(
            "Monitoring interval (cycles)", min_value=1, max_value=1_000_000, value=400, step=100, key="rul_interval_cycles"
        ))
    with check_cols[1]:
        torque_check_lead_km = float(st.number_input(
            "Torque-check lead before Toff threshold (km)",
            min_value=0.0,
            max_value=10_000_000.0,
            value=5000.0,
            step=500.0,
            key="rul_torque_check_lead_km",
            help="The app schedules the torque check this many kilometres before predicted Toff reaches the residual threshold.",
        ))

    if mission_cycles <= 0 or mission_km <= 0 or interval_cycles <= 0:
        st.error("Mission cycles, mission kilometres, and monitoring interval must be positive.")
        return

    csv_for_model = csv_records if csv_records else None
    result = calculate_fos_rul(
        thread_label=thread_label,
        surface_label=surface_label,
        bolt_grade=bolt_grade,
        mission_cycles=mission_cycles,
        mission_km=mission_km,
        design_factor_safety=fos,
        residual_percent=residual_percent,
        current_cycle=current_cycle,
        interval_cycles=interval_cycles,
        torque_check_lead_km=torque_check_lead_km,
        csv_records=csv_for_model,
        csv_torque_unit=csv_torque_unit,
    )
    database_row = performance_table_for(thread_label)[SURFACE_PROTECTION[surface_label]][bolt_grade]

    st.divider()
    st.markdown("#### Results")
    result_metrics = st.columns(4)
    result_metrics[0].metric("Ton reference", f"{result['database_ton_kgfm']:.2f} kgf·m")
    result_metrics[1].metric("Database preload basis", f"{result['database_preload_kgf']:.0f} kgf")
    result_metrics[2].metric("Design capacity / failure boundary", f"{result['design_capacity_cycles']:,} cycles")
    result_metrics[3].metric("Remaining life from current cycle", f"{result['remaining_cycles']:,} cycles")
    km_metrics = st.columns(2)
    km_metrics[0].metric("FoS-scaled km horizon", f"{result['threshold_km']:,.0f} km")
    km_metrics[1].metric(
        "Reference Toff limit at horizon",
        f"{result['reference_toff_limit']:.3f} kgf·m",
    )
    st.caption(
        f"Reference Toff: {result['database_ton_kgfm']:.3f} Ton × 90% initial Toff × "
        f"{residual_percent:.1f}% residual = {result['reference_toff_limit']:.3f} kgf·m. "
        f"Reference preload limit: {result['reference_preload_limit']:.0f} kgf."
    )

    if current_cycle >= result["design_capacity_cycles"]:
        st.warning(
            "The entered current cycle has reached or exceeded the FoS-scaled model horizon. "
            "Use the MAT-specific re-torque requirements below."
        )
    else:
        st.info(
            f"At {current_cycle:,} cycles, the model predicts {result['remaining_cycles']:,} cycles "
            f"({result['remaining_km']:,.0f} km) to the design-capacity boundary. Use an actual torque reading "
            "at inspection to decide whether the joint needs retightening."
        )

    st.markdown("#### Design inputs")
    st.dataframe([
        {"Input": "Project name", "Value": project_name or "Not entered"},
        {"Input": "Joint name", "Value": joint_name or "Not entered"},
        {"Input": "Fastener", "Value": f"{thread_label}, class {bolt_grade}, {surface_label}"},
        {"Input": "Thread class", "Value": f"{thread_class} (recorded as a formality)"},
        {"Input": "Mission definition", "Value": f"{mission_cycles:,} cycles / {mission_km:,.0f} km"},
        {"Input": "FOS-scaled capacity", "Value": f"{mission_cycles:,} × {fos:.2f} = {result['design_capacity_cycles']:,} cycles"},
        {"Input": "Shared reference Toff limit", "Value": f"{result['reference_toff_limit']:.3f} kgf·m"},
        {"Input": "Shared reference preload limit", "Value": f"{result['reference_preload_limit']:.0f} kgf"},
        {"Input": "Monitoring interval / current cycle", "Value": f"{interval_cycles:,} / {current_cycle:,} cycles"},
        {"Input": "Torque-check lead", "Value": f"{torque_check_lead_km:,.0f} km before Toff threshold"},
        {"Input": "Torque/preload source", "Value": "MAT CSV" if csv_for_model else "Existing database"},
        {"Input": "Database reference preload", "Value": f"{database_row['P_kgf']:.0f} kgf"},
    ], width="stretch", hide_index=True)

    st.markdown("#### Re-Torque Requirement as per MAT number")
    st.dataframe(result["fasteners"], width="stretch", hide_index=True)
    st.caption(
        "The MAT/Torque CSV is treated as assembly Ton. Each MAT starts at Toff = 90% of its Ton. "
        "Each MAT curve is compared with one shared Toff/preload limit derived from the selected database fastener at the FoS horizon. "
        "The first predicted crossing sets the re-torque date, advanced by the selected kilometre lead."
    )

    st.markdown("#### Toff versus cycle interval")
    st.caption(
        f"Charts span 0 to {result['design_capacity_cycles']:,} cycles. The vertical line marks mission life "
        f"({mission_cycles:,} cycles); the dotted horizontal line is the shared database Toff limit at mission life × FoS."
    )
    toff_columns = [
        "MAT number", "Cycle", "Retention (%)", "Ton (kgf·m)",
        "Toff (kgf·m)", "Reference Toff limit (kgf·m)", "Toff (N·m)", "Toff loss (kgf·m)",
    ]
    st.dataframe(
        [{key: row[key] for key in toff_columns} for row in result["curve"]],
        width="stretch",
        hide_index=True,
    )
    fig = create_rul_figure(
        result["curve"],
        "Toff (kgf·m)",
        result["design_capacity_cycles"],
        mission_cycles,
        result["reference_toff_limit"],
        "Predicted Toff retention",
        "Toff (kgf·m)",
        "Reference Toff limit",
    )
    st.pyplot(fig, clear_figure=True, width="stretch")
    plt.close(fig)

    st.markdown("#### Preload versus cycle interval")
    st.caption(
        f"The dotted horizontal line is the shared database preload limit ({result['reference_preload_limit']:.0f} kgf) "
        "at mission life × FoS."
    )
    preload_columns = [
        "MAT number", "Cycle", "Retention (%)", "Preload (kgf)",
        "Reference preload limit (kgf)", "Preload (kN)", "Preload loss (kgf)",
    ]
    st.dataframe(
        [{key: row[key] for key in preload_columns} for row in result["curve"]],
        width="stretch",
        hide_index=True,
    )
    fig = create_rul_figure(
        result["curve"],
        "Preload (kgf)",
        result["design_capacity_cycles"],
        mission_cycles,
        result["reference_preload_limit"],
        "Estimated preload retention",
        "Preload (kgf)",
        "Reference preload limit",
    )
    st.pyplot(fig, clear_figure=True, width="stretch")
    plt.close(fig)


def render_trend_rul_mode(
    st,
    *,
    model_title: str,
    trend_name: str,
    key_prefix: str,
    template_filename: str,
    template_builder,
    demo_trend: list[dict[str, float]],
) -> None:
    st.title("Fastener Joint Digital Twin — RUL Mode")
    st.subheader(model_title)
    st.caption(
        f"Upload a {trend_name} retention trend by cycle. The normalized Toff and preload curves are scaled to each MAT's "
        "assembly torque, then compared with the shared database reference limits."
    )

    st.markdown("#### Case and fastener inputs")
    top = st.columns(2)
    with top[0]:
        project_name = st.text_input("Project name", key=f"{key_prefix}_project_name")
        joint_name = st.text_input("Joint name", key=f"{key_prefix}_joint_name")
        thread_label = st.selectbox("Thread size", list(THREAD_OPTIONS), key=f"{key_prefix}_thread")
    with top[1]:
        surface_label = st.selectbox("Surface protection", list(SURFACE_PROTECTION), key=f"{key_prefix}_surface")
        thread_class = st.selectbox("Thread class (Fine / Medium / Coarse)", HOLE_CLASSES, key=f"{key_prefix}_thread_class")
        bolt_grade = st.selectbox(
            "Bolt property class for database lookup",
            BOLT_GRADES,
            key=f"{key_prefix}_bolt_grade",
            help="Selects the existing torque and preload row; no stress values need to be entered.",
        )

    st.markdown("#### Assembly-line torque information")
    template_cols = st.columns([2.5, 1.0])
    with template_cols[0]:
        st.caption(
            "The MAT template has five starter rows. Replace the MAT numbers, enter one assembly torque per row, "
            "and choose the matching torque unit."
        )
    with template_cols[1]:
        st.download_button(
            "Download MAT CSV template",
            data=build_rul_torque_csv_template(),
            file_name=f"rul_{key_prefix}_mat_torque_template.csv",
            mime="text/csv",
            width="stretch",
        )
    torque_source = st.radio(
        "Is assembly-line torque information available?",
        ["No — use database Ton", "Yes — upload MAT/Torque CSV"],
        horizontal=True,
        key=f"{key_prefix}_torque_source",
    )
    csv_records: list[dict[str, Any]] | None = None
    csv_torque_unit = "kgf·m"
    if torque_source.startswith("Yes"):
        csv_cols = st.columns([1.3, 1.0])
        with csv_cols[0]:
            uploaded_torque = st.file_uploader(
                "CSV with MAT number and Torque value columns",
                type=["csv"],
                key=f"{key_prefix}_torque_csv",
                help="The Torque column is each MAT's assembly Ton. Use one row per vehicle/fastener.",
            )
        with csv_cols[1]:
            csv_torque_unit = st.selectbox("CSV torque unit", ["kgf·m", "N·m"], key=f"{key_prefix}_torque_csv_unit")
        if uploaded_torque is not None:
            parsed_torque, torque_error = parse_rul_torque_csv(uploaded_torque)
            if torque_error:
                st.error(torque_error)
                return
            else:
                csv_records = parsed_torque
                st.success(f"Loaded {len(parsed_torque)} MAT torque record(s). CSV torque is interpreted as assembly Ton.")
                st.dataframe(parsed_torque, width="stretch", hide_index=True)
        else:
            st.info("Upload the assembly-line CSV. Until then, database Ton is used for the preview.")

    st.markdown(f"#### {trend_name} results trend")
    trend_cols = st.columns([2.5, 1.0])
    with trend_cols[0]:
        st.caption(
            f"Download the example, replace its rows with {trend_name.lower()} results, and upload it. The template reports normalized "
            "Toff and preload retention percentages at cycle intervals and includes a sample declining trend."
        )
    with trend_cols[1]:
        st.download_button(
            f"Download {trend_name} results template",
            data=template_builder(),
            file_name=template_filename,
            mime="text/csv",
            width="stretch",
        )
    uploaded_trend = st.file_uploader(
        f"Upload {trend_name} results CSV",
        type=["csv"],
        key=f"{key_prefix}_results_csv",
        help=f"Required columns: Cycle, Toff retention (%), Preload retention (%). The {trend_name.lower()} trend must start at 0 cycles/100% and cover the full FoS horizon.",
    )
    if uploaded_trend is not None:
        trend_points, trend_error = parse_rul_trend_csv(uploaded_trend, trend_name)
        trend_source_label = f"Uploaded {trend_name} results CSV"
        if trend_error:
            st.error(trend_error)
            return
        st.success(f"Loaded {len(trend_points)} {trend_name.lower()} trend points.")
    else:
        trend_points = demo_trend
        trend_source_label = "Illustrative downloadable template trend (preview only)"
        st.info(f"Using the sample {trend_name.lower()} trend for preview. Upload your results CSV to calculate from project data.")
    st.dataframe(trend_points, width="stretch", hide_index=True)

    st.markdown("#### Mission and monitoring inputs")
    mission_cols = st.columns(5)
    with mission_cols[0]:
        mission_cycles = int(st.number_input("Mission cycles", min_value=1, max_value=10_000_000, value=1600, step=100, key=f"{key_prefix}_mission_cycles"))
    with mission_cols[1]:
        mission_km = float(st.number_input("Mission km", min_value=1.0, max_value=100_000_000.0, value=240000.0, step=1000.0, key=f"{key_prefix}_mission_km"))
    with mission_cols[2]:
        fos = float(st.number_input("Design factor of safety", min_value=0.1, max_value=10.0, value=2.0, step=0.1, key=f"{key_prefix}_fos"))
    with mission_cols[3]:
        residual_percent = float(st.number_input("Expected residual Toff at design capacity (%)", min_value=1.0, max_value=100.0, value=90.0, step=1.0, key=f"{key_prefix}_residual_percent"))
    with mission_cols[4]:
        current_cycle = int(st.number_input("Current working cycle", min_value=0, max_value=10_000_000, value=0, step=100, key=f"{key_prefix}_current_cycle"))
    check_cols = st.columns(2)
    with check_cols[0]:
        interval_cycles = int(st.number_input("Monitoring interval (cycles)", min_value=1, max_value=1_000_000, value=400, step=100, key=f"{key_prefix}_interval_cycles"))
    with check_cols[1]:
        torque_check_lead_km = float(st.number_input(
            "Torque-check lead before Toff threshold (km)", min_value=0.0, max_value=10_000_000.0,
            value=5000.0, step=500.0, key=f"{key_prefix}_torque_check_lead_km",
            help="Schedule the torque check this many kilometres before the predicted Toff limit crossing.",
        ))

    if mission_cycles <= 0 or mission_km <= 0 or interval_cycles <= 0:
        st.error("Mission cycles, mission kilometres, and monitoring interval must be positive.")
        return

    result, calculation_error = calculate_trend_rul(
        thread_label=thread_label,
        surface_label=surface_label,
        bolt_grade=bolt_grade,
        mission_cycles=mission_cycles,
        mission_km=mission_km,
        design_factor_safety=fos,
        residual_percent=residual_percent,
        current_cycle=current_cycle,
        interval_cycles=interval_cycles,
        torque_check_lead_km=torque_check_lead_km,
        trend_points=trend_points,
        trend_name=trend_name,
        csv_records=csv_records,
        csv_torque_unit=csv_torque_unit,
    )
    if calculation_error:
        st.error(calculation_error)
        return
    assert result is not None
    database_row = performance_table_for(thread_label)[SURFACE_PROTECTION[surface_label]][bolt_grade]

    st.divider()
    st.markdown("#### Results")
    result_metrics = st.columns(4)
    result_metrics[0].metric("Ton reference", f"{result['database_ton_kgfm']:.2f} kgf·m")
    result_metrics[1].metric("Database preload basis", f"{result['database_preload_kgf']:.0f} kgf")
    result_metrics[2].metric("Design capacity / failure boundary", f"{result['design_capacity_cycles']:,} cycles")
    result_metrics[3].metric("Remaining life from current cycle", f"{result['remaining_cycles']:,} cycles")
    km_metrics = st.columns(2)
    km_metrics[0].metric("FoS-scaled km horizon", f"{result['threshold_km']:,.0f} km")
    km_metrics[1].metric("Reference Toff limit", f"{result['reference_toff_limit']:.3f} kgf·m")
    st.caption(
        f"Reference Toff limit = database Ton ({result['database_ton_kgfm']:.3f} kgf·m) × 90% initial Toff × "
        f"{residual_percent:.1f}% residual = {result['reference_toff_limit']:.3f} kgf·m. "
        f"Reference preload limit = {result['reference_preload_limit']:.0f} kgf. Re-torque timing is based on Toff crossing."
    )
    if current_cycle >= result["design_capacity_cycles"]:
        st.warning(f"The entered current cycle has reached or exceeded the FoS-scaled {trend_name} horizon. See MAT-specific re-torque requirements below.")
    else:
        st.info(
            f"At {current_cycle:,} cycles, {result['remaining_cycles']:,} cycles ({result['remaining_km']:,.0f} km) remain to the model horizon. "
            "Use an actual torque reading at inspection to decide whether the joint needs retightening."
        )

    st.markdown("#### Design inputs")
    st.dataframe([
        {"Input": "Project name", "Value": project_name or "Not entered"},
        {"Input": "Joint name", "Value": joint_name or "Not entered"},
        {"Input": "Fastener", "Value": f"{thread_label}, class {bolt_grade}, {surface_label}"},
        {"Input": "Thread class", "Value": f"{thread_class} (recorded as a formality)"},
        {"Input": "Mission definition", "Value": f"{mission_cycles:,} cycles / {mission_km:,.0f} km"},
        {"Input": "FoS-scaled capacity", "Value": f"{mission_cycles:,} × {fos:.2f} = {result['design_capacity_cycles']:,} cycles"},
        {"Input": "Shared reference Toff limit", "Value": f"{result['reference_toff_limit']:.3f} kgf·m"},
        {"Input": "Shared reference preload limit", "Value": f"{result['reference_preload_limit']:.0f} kgf"},
        {"Input": "Monitoring interval / current cycle", "Value": f"{interval_cycles:,} / {current_cycle:,} cycles"},
        {"Input": "Torque-check lead", "Value": f"{torque_check_lead_km:,.0f} km before Toff threshold"},
        {"Input": "Torque/preload source", "Value": "MAT CSV" if csv_records else "Existing database"},
        {"Input": f"{trend_name} curve source", "Value": trend_source_label},
        {"Input": "Database reference preload", "Value": f"{database_row['P_kgf']:.0f} kgf"},
    ], width="stretch", hide_index=True)

    st.markdown("#### Re-Torque Requirement as per MAT number")
    st.dataframe(result["fasteners"], width="stretch", hide_index=True)
    st.caption(
        f"Each MAT starts at estimated Toff = 90% of its assembly Ton. The uploaded {trend_name} retention trend is applied to each MAT. "
        "The Toff trend is compared with the shared database reference limit; the re-torque date is scheduled by the configured km lead."
    )

    st.markdown("#### Toff versus cycle interval")
    st.caption(
        f"Charts span 0 to {result['design_capacity_cycles']:,} cycles. The vertical line marks mission life "
        f"({mission_cycles:,} cycles); the horizontal line is the shared database Toff limit."
    )
    toff_columns = [
        "MAT number", "Cycle", "Toff retention (%)", "Ton (kgf·m)", "Toff (kgf·m)",
        "Reference Toff limit (kgf·m)", "Toff (N·m)", "Toff loss (kgf·m)",
    ]
    st.dataframe([{key: row[key] for key in toff_columns} for row in result["curve"]], width="stretch", hide_index=True)
    fig = create_rul_figure(
        result["curve"], "Toff (kgf·m)", result["design_capacity_cycles"], mission_cycles,
        result["reference_toff_limit"], f"{trend_name}-predicted Toff retention", "Toff (kgf·m)", "Reference Toff limit",
    )
    st.pyplot(fig, clear_figure=True, width="stretch")
    plt.close(fig)

    st.markdown("#### Preload versus cycle interval")
    st.caption(f"The horizontal line is the shared database preload limit ({result['reference_preload_limit']:.0f} kgf).")
    preload_columns = [
        "MAT number", "Cycle", "Preload retention (%)", "Preload (kgf)",
        "Reference preload limit (kgf)", "Preload (kN)", "Preload loss (kgf)",
    ]
    st.dataframe([{key: row[key] for key in preload_columns} for row in result["curve"]], width="stretch", hide_index=True)
    fig = create_rul_figure(
        result["curve"], "Preload (kgf)", result["design_capacity_cycles"], mission_cycles,
        result["reference_preload_limit"], f"{trend_name}-predicted preload retention", "Preload (kgf)", "Reference preload limit",
    )
    st.pyplot(fig, clear_figure=True, width="stretch")
    plt.close(fig)


def render_cae_rul_mode(st) -> None:
    render_trend_rul_mode(
        st,
        model_title="RUL Model 2: CAE Model",
        trend_name="CAE",
        key_prefix="cae",
        template_filename="rul_cae_trend_template.csv",
        template_builder=build_cae_rul_csv_template,
        demo_trend=DEMO_CAE_TREND,
    )


def render_test_rul_mode(st) -> None:
    render_trend_rul_mode(
        st,
        model_title="RUL Model 3: Test Model",
        trend_name="Test",
        key_prefix="test",
        template_filename="rul_test_results_template.csv",
        template_builder=build_test_rul_csv_template,
        demo_trend=DEMO_TEST_TREND,
    )


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Fastener Joint Digital Twin", layout="wide")
    mode = st.sidebar.radio("Select mode", ["Design Mode", "Verification Mode", "RUL Mode"])
    if mode == "Design Mode":
        render_design_mode(st)
    elif mode == "Verification Mode":
        render_verification_mode(st)
    else:
        rul_model = st.sidebar.selectbox(
            "RUL Model",
            ["RUL Model 1: FOS Model", "RUL Model 2: CAE Model", "RUL Model 3: Test Model"],
        )
        if rul_model == "RUL Model 1: FOS Model":
            render_fos_rul_mode(st)
        elif rul_model == "RUL Model 2: CAE Model":
            render_cae_rul_mode(st)
        else:
            render_test_rul_mode(st)


if __name__ == "__main__":
    main()

