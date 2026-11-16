"""Generate hardware/pcb/damper.kicad_pcb and bom.csv.

Run with KiCad's bundled Python (it ships the pcbnew module):

    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" gen_pcb.py

There is no schematic: the netlist is the part tables below. Parts are placed
by hand; the tracks are found by the small grid router at the end of this file,
so moving a part and re-running re-routes the board. Coordinates are in mm,
origin at the board's top-left corner, x to the right, y DOWN (as KiCad draws
it). hardware/case/case.scad uses the same numbers.

Two grounds: AC_GND (damper side, bottom-left block) and GND (ESP side). Only
U1, U2, U3/U4 and JP2 straddle the gap between them.
"""
import csv
import heapq
import math
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_FP = os.environ.get("KICAD_FOOTPRINTS") or os.path.join(
    os.path.dirname(os.path.dirname(sys.executable)), "share", "kicad", "footprints")

OX, OY = 100.0, 50.0            # where the board sits on the KiCad sheet
W, H = 60.96, 71.12
F, B = pcbnew.F_Cu, pcbnew.B_Cu
SILK = pcbnew.F_SilkS

# The damper side: x < AC_X and y > AC_Y. GAP is the copper-free band around it.
AC_X, AC_Y, GAP = 22.36, 26.0, 1.0
AC_NETS = {"AC_GND", "12V_IN", "12V_F", "12V_P", "CTRL", "CTRL_Q", "STATE", "ST_Z",
           "Q1_B", "Q1_C", "Q2_B", "U1_C", "U2_A"}
POWER_NETS = {"12V_IN", "12V_F", "12V_P", "5V_REG", "5V_SEL", "5V_EXT", "+5V"}
POUR_NETS = {"GND", "AC_GND"}   # connected by the copper pours, not routed

# JST PH pin order of the wall cable, pin 1 first: yellow, green, red, black
J1_NETS = ["12V_IN", "AC_GND", "CTRL", "STATE"]
# LD2410 pin order, pin 1 first (check against the silkscreen of your module)
RADAR_C = ["IO20", "IO21", "IO3", "GND", "+5V"]      # TX RX OUT GND VCC
RADAR_B = ["IO3", "IO20", "IO21", "GND", "+5V"]      # OUT TX RX GND VCC

board = pcbnew.BOARD()
nets = {}
bom = []


def pt(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def net(name):
    if name is None:
        return None
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]


def lib(ref, value, library, name, x, y, rot, padnets, note="", fit=True):
    """Place a KiCad library footprint with its pad 1 at (x, y)."""
    fp = pcbnew.FootprintLoad(os.path.join(KICAD_FP, library + ".pretty"), name)
    if fp is None:
        raise SystemExit("footprint not found: %s:%s" % (library, name))
    board.Add(fp)
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(pt(x, y))
    fp.SetOrientationDegrees(rot)
    fp.Value().SetVisible(False)
    fp.Reference().SetVisible(False)
    if isinstance(padnets, (list, tuple)):
        padnets = {str(i + 1): n for i, n in enumerate(padnets)}
    for p in fp.Pads():
        n = padnets.get(p.GetNumber())
        if n:
            p.SetNet(net(n))
    if fit is not None:
        bom.append((ref, value, name, note if fit else "optional: " + note))
    return fp


