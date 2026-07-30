#!/usr/bin/env python3
"""
Generate a to-scale architectural floor plan (SVG) for a ground-floor bar
in Hong Kong, annotated for BD / FSD / Liquor Licensing Board compliance.

Model space  : millimetres, origin at the internal south-west corner of the
               tenancy, +X east, +Y north.
Paper space  : millimetres on an ISO A0 landscape sheet (1189 x 841), plan
               drawn at 1:20.

The geometry below is hand-tuned to a 12.0 m x 8.0 m rectangular unit.
Changing ROOM_W / ROOM_H alone will move the walls but will NOT re-plan the
furniture -- the zone coordinates have to be re-tuned with them.

Run:  python3 generate_plan.py [output.svg]
"""

from __future__ import annotations

import math
import sys
import textwrap

# ==========================================================================
# 1.  SPACE AND SHEET PARAMETERS
# ==========================================================================

ROOM_W = 12000          # internal clear width  (east-west)
ROOM_H = 8000           # internal clear depth  (north-south)
WALL = 200              # external / demising wall thickness
PART = 100              # internal partition thickness

SCALE = 20              # 1:20
SHEET_W, SHEET_H = 1189.0, 841.0        # A0 landscape, mm
MARGIN = 12.0

PLAN_X0 = 92.0          # paper x of model x = -WALL
PLAN_Y0 = 522.0         # paper y of model y = -WALL  (paper y grows downward)
PANEL_X = 756.0         # right-hand information panel

# ==========================================================================
# 2.  MODEL GEOMETRY  (all millimetres)
# ==========================================================================

# ---- back-of-house strip -------------------------------------------------
BOH_PART_Y0, BOH_PART_Y1 = 5400, 5500       # east-west partition
BOH_Y0, BOH_Y1 = 5500, 8000                 # BOH clear depth = 2500

BOH_ROOMS = [
    (0,     1300,  "corr",   ["PROTECTED ESCAPE CORRIDOR"]),
    (1400,  3400,  "glass",  ["GLASSWASH /", "SERVERY"]),
    (3500,  5700,  "cellar", ["CELLAR /", "LIQUOR STORE"]),
    (5800,  7200,  "staff",  ["STAFF /", "BOH LOBBY"]),
    (7300,  9300,  "acc",    ["ACCESSIBLE", "UNISEX WC"]),
    (9400,  10600, "wcf",    ["WC (F)"]),
    (10700, 12000, "wcm",    ["WC (M)"]),
]
BOH_PARTS_X = [(1300, 1400), (3400, 3500), (5700, 5800),
               (7200, 7300), (9300, 9400), (10600, 10700)]

# ---- bar -----------------------------------------------------------------
BAR_X0, BAR_X1 = 1400, 5900                 # main counter run
CTR_Y0, CTR_Y1 = 3450, 4050                 # counter, 600 deep
WORK_Y0, WORK_Y1 = 4050, 5050               # working zone, 1000 clear
BACK_Y0, BACK_Y1 = 5050, 5400               # back-bar shelving, 350 deep
WORK_X1 = 5300                              # working zone stops at the return
RET_X0, RET_X1 = 5300, 5900                 # return counter (north-south)
RET_Y0, RET_Y1 = 4050, 5400

# openings in the BOH partition
D_GLASS = (1900, 2700)                      # glasswash  -> bar working zone
D_CELLAR = (4300, 5100)                     # cellar     -> bar working zone
D_STAFF = (6400, 7200)                      # staff room -> public room
D_ACC = (7600, 8600)                        # accessible WC (sliding)
D_WCF = (9600, 10400)
D_WCM = (10900, 11700)

# ---- final exits ---------------------------------------------------------
EXIT1_X0, EXIT1_X1 = 8300, 10100            # south wall, 1800 opening
EXIT2_X0, EXIT2_X1 = 50, 1250               # north wall, 1200 opening
EXIT1_CLEAR, EXIT2_CLEAR = 1700, 1130

# ---- circulation / means of escape (kept clear of all furniture) ---------
SPINE_A = (700, 9700, 1650, 2850)           # east-west, 1200 clear
SPINE_B = (0, 1400, 1650, 5400)             # west, 1400 clear -> EXIT 2
CORRIDOR = (0, 1300, 5400, 8000)            # protected corridor, 1300 clear
SPINE_C = (8500, 9700, 1650, 4000)          # north-south, 1200 clear
ENTRY = (8300, 10100, 0, 1650)              # entrance lobby / EXIT 1 route
WC_LOBBY = (7300, 12000, 4000, 5400)        # toilet lobby, 1400 clear

ESCAPE_ZONES = [SPINE_A, SPINE_B, CORRIDOR, SPINE_C, ENTRY, WC_LOBBY]

# ---- seating -------------------------------------------------------------
BENCH = (1500, 6900, 0, 550)                # continuous banquette
BAY_X0, BAY_X1, N_BAYS = 1500, 6900, 4
TBL_W = 1100
TBL_Y0, TBL_Y1 = 600, 1200
CHAIR = 450
CHAIR_Y0, CHAIR_Y1 = 1200, 1650

STOOL_D = 400
STOOL_XS = [1750, 2400, 3050, 3700, 4350, 5000, 5650]
STOOL_Y = 3050
RET_STOOL_X = 6250
RET_STOOL_YS = [4350, 4900]

SOFA_A = (10150, 11950, 0, 750)             # lounge cluster A
CTBL_A = (10600, 11500, 900, 1550)
TUB_A = [(10300, 11000, 1650, 2350), (11100, 11800, 1650, 2350)]
SOFA_B = (11250, 12000, 2400, 4000)         # lounge cluster B
CTBL_B = (10400, 11150, 2850, 3600)

POSEUR = [(6600, 3400), (7800, 3400)]
POSEUR_R = 300

STAND_1 = (6900, 8300, 0, 1650)
STAND_2 = (5900, 8500, 2850, 4000)
STAND_3 = (5900, 7300, 4000, 5400)
DRINK_RAIL = (6950, 8250, 0, 300)

# ---- compliance figures reported on the sheet ----------------------------
TRAVEL_MAX = 8.6            # m, longest travel distance to the nearest exit
TRAVEL_DEADEND = 5.0        # m, longest single-direction travel
EXIT_SEPARATION = 12.0      # m, EXIT 1 to EXIT 2
HALF_DIAGONAL = round(math.hypot(ROOM_W + 2 * WALL, ROOM_H + 2 * WALL)
                      / 2 / 1000, 1)
HEADROOM = 2600             # mm, finished clear height to escape routes

# ==========================================================================
# 3.  DERIVED SCHEDULES
# ==========================================================================

M2 = 1_000_000.0


def area(x0, x1, y0, y1):
    return (x1 - x0) * (y1 - y0) / M2


def rarea(r):
    return area(r[0], r[1], r[2], r[3])


PUBLIC_GROSS = area(0, ROOM_W, 0, BOH_PART_Y0)
A_COUNTER = area(BAR_X0, BAR_X1, CTR_Y0, CTR_Y1)
A_RETURN = area(RET_X0, RET_X1, RET_Y0, RET_Y1)
A_WORK = area(BAR_X0, WORK_X1, WORK_Y0, WORK_Y1)
A_BACK = area(BAR_X0, WORK_X1, BACK_Y0, BACK_Y1)
A_SERVERY = A_COUNTER + A_RETURN + A_WORK + A_BACK
A_STAFFSIDE = A_WORK + A_BACK
A_WC_LOBBY = rarea(WC_LOBBY)

A_PUBLIC_NET = PUBLIC_GROSS - A_SERVERY - A_WC_LOBBY
A_LICENSED = PUBLIC_GROSS - A_STAFFSIDE - A_WC_LOBBY

A_GLASS = area(1400, 3400, BOH_Y0, BOH_Y1)
A_CELLAR = area(3500, 5700, BOH_Y0, BOH_Y1)
A_STAFF = area(5800, 7200, BOH_Y0, BOH_Y1)

_stool_area = ((len(STOOL_XS) + len(RET_STOOL_YS))
               * math.pi * (STOOL_D / 2) ** 2 / M2)
A_STAND = (rarea(STAND_1) + rarea(STAND_2) + rarea(STAND_3)
           - rarea(DRINK_RAIL)
           - len(POSEUR) * math.pi * POSEUR_R ** 2 / M2
           - len(RET_STOOL_YS) * math.pi * (STOOL_D / 2) ** 2 / M2)

OCC_ROWS = [
    ("Public drinking / seating area (net)", A_PUBLIC_NET, 1.0),
    ("Bar servery", A_SERVERY, 7.0),
    ("Glasswash / servery", A_GLASS, 7.0),
    ("Cellar / liquor store", A_CELLAR, 30.0),
    ("Staff room / BOH lobby", A_STAFF, 9.0),
]
OCC_TOTAL = sum(int(math.ceil(a / f)) for _, a, f in OCC_ROWS)
OCC_DESIGN = 60

SEATS_BAR = len(STOOL_XS) + len(RET_STOOL_YS)
SEATS_TABLE = N_BAYS * 4
SEATS_LOUNGE = 3 + 2 + 3
SEATS_TOTAL = SEATS_BAR + SEATS_TABLE + SEATS_LOUNGE
STANDING_PERSONS = int(A_STAND / 0.5)

# ==========================================================================
# 4.  DRAWING PRIMITIVES
# ==========================================================================

out: list[str] = []
RED, GRN, BLU, MAG = "#c8102e", "#00843d", "#1b4f9c", "#8e2f9c"


def add(s):
    out.append(s)


def px(x):
    return PLAN_X0 + (x + WALL) / SCALE


def py(y):
    return PLAN_Y0 - (y + WALL) / SCALE


def d(v):
    return v / SCALE


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attrs(kw):
    m = {"fill": "fill", "stroke": "stroke", "sw": "stroke-width",
         "dash": "stroke-dasharray", "op": "opacity",
         "lc": "stroke-linecap", "lj": "stroke-linejoin",
         "fo": "fill-opacity"}
    return " ".join(f'{m.get(k, k)}="{v}"' for k, v in kw.items())


def rect(x, y, w, h, **kw):
    add(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}"'
        f' {attrs(kw)}/>')


def mrect(x0, y0, x1, y1, **kw):
    rect(px(x0), py(y1), d(x1 - x0), d(y1 - y0), **kw)


def line(x1, y1, x2, y2, **kw):
    add(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}"'
        f' {attrs(kw)}/>')


def mline(x1, y1, x2, y2, **kw):
    line(px(x1), py(y1), px(x2), py(y2), **kw)


