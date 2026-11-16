// Damper controller case: body + snap-on cover + two-axis wall mount
// (swing plate for left/right, hinge under the body for up/down).
//
// Render one part at a time (STLs come out in print orientation):
//   openscad -D "part=\"body\""       -o body.stl       case.scad
//   openscad -D "part=\"cover\""      -o cover.stl      case.scad
//   openscad -D "part=\"swing_plate\"" -o swing-plate.stl case.scad
//   openscad -D "part=\"wall_plate\""  -o wall-plate.stl  case.scad
//
// Coordinates follow the PCB as KiCad draws it: x to the right, y DOWN, origin
// at the board's top-left corner. P() converts to OpenSCAD's y-up frame, so
// positions can be copied straight from hardware/pcb/gen_pcb.py. z = 0 is the
// back of the body (the wall side), the cover's face is at the top.

part = "assembly"; // body | cover | swing_plate | wall_plate | assembly | clash
tilt = 25;         // assembly only: degrees the face looks down
pan  = 35;         // assembly only: degrees the face looks right (hinged on the left); negative = left

// ---- Measure these on the real parts before printing ----------------------
stack_h = 18;   // top of PCB to the highest thing inside: the USB-C plug's body
usb_z   = 13.6; // top of PCB to the centre of the ESP32's USB-C socket
usb_plug = [13.5, 8.5]; // opening for the USB-C plug's body, w x h
// ---------------------------------------------------------------------------

pcb      = [60.96, 71.12, 1.6];
margin   = 2;    // PCB edge to inner wall
wall     = 2;
floor_t  = 2.4;
top_t    = 1.2;  // also what the radar looks through
standoff_h = 4;  // room under the PCB for solder joints (and flat-mount screw heads)
headroom = 1;
corner_r = 3;

screw_pilot_d = 2.7; // M3 straight into plastic. Use 4.0 for heat-set inserts
standoff_d    = 6.5;
lip_gap = 0.25; lip_t = 1.5; lip_h = 5;
snap = 0.5;

// PCB features, KiCad coordinates
mount_holes = [[3.81, 3.81], [57.15, 3.81], [3.81, 67.31], [57.15, 67.31]];
leds        = [[20.32, 3.81], [30.48, 3.81], [40.64, 3.81]]; // green, red, blue
esp_centre  = [43.18, 58.4];
// cable openings in the bottom wall: [x from, x to, height above the PCB top]
cable_notches = [[6.5, 32.8, 8]];                            // JST plug and 5 V terminal
usb_x = 43.18;

// flat mounting without the wall plate: two keyholes in the back
keyholes = [[15, 30], [46, 30]];
key_head_d = 8.5; key_shank_d = 4.4; key_travel = 7;

// hinge
knuckle_d = 9; knuckle_w = 10; hinge_bore = 3.4;
lug_w = 6.2; hinge_gap = 0.3;
nut_af = 5.7; nut_t = 2.6;
plate_t = 5; plate_h = 56;
wplate_t = 5; pan_off = 5;         // wall plate thickness; pan axis to the swing plate's edge
wall_screw_d = 4.6; wall_screw_dx = 24; pan_head = 9.2; pan_head_depth = 3;
wall_cable = [20, 16];

$fn = 56;

function P(p) = [p[0], pcb[1] - p[1]];

in_x0 = -margin; in_y0 = -margin;
in_w  = pcb[0] + 2 * margin; in_h = pcb[1] + 2 * margin;
out_x0 = in_x0 - wall; out_x1 = in_x0 + in_w + wall; out_y0 = in_y0 - wall;
pcb_z = floor_t + standoff_h;
pcb_top = pcb_z + pcb[2];
cover_top = pcb_top + stack_h + headroom;       // inside face of the cover
hinge_y = out_y0 - 0.4 - knuckle_d / 2;         // hinge axis, below the bottom wall
hinge_z = knuckle_d / 2;
knuckle_x = [out_x0, out_x1 - knuckle_w];       // left ends of the two knuckles
neck_h = 5.5;                                   // knuckle neck, passes under the cover's corners

module rrect(x0, y0, w, h, r) {
    translate([x0 + r, y0 + r]) offset(r) square([w - 2 * r, h - 2 * r]);
}
module outer2d() { rrect(out_x0, out_y0, in_w + 2 * wall, in_h + 2 * wall, corner_r); }
module inner2d() { rrect(in_x0, in_y0, in_w, in_h, max(corner_r - wall, 0.5)); }