def pads(ref, value, plist, drill=1.0, size=1.7, npth=False, note=None):
    """A footprint made of bare pads. plist: (number, x, y, net)."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(pt(plist[0][1], plist[0][2]))
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)
    for i, (num, x, y, n) in enumerate(plist):
        p = pcbnew.PAD(fp)
        p.SetNumber(str(num))
        shp = pcbnew.PAD_SHAPE_RECT if (i == 0 and len(plist) > 1 and num == 1) else pcbnew.PAD_SHAPE_CIRCLE
        p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH if npth else pcbnew.PAD_ATTRIB_PTH)
        p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask() if npth else pcbnew.PAD.PTHMask())
        p.SetShape(F, shp)
        p.SetSize(F, VECTOR2I(FromMM(size), FromMM(size)))
        p.SetDrillSize(VECTOR2I(FromMM(drill), FromMM(drill)))
        p.SetPosition(pt(x, y))
        if n:
            p.SetNet(net(n))
        fp.Add(p)
    if note is not None:
        bom.append((ref, value, "", note))
    return fp


def line(a, b, layer=SILK, width=0.15):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pt(*a))
    s.SetEnd(pt(*b))
    s.SetLayer(layer)
    s.SetWidth(FromMM(width))
    board.Add(s)


def rect(x0, y0, x1, y1, layer=SILK, width=0.15):
    line((x0, y0), (x1, y0), layer, width)
    line((x1, y0), (x1, y1), layer, width)
    line((x1, y1), (x0, y1), layer, width)
    line((x0, y1), (x0, y0), layer, width)


def text(s, x, y, size=0.8, angle=0, layer=SILK, just="c"):
    if layer == SILK:
        size = max(size, 0.8)
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(max(0.12, size * 0.15)))
    t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    t.SetHorizJustify({"c": pcbnew.GR_TEXT_H_ALIGN_CENTER, "l": pcbnew.GR_TEXT_H_ALIGN_LEFT,
                       "r": pcbnew.GR_TEXT_H_ALIGN_RIGHT}[just])
    if layer in (pcbnew.B_SilkS, pcbnew.B_Cu):
        t.SetMirrored(True)
    board.Add(t)


R_AX = ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal")
HDR = "Connector_PinHeader_2.54mm"

# --------------------------------------------------------------------------- outline, mounting
rect(0, 0, W, H, pcbnew.Edge_Cuts, 0.1)
MOUNT = [(3.81, 3.81), (57.15, 3.81), (3.81, 67.31), (57.15, 67.31)]
for i, (x, y) in enumerate(MOUNT):
    pads("H%d" % (i + 1), "M3", [("", x, y, None)], 3.2, 3.2, npth=True)

# --------------------------------------------------------------------------- ESP32-C3 SuperMini
# Socketed, USB-C at the bottom board edge. Rows 15.24 mm apart. Seen from the
# component side with USB down, pins from the antenna end to the USB end:
ESP_XL, ESP_XR, ESP_Y0, P = 35.56, 50.80, 49.53, 2.54
ESP_L = ["IO0", "IO1", "IO2", "IO3", "IO4", "+3V3", "GND", "+5V"]
ESP_R = ["IO21", "IO20", "IO10", "IO9", "IO8", "IO7", "IO6", "IO5"]
LABEL = {"+3V3": "3V3", "+5V": "5V", "GND": "G"}
lib("J3", "socket 1x8", "Connector_PinSocket_2.54mm", "PinSocket_1x08_P2.54mm_Vertical",
    ESP_XL, ESP_Y0, 0, ESP_L, "for the ESP32-C3 SuperMini")
lib("J4", "socket 1x8", "Connector_PinSocket_2.54mm", "PinSocket_1x08_P2.54mm_Vertical",
    ESP_XR, ESP_Y0, 0, ESP_R, "for the ESP32-C3 SuperMini")
pads("J5", "breakout", [(i + 1, ESP_XL - P, ESP_Y0 + i * P, n) for i, n in enumerate(ESP_L[:6])])
pads("J6", "breakout", [(i + 1, ESP_XR + P, ESP_Y0 + i * P, n) for i, n in enumerate(ESP_R)])
for i, (a, b) in enumerate(zip(ESP_L, ESP_R)):
    y = ESP_Y0 + i * P
    if i < 6:
        text(LABEL.get(a, a[2:]), ESP_XL - P - 1.3, y, 0.7, just="r")
    text(LABEL.get(b, b[2:]), ESP_XR + P + 1.3, y, 0.7, just="l")
rect(ESP_XL - 1.38, ESP_Y0 - 2.36, ESP_XR + 1.38, H - 0.3, pcbnew.F_Fab)
text("ESP32-C3", 43.18, 50.0, 0.9)
text("SuperMini", 43.18, 51.5, 0.9)
text("USB", 43.18, 69.3, 0.9)

# resistors lying under the ESP
RX0 = 39.37
lib("R11", "330R", *R_AX, RX0, 64.77, 0, ["LED_G", "IO6"], "green LED")
lib("R12", "330R", *R_AX, RX0, 62.23, 0, ["LED_R", "IO7"], "red LED")
lib("R13", "330R", *R_AX, RX0, 59.69, 0, ["LED_B", "IO10"], "blue LED")
lib("R2", "10k", *R_AX, RX0, 57.15, 0, ["IO1", "+3V3"], "state pull-up")
lib("R1", "220R", *R_AX, RX0, 54.61, 0, ["IO0", "U1_A"], "U1 LED current")

# --------------------------------------------------------------------------- damper side
lib("J1", "JST S4B-PH-K", "Connector_JST", "JST_PH_S4B-PH-K_1x04_P2.00mm_Horizontal",
    10.16, 64.77, 0, J1_NETS, "side entry, mates with the wall cable")
pads("J1B", "pigtail pads", [(i + 1, 6.35 + i * P, 62.23, n) for i, n in enumerate(J1_NETS)])
pads("F1", "PTC 500mA", [(1, 3.81, 57.15, "12V_IN"), (2, 3.81, 52.07, "12V_F")], 1.0, 2.0,
     note="resettable fuse, 5 mm pitch, e.g. RXEF050")
lib("D2", "1N5819", "Diode_THT", "D_DO-41_SOD81_P10.16mm_Horizontal", 17.78, 52.07, 180,
    {"1": "12V_P", "2": "12V_F"}, "reverse polarity")
lib("D3", "P6KE15A", "Diode_THT", "D_DO-15_P10.16mm_Horizontal", 2.54, 40.64, 90,
    {"1": "12V_P", "2": "AC_GND"}, "TVS")
lib("C1", "100uF 25V", "Capacitor_THT", "CP_Radial_D6.3mm_P2.50mm", 8.89, 57.15, 0,
    ["12V_P", "AC_GND"], "")
# control: U1 turns on Q2, Q2 pulls the red wire down through R7
lib("Q2", "2N3904", "Package_TO_SOT_THT", "TO-92_Inline_Wide", 11.43, 27.94, 0,
    ["AC_GND", "Q2_B", "CTRL_Q"], "E B C")
lib("R6", "10k", *R_AX, 6.35, 30.48, 0, ["AC_GND", "Q2_B"], "")
lib("R5", "4k7", *R_AX, 6.35, 33.02, 0, ["12V_P", "U1_C"], "")
lib("R7", "33R", *R_AX, 6.35, 35.56, 0, ["CTRL", "CTRL_Q"], "wire link if the damper does not react")
lib("U1", "PC817C", "Package_DIP", "DIP-4_W7.62mm", 26.67, 33.02, 180,
    ["U1_A", "GND", "Q2_B", "U1_C"], "control optocoupler")
# state: black wire -> zener -> Q1 -> U2 LED
lib("R10", "2k2", *R_AX, 6.35, 38.10, 0, ["12V_P", "U2_A"], "")
lib("U2", "PC817C", "Package_DIP", "DIP-4_W7.62mm", 19.05, 36.83, 0,
    ["U2_A", "Q1_C", "GND", "IO1"], "state optocoupler")
lib("Q1", "2N3904", "Package_TO_SOT_THT", "TO-92_Inline_Wide", 8.89, 41.91, 0,
    ["AC_GND", "Q1_B", "Q1_C"], "E B C")
lib("R9", "10k", *R_AX, 6.35, 44.45, 0, ["AC_GND", "Q1_B"], "")
lib("R8", "10k", *R_AX, 6.35, 46.99, 0, ["ST_Z", "Q1_B"], "")
lib("ZD1", "5V1 zener 0.5W", "Diode_THT", "D_DO-35_SOD27_P7.62mm_Horizontal", 13.97, 49.53, 180,
    {"1": "STATE", "2": "ST_Z"}, "BZX55C5V1")

# --------------------------------------------------------------------------- 12 V -> 5 V, fit ONE
pads("U4", "B1205S-1W", [(1, 19.05, 46.99, "AC_GND"), (2, 21.59, 46.99, "12V_P"),
                         (3, 24.13, 46.99, "GND"), (4, 26.67, 46.99, "5V_REG")], 1.0, 1.7,
     note="optional: isolated SIP-4 (-Vin +Vin -Vo +Vo), INSTEAD of U3, JP2 open")
rect(17.1, 41.9, 28.6, 48.1)
lib("U3", "K7805-1000R3", "Converter_DCDC", "Converter_DCDC_RECOM_R-78E-0.5_THT", 19.05, 59.69, 0,
    ["12V_P", "AC_GND", "5V_REG"], "or R-78E5.0-1.0; needs JP2 closed")
lib("JP2", "GND link", HDR, "PinHeader_1x02_P2.54mm_Vertical", 21.59, 50.80, 90,
    ["AC_GND", "GND"], "2-pin header + jumper")

# --------------------------------------------------------------------------- 5 V selection
lib("JP1", "power select", HDR, "PinHeader_1x03_P2.54mm_Vertical", 30.48, 35.56, 0,
    ["5V_REG", "5V_SEL", "5V_EXT"], "3-pin header + jumper")
pads("JP3", "jumper park", [("", 33.02, 35.56, None), ("", 33.02, 38.10, None)],
     note="2-pin header, optional")
lib("D1", "1N5817", "Diode_THT", "D_DO-41_SOD81_P10.16mm_Horizontal", 45.72, 43.18, 180,
    {"1": "+5V", "2": "5V_SEL"}, "")
lib("C2", "470uF 10V", "Capacitor_THT", "CP_Radial_D8.0mm_P3.50mm", 38.10, 31.75, 0,
    ["+5V", "GND"], "")
lib("J2", "5V in", "TerminalBlock_Phoenix", "TerminalBlock_Phoenix_PT-1,5-2-3.5-H_1x02_P3.50mm_Horizontal",
    25.40, 66.04, 0, ["5V_EXT", "GND"], "3.5 mm screw terminal")

# --------------------------------------------------------------------------- radar
# LD2410C plugs flat onto J7 and lies to the left or to the right of it,
# whichever way its pin 1 lands on J7 pin 1. Keep y 7..23.5 free of tall parts.
lib("J7", "socket 1x5", "Connector_PinSocket_2.54mm", "PinSocket_1x05_P2.54mm_Vertical",
    30.48, 10.16, 0, RADAR_C, "for LD2410C")
lib("J8", "header 1x5 1.27mm", "Connector_PinHeader_1.27mm", "PinHeader_1x05_P1.27mm_Vertical",
    6.35, 12.70, 0, RADAR_B, "for LD2410B", fit=False)
lib("C4", "100nF", "Capacitor_THT", "C_Disc_D3.0mm_W1.6mm_P2.50mm", 33.02, 20.32, 0, ["+5V", "GND"], "")
lib("C3", "100uF 10V", "Capacitor_THT", "CP_Radial_D6.3mm_P2.50mm", 46.99, 3.81, 0, ["+5V", "GND"], "")

# --------------------------------------------------------------------------- LEDs
LEDS = [("D4", "green", "LED_G", 19.05), ("D5", "red", "LED_R", 29.21), ("D6", "blue", "LED_B", 39.37)]
for ref, colour, n, x in LEDS:
    lib(ref, "LED 3mm " + colour, "LED_THT", "LED_D3.0mm", x, 3.81, 0, ["GND", n], "")

# --------------------------------------------------------------------------- spare holes
pads("J9", "I2C", [(1, 45.72, 38.10, "+3V3"), (2, 48.26, 38.10, "GND"),
                   (3, 50.80, 38.10, "IO4"), (4, 53.34, 38.10, "IO5")])
pads("J10", "AUX", [(1, 48.26, 33.02, "+3V3"), (2, 50.80, 33.02, "GND"), (3, 53.34, 33.02, "IO3")])
pads("J11", "5V out", [(1, 48.26, 27.94, "+5V"), (2, 50.80, 27.94, "GND")])
pads("PROTO", "prototyping pads",
     [("", 10.16 + i * P, y, None) for y in (21.59, 24.13) for i in range(6)])

# --------------------------------------------------------------------------- silkscreen
text("Damper rev1", 52.0, 22.0, 1.2)
for ref, colour, n, x in LEDS:
    text(colour[0].upper(), x + 1.27, 6.4, 0.9)
for y, s in zip((10.16, 12.70, 15.24, 17.78, 20.32), ("TX", "RX", "OUT", "GND", "VCC")):
    text(s, 28.9, y, 0.7, just="r")
text("LD2410C", 30.48, 8.1, 0.8)
text("LD2410B", 6.35, 10.9, 0.7)
text("OUT", 7.6, 12.70, 0.6, just="l")
text("VCC", 7.6, 17.78, 0.6, just="l")
text("Y G R B", 15.5, 62.5, 0.8, just="l")          # wire colours, J1 and J1B, left to right
text("AC", 29.0, 35.56, 0.8, just="r")
text("EXT", 29.0, 40.64, 0.8, just="r")
text("PARK", 33.02, 40.1, 0.6)
text("=USB", 33.02, 41.2, 0.6)
text("JP1 5V", 30.48, 33.7, 0.7)
text("GND", 26.0, 50.2, 0.8, just="l")
text("LINK", 26.0, 51.5, 0.8, just="l")
text("U4 isolated", 22.86, 43.0, 0.7)
text("U3 buck", 21.6, 56.0, 0.8)
text("+", 24.0, 69.9, 1.0)
text("-", 30.4, 69.9, 1.0)
text("5V IN", 30.6, 63.6, 0.8, 90)
text("I2C 3V3 G SDA SCL", 49.5, 36.2, 0.7)
text("AUX 3V3 G IO3", 50.8, 31.1, 0.7)
text("5V G", 49.5, 26.0, 0.7)
text("PROTO", 5.5, 22.9, 0.7)
text("F1", 3.81, 54.6, 0.7)
for ref, x, y in (("R6", 10.16, 30.48), ("R5", 10.16, 33.02), ("R7", 10.16, 35.56), ("R10", 10.16, 38.10),
                  ("R9", 10.16, 44.45), ("R8", 10.16, 46.99), ("ZD1", 10.16, 49.53), ("D2", 12.70, 52.07),
                  ("R11", 43.18, 64.77), ("R12", 43.18, 62.23), ("R13", 43.18, 59.69),
                  ("R2", 43.18, 57.15), ("R1", 43.18, 54.61), ("D1", 40.64, 43.18)):
    text(ref, x, y, 0.7, layer=pcbnew.F_Fab)
text("Q2", 9.6, 27.3, 0.7)
text("Q1", 7.0, 41.3, 0.7)
text("D3", 2.54, 28.4, 0.7)
text("U1", 22.86, 29.0, 0.7)
text("U2", 22.86, 40.9, 0.7)
text("C1", 5.9, 59.8, 0.7)
text("C2", 44.6, 28.6, 0.7)
text("C3", 52.4, 5.6, 0.7)
# the isolation gap
line((AC_X + GAP / 2, AC_Y - GAP / 2), (AC_X + GAP / 2, 41.2), SILK, 0.12)
line((0.6, AC_Y - GAP / 2), (AC_X + GAP / 2, AC_Y - GAP / 2), SILK, 0.12)

# =========================================================================== router
G = 0.254                       # grid; every 2.54 mm pad centre is a node
NX, NY = int(round(W / G)) + 1, int(round(H / G)) + 1
CLR = 0.25                      # clearance kept at grid nodes (KiCad minimum is 0.2)
EDGE = 0.6
VIA_D, VIA_DRILL = 0.8, 0.4
SPOKE = 0.4                     # extra room kept around ground pads
near = [dict(), dict()]         # per layer: node -> {net id: distance to that net's copper}
KEEPOUT = (37.0, 46.5, 49.4, 53.2)   # under the ESP antenna: no copper


def dist(shape, x, y):
    if shape[0] == "seg":
        _, x1, y1, x2, y2, r = shape
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
        return math.hypot(x - x1 - t * dx, y - y1 - t * dy) - r
    _, cx, cy, hw, hh = shape
    qx, qy = abs(x - cx) - hw, abs(y - cy) - hh
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0)


def stamp(layers, nid, shape, reach=1.0):
    if shape[0] == "seg":
        xs, ys, r = (shape[1], shape[3]), (shape[2], shape[4]), shape[5]
        x0, x1, y0, y1 = min(xs) - r, max(xs) + r, min(ys) - r, max(ys) + r
    else:
        x0, x1, y0, y1 = shape[1] - shape[3], shape[1] + shape[3], shape[2] - shape[4], shape[2] + shape[4]
    for iy in range(max(0, int((y0 - reach) / G)), min(NY - 1, int((y1 + reach) / G) + 1) + 1):
        for ix in range(max(0, int((x0 - reach) / G)), min(NX - 1, int((x1 + reach) / G) + 1) + 1):
            d = dist(shape, ix * G, iy * G)
            if d < reach:
                for l in layers:
                    cell = near[l].setdefault(iy * NX + ix, {})
                    if d < cell.get(nid, 9.0):
                        cell[nid] = d


def pad_shape(p):
    pos = p.GetPosition()
    x, y = ToMM(pos.x) - OX, ToMM(pos.y) - OY
    sz = p.GetSize(F)
    sx, sy = ToMM(sz.x), ToMM(sz.y)
    if int(round(p.GetOrientation().AsDegrees())) % 180 == 90:
        sx, sy = sy, sx
    if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        return x, y, ("seg", x, y, x, y, ToMM(p.GetDrillSize().x) / 2 + 0.15)
    shp = p.GetShape(F)
    if shp in (pcbnew.PAD_SHAPE_RECT, pcbnew.PAD_SHAPE_ROUNDRECT):
        return x, y, ("rect", x, y, sx / 2, sy / 2)
    r = min(sx, sy) / 2
    return x, y, ("seg", x - (sx / 2 - r), y - (sy / 2 - r), x + (sx / 2 - r), y + (sy / 2 - r), r)


netpads = {}
uniq = 0
for fp in board.GetFootprints():
    for p in fp.Pads():
        x, y, shape = pad_shape(p)
        name = p.GetNetname()
        if name:
            netpads.setdefault(name, []).append((x, y))
            nid = name
        else:
            uniq += 1
            nid = "_%d" % uniq
        if name in POUR_NETS:                 # leave room for the thermal spokes
            shape = shape[:-1] + (shape[-1] + SPOKE,) if shape[0] == "seg" else                 shape[:3] + (shape[3] + SPOKE, shape[4] + SPOKE)
        stamp((0, 1), nid, shape)


def allowed(ix, iy, ac):
    x, y = ix * G, iy * G
    if x < EDGE or y < EDGE or x > W - EDGE or y > H - EDGE:
        return False
    if ac:
        return x <= AC_X - 0.3 and y >= AC_Y + 0.3
    if x <= AC_X + GAP + 0.3 and y >= AC_Y - GAP - 0.3:
        return False
    m = 0.45                                             # half a track and some air
    return not (KEEPOUT[0] - m <= x <= KEEPOUT[2] + m and KEEPOUT[1] - m <= y <= KEEPOUT[3] + m)


def free(l, node, nid, need):
    cell = near[l].get(node)
    if not cell:
        return True
    for n, d in cell.items():
        if n != nid and d < need:
            return False
    return True


STEPS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
LAYER_COST = (1.0, 2.5)         # prefer the front, the back stays mostly ground pour
VIA_COST = 40.0


def node_of(x, y):
    return int(round(y / G)) * NX + int(round(x / G))


def search(nid, starts, targets, width, ac):
    need, need_via = width / 2 + CLR, VIA_D / 2 + CLR
    best, prev, heap = {}, {}, []
    for s in starts:
        best[s] = 0.0
        heap.append((0.0, s))
    heapq.heapify(heap)
    while heap:
        c, s = heapq.heappop(heap)
        if c > best.get(s, 1e18):
            continue
        if s in targets:
            path = [s]
            while s in prev:
                s = prev[s]
                path.append(s)
            return path
        l, node = s
        iy, ix = divmod(node, NX)
        for dx, dy, k in STEPS:
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < NX and 0 <= jy < NY) or not allowed(jx, jy, ac):
                continue
            t = (l, jy * NX + jx)
            if t not in targets and not free(l, t[1], nid, need):
                continue
            nc = c + k * LAYER_COST[l]
            if nc < best.get(t, 1e18):
                best[t] = nc
                prev[t] = s
                heapq.heappush(heap, (nc, t))
        t = (1 - l, node)
        if free(0, node, nid, need_via) and free(1, node, nid, need_via):
            nc = c + VIA_COST
            if nc < best.get(t, 1e18):
                best[t] = nc
                prev[t] = s
                heapq.heappush(heap, (nc, t))
    return None


def add_track(netname, layer, width, a, b):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(*a))
    t.SetEnd(pt(*b))
    t.SetWidth(FromMM(width))
    t.SetLayer(F if layer == 0 else B)
    t.SetNet(net(netname))
    board.Add(t)
    stamp((layer,), netname, ("seg", a[0], a[1], b[0], b[1], width / 2))


def add_via(netname, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetWidth(F, FromMM(VIA_D))
    v.SetDrill(FromMM(VIA_DRILL))
    v.SetLayerPair(F, B)
    v.SetNet(net(netname))
    board.Add(v)
    stamp((0, 1), netname, ("seg", x, y, x, y, VIA_D / 2))


def emit(netname, width, path):
    """path: list of (layer, node). Merge straight runs into single tracks."""
    xy = lambda s: ((s[1] % NX) * G, (s[1] // NX) * G)
    i = 0
    while i < len(path) - 1:
        a, b = path[i], path[i + 1]
        if a[0] != b[0]:
            add_via(netname, *xy(a))
            i += 1
            continue
        d = (b[1] - a[1])
        j = i + 1
        while j < len(path) - 1 and path[j + 1][0] == a[0] and path[j + 1][1] - path[j][1] == d:
            j += 1
        add_track(netname, a[0], width, xy(a), xy(path[j]))
        i = j


failed = []


def route_net(name, width):
    ac = name in AC_NETS
    plist = netpads[name]
    done = set()

    def attach(x, y):
        n = node_of(x, y)
        gx, gy = (n % NX) * G, (n // NX) * G
        if abs(gx - x) > 0.005 or abs(gy - y) > 0.005:      # pad centre is off the grid
            add_track(name, 0, min(width, 0.4), (x, y), (gx, gy))
        return {(0, n), (1, n)}

    done |= attach(*plist[0])
    todo = list(plist[1:])
    while todo:
        # connect the pad that is nearest to what is already connected
        def gap(p):
            return min(math.hypot(p[0] - (s[1] % NX) * G, p[1] - (s[1] // NX) * G) for s in done)
        todo.sort(key=gap)
        p = todo.pop(0)
        starts = attach(*p)
        path = search(name, starts, done, width, ac)
        if path is None and width > 0.3:
            path = search(name, starts, done, 0.3, ac)
            w = 0.3
        else:
            w = width
        if path is None:
            failed.append((name, p))
            continue
        emit(name, w, path)
        done |= set(path) | starts


ORDER = sorted((n for n in netpads if n not in POUR_NETS and len(netpads[n]) > 1),
               key=lambda n: (n not in AC_NETS, sum(math.hypot(a[0] - b[0], a[1] - b[1])
                                                    for a, b in zip(netpads[n], netpads[n][1:]))))
pads_only = [{k: dict(v) for k, v in layer.items()} for layer in near]
for attempt in range(10):
    failed = []
    for name in ORDER:
        route_net(name, 0.6 if name in POWER_NETS else 0.4 if name == "+3V3" else 0.3)
    if not failed:
        break
    # a net got boxed in: start over with it at the front of the queue
    print("attempt %d, unrouted: %s" % (attempt + 1, sorted({n for n, _ in failed})))
    first = [n for n in ORDER if n in {f[0] for f in failed}]
    ORDER = first + [n for n in ORDER if n not in first]
    for t in list(board.GetTracks()):
        board.Remove(t)
    near = [{k: dict(v) for k, v in layer.items()} for layer in pads_only]
if failed:
    print("UNROUTED:", failed)


# =========================================================================== copper pours
def zone(layer, netname=None, pts=None, keepout=False):
    z = pcbnew.ZONE(board)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(FromMM(OX + x), FromMM(OY + y))
    if keepout:
        ls = pcbnew.LSET()
        ls.AddLayer(F)
        ls.AddLayer(B)
        z.SetLayerSet(ls)
        z.SetIsRuleArea(True)
        for setter in ("SetDoNotAllowZoneFills", "SetDoNotAllowCopperPour"):
            if hasattr(z, setter):
                getattr(z, setter)(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
    else:
        z.SetLayer(layer)
        z.SetNet(net(netname))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetMinThickness(FromMM(0.25))
        z.SetLocalClearance(FromMM(0.3))
        z.SetThermalReliefGap(FromMM(0.3))
        z.SetThermalReliefSpokeWidth(FromMM(0.5))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z


# Ground pads that cannot get two thermal spokes (hemmed in by their neighbours
# or sitting on the edge of the pour) are joined to the pour solidly instead.
SOLID = {("J1", "2"), ("JP2", "1"), ("JP2", "2"), ("U4", "1"), ("U4", "3"), ("U3", "2"), ("J11", "2"), ("J1B", "2")}
for fp in board.GetFootprints():
    for p in fp.Pads():
        if (fp.GetReference(), p.GetNumber()) in SOLID:
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

ac_poly = [(0, AC_Y), (AC_X, AC_Y), (AC_X, H), (0, H)]
esp_poly = [(0, 0), (W, 0), (W, H), (AC_X + GAP, H), (AC_X + GAP, AC_Y - GAP), (0, AC_Y - GAP)]
for layer in (F, B):
    zone(layer, "AC_GND", ac_poly)
    zone(layer, "GND", esp_poly)
zone(None, pts=[(KEEPOUT[0], KEEPOUT[1]), (KEEPOUT[2], KEEPOUT[1]),
                (KEEPOUT[2], KEEPOUT[3]), (KEEPOUT[0], KEEPOUT[3])], keepout=True)

# nothing but the parts meant to may cross the isolation gap
for t in board.GetTracks():
    for q in (t.GetStart(), t.GetEnd()):
        x, y = ToMM(q.x) - OX, ToMM(q.y) - OY
        in_ac = x <= AC_X and y >= AC_Y
        in_esp = x >= AC_X + GAP or y <= AC_Y - GAP
        if not (in_ac if t.GetNetname() in AC_NETS else in_esp):
            raise SystemExit("isolation: %s at %.2f, %.2f" % (t.GetNetname(), x, y))

ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.2)
ds.m_MinClearance = FromMM(0.2)
ds.m_CopperEdgeClearance = FromMM(0.5)

board.BuildConnectivity()
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(os.path.join(HERE, "damper.kicad_pcb"), board)

with open(os.path.join(HERE, "bom.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Ref", "Value", "Footprint", "Note"])
    w.writerows(sorted(bom, key=lambda r: (r[0].rstrip("0123456789"), int("".join(c for c in r[0] if c.isdigit()) or 0))))
    w.writerow(["-", "ESP32-C3 SuperMini", "", "plugs into J3/J4"])
    w.writerow(["-", "HLK-LD2410C (or LD2410B)", "", "plugs into J7 (or wired to J8)"])
    w.writerow(["-", "jumper 2.54 mm x2", "", "JP1, JP2"])
print("wrote damper.kicad_pcb: %d nets, %d tracks/vias, %d unrouted" % (len(nets), len(board.GetTracks()), len(failed)))