def circle(cx, cy, r, **kw):
    add(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" {attrs(kw)}/>')


def mcircle(cx, cy, r_model, **kw):
    circle(px(cx), py(cy), d(r_model), **kw)


def path(dstr, **kw):
    add(f'<path d="{dstr}" {attrs(kw)}/>')


def text(x, y, s, size=2.6, anchor="start", fill="#111", weight="normal",
         ls=0.0, rotate=None, halo=None, op=None):
    tr = f' transform="rotate({rotate} {x:.3f} {y:.3f})"' if rotate else ""
    oo = f' opacity="{op}"' if op is not None else ""
    hh = (f' stroke="{halo}" stroke-width="{size * 0.42:.2f}"'
          f' paint-order="stroke" stroke-linejoin="round"' if halo else "")
    add(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" fill="{fill}"'
        f' text-anchor="{anchor}" font-weight="{weight}"'
        f' letter-spacing="{ls}"{tr}{hh}{oo}>{esc(s)}</text>')


def mtext(mx, my_, s, **kw):
    text(px(mx), py(my_), s, **kw)


# ---- dimension lines ------------------------------------------------------

TICK = 1.5


def dim_h(x0m, x1m, ypaper, label=None, size=2.4, colour=BLU, halo=None):
    a, b = px(x0m), px(x1m)
    line(a, ypaper, b, ypaper, stroke=colour, sw=0.18)
    for xx in (a, b):
        line(xx, ypaper - TICK, xx, ypaper + TICK, stroke=colour, sw=0.35)
    lab = label if label is not None else f"{int(round(x1m - x0m))}"
    text((a + b) / 2, ypaper - 1.2, lab, size=size, anchor="middle",
         fill=colour, halo=halo)


def dim_v(y0m, y1m, xpaper, label=None, size=2.4, colour=BLU, halo=None):
    a, b = py(y0m), py(y1m)
    line(xpaper, a, xpaper, b, stroke=colour, sw=0.18)
    for yy in (a, b):
        line(xpaper - TICK, yy, xpaper + TICK, yy, stroke=colour, sw=0.35)
    lab = label if label is not None else f"{int(round(y1m - y0m))}"
    text(xpaper - 1.2, (a + b) / 2, lab, size=size, anchor="middle",
         fill=colour, rotate=-90, halo=halo)


# ---- doors ----------------------------------------------------------------

def door_swing(hinge_x, hinge_y, leaf_mm, closed_deg, sweep_deg,
               leaf_w=0.55, colour="#111"):
    """Leaf drawn in the OPEN position, arc sweeping back to CLOSED.
    Angles measured CCW from east, in model orientation."""
    r = d(leaf_mm)
    hx, hy = px(hinge_x), py(hinge_y)

    def pt(ang):
        a = math.radians(ang)
        return hx + r * math.cos(a), hy - r * math.sin(a)

    x1, y1 = pt(closed_deg)
    x2, y2 = pt(closed_deg + sweep_deg)
    path(f"M {x1:.3f} {y1:.3f} A {r:.3f} {r:.3f} 0 0 "
         f"{1 if sweep_deg > 0 else 0} {x2:.3f} {y2:.3f}",
         fill="none", stroke=colour, sw=0.16, dash="1.2,1.0")
    line(hx, hy, x2, y2, stroke=colour, sw=leaf_w, lc="round")


def opening(x0, y0, x1, y1):
    a, b = sorted((px(x0), px(x1)))
    c, e = sorted((py(y0), py(y1)))
    rect(a - 0.06, c - 0.06, b - a + 0.12, e - c + 0.12, fill="#fff",
         stroke="none")


# ---- fire-services symbols -----------------------------------------------

def sym_exit(mx, my_, arrow=None, size=5.0):
    x, y = px(mx), py(my_)
    w, h = size, size * 0.5
    rect(x - w / 2, y - h / 2, w, h, fill=GRN, stroke="#04502a", sw=0.15)
    text(x + w * 0.08, y + h * 0.20, "EXIT", size=h * 0.60, anchor="middle",
         fill="#fff", weight="bold")
    circle(x - w * 0.34, y - h * 0.12, h * 0.11, fill="#fff", stroke="none")
    path(f"M {x - w * 0.40:.2f} {y + h * 0.02:.2f} "
         f"l {w * 0.10:.2f} {h * 0.20:.2f} l {w * 0.07:.2f} {-h * 0.06:.2f}",
         fill="none", stroke="#fff", sw=0.28)
    if arrow:
        ax = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[arrow]
        sx, sy = x + ax[0] * w * 0.55, y + ax[1] * h * 0.65
        bx, by = x + ax[0] * (w * 0.55 + 2.4), y + ax[1] * (h * 0.65 + 2.4)
        line(sx, sy, bx, by, stroke=GRN, sw=0.5)
        ang = math.degrees(math.atan2(by - sy, bx - sx))
        for s in (150, -150):
            a = math.radians(ang + s)
            line(bx, by, bx + 1.3 * math.cos(a), by + 1.3 * math.sin(a),
                 stroke=GRN, sw=0.5)


def sym_el(mx, my_, r=1.6):
    x, y = px(mx), py(my_)
    circle(x, y, r, fill="#fff", stroke=GRN, sw=0.35)
    line(x - r, y, x + r, y, stroke=GRN, sw=0.35)
    line(x, y - r, x, y + r, stroke=GRN, sw=0.35)


def sym_fe(mx, my_, kind="H2O", r=2.0):
    x, y = px(mx), py(my_)
    circle(x, y, r, fill="#fff", stroke=RED, sw=0.4)
    text(x, y + 0.9, kind, size=2.0, anchor="middle", fill=RED, weight="bold")


def sym_box(mx, my_, label, w=4.8, h=3.4, colour=RED, fs=2.1):
    x, y = px(mx), py(my_)
    rect(x - w / 2, y - h / 2, w, h, fill="#fff", stroke=colour, sw=0.4)
    text(x, y + fs * 0.36, label, size=fs, anchor="middle", fill=colour,
         weight="bold")


def sym_det(mx, my_, kind="S", r=1.8):
    x, y = px(mx), py(my_)
    circle(x, y, r, fill="#fff", stroke=RED, sw=0.35)
    text(x, y + 0.78, kind, size=2.2, anchor="middle", fill=RED,
         weight="bold")


def sym_sounder(mx, my_, r=1.8):
    x, y = px(mx), py(my_)
    path(f"M {x - r:.3f} {y + r * 0.5:.3f} A {r:.3f} {r:.3f} 0 0 1 "
         f"{x + r:.3f} {y + r * 0.5:.3f} Z", fill="#fff", stroke=RED, sw=0.4)
    line(x - r * 1.3, y + r * 0.5, x + r * 1.3, y + r * 0.5, stroke=RED,
         sw=0.4)


def sym_sprk(mx, my_, r=1.25):
    x, y = px(mx), py(my_)
    circle(x, y, r, fill="#fff", stroke=BLU, sw=0.28)
    for s in (1, -1):
        line(x - r * 0.72, y - s * r * 0.72, x + r * 0.72, y + s * r * 0.72,
             stroke=BLU, sw=0.28)


# ==========================================================================
# 5.  SHEET SET-UP
# ==========================================================================

add(f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{SHEET_W}mm" height="{SHEET_H}mm" '
    f'viewBox="0 0 {SHEET_W} {SHEET_H}" '
    f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif">')

add('''<defs>
  <pattern id="hatchWall" width="1.3" height="1.3" patternTransform="rotate(45)"
           patternUnits="userSpaceOnUse">
    <line x1="0" y1="0" x2="0" y2="1.3" stroke="#2b2b2b" stroke-width="0.7"/>
  </pattern>
  <pattern id="hatchEsc" width="2.8" height="2.8" patternTransform="rotate(45)"
           patternUnits="userSpaceOnUse">
    <rect width="2.8" height="2.8" fill="#e9f7ee"/>
    <line x1="0" y1="0" x2="0" y2="2.8" stroke="#83c9a0" stroke-width="0.3"/>
  </pattern>
  <pattern id="hatchLic" width="3.6" height="3.6" patternTransform="rotate(-45)"
           patternUnits="userSpaceOnUse">
    <line x1="0" y1="0" x2="0" y2="3.6" stroke="#c088c8" stroke-width="0.3"/>
  </pattern>
  <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"
          markerHeight="5" orient="auto-start-reverse">
    <path d="M 0 1 L 10 5 L 0 9 z" fill="#00843d"/>
  </marker>
  <marker id="arwR" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"
          markerHeight="5" orient="auto-start-reverse">
    <path d="M 0 1 L 10 5 L 0 9 z" fill="#c8102e"/>
  </marker>
</defs>''')

rect(0, 0, SHEET_W, SHEET_H, fill="#ffffff")
rect(MARGIN, MARGIN, SHEET_W - 2 * MARGIN, SHEET_H - 2 * MARGIN,
     fill="none", stroke="#111", sw=0.6)
rect(MARGIN + 2, MARGIN + 2, SHEET_W - 2 * MARGIN - 4,
     SHEET_H - 2 * MARGIN - 4, fill="none", stroke="#111", sw=0.2)
line(PANEL_X - 6, MARGIN + 2, PANEL_X - 6, SHEET_H - MARGIN - 2,
     stroke="#111", sw=0.35)

text(MARGIN + 10, 33, "BAR FIT-OUT — GROUND FLOOR PLAN", size=8.0,
     weight="bold", ls=0.6)
text(MARGIN + 10, 42.5,
     "General arrangement · means of escape · fire service installations · "
     "designated liquor-consumption area", size=3.5, fill="#444")
line(MARGIN + 10, 47.5, PANEL_X - 24, 47.5, stroke="#111", sw=0.3)
text(MARGIN + 10, 55.0,
     f"Internal clear area {ROOM_W / 1000:.1f} m × {ROOM_H / 1000:.1f} m = "
     f"{ROOM_W * ROOM_H / M2:.1f} m²    ·    Scale 1:{SCALE} at A0    ·    "
     "Ground / street level    ·    All dimensions in millimetres "
     "unless noted otherwise", size=3.0, fill="#333")

# ==========================================================================
# 6.  CONTEXT BEYOND THE DEMISE
# ==========================================================================

add('<g id="context">')
BAND = 11.0
rect(px(-WALL) - 7, py(-WALL), d(ROOM_W + 2 * WALL) + 14, BAND,
     fill="#f3f3f0", stroke="none")
line(px(-WALL) - 7, py(-WALL) + BAND, px(ROOM_W + WALL) + 7,
     py(-WALL) + BAND, stroke="#aaa", sw=0.3, dash="3,2")
text(px(ROOM_W * 0.34), py(-WALL) + 7.0,
     "PUBLIC STREET — PLACE OF SAFETY (open air, ground level)",
     size=3.1, anchor="middle", fill="#555", ls=0.4)

rect(px(-WALL) - 7, py(ROOM_H + WALL) - BAND, d(ROOM_W + 2 * WALL) + 14,
     BAND, fill="#f3f3f0", stroke="none")
line(px(-WALL) - 7, py(ROOM_H + WALL) - BAND, px(ROOM_W + WALL) + 7,
     py(ROOM_H + WALL) - BAND, stroke="#aaa", sw=0.3, dash="3,2")
text(px(ROOM_W * 0.44), py(ROOM_H + WALL) - 4.2,
     "COMMON REAR CORRIDOR → PROTECTED STAIRCASE / REAR LANE — "
     "PLACE OF SAFETY", size=3.1, anchor="middle", fill="#555", ls=0.4)

for side in (-1, 1):
    xx = px(-WALL) - 7 if side < 0 else px(ROOM_W + WALL)
    rect(xx, py(ROOM_H + WALL), 7, d(ROOM_H + 2 * WALL), fill="#f3f3f0",
         stroke="none")
    text(xx + 3.5, py(ROOM_H / 2), "ADJOINING TENANCY", size=2.7,
         anchor="middle", fill="#888", rotate=-90)
add('</g>')

# ==========================================================================
# 7.  ZONE FILLS
# ==========================================================================

add('<g id="fills">')
mrect(0, 0, ROOM_W, ROOM_H, fill="#fcfcfa", stroke="none")

LIC_PATH = (
    f"M {px(0)} {py(0)} L {px(ROOM_W)} {py(0)} "
    f"L {px(ROOM_W)} {py(WC_LOBBY[2])} L {px(WC_LOBBY[0])} {py(WC_LOBBY[2])} "
    f"L {px(WC_LOBBY[0])} {py(BOH_PART_Y0)} L {px(RET_X1)} {py(BOH_PART_Y0)} "
    f"L {px(RET_X1)} {py(WORK_Y0)} L {px(BAR_X0)} {py(WORK_Y0)} "
    f"L {px(BAR_X0)} {py(BOH_PART_Y0)} L {px(0)} {py(BOH_PART_Y0)} Z"
)
path(LIC_PATH, fill="#faf1fb", stroke="none")
path(LIC_PATH, fill="url(#hatchLic)", stroke="none", op="0.55")

for z in ESCAPE_ZONES:
    mrect(z[0], z[2], z[1], z[3], fill="url(#hatchEsc)", stroke="none",
          op="0.82")

for x0, x1, key, _ in BOH_ROOMS:
    if key == "corr":
        mrect(x0, BOH_Y0, x1, BOH_Y1, fill="url(#hatchEsc)", stroke="none",
              op="0.82")
        continue
    tint = {"glass": "#eef3f7", "cellar": "#f4f1e8", "staff": "#eef3f7",
            "acc": "#e9f0f7", "wcf": "#e9f0f7", "wcm": "#e9f0f7"}[key]
    mrect(x0, BOH_Y0, x1, BOH_Y1, fill=tint, stroke="none")

mrect(BAR_X0, WORK_Y0, WORK_X1, BACK_Y1, fill="#f7f2e5", stroke="none")
add('</g>')

add('<g id="escArrows">')
for (ax, ay), (bx, by) in [
        ((3200, 2250), (5600, 2250)), ((6500, 2250), (8250, 2250)),
        ((9100, 1950), (9100, 550)),
        ((2800, 2250), (1050, 2250)), ((400, 3000), (400, 4700)),
        ((400, 5700), (400, 7300)),
        ((11300, 4550), (10050, 4550)), ((9100, 3800), (9100, 2950))]:
    line(px(ax), py(ay), px(bx), py(by), stroke=GRN, sw=0.6, op="0.85",
         **{"marker-end": "url(#arw)"})
add('</g>')

# ==========================================================================
# 8.  WALLS, OPENINGS, DOORS
# ==========================================================================

add('<g id="walls">')


def wall(x0, y0, x1, y1):
    mrect(x0, y0, x1, y1, fill="url(#hatchWall)", stroke="#111", sw=0.35)


wall(-WALL, -WALL, ROOM_W + WALL, 0)
wall(-WALL, ROOM_H, ROOM_W + WALL, ROOM_H + WALL)
wall(-WALL, 0, 0, ROOM_H)
wall(ROOM_W, 0, ROOM_W + WALL, ROOM_H)
wall(0, BOH_PART_Y0, ROOM_W, BOH_PART_Y1)
for x0, x1 in BOH_PARTS_X:
    wall(x0, BOH_Y0, x1, ROOM_H)
add('</g>')

add('<g id="openings">')
opening(EXIT1_X0, -WALL, EXIT1_X1, 0)
opening(EXIT2_X0, ROOM_H, EXIT2_X1, ROOM_H + WALL)
opening(0, BOH_PART_Y0, 1300, BOH_PART_Y1)
for a, b in (D_GLASS, D_CELLAR, D_STAFF, D_ACC, D_WCF, D_WCM):
    opening(a, BOH_PART_Y0, b, BOH_PART_Y1)
opening(1300, 6900, 1400, 7700)
opening(3400, 6300, 3500, 7100)
opening(5700, 6300, 5800, 7100)
add('</g>')

add('<g id="glazing">')
for gx0, gx1 in [(200, EXIT1_X0 - 200), (EXIT1_X1 + 200, ROOM_W - 200)]:
    opening(gx0, -WALL + 50, gx1, -50)
    mline(gx0, -55, gx1, -55, stroke="#3a6ea5", sw=0.4)
    mline(gx0, -145, gx1, -145, stroke="#3a6ea5", sw=0.4)
    for t in (gx0, gx1):
        mline(t, -50, t, -150, stroke="#111", sw=0.35)
mtext(4050, -560, "SHOPFRONT GLAZING (FIXED)", size=2.6, anchor="middle",
      fill="#3a6ea5")
add('</g>')

add('<g id="doors">')
door_swing(EXIT1_X0, -WALL / 2, 900, 0, -90)        # EXIT 1, opens south
door_swing(EXIT1_X1, -WALL / 2, 900, 180, 90)
door_swing(EXIT2_X1, ROOM_H + WALL / 2, 1150, 180, -90)   # EXIT 2, opens north
door_swing(D_GLASS[0], BOH_PART_Y1, 800, 0, 90)
door_swing(D_CELLAR[1], BOH_PART_Y1, 800, 180, -90)
door_swing(D_STAFF[0], BOH_PART_Y1, 800, 0, 90)
door_swing(D_WCF[0], BOH_PART_Y0, 800, 0, -90)
door_swing(D_WCM[0], BOH_PART_Y0, 800, 0, -90)
door_swing(1400, 6900, 800, 90, -90)                # glasswash -> corridor
door_swing(3500, 6300, 800, 90, -90)                # glasswash -> cellar
door_swing(5800, 6300, 800, 90, -90)                # cellar -> staff

mrect(D_ACC[0], BOH_PART_Y0 + 20, D_ACC[1], BOH_PART_Y0 + 70,
      fill="#fff", stroke="#111", sw=0.35)
mline(D_ACC[1], BOH_PART_Y0 + 45, D_ACC[1] + 650, BOH_PART_Y0 + 45,
      stroke="#111", sw=0.25, dash="1.2,0.8")
mtext((D_ACC[0] + D_ACC[1]) / 2, BOH_PART_Y0 - 210, "SLIDING DOOR",
      size=2.1, anchor="middle", fill="#555")

mline(BAR_X0, WORK_Y0, BAR_X0, WORK_Y1, stroke="#111", sw=0.45)
door_swing(BAR_X0, WORK_Y0, 950, 90, -90, leaf_w=0.45)
add('</g>')

# ==========================================================================
# 9.  FURNITURE AND FITTINGS
# ==========================================================================

FURN = dict(fill="#ffffff", stroke="#444", sw=0.3)
SOFT = dict(fill="#f0efe8", stroke="#444", sw=0.3)

add('<g id="furniture">')

# ---- bar ------------------------------------------------------------------
mrect(BAR_X0, CTR_Y0, BAR_X1, CTR_Y1, fill="#e5dccc", stroke="#111", sw=0.5)
mrect(RET_X0, RET_Y0, RET_X1, RET_Y1, fill="#e5dccc", stroke="#111", sw=0.5)
mline(BAR_X0, CTR_Y0 + 70, BAR_X1, CTR_Y0 + 70, stroke="#8a7f6c", sw=0.2)
mline(RET_X0 + 70, RET_Y0, RET_X0 + 70, RET_Y1, stroke="#8a7f6c", sw=0.2)

for sx0, sx1 in [(BAR_X0, D_GLASS[0]), (D_GLASS[1], D_CELLAR[0]),
                 (D_CELLAR[1], WORK_X1)]:
    if sx1 - sx0 > 50:
        mrect(sx0, BACK_Y0, sx1, BACK_Y1, fill="#dcd1bd", stroke="#111",
              sw=0.35)
        for i in range(1, 3):
            yy = BACK_Y0 + i * (BACK_Y1 - BACK_Y0) / 3
            mline(sx0, yy, sx1, yy, stroke="#a1957f", sw=0.15)

for sx in STOOL_XS:
    mcircle(sx, STOOL_Y, STOOL_D / 2, **SOFT)
for sy in RET_STOOL_YS:
    mcircle(RET_STOOL_X, sy, STOOL_D / 2, **SOFT)

# ---- banquette / table seating -------------------------------------------
mrect(BENCH[0], BENCH[2], BENCH[1], BENCH[3], fill="#eee6d8", stroke="#444",
      sw=0.35)
bay_w = (BAY_X1 - BAY_X0) / N_BAYS
for i in range(N_BAYS + 1):
    mline(BAY_X0 + bay_w * i, BENCH[2], BAY_X0 + bay_w * i, BENCH[3],
          stroke="#b3a794", sw=0.2)
for i in range(N_BAYS):
    cx = BAY_X0 + bay_w * (i + 0.5)
    mrect(cx - TBL_W / 2, TBL_Y0, cx + TBL_W / 2, TBL_Y1, **FURN)
    for s in (-1, 1):
        mrect(cx + s * 300 - CHAIR / 2, CHAIR_Y0, cx + s * 300 + CHAIR / 2,
              CHAIR_Y1, **SOFT)

# ---- standing -------------------------------------------------------------
mrect(DRINK_RAIL[0], DRINK_RAIL[2], DRINK_RAIL[1], DRINK_RAIL[3],
      fill="#eee6d8", stroke="#444", sw=0.3)
for pxm, pym in POSEUR:
    mcircle(pxm, pym, POSEUR_R, **FURN)

# ---- lounge ---------------------------------------------------------------
mrect(SOFA_A[0], SOFA_A[2], SOFA_A[1], SOFA_A[3], fill="#eee6d8",
      stroke="#444", sw=0.35)
for k in (1, 2):
    xx = SOFA_A[0] + (SOFA_A[1] - SOFA_A[0]) * k / 3
    mline(xx, SOFA_A[2], xx, SOFA_A[3], stroke="#b3a794", sw=0.2)
mrect(CTBL_A[0], CTBL_A[2], CTBL_A[1], CTBL_A[3], **FURN)
for t in TUB_A:
    mrect(t[0], t[2], t[1], t[3], **SOFT)
mrect(SOFA_B[0], SOFA_B[2], SOFA_B[1], SOFA_B[3], fill="#eee6d8",
      stroke="#444", sw=0.35)
for k in (1, 2):
    yy = SOFA_B[2] + (SOFA_B[3] - SOFA_B[2]) * k / 3
    mline(SOFA_B[0], yy, SOFA_B[1], yy, stroke="#b3a794", sw=0.2)
mrect(CTBL_B[0], CTBL_B[2], CTBL_B[1], CTBL_B[3], **FURN)

# ---- back of house --------------------------------------------------------
mrect(1500, 6300, 3300, 6800, fill="#e5eaf0", stroke="#444", sw=0.3)
mtext(2400, 6480, "GLASSWASHER + DOUBLE SINK", size=2.0, anchor="middle",
      fill="#555")
mrect(2600, 7100, 3300, 7500, fill="#e5eaf0", stroke="#444", sw=0.3)
mtext(2950, 7260, "WHB", size=2.0, anchor="middle", fill="#555")

mrect(4400, 6300, 5600, 7700, fill="none", stroke="#444", sw=0.3,
      dash="1.6,1.0")
mtext(5000, 7150, "KEG /", size=2.0, anchor="middle", fill="#666")
mtext(5000, 6920, "BOTTLE", size=2.0, anchor="middle", fill="#666")
mtext(5000, 6690, "RACKING", size=2.0, anchor="middle", fill="#666")
mrect(3550, 7200, 4250, 7700, fill="none", stroke="#444", sw=0.3,
      dash="1.6,1.0")
mtext(3900, 7530, "SPIRIT", size=1.95, anchor="middle", fill="#666")
mtext(3900, 7320, "STORE", size=1.95, anchor="middle", fill="#666")

mrect(6300, 7150, 7100, 7650, fill="#e5eaf0", stroke="#444", sw=0.3)
mtext(6700, 7370, "LOCKERS", size=2.0, anchor="middle", fill="#555")


def wc_pan(cx, cy, w=380, dp=620):
    mrect(cx - w / 2, cy - dp / 2, cx + w / 2, cy + dp / 2, **FURN)
    mcircle(cx, cy + dp * 0.10, w * 0.40, **FURN)


def whb(cx, cy, w=520, dp=420):
    mrect(cx - w / 2, cy - dp / 2, cx + w / 2, cy + dp / 2, **FURN)


mcircle(8150, 6520, 750, fill="none", stroke=BLU, sw=0.32, dash="2.2,1.8")
mtext(8150, 6470, "Ø1500", size=2.2, anchor="middle", fill=BLU)
wc_pan(7660, 7600)
mline(7400, 7290, 7400, 7910, stroke=BLU, sw=0.5)
mline(7480, 7940, 8080, 7940, stroke=BLU, sw=0.5)
whb(9000, 7760, 560, 420)

wc_pan(9760, 7560)
whb(10330, 7710, 480, 400)

wc_pan(11020, 7560)
mrect(11450, 7550, 11880, 7900, **FURN)
mtext(11665, 7420, "URINAL", size=1.95, anchor="middle", fill="#555")
whb(11250, 6600, 480, 400)
add('</g>')

# ==========================================================================
# 10.  ZONE LABELS
# ==========================================================================

add('<g id="labels">')


def zlabel(mx, my_, lines, size=3.2, sub=None, colour="#111", subsize=2.4,
           subcol="#555", rotate=None, halo="#ffffff"):
    x, y = px(mx), py(my_)
    for i, ln in enumerate(lines):
        text(x, y + i * (size + 0.9), ln, size=size, anchor="middle",
             fill=colour, weight="bold", ls=0.4, rotate=rotate, halo=halo)
    if sub:
        yy = y + len(lines) * (size + 0.9) + 0.4
        for j, s in enumerate(sub):
            text(x, yy + j * (subsize + 0.7), s, size=subsize,
                 anchor="middle", fill=subcol, rotate=rotate, halo=halo)


zlabel(3350, 4780, ["BAR SERVERY — STAFF ONLY"], size=3.0,
       sub=["1000 clear working zone (900 min. required)"], subsize=2.3)
zlabel(3650, 3900, ["FRONT BAR COUNTER"], size=2.9,
       sub=["4500 run + 1350 return  ·  under-counter coolers, ice well "
            "and glasswasher  ·  9 bar stools"], subsize=2.1)
zlabel(4200, 1900, ["TABLE SEATING ZONE"], size=3.4,
       sub=["4 banquette bays  ·  16 seats"], subsize=2.5)
zlabel(7550, 1000, ["STANDING"], size=2.9, sub=["+ drink rail"],
       subsize=2.2)
zlabel(7250, 3900, ["STANDING AREA"], size=2.9,
       sub=["2 poseur tables"], subsize=2.2)
zlabel(11050, 2100, ["LOUNGE SEATING"], size=3.2, sub=["8 seats"], subsize=2.5)
zlabel(9200, 1050, ["MAIN ENTRANCE"], size=2.8, colour="#0d5c33")
zlabel(1050, 3800, ["ESCAPE ROUTE — 1400 CLEAR"], size=2.5,
       colour="#0d5c33", rotate=-90)
zlabel(9550, 4250, ["TOILET LOBBY — 1400 CLEAR"], size=2.6,
       colour="#0d5c33")
zlabel(2000, 4250, ["BAR GATE"], size=2.3, colour="#333")

# back-of-house room names, set low in each room and clear of the fittings
BOH_LABEL_POS = {"glass": 2200, "cellar": 4000, "staff": 6800,
                 "acc": 8300, "wcf": 10000, "wcm": 11350}
for x0, x1, key, lines in BOH_ROOMS:
    if key == "corr":
        zlabel(1050, 6500, lines, size=2.6, colour="#0d5c33", rotate=-90)
        continue
    zlabel(BOH_LABEL_POS[key], 5820, lines, size=2.8)
add('</g>')

# ==========================================================================
# 11.  FIRE SERVICE INSTALLATIONS
# ==========================================================================

add('<g id="fsi">')
N_SPRK = 0
for sx in (1500, 4500, 7500, 10500):
    for sy in (1350, 4050, 6750):
        sym_sprk(sx, sy)
        N_SPRK += 1

DETECTORS = [(2600, 1000, "S"), (6950, 450, "S"), (10900, 1200, "S"),
             (3300, 2500, "S"), (6900, 4600, "S"), (10800, 3300, "S"),
             (250, 6800, "S"), (2400, 7800, "H"), (4700, 6100, "S"),
             (6800, 6600, "S"), (3400, 4550, "H"), (8800, 6300, "S")]
for dx, dy, k in DETECTORS:
    sym_det(dx, dy, k)

ELS = [(200, 800), (200, 3900), (200, 5200), (1050, 7100), (2500, 1900),
       (5000, 1900), (7600, 1900), (8650, 1300), (9450, 3300), (8100, 4550),
       (11750, 4250), (1650, 6150), (3800, 6150), (6100, 6150),
       (7800, 7300), (10000, 6900), (11450, 7100)]
for ex, ey in ELS:
    sym_el(ex, ey)

EXIT_SIGNS = [(9200, 480, None), (9200, -620, None), (650, 7800, None),
              (1000, 5150, "N"), (2000, 2650, "W"), (7000, 2650, "E"),
              (9100, 4400, "S"), (11620, 4550, "W")]
for sx, sy, ar in EXIT_SIGNS:
    sym_exit(sx, sy, arrow=ar)

sym_box(8500, 520, "MCP")
sym_box(250, 7500, "MCP")
sym_sounder(8500, 1150)
sym_sounder(1050, 7500)

sym_fe(8500, 870, "H₂O")
sym_fe(250, 6200, "H₂O")
sym_fe(1750, 4500, "CO₂")
sym_fe(2900, 6150, "CO₂")
sym_box(3200, 5750, "F.B.", w=4.4, h=3.2)

sym_box(10600, 8330, "HR", w=4.4, h=3.2)
mtext(10950, 8330, "EXISTING HOSE REEL (BY OTHERS)", size=2.3, fill=RED)
add('</g>')

# ==========================================================================
# 12.  ESCAPE ANNOTATION
# ==========================================================================

# remoteness check line
E1C = (( EXIT1_X0 + EXIT1_X1) / 2, -WALL)
E2C = ((EXIT2_X0 + EXIT2_X1) / 2, ROOM_H + WALL)
add('<g id="remote">')
mline(E1C[0], E1C[1], E2C[0], E2C[1], stroke=BLU, sw=0.35, dash="4,3",
      op="0.42")
for pt_ in (E1C, E2C):
    mcircle(pt_[0], pt_[1], 90, fill="#fff", stroke=BLU, sw=0.4)
_ang = math.degrees(math.atan2(py(E2C[1]) - py(E1C[1]),
                               px(E2C[0]) - px(E1C[0]))) + 180
_t = 0.215
_lp = (E1C[0] + _t * (E2C[0] - E1C[0]), E1C[1] + _t * (E2C[1] - E1C[1]))
text(px(_lp[0]), py(_lp[1]),
     f"EXITS {EXIT_SEPARATION:.1f} m APART  >  ½ DIAGONAL "
     f"{HALF_DIAGONAL:.1f} m", size=2.6, anchor="middle", fill=BLU,
     weight="bold", rotate=_ang, halo="#ffffff")
add('</g>')

add('<g id="escNotes">')


def callout(mx, my_, tx, ty, lines, colour=GRN, size=2.6, anchor="start"):
    x1, y1 = px(mx), py(my_)
    x2, y2 = px(tx), py(ty)
    line(x1, y1, x2, y2, stroke=colour, sw=0.28)
    circle(x1, y1, 0.8, fill=colour, stroke="none")
    w = max(len(s) for s in lines) * size * 0.52 + 4
    h = len(lines) * (size + 1.1) + 2.0
    ox = 0 if anchor == "start" else -w
    rect(x2 + ox, y2 - h + 2.0, w, h, fill="#ffffff", stroke=colour, sw=0.3,
         fo="0.95")
    for i, s in enumerate(lines):
        text(x2 + ox + 2, y2 - h + 2.0 + (i + 1) * (size + 1.1) - 1.3, s,
             size=size, fill="#123", weight="bold" if i == 0 else "normal")


callout(9850, -200, 10380, -580,
        ["EXIT 1 — FINAL EXIT TO STREET",
         "1800 opening · 2 No. 900 leaves · 1700 clear.",
         "Opens outward in the direction of escape.",
         "Panic bolt — openable from inside without a key."])
callout(650, 8200, 1450, 8800,
        ["EXIT 2 — FINAL EXIT TO REAR COMMON CORRIDOR",
         "1200 opening · 1130 clear leaf · FRD −/60/30 self-closing.",
         "Opens outward in the direction of escape. Lever handle "
         "inside — no key."])
add('</g>')

add('<g id="sectionMark">')
for stub0, stub1, arrow_y, tag_y in [(8210, 8020, 8110, 8420),
                                     (-210, -20, -110, -420)]:
    mline(9100, stub0, 9100, stub1, stroke="#111", sw=0.55, dash="7,2,1.6,2")
    mline(9100, arrow_y, 8720, arrow_y, stroke="#111", sw=0.55)
    _ax, _ay = px(8720), py(arrow_y)
    path(f"M {_ax:.2f} {_ay:.2f} l 3.0 -1.7 l 0 3.4 z", fill="#111",
         stroke="none")
    mcircle(9100, tag_y, 185, fill="#fff", stroke="#111", sw=0.55)
    mtext(9100, tag_y - 95, "A", size=3.0, anchor="middle", weight="bold")
add('</g>')

add('<g id="travel">')


def travel(points, label, lx, ly, colour=RED, rot=None):
    pts = " ".join(f"{px(x):.3f},{py(y):.3f}" for x, y in points)
    add(f'<polyline points="{pts}" fill="none" stroke="{colour}" '
        f'stroke-width="0.55" stroke-dasharray="3.4,2.0" '
        f'marker-end="url(#arwR)"/>')
    circle(px(points[0][0]), py(points[0][1]), 1.1, fill=colour,
           stroke="#fff", sw=0.35)
    if label:
        text(px(lx), py(ly), label, size=2.6, fill=colour, weight="bold",
             anchor="middle", halo="#ffffff", rotate=rot)


travel([(5950, 5250), (5950, 2250), (9100, 2250), (9100, -100)],
       f"TD-1   {TRAVEL_MAX} m", 7550, 2560)
travel([(150, 150), (150, 2250), (700, 2250), (700, 8100)],
       "TD-2   7.9 m", 430, 1150, rot=-90)
travel([(11900, 4950), (9100, 4950), (9100, 2900)], "TD-3   7.5 m",
       10700, 5120)
add('</g>')

# ==========================================================================
# 13.  DIMENSIONS
# ==========================================================================

add('<g id="dims">')
Y_D1, Y_D2, Y_D3 = py(-WALL) + 27, py(-WALL) + 36, py(-WALL) + 45
Y_T1, Y_T2 = py(ROOM_H + WALL) - 24, py(ROOM_H + WALL) - 33
X_R1, X_R2 = px(ROOM_W + WALL) + 19, px(ROOM_W + WALL) + 28
X_L1, X_L2 = px(-WALL) - 19, px(-WALL) - 28

for a, b in [(0, EXIT1_X0), (EXIT1_X0, EXIT1_X1), (EXIT1_X1, ROOM_W)]:
    dim_h(a, b, Y_D1, size=2.3)
dim_h(0, ROOM_W, Y_D2, f"{ROOM_W}  INTERNAL CLEAR")
dim_h(-WALL, ROOM_W + WALL, Y_D3, f"{ROOM_W + 2 * WALL}  OVERALL")

for x0, x1, _, _ in BOH_ROOMS:
    dim_h(x0, x1, Y_T1, size=2.2)
dim_h(EXIT2_X0, EXIT2_X1, Y_T2, "1200")

dim_v(0, BOH_PART_Y0, X_R1, f"{BOH_PART_Y0}")
dim_v(BOH_Y0, ROOM_H, X_R1, f"{ROOM_H - BOH_Y0}")
dim_v(0, ROOM_H, X_R2, f"{ROOM_H}  INTERNAL CLEAR")

dim_v(0, CHAIR_Y1, X_L1, "1650")
dim_v(SPINE_A[2], SPINE_A[3], X_L1, "1200")
dim_v(CTR_Y0, CTR_Y1, X_L1, "600")
dim_v(WORK_Y0, WORK_Y1, X_L1, "1000")
dim_v(BACK_Y0, BACK_Y1, X_L1, "350")
dim_v(-WALL, ROOM_H + WALL, X_L2, f"{ROOM_H + 2 * WALL}  OVERALL")

# in-plan clear widths
dim_h(0, 1400, py(2150), "1400 CLEAR", size=2.2, halo="#ffffff")
dim_h(0, 1300, py(5800), "1300 CLEAR", size=2.2, halo="#ffffff")
dim_h(SPINE_C[0], SPINE_C[1], py(3650), "1200", size=2.2, halo="#ffffff")
dim_v(SPINE_A[2], SPINE_A[3], px(8150), "1200 CLEAR", size=2.2,
      halo="#ffffff")
dim_v(WC_LOBBY[2], WC_LOBBY[3], px(11700), "1400", size=2.2, halo="#ffffff")
dim_v(WORK_Y0, WORK_Y1, px(4750), "1000 CLEAR", size=2.2, halo="#ffffff")
dim_h(EXIT1_X0, EXIT1_X1, py(700), "1800 (1700 CLEAR)", size=2.2,
      halo="#ffffff")
add('</g>')

# ==========================================================================
# 14.  LICENSED-AREA BOUNDARY
# ==========================================================================

add('<g id="licence">')
path(LIC_PATH, fill="none", stroke=MAG, sw=1.0, dash="8,2.4,1.8,2.4")
mtext(3000, 2450, "DESIGNATED LIQUOR-CONSUMPTION AREA", size=3.3,
      anchor="middle", fill=MAG, weight="bold", ls=0.5, halo="#ffffff")
mtext(3000, 2080,
      f"{A_LICENSED:.1f} m²   ·   {SEATS_TOTAL} seats + "
      f"{STANDING_PERSONS} standing", size=2.7, anchor="middle", fill=MAG,
      halo="#ffffff")
mrect(-WALL, -WALL, ROOM_W + WALL, ROOM_H + WALL, fill="none", stroke=MAG,
      sw=0.55, dash="5,1.8,1.2,1.8", op="0.6")
add('</g>')

# ==========================================================================
# 15.  TABLES AND NOTES
# ==========================================================================


def block_title(x, y, t, w):
    rect(x, y - 5.6, w, 7.2, fill="#1f1f1f", stroke="none")
    text(x + 2.6, y, t, size=3.4, fill="#fff", weight="bold", ls=0.5)


def rows(x, y0, data, widths, w, size=2.75, lh=5.0, head=None):
    y = y0
    if head:
        for i, h in enumerate(head):
            cx = x + sum(widths[:i])
            al = "start" if i == 0 else "end"
            ax = cx + 1.6 if i == 0 else cx + widths[i] - 1.6
            text(ax, y, h, size=size - 0.2, weight="bold", fill="#333",
                 anchor=al)
        y += 1.8
        line(x, y, x + w, y, stroke="#999", sw=0.3)
        y += lh - 1.2
    for r in data:
        bold = r[0].startswith("*")
        cells = [c.lstrip("*") for c in r]
        if bold:
            line(x, y - lh + 1.7, x + w, y - lh + 1.7, stroke="#999", sw=0.3)
        for i, c in enumerate(cells):
            if not c:
                continue
            cx = x + sum(widths[:i])
            al = "start" if i == 0 else "end"
            ax = cx + 1.6 if i == 0 else cx + widths[i] - 1.6
            text(ax, y, c, size=size, anchor=al,
                 weight="bold" if bold else "normal",
                 fill="#111" if bold else "#222")
        y += lh
    return y


def para(x, y, body, w_chars, size=2.75, lh=4.0, indent=""):
    lines = textwrap.wrap(body, w_chars)
    for i, ln in enumerate(lines):
        text(x + (0 if i == 0 else len(indent) * size * 0.52), y, ln,
             size=size, fill="#222")
        y += lh
    return y


TOP = 590.0
COL1, COL2, COL3 = 22.0, 270.0, 518.0
CW = 232.0
CW3 = 228.0

# ---- occupant capacity ----------------------------------------------------
block_title(COL1, TOP, "OCCUPANT CAPACITY  —  CoP FIRE SAFETY IN BUILDINGS "
            "2011, TABLE B1 METHOD", CW)
occ = [[n, f"{a:.2f}", f"{f:g}", str(int(math.ceil(a / f)))]
       for n, a, f in OCC_ROWS]
occ += [["*TOTAL CALCULATED OCCUPANT CAPACITY", "", "", f"*{OCC_TOTAL}"],
        ["Exit provision designed for", "", "", f"{OCC_DESIGN}"]]
y = rows(COL1, TOP + 9, occ, [130, 36, 28, 38], CW,
         head=["Accommodation", "Area m²", "m²/p", "Persons"])
y = para(COL1 + 1.6, y + 1.2,
         "Toilets, the escape corridor and the toilet lobby are not counted "
         "as separate accommodation.", 78, size=2.4, lh=3.4)

# ---- seating --------------------------------------------------------------
block_title(COL1, y + 11, "SEATING AND STANDING SCHEDULE", CW)
seat = [
    ["Bar stools at counter (7 run + 2 return)", "", "", f"{SEATS_BAR}"],
    ["Table seating — 4 banquette bays × 4", "", "", f"{SEATS_TABLE}"],
    ["Lounge seating — 2 clusters", "", "", f"{SEATS_LOUNGE}"],
    ["*TOTAL SEATS", "", "", f"*{SEATS_TOTAL}"],
    [f"Standing area {A_STAND:.1f} m² net @ 0.5 m²/person", "", "",
     f"{STANDING_PERSONS}"],
    ["*TOTAL GUESTS (seated + standing)", "", "",
     f"*{SEATS_TOTAL + STANDING_PERSONS}"],
    ["Staff on duty (assumed)", "", "", "5"],
    ["*TOTAL DESIGN POPULATION", "", "",
     f"*{SEATS_TOTAL + STANDING_PERSONS + 5}"],
]
y = rows(COL1, y + 20, seat, [130, 36, 28, 38], CW)
y = para(COL1 + 1.6, y + 1.2,
         f"Designated liquor-consumption area = {A_LICENSED:.1f} m² "
         f"(hatched magenta). Licensed premises = the whole tenancy, "
         f"{ROOM_W * ROOM_H / M2:.1f} m² internal.", 78, size=2.4, lh=3.4)

# ---- key clear dimensions -------------------------------------------------
block_title(COL1, y + 11, "KEY CLEAR DIMENSIONS", CW)
kd = [
    ["Bartender working zone", "1000", "900 min"],
    ["Protected escape corridor", "1300", "1050 min"],
    ["Circulation spine A and C", "1200", "1050 min"],
    ["West escape route to EXIT 2", "1400", "1050 min"],
    ["Toilet lobby", "1400", "1050 min"],
    ["EXIT 1 clear door opening", "1700", "750 min"],
    ["EXIT 2 clear door opening", "1130", "750 min"],
    ["Accessible WC turning circle", "Ø1500", "DM:BFA 2008"],
    ["Clear headroom to escape routes", f"{HEADROOM}", "2000 min"],
]
rows(COL1, y + 20, kd, [128, 44, 60], CW)

# ---- means of escape ------------------------------------------------------
block_title(COL2, TOP, "MEANS OF ESCAPE — COMPLIANCE CHECK", CW)
moe = [
    ["Number of exits", "2", "2", "OK"],
    ["Separation of exits", "remote", f"{EXIT_SEPARATION:.1f} m", "OK"],
    ["  — against ½ diagonal of unit", f"{HALF_DIAGONAL:.1f} m",
     f"{EXIT_SEPARATION:.1f} m", "OK"],
    ["Exit route clear width", "1050", "1200 – 1400", "OK"],
    ["EXIT 1 clear door width", "750", f"{EXIT1_CLEAR}", "OK"],
    ["EXIT 2 clear door width", "750", f"{EXIT2_CLEAR}", "OK"],
    ["Aggregate clear exit width", "1050", f"{EXIT1_CLEAR + EXIT2_CLEAR}",
     "OK"],
    ["Widest exit discounted", "1050", f"{EXIT2_CLEAR}", "OK"],
    ["Longest travel distance", "24 m", f"{TRAVEL_MAX} m", "OK"],
    ["Longest single-direction travel", "18 m", f"{TRAVEL_DEADEND} m", "OK"],
    ["Headroom on escape routes", "2000", f"{HEADROOM}", "OK"],
    ["Doors open in escape direction", "required", "both exits", "OK"],
    ["Openable from inside, no key", "required", "panic / lever", "OK"],
    ["Escape routes free of furniture", "required", "hatched green", "OK"],
]
y2 = rows(COL2, TOP + 9, moe, [92, 42, 52, 46], CW,
          head=["Item", "Required", "Provided", ""], size=2.7, lh=4.7)
y2 = para(COL2 + 1.6, y2 + 1.2,
          "\"Required\" figures are the design targets set in the brief "
          "together with the values normally applied to this use class. "
          "The governing table and the sprinklered / unsprinklered basis "
          "must be confirmed by the Authorized Person before submission.",
          80, size=2.4, lh=3.4)

# ---- FSI schedule ---------------------------------------------------------
block_title(COL2, y2 + 11, "FIRE SERVICE INSTALLATIONS — SCHEDULE", CW)
n_exit = len(EXIT_SIGNS)
n_el = len(ELS)
n_sd = sum(1 for *_, k in DETECTORS if k == "S")
n_hd = sum(1 for *_, k in DETECTORS if k == "H")
fsi = [
    ["Illuminated exit signs (incl. directional)", "", f"{n_exit}"],
    ["Emergency light fittings, 2 hour duration", "", f"{n_el}"],
    ["Portable extinguisher — water 9 L", "", "2"],
    ["Portable extinguisher — CO₂ 2 kg", "", "2"],
    ["Fire blanket — glasswash", "", "1"],
    ["Manual call point — one at each exit", "", "2"],
    ["Alarm sounder", "", "2"],
    ["Smoke detector", "", f"{n_sd}"],
    ["Heat detector — glasswash, back bar", "", f"{n_hd}"],
    ["Sprinkler head (indicative, OH Group 1)", "", f"{N_SPRK}"],
    ["Hose reel — existing, common corridor", "", "by others"],
]
y2 = rows(COL2, y2 + 20, fsi, [150, 30, 52], CW, size=2.7, lh=4.7)
y2 = para(COL2 + 1.6, y2 + 1.2,
          "Maximum travel distance to a portable extinguisher on any part "
          "of the premises is 10.5 m.", 80, size=2.4, lh=3.4)

# ---- exit capacity --------------------------------------------------------
block_title(COL3, TOP, "EXIT AND ESCAPE ROUTE SCHEDULE", CW3)
exs = [
    ["EXIT 1 — main entrance", "1700", "Public street"],
    ["   via spine A + spine C", "1200", ""],
    ["EXIT 2 — rear final exit", "1130", "Rear common corridor"],
    ["   via spine B + protected corridor", "1300", ""],
    ["*Aggregate clear exit width", f"*{EXIT1_CLEAR + EXIT2_CLEAR}", ""],
    ["*Least favourable (widest discounted)", f"*{EXIT2_CLEAR}", ""],
    [f"Required for {OCC_DESIGN} persons", "1050", ""],
]
y3 = rows(COL3, TOP + 9, exs, [128, 34, 66], CW3, size=2.7, lh=4.8,
          head=["Exit / route", "Clear", "Discharges to"])

# ---- fire resisting construction -----------------------------------------
block_title(COL3, y3 + 11, "FIRE RESISTING CONSTRUCTION AND FINISHES", CW3)
frc = [
    ["Escape corridor enclosure", "FRR −/60/60"],
    ["Doors onto escape corridor", "FRD −/60/30, self-closing"],
    ["Cellar / liquor store enclosure", "FRR −/60/60"],
    ["Cellar door", "FRD −/60/30, self-closing"],
    ["Tenancy separation to common areas", "as building, min. −/60/60"],
    ["Surface finishes on escape routes", "Class 1 spread of flame"],
    ["Fixed seating and upholstery", "low flammability, FSD approved"],
]
y3 = rows(COL3, y3 + 20, frc, [110, 118], CW3, size=2.7, lh=4.8)

# ---- travel distance schedule --------------------------------------------
block_title(COL2, y2 + 11, "TRAVEL DISTANCE SCHEDULE", CW)
td = [
    ["TD-1   Standing area NW corner → spine A → spine C", "EXIT 1",
     f"{TRAVEL_MAX} m"],
    ["TD-2   Public room SW corner → spine B → corridor", "EXIT 2", "7.9 m"],
    ["TD-3   Toilet lobby east end → spine C", "EXIT 1", "7.5 m"],
    ["*Longest single-direction (dead-end) travel", "",
     f"*{TRAVEL_DEADEND} m"],
]
rows(COL2, y2 + 20, td, [148, 38, 46], CW, size=2.7, lh=4.7,
     head=["Ref · from · route", "To", "Distance"])

# ---- sanitary fitments ----------------------------------------------------
block_title(COL3, y3 + 11, "SANITARY FITMENT SCHEDULE", CW3)
san = [
    ["WC — female", "1"],
    ["WC — male", "1"],
    ["Urinal — male", "1"],
    ["Accessible unisex WC — counts for both sexes", "1"],
    ["Wash hand basin — public", "3"],
    ["Wash hand basin — staff, glasswash", "1"],
    ["Cleaner's sink — to be confirmed", "—"],
]
y3 = rows(COL3, y3 + 20, san, [180, 48], CW3, size=2.7, lh=4.6)
y3 = para(COL3 + 1.6, y3 + 1.2,
          "Fitment numbers to be verified against Cap. 123I for the "
          "assessed occupant capacity.", 76, size=2.4, lh=3.4)

# ---- assumptions ----------------------------------------------------------
block_title(COL3, y3 + 11, "ASSUMPTIONS AND EXCLUSIONS", CW3)
ay = y3 + 19
for a in [
    "Rectangular ground-floor tenancy, 12.0 × 8.0 m internal, single "
    "storey, no basement or mezzanine.",
    "Street frontage to the south; a common rear corridor leading to a "
    "protected staircase to the north. Both are places of safety.",
    "Building assumed sprinkler protected. Structural grid, services "
    "risers and any existing columns are not shown.",
    "No cooking. Drinks only, with cold pre-packed food if any. A kitchen "
    "would change both the licence and the FSI requirements.",
    "No live entertainment, dancing or amplified performance.",
]:
    ay = para(COL3 + 1.6, ay, "•  " + a, 76, size=2.55, lh=3.7) + 1.0

# ==========================================================================
# 16.  RIGHT PANEL
# ==========================================================================

PX0 = PANEL_X + 4
PW = SHEET_W - MARGIN - 4 - PX0

# ---- north arrow ----------------------------------------------------------
nax, nay, nar = PX0 + 36, 66, 27
circle(nax, nay, nar, fill="#fff", stroke="#111", sw=0.45)
circle(nax, nay, nar - 3.5, fill="none", stroke="#111", sw=0.15)
path(f"M {nax:.2f} {nay - nar + 4:.2f} L {nax + 7.5:.2f} {nay + 11:.2f} "
     f"L {nax:.2f} {nay + 4.5:.2f} Z", fill="#111", stroke="none")
path(f"M {nax:.2f} {nay - nar + 4:.2f} L {nax - 7.5:.2f} {nay + 11:.2f} "
     f"L {nax:.2f} {nay + 4.5:.2f} Z", fill="#fff", stroke="#111", sw=0.4)
text(nax, nay + 21.5, "N", size=7.0, anchor="middle", weight="bold")
text(nax, nay + nar + 9, "NORTH", size=2.8, anchor="middle", fill="#555",
     ls=0.8)

# ---- scale bar ------------------------------------------------------------
sbx, sby = PX0 + 96, 52
seg = 1000.0 / SCALE
text(sbx, sby - 7, f"SCALE  1:{SCALE}  at A0 (1189 × 841 mm)", size=3.4,
     weight="bold")
for i in range(5):
    rect(sbx + i * seg, sby, seg, 5.5, fill="#111" if i % 2 == 0 else "#fff",
         stroke="#111", sw=0.3)
for i in range(6):
    text(sbx + i * seg, sby + 11, f"{i}", size=2.9, anchor="middle")
text(sbx + 5 * seg + 5, sby + 11, "metres", size=2.9)
rect(sbx, sby + 18, seg / 2, 3.6, fill="#111", stroke="#111", sw=0.25)
rect(sbx + seg / 2, sby + 18, seg / 2, 3.6, fill="#fff", stroke="#111",
     sw=0.25)
text(sbx + seg + 4, sby + 21, "500 mm divisions", size=2.5, fill="#555")
text(sbx, sby + 30, "Drawn to scale. Verify all dimensions on site before "
     "any work.", size=2.5, fill="#777")

line(PX0, 108, PX0 + PW, 108, stroke="#111", sw=0.3)

# ---- legend ---------------------------------------------------------------
block_title(PX0, 122, "LEGEND", PW)


def legend_swatch(x, y, kind):
    if kind == "wall":
        rect(x, y - 3.5, 9.5, 4.6, fill="url(#hatchWall)", stroke="#111",
             sw=0.3)
    elif kind == "esc":
        rect(x, y - 3.5, 9.5, 4.6, fill="url(#hatchEsc)", stroke="#83c9a0",
             sw=0.3)
    elif kind == "lic":
        rect(x, y - 3.5, 9.5, 4.6, fill="#faf1fb", stroke="none")
        rect(x, y - 3.5, 9.5, 4.6, fill="url(#hatchLic)", stroke=MAG, sw=0.5)
    elif kind == "bar":
        rect(x, y - 3.5, 9.5, 4.6, fill="#e5dccc", stroke="#111", sw=0.4)
    elif kind == "staff":
        rect(x, y - 3.5, 9.5, 4.6, fill="#f7f2e5", stroke="#999", sw=0.3)
    elif kind == "soft":
        rect(x, y - 3.5, 9.5, 4.6, fill="#eee6d8", stroke="#444", sw=0.3)
    elif kind == "td":
        line(x, y - 1.3, x + 9.5, y - 1.3, stroke=RED, sw=0.55,
             dash="3.4,2.0")
    elif kind == "arrow":
        line(x, y - 1.3, x + 8.5, y - 1.3, stroke=GRN, sw=0.6,
             **{"marker-end": "url(#arw)"})
    elif kind == "remote":
        line(x, y - 1.3, x + 9.5, y - 1.3, stroke=BLU, sw=0.4, dash="4,2.5")
    elif kind == "dim":
        line(x, y - 1.3, x + 9.5, y - 1.3, stroke=BLU, sw=0.18)
        for xx in (x, x + 9.5):
            line(xx, y - 2.7, xx, y + 0.1, stroke=BLU, sw=0.35)


def draw_sym_at(x, y, kind):
    global PLAN_X0, PLAN_Y0
    ox, oy = PLAN_X0, PLAN_Y0
    PLAN_X0, PLAN_Y0 = x - WALL / SCALE, y + WALL / SCALE
    try:
        {"exit": lambda: sym_exit(0, 0),
         "exitd": lambda: sym_exit(0, 0, arrow="E"),
         "el": lambda: sym_el(0, 0),
         "feh": lambda: sym_fe(0, 0, "H₂O"),
         "fec": lambda: sym_fe(0, 0, "CO₂"),
         "fb": lambda: sym_box(0, 0, "F.B.", w=4.4, h=3.2),
         "mcp": lambda: sym_box(0, 0, "MCP"),
         "snd": lambda: sym_sounder(0, 0),
         "sd": lambda: sym_det(0, 0, "S"),
         "hd": lambda: sym_det(0, 0, "H"),
         "sp": lambda: sym_sprk(0, 0),
         "hr": lambda: sym_box(0, 0, "HR", w=4.4, h=3.2)}[kind]()
    finally:
        PLAN_X0, PLAN_Y0 = ox, oy


ly = 132.0
for kind, lab in [
        ("wall", "Wall / partition"),
        ("bar", "Bar counter and joinery"),
        ("staff", "Bar servery — staff only"),
        ("soft", "Fixed / soft seating"),
        ("esc", "Means of escape route — kept clear"),
        ("arrow", "Direction of escape"),
        ("td", "Travel distance to the nearest exit"),
        ("remote", "Exit remoteness check"),
        ("lic", "Designated liquor-consumption area"),
        ("dim", "Dimension line (millimetres)")]:
    legend_swatch(PX0 + 3, ly, kind)
    text(PX0 + 17, ly, lab, size=2.9, fill="#222")
    ly += 6.6

ly2 = 132.0
for kind, lab in [
        ("exit", "Illuminated exit sign"),
        ("exitd", "Illuminated directional exit sign"),
        ("el", "Emergency light fitting, 2 h"),
        ("feh", "Portable extinguisher — water 9 L"),
        ("fec", "Portable extinguisher — CO₂ 2 kg"),
        ("fb", "Fire blanket"),
        ("mcp", "Manual call point"),
        ("snd", "Alarm sounder"),
        ("sd", "Smoke detector"),
        ("hd", "Heat detector"),
        ("sp", "Sprinkler head (indicative)"),
        ("hr", "Hose reel — existing, by others")]:
    draw_sym_at(PX0 + PW / 2 + 8, ly2 - 1.0, kind)
    text(PX0 + PW / 2 + 17, ly2, lab, size=2.9, fill="#222")
    ly2 += 6.6

LEG_BOT = max(ly, ly2) + 1
line(PX0, LEG_BOT, PX0 + PW, LEG_BOT, stroke="#111", sw=0.3)

# ---- key figures ----------------------------------------------------------
block_title(PX0, LEG_BOT + 13, "KEY FIGURES", PW)
TILE_Y = LEG_BOT + 18
TILE_H = 26.0
TILE_W = (PW - 3 * 4) / 4
for i, (big, small) in enumerate([
        (f"{OCC_TOTAL}", "OCCUPANT CAPACITY (PERSONS)"),
        (f"{SEATS_TOTAL} + {STANDING_PERSONS}", "SEATS + STANDING"),
        (f"{TRAVEL_MAX} m", "LONGEST TRAVEL DISTANCE"),
        (f"{A_LICENSED:.1f} m²", "LICENSED DRINKING AREA")]):
    tx = PX0 + i * (TILE_W + 4)
    rect(tx, TILE_Y, TILE_W, TILE_H, fill="#f4f4f1", stroke="#bbb", sw=0.3)
    text(tx + TILE_W / 2, TILE_Y + 13.5, big, size=9.0, anchor="middle",
         weight="bold", fill="#111")
    text(tx + TILE_W / 2, TILE_Y + 21, small, size=2.5, anchor="middle",
         fill="#555", ls=0.3)

# ---- section A-A through the escape route ---------------------------------
SEC_SCALE = 25
SEC_TOP = TILE_Y + TILE_H + 13
block_title(PX0, SEC_TOP, "SECTION A–A THROUGH THE ESCAPE ROUTE  —  "
            f"SCALE 1:{SEC_SCALE}", PW)

SEC_X0 = PX0 + 44
SEC_Y0 = SEC_TOP + 156           # paper y of finished floor level


def sx(mv):
    return SEC_X0 + (mv + WALL) / SEC_SCALE


def sy(lv):
    return SEC_Y0 - lv / SEC_SCALE


SOFFIT, CEIL, CEIL_WC, BULK, DOOR_H = 3400, 2700, 2400, 2400, 2100


def swall(y0, y1, l0, l1):
    rect(sx(y0), sy(l1), (y1 - y0) / SEC_SCALE, (l1 - l0) / SEC_SCALE,
         fill="url(#hatchWall)", stroke="#111", sw=0.3)


# floor slab and structure
rect(sx(-WALL), sy(0), (ROOM_H + 2 * WALL) / SEC_SCALE, 7.0,
     fill="url(#hatchWall)", stroke="#111", sw=0.3)
rect(sx(-WALL), sy(SOFFIT) - 7.0, (ROOM_H + 2 * WALL) / SEC_SCALE, 7.0,
     fill="url(#hatchWall)", stroke="#111", sw=0.3)
swall(-WALL, 0, DOOR_H, SOFFIT)          # over the EXIT 1 opening
swall(ROOM_H, ROOM_H + WALL, 0, SOFFIT)
swall(BOH_PART_Y0, BOH_PART_Y1, 0, SOFFIT)

# suspended ceilings and the services zone
rect(sx(0), sy(CEIL), (BOH_PART_Y0) / SEC_SCALE,
     (SOFFIT - CEIL) / SEC_SCALE, fill="#f2f5f8", stroke="none")
line(sx(0), sy(CEIL), sx(BOH_PART_Y0), sy(CEIL), stroke="#111", sw=0.45)
rect(sx(BOH_PART_Y1), sy(CEIL_WC), (ROOM_H - BOH_PART_Y1) / SEC_SCALE,
     (SOFFIT - CEIL_WC) / SEC_SCALE, fill="#f2f5f8", stroke="none")
line(sx(BOH_PART_Y1), sy(CEIL_WC), sx(ROOM_H), sy(CEIL_WC), stroke="#111",
     sw=0.45)
# local bulkhead over the toilet lobby
rect(sx(WC_LOBBY[2]), sy(BULK), (WC_LOBBY[3] - WC_LOBBY[2]) / SEC_SCALE,
     (CEIL - BULK) / SEC_SCALE, fill="#e6ebf1", stroke="#111", sw=0.35)
text(sx((WC_LOBBY[2] + WC_LOBBY[3]) / 2), sy(BULK) + 4.0,
     "BULKHEAD / DUCT", size=2.1, anchor="middle", fill="#555")
text(sx(3600), sy(CEIL) - 3.5, "SERVICES ZONE  700", size=2.3,
     anchor="middle", fill="#666")

# exit door leaf, shown in elevation beyond
rect(sx(-WALL), sy(DOOR_H), WALL / SEC_SCALE, DOOR_H / SEC_SCALE,
     fill="#fff", stroke="#111", sw=0.4)
text(sx(-100), sy(DOOR_H) + 12, "EXIT 1", size=2.2, anchor="middle",
     fill="#111", weight="bold", rotate=-90)

# floor line, escape-route band and datum
rect(sx(0), sy(0) - 2.6, ROOM_H / SEC_SCALE, 2.6, fill="url(#hatchEsc)",
     stroke="none", op="0.85")
line(sx(-WALL), sy(0), sx(ROOM_H + WALL), sy(0), stroke="#111", sw=0.6)
text(sx(300), sy(0) - 5.0, "FFL ±0", size=2.4, fill="#666")

# vertical dimensions
dv_x = SEC_X0 - 8
line(dv_x, sy(0), dv_x, sy(CEIL), stroke=BLU, sw=0.18)
for lv in (0, CEIL):
    line(dv_x - 1.4, sy(lv), dv_x + 1.4, sy(lv), stroke=BLU, sw=0.35)
text(dv_x - 1.2, (sy(0) + sy(CEIL)) / 2, "2700 CLEAR", size=2.4,
     anchor="middle", fill=BLU, rotate=-90)
dv2 = SEC_X0 - 17
line(dv2, sy(0), dv2, sy(SOFFIT), stroke=BLU, sw=0.18)
for lv in (0, SOFFIT):
    line(dv2 - 1.4, sy(lv), dv2 + 1.4, sy(lv), stroke=BLU, sw=0.35)
text(dv2 - 1.2, (sy(0) + sy(SOFFIT)) / 2, "3400 SOFFIT", size=2.4,
     anchor="middle", fill=BLU, rotate=-90)

dv3 = sx(ROOM_H + WALL) + 9
line(dv3, sy(0), dv3, sy(CEIL_WC), stroke=BLU, sw=0.18)
for lv in (0, CEIL_WC):
    line(dv3 - 1.4, sy(lv), dv3 + 1.4, sy(lv), stroke=BLU, sw=0.35)
text(dv3 - 1.2, (sy(0) + sy(CEIL_WC)) / 2, "2400", size=2.4,
     anchor="middle", fill=BLU, rotate=-90)
text(sx((WC_LOBBY[2] + WC_LOBBY[3]) / 2), sy(BULK) + 8.5,
     "2400 CLEAR UNDER BULKHEAD  (2000 min.)", size=2.3, anchor="middle",
     fill=BLU)
text(sx(2000), sy(CEIL) + 5.5, "SUSPENDED CEILING  2700 AFFL", size=2.4,
     fill="#444")
text(sx(2000), sy(SOFFIT) + 12.5, "STRUCTURAL SOFFIT  3400 AFFL", size=2.4,
     fill="#444")

text(sx(400), sy(DOOR_H) - 2.2, "DOOR HEAD 2100", size=2.3, fill=BLU)
line(sx(0), sy(DOOR_H), sx(1400), sy(DOOR_H), stroke=BLU, sw=0.18,
     dash="2,1.5")

# zone captions along the base
for a, b, lab in [(-WALL, 0, "EXIT 1"), (0, ENTRY[3], "ENTRANCE"),
                  (SPINE_C[2], SPINE_C[3], "SPINE C"),
                  (WC_LOBBY[2], WC_LOBBY[3], "WC LOBBY"),
                  (BOH_Y0, ROOM_H, "ACCESSIBLE WC")]:
    text((sx(a) + sx(b)) / 2, SEC_Y0 + 10, lab, size=2.3, anchor="middle",
         fill="#555")
    for t in (a, b):
        line(sx(t), SEC_Y0 + 1.5, sx(t), SEC_Y0 + 4.0, stroke="#999", sw=0.25)
text(sx(ROOM_H / 2), SEC_Y0 + 17,
     "Clear headroom on every escape route exceeds the 2000 mm minimum. "
     "Section taken on line A–A, looking west.", size=2.4, anchor="middle",
     fill="#666")

SEC_BOT = SEC_Y0 + 22

# ---- notes ----------------------------------------------------------------
NOTES = [
    "This drawing is a design study prepared to scale for compliance "
    "review. It is not a submission drawing. Plans for building works, "
    "means of escape and fire service installations must be prepared and "
    "certified by an Authorized Person / Registered Structural Engineer and "
    "a Registered Fire Service Installation Contractor and submitted to the "
    "Buildings Department and the Fire Services Department for approval "
    "before any work is carried out or any licence is granted.",

    "Means of escape designed to the Code of Practice for Fire Safety in "
    "Buildings 2011, Part B. Two exits are provided, remote from one "
    "another, each leading by a clear and direct route to a place of safety "
    "in the open air at ground level. Escape routes are shown hatched green "
    "and are to be kept permanently free of furniture, stock and "
    "obstruction.",

    "Alternative directions of escape: where two routes subtend an angle of "
    "less than 45° at the point of origin, that part of the floor is "
    "treated as single-direction escape. The longest such travel on this "
    f"layout is {TRAVEL_DEADEND} m, from the east end of the toilet lobby "
    "to the point of divergence at spine A.",

    "Ground / street level premises are assumed. Premises on upper floors "
    "or in a basement attract more onerous requirements — discharge through "
    "a protected staircase, shorter permitted travel distances and a lower "
    "permitted occupant capacity assessed by the Fire Services Department.",

    "Sprinklers: the building is assumed to be sprinkler protected and "
    "heads are shown indicatively at approximately 3.0 × 2.7 m centres, "
    "Ordinary Hazard Group 1. If the building is NOT sprinklered, travel "
    "distances and the permitted occupant capacity must be re-assessed, as "
    "the escape-time assumptions and the margins applied by the Fire "
    "Services Department are more restrictive for unsprinklered premises.",

    "Emergency lighting to all escape routes, exits, toilets and back of "
    "house, 2 hour duration, maintained. Illuminated directional exit signs "
    "sited so that at least one sign is visible from every part of the "
    "premises to which the public has access.",

    "Liquor licence: this layout plan is intended to accompany an "
    "application to the Liquor Licensing Board through the Food and "
    "Environmental Hygiene Department. The designated liquor-consumption "
    "area is demarcated by the chain-dashed magenta boundary. The maximum "
    "number of persons permitted on the premises is set by the Fire "
    "Services Department and must be displayed on the premises together "
    "with the licence.",

    "Live entertainment, dancing or amplified performance would require a "
    "Places of Public Entertainment licence under Cap. 172, which brings "
    "further Buildings Department and Fire Services Department "
    "requirements. Any cooking would require a food business licence and "
    "additional provisions including a wet chemical extinguisher, a fire "
    "blanket, kitchen extract fire protection and a separate hand-wash "
    "basin.",

    "Sanitary fitments shown are indicative. Numbers are to be confirmed "
    "against the Building (Standards of Sanitary Fitments, Plumbing, "
    "Drainage Works and Latrines) Regulations for the assessed occupant "
    "capacity. The accessible unisex WC follows the Design Manual: Barrier "
    "Free Access 2008, with a 1500 mm diameter clear turning circle and an "
    "outward-opening or sliding door.",

    "No-smoking signage is required throughout under the Smoking (Public "
    "Health) Ordinance, Cap. 371. Notices prohibiting the sale of liquor to "
    "persons under 18 are to be displayed at the bar counter.",

    "Operational: exits and escape routes are to be kept unlocked and "
    "unobstructed whenever the premises are occupied; the capacity notice "
    "is to be displayed and observed; fire service installations are to be "
    "inspected and certified annually on Form FS 251 by a registered "
    "contractor.",
]

block_title(PX0, SEC_BOT + 13, "GENERAL, STATUTORY AND OPERATIONAL NOTES",
            PW)
ny = SEC_BOT + 21
for i, n in enumerate(NOTES, 1):
    text(PX0 + 1.6, ny, f"{i}.", size=2.9, weight="bold", fill="#111")
    for ln in textwrap.wrap(n, 172):
        text(PX0 + 9.5, ny, ln, size=2.9, fill="#222")
        ny += 4.2
    ny += 1.6

# ---- references -----------------------------------------------------------
block_title(PX0, ny + 8, "REFERENCES", PW)
ry = ny + 16
for r in [
    "Code of Practice for Fire Safety in Buildings 2011 — Buildings "
    "Department (Part B: Means of Escape; Part C: Fire Resisting "
    "Construction)",
    "Codes of Practice for Minimum Fire Service Installations and Equipment "
    "— Fire Services Department",
    "Design Manual: Barrier Free Access 2008 — Buildings Department",
    "Dutiable Commodities (Liquor) Regulations, Cap. 109B — liquor licence "
    "and the \"bar\" endorsement",
    "Building (Standards of Sanitary Fitments, Plumbing, Drainage Works and "
    "Latrines) Regulations, Cap. 123I",
    "Places of Public Entertainment Ordinance, Cap. 172 · Smoking (Public "
    "Health) Ordinance, Cap. 371",
]:
    for j, ln in enumerate(textwrap.wrap(r, 172)):
        text(PX0 + (1.6 if j == 0 else 5.5), ry, ("— " if j == 0 else "") + ln,
             size=2.8, fill="#333")
        ry += 4.0
    ry += 0.6

# ---- revisions ------------------------------------------------------------
block_title(PX0, ry + 9, "REVISIONS", PW)
rows(PX0, ry + 17,
     [["P1", "2026-07-30", "First issue — preliminary, for compliance "
       "review", "—"]],
     [22, 44, PW - 108, 42], PW, size=2.8, lh=5.0,
     head=["Rev", "Date", "Description", "By"])

# ---- title block ----------------------------------------------------------
TBX, TBY = PANEL_X, 704.0
TBW, TBH = SHEET_W - MARGIN - 2 - TBX, SHEET_H - MARGIN - 2 - TBY
rect(TBX, TBY, TBW, TBH, fill="#fff", stroke="#111", sw=0.5)
for yy in (26, 56, 88):
    line(TBX, TBY + yy, TBX + TBW, TBY + yy, stroke="#111", sw=0.3)
line(TBX + TBW * 0.60, TBY + 88, TBX + TBW * 0.60, TBY + TBH, stroke="#111",
     sw=0.3)

text(TBX + 4, TBY + 10.5, "PROJECT", size=2.5, fill="#777", ls=0.6)
text(TBX + 4, TBY + 21, "BAR VENUE — GROUND FLOOR TENANCY, HONG KONG",
     size=5.4, weight="bold")
text(TBX + 4, TBY + 35, "DRAWING", size=2.5, fill="#777", ls=0.6)
text(TBX + 4, TBY + 47,
     "GENERAL ARRANGEMENT · MEANS OF ESCAPE · FSI LAYOUT", size=4.4,
     weight="bold")
text(TBX + 4, TBY + 66, "STATUS", size=2.5, fill="#777", ls=0.6)
text(TBX + 4, TBY + 78,
     "PRELIMINARY — FOR COMPLIANCE REVIEW, NOT FOR SUBMISSION", size=3.7,
     weight="bold", fill=RED)

fy = TBY + 99
for k, v in [("SCALE", f"1:{SCALE} at A0 (1189 × 841 mm)"),
             ("SPACE", f"{ROOM_W / 1000:.1f} m × {ROOM_H / 1000:.1f} m "
                       f"internal = {ROOM_W * ROOM_H / M2:.1f} m²"),
             ("LEVEL", "Ground / street level"),
             ("CAPACITY", f"{OCC_TOTAL} persons calculated · "
                          f"{OCC_DESIGN} designed"),
             ("UNITS", "Millimetres unless noted otherwise")]:
    text(TBX + 4, fy, k, size=2.4, fill="#777", ls=0.5)
    text(TBX + 38, fy, v, size=2.9, fill="#111")
    fy += 7.4

fy = TBY + 99
for k, v in [("DRAWING No.", "BAR-GA-001"), ("REVISION", "P1"),
             ("DATE", "2026-07-30"), ("DRAWN", "—"), ("SHEET", "1 of 1")]:
    text(TBX + TBW * 0.60 + 4, fy, k, size=2.4, fill="#777", ls=0.5)
    text(TBX + TBW - 4, fy, v, size=2.9, anchor="end", weight="bold")
    fy += 7.4

add('</svg>')


# ==========================================================================

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "bar-floor-plan-1-20.svg"
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print(f"wrote {target}")
    print(f"  public area (net)     {A_PUBLIC_NET:6.2f} m2")
    print(f"  licensed area         {A_LICENSED:6.2f} m2")
    print(f"  standing area (net)   {A_STAND:6.2f} m2 -> {STANDING_PERSONS} p")
    print(f"  occupant capacity     {OCC_TOTAL} persons "
          f"(exits designed for {OCC_DESIGN})")
    print(f"  seats                 {SEATS_TOTAL} "
          f"(bar {SEATS_BAR} / table {SEATS_TABLE} / lounge {SEATS_LOUNGE})")
    print(f"  design population     {SEATS_TOTAL + STANDING_PERSONS + 5}")


if __name__ == "__main__":
    main()