snap_y = [in_y0 + in_h * 0.3, in_y0 + in_h * 0.7];
snap_len = 14; snap_z = floor_t + 3.2;
module snap_ridge(len, h) { // triangular ridge along y, pointing +x
    rotate([90, 0, 0]) linear_extrude(len, center = true)
        polygon([[-0.2, -h * 1.6], [0, -h * 1.6], [h, 0], [0, h * 1.6], [-0.2, h * 1.6]]); // 0.2 of overlap into the wall
}

module knuckle_solid(x) {
    hull() {
        translate([x, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(d = knuckle_d, h = knuckle_w);
        translate([x, hinge_y - knuckle_d / 2, 0]) cube([knuckle_w, knuckle_d / 2, 1]);
        translate([x, out_y0 - 1, 0]) cube([knuckle_w, wall + 1, neck_h]);
    }
}

module body() {
    difference() {
        union() {
            linear_extrude(floor_t) outer2d();
            // lip the cover slides over
            translate([0, 0, floor_t]) linear_extrude(lip_h) difference() {
                offset(-lip_gap) inner2d();
                offset(-lip_gap - lip_t) inner2d();
            }
            for (h = mount_holes) translate([P(h)[0], P(h)[1], floor_t])
                cylinder(d = standoff_d, h = standoff_h);
            for (y = snap_y) {
                translate([in_x0 + lip_gap, y, snap_z]) rotate([0, 0, 180]) snap_ridge(snap_len, lip_gap + snap);
                translate([in_x0 + in_w - lip_gap, y, snap_z]) snap_ridge(snap_len, lip_gap + snap);
            }
            for (x = knuckle_x) knuckle_solid(x);
        }
        for (h = mount_holes) translate([P(h)[0], P(h)[1], 0.6])
            cylinder(d = screw_pilot_d, h = floor_t + standoff_h);
        // the lip gives way where the cables come in
        for (n = cable_notches) translate([n[0], in_y0 - 1, floor_t]) cube([n[1] - n[0], lip_t + 2, lip_h + 1]);
        for (k = keyholes) translate([P(k)[0], P(k)[1], -1]) {
            cylinder(d = key_head_d, h = floor_t + 2);
            hull() {
                cylinder(d = key_shank_d, h = floor_t + 2);
                translate([0, key_travel, 0]) cylinder(d = key_shank_d, h = floor_t + 2);
            }
        }
        // hinge bore, and a nut trap on the inner end of each knuckle
        translate([out_x0 - 1, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(d = hinge_bore, h = in_w + 2 * wall + 2);
        translate([knuckle_x[0] + knuckle_w - nut_t, hinge_y, hinge_z]) rotate([0, 90, 0])
            cylinder(d = nut_af / cos(30), h = nut_t + 1, $fn = 6);
        translate([knuckle_x[1] - 1, hinge_y, hinge_z]) rotate([0, 90, 0])
            cylinder(d = nut_af / cos(30), h = nut_t + 1, $fn = 6);
    }
}

module cover() {
    zt = cover_top;
    difference() {
        union() {
            difference() {
                translate([0, 0, floor_t]) linear_extrude(zt + top_t - floor_t) outer2d();
                translate([0, 0, floor_t - 1]) linear_extrude(zt - floor_t + 1) inner2d();
            }
            // tubes that keep the tall LEDs centred in their holes
            for (l = leds) translate([P(l)[0], P(l)[1], zt - 5]) cylinder(d = 6, h = 5.01);
        }
        for (l = leds) translate([P(l)[0], P(l)[1], zt - 6]) cylinder(d = 3.3, h = top_t + 8);
        // thin spot over the ESP32 so its own LED shows through
        translate([P(esp_centre)[0] - 6, P(esp_centre)[1] - 9, zt - 0.01]) cube([12, 18, top_t - 0.4]);
        // cable notches, open towards the rim so the cover goes on over plugged cables
        for (n = cable_notches) translate([n[0], out_y0 - 1, floor_t - 1])
            cube([n[1] - n[0], wall + 2, pcb_top + n[2] - floor_t + 1]);
        // USB-C
        translate([usb_x - usb_plug[0] / 2, out_y0 - 1, pcb_top + usb_z - usb_plug[1] / 2])
            cube([usb_plug[0], wall + 2, usb_plug[1]]);
        // room for the necks of the hinge knuckles under the two bottom corners
        for (x = knuckle_x) translate([x - 0.3, out_y0 - 1, floor_t - 1])
            cube([knuckle_w + 0.6, wall + 1.3, neck_h - floor_t + 1.3]);
        // snap grooves
        for (y = snap_y) {
            translate([in_x0, y, snap_z]) rotate([0, 0, 180]) snap_ridge(snap_len + 1, snap + 0.15);
            translate([in_x0 + in_w, y, snap_z]) snap_ridge(snap_len + 1, snap + 0.15);
        }
        // fingernail notch, top wall
        translate([in_x0 + in_w / 2 - 7, in_y0 + in_h + wall - 0.2, floor_t - 0.01]) cube([14, wall + 0.2, 1.6]);
    }
}

// Mount, two stages behind the body (z < 0):
//   swing plate - carries the lugs the body tilts on (up/down), and knuckles on
//                 both side edges for the pan hinge;
//   wall plate  - screws to the wall, has the pan lugs on both sides.
// Fit the two pan screws on ONE side only: the swing plate then opens like a
// door on that side (left/right aim), and the free side's knuckles simply leave
// their lugs.
plate_x0 = out_x0 - hinge_gap - lug_w; plate_x1 = out_x1 + hinge_gap + lug_w;
plate_y0 = hinge_y - knuckle_d / 2 - 1;
plate_c  = [(plate_x0 + plate_x1) / 2, plate_y0 + plate_h / 2 + 3];

pan_xa = [plate_x0 - pan_off, plate_x1 + pan_off];   // the two possible pan axes (along y)
pan_z  = -plate_t + knuckle_d / 2;
pan_y0 = plate_y0 + 14;                              // keeps clear of the tilt screws' heads
pan_y1 = plate_y0 + plate_h;
pan_lug_y = [pan_y0, pan_y1 - lug_w];
pan_knk_y = [pan_y0 + lug_w + hinge_gap, pan_y1 - lug_w - hinge_gap - knuckle_w];
wp_z1 = -plate_t - hinge_gap;                        // front face of the wall plate
wp_x0 = pan_xa[0] - knuckle_d / 2; wp_x1 = pan_xa[1] + knuckle_d / 2;

module ycyl(d, h, fn = $fn) { rotate([-90, 0, 0]) cylinder(d = d, h = h, $fn = fn); }

module swing_plate() {
    difference() {
        union() {
            translate([0, 0, -plate_t]) linear_extrude(plate_t)
                rrect(plate_x0, plate_y0, plate_x1 - plate_x0, plate_h, 4);
            // tilt lugs
            for (x = [plate_x0, plate_x1 - lug_w]) hull() {
                translate([x, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(d = knuckle_d, h = lug_w);
                translate([x, hinge_y - knuckle_d / 2, -1]) cube([lug_w, knuckle_d, 1]);
            }
            // pan knuckles, both sides
            for (i = [0, 1], y = pan_knk_y) hull() {
                translate([pan_xa[i], y, pan_z]) ycyl(knuckle_d, knuckle_w);
                translate([pan_xa[i] - 1.5, y, -plate_t]) cube([3, knuckle_w, 0.6]); // narrow foot: must stay inside the swing radius
                translate([i == 0 ? plate_x0 : plate_x1 - 1, y, -plate_t]) cube([1, knuckle_w, plate_t]);
            }
        }
        translate([plate_x0 - 1, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(d = hinge_bore, h = plate_x1 - plate_x0 + 2);
        for (i = [0, 1]) {
            translate([pan_xa[i], pan_y0 - 1, pan_z]) ycyl(hinge_bore, pan_y1 - pan_y0 + 2);
            // nut traps on the inner ends of the knuckles
            translate([pan_xa[i], pan_knk_y[0] + knuckle_w - nut_t, pan_z]) ycyl(nut_af / cos(30), nut_t + 1, 6);
            translate([pan_xa[i], pan_knk_y[1] - 1, pan_z]) ycyl(nut_af / cos(30), nut_t + 1, 6);
        }
        translate([plate_c[0], plate_c[1], -plate_t - 1]) {
            // screwdriver access to the wall screws
            for (sx = [-1, 1]) translate([sx * wall_screw_dx, 0, 0]) cylinder(d = pan_head + 0.6, h = plate_t + 2);
            linear_extrude(plate_t + 2) rrect(-wall_cable[0] / 2, -wall_cable[1] / 2, wall_cable[0], wall_cable[1], 4);
        }
    }
}

module wall_plate() {
    difference() {
        intersection() {
            union() {
                translate([0, 0, wp_z1 - wplate_t]) linear_extrude(wplate_t)
                    rrect(wp_x0, plate_y0, wp_x1 - wp_x0, plate_h, 4);
                for (i = [0, 1], y = pan_lug_y) hull() {
                    translate([pan_xa[i], y, pan_z]) ycyl(knuckle_d, lug_w);
                    translate([pan_xa[i] - knuckle_d / 2, y, wp_z1 - 1]) cube([knuckle_d, lug_w, 1]);
                }
            }
            translate([0, 0, wp_z1 - wplate_t - 1]) linear_extrude(40)
                rrect(wp_x0, plate_y0, wp_x1 - wp_x0, plate_h, 4);
        }
        for (i = [0, 1]) translate([pan_xa[i], pan_y0 - 1, pan_z]) ycyl(hinge_bore, pan_y1 - pan_y0 + 2);
        translate([plate_c[0], plate_c[1], wp_z1 - wplate_t - 1]) {
            for (sx = [-1, 1]) translate([sx * wall_screw_dx, 0, 0]) {
                cylinder(d = wall_screw_d, h = wplate_t + 2);
                translate([0, 0, wplate_t + 1 - pan_head_depth]) cylinder(d = pan_head, h = pan_head_depth + 1);
            }
            linear_extrude(wplate_t + 2) rrect(-wall_cable[0] / 2, -wall_cable[1] / 2, wall_cable[0], wall_cable[1], 4);
        }
    }
}

module pcb_mock() {
    translate([0, 0, pcb_z]) {
        color("green") difference() {
            cube(pcb);
            for (h = mount_holes) translate([P(h)[0], P(h)[1], -1]) cylinder(d = 3.2, h = 4);
        }
        // ESP32-C3 SuperMini on its sockets, USB-C plug
        color("dimgray") translate([34.2, P([0, 69.7])[1], pcb[2] + 11]) cube([18, 22.5, 1]);
        color("black") for (x = [35.56, 50.8]) translate([x - 1.27, P([0, 68.6])[1], pcb[2]]) cube([2.54, 20.3, 8.5]);
        color("silver") translate([usb_x - 4.5, -14, pcb[2] + usb_z - 1.6]) cube([9, 20, 3.2]);
        // LD2410C on its socket (right-hand position)
        color("black") translate([29.21, P([0, 21.6])[1], pcb[2]]) cube([2.54, 12.7, 8.5]);
        color("royalblue") translate([29.2, P([0, 23.24])[1], pcb[2] + 11]) cube([22, 16, 1.2]);
        // JST header and plug, 5 V terminal
        color("white") translate([8.2, -6, pcb[2]]) cube([9.9, 13.6, 4.8]);
        color("seagreen") translate([23.1, 0.1, pcb[2]]) cube([8.1, 8.6, 8.5]);
        for (i = [0 : 2]) color(["lime", "red", "blue"][i])
            translate([P(leds[i])[0], P(leds[i])[1], pcb[2]]) cylinder(d = 3, h = stack_h + headroom + 1);
        color("steelblue") translate([39.85, P([0, 31.75])[1], pcb[2]]) cylinder(d = 8, h = 11.5);
    }
}

module tilted() {
    translate([0, hinge_y, hinge_z]) rotate([tilt, 0, 0]) translate([0, -hinge_y, -hinge_z]) children();
}
module panned() {
    ax = pan_xa[pan >= 0 ? 0 : 1];
    translate([ax, 0, pan_z]) rotate([0, -pan, 0]) translate([-ax, 0, -pan_z]) children();
}

if (part == "body") body();
else if (part == "cover") translate([0, 0, cover_top + top_t]) rotate([180, 0, 0]) cover();
else if (part == "swing_plate") translate([0, 0, plate_t]) swing_plate();
else if (part == "wall_plate") translate([0, 0, wplate_t - wp_z1]) wall_plate();
else if (part == "clash") intersection() {   // must render empty
    wall_plate();
    panned() union() { swing_plate(); tilted() { body(); cover(); } }
}
else {
    color("gainsboro") wall_plate();
    panned() {
        color("lightsteelblue") swing_plate();
        tilted() { body(); pcb_mock(); %cover(); }
    }
}
