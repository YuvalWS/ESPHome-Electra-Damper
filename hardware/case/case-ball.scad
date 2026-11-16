// Damper controller case on a ball joint: the same body and cover as
// case.scad, without the hinge, on a printed ball-and-socket wall mount.
// The joint aims the case anywhere within about 50 degrees of straight out.
//
// Render one part at a time (STLs come out in print orientation):
//   openscad -D "part=\"body\""    -o body-ball.stl      case-ball.scad
//   openscad -D "part=\"cover\""   -o cover-ball.stl     case-ball.scad
//   openscad -D "part=\"stalk\""   -o ball-stalk.stl     case-ball.scad
//   openscad -D "part=\"base\""    -o ball-base.stl      case-ball.scad
//   openscad -D "part=\"adapter\"" -o tripod-adapter.stl case-ball.scad
//
// "adapter" replaces stalk + base with a captive 1/4"-20 nut, for a bought
// camera ball head or CCTV mount.

include <case.scad>

part = "ball_assembly"; // body | cover | stalk | base | adapter | ball_assembly | ball_clash
tilt = 30;              // assembly only: degrees the face looks down
pan  = 35;              // assembly only: degrees the face looks right; negative = left

hinge = false;
keyholes = [];
back_c = [pcb[0] / 2, pcb[1] / 2];                 // where the stalk meets the back of the body
// An override takes the place of the original assignment in case.scad, so this
// line may only use what case.scad defines before it: pcb, and literals.
back_screws = [for (a = [45 : 90 : 315]) [pcb[0] / 2 + 11 * cos(a), pcb[1] / 2 + 11 * sin(a)]];
flange_screw_r = 11;    // keep equal to the 11 above

ball_r     = 11;
ball_clr   = 0.15;  // socket radius minus ball radius. Smaller = stiffer
ball_flat  = 45;    // the ball is cut flat this far from its pole, to sit on the print bed
neck_r     = 4;
neck_z     = 14;    // ball centre to where the neck starts to flare
flange_r   = 17;
stalk_len  = 29;    // ball centre to the back of the body
core_d     = 2.7;   // pilot for an M3 x 30 screw down the middle of the neck (stiffens it)

socket_wall = 2.8;
socket_past = 15;   // degrees the socket reaches past the equator of the ball
ball_h      = 26;   // wall to ball centre
base_d = 64; base_t = 4;
base_screw_dx = 24; base_screw_d = 4.6;
ear_w = 7; ear_out = 7.5; ear_h = 7;
slit = 2;

socket_ro = ball_r + ball_clr + socket_wall;
rim_z = ball_h + ball_r * sin(socket_past);

// Origin at the centre of the ball, +z towards the case.
module stalk() {
    difference() {
        union() {
            intersection() {
                sphere(r = ball_r);
                translate([0, 0, -ball_r * cos(ball_flat) + 50]) cube(100, center = true);
            }
            cylinder(r = neck_r, h = neck_z + 0.01);
            translate([0, 0, neck_z]) cylinder(r1 = neck_r, r2 = flange_r, h = flange_r - neck_r);
            translate([0, 0, neck_z + flange_r - neck_r - 0.01])
                cylinder(r = flange_r, h = stalk_len - neck_z - flange_r + neck_r + 0.01);
        }
        for (a = [45 : 90 : 315]) rotate([0, 0, a]) translate([flange_screw_r, 0, stalk_len - 7])
            cylinder(d = screw_pilot_d, h = 8);
        translate([0, 0, -5]) cylinder(d = core_d, h = stalk_len + 6);
        translate([0, 0, stalk_len - 3.4]) cylinder(d = 6.6, h = 4);       // head of the core screw
    }
}

// Origin on the wall, under the centre of the ball; +z away from the wall.
module base() {
    ear_y = -(socket_ro + ear_out);
    screw_y = -(socket_ro + 3.6); screw_z = ball_h - 0.5;
    difference() {
        union() {
            cylinder(d = base_d, h = base_t);
            cylinder(r = socket_ro, h = rim_z);
            cylinder(r1 = socket_ro + 5, r2 = socket_ro, h = base_t + 5);
            // clamp ears either side of the slit, undersides sloped for printing
            for (sx = [-1, 1]) hull() {
                translate([sx > 0 ? slit / 2 : -slit / 2 - ear_w, ear_y, rim_z - ear_h])
                    cube([ear_w, ear_out + 1.5, ear_h]);
                translate([sx > 0 ? slit / 2 : -slit / 2 - ear_w, -socket_ro, rim_z - ear_h - ear_out])
                    cube([ear_w, 1.5, 1]);
            }
        }
        translate([0, 0, ball_h]) sphere(r = ball_r + ball_clr);
        // clamp slit (downward side) and a relief slit opposite
        translate([-slit / 2, -socket_ro - ear_out - 1, ball_h - 8]) cube([slit, socket_ro + ear_out - 4, 30]);
        translate([-0.6, 5, ball_h - 3]) cube([1.2, socket_ro, 30]);
        // M3 x 16 clamp screw and its nut
        translate([-20, screw_y, screw_z]) rotate([0, 90, 0]) cylinder(d = hinge_bore, h = 40);
        translate([-slit / 2 - ear_w - 1, screw_y, screw_z]) rotate([0, 90, 0])
            cylinder(d = nut_af / cos(30), h = nut_t + 1, $fn = 6);
        for (sx = [-1, 1]) translate([sx * base_screw_dx, 0, -1]) {
            cylinder(d = base_screw_d, h = base_t + 2);
            translate([0, 0, 1 + base_t - 2.2]) cylinder(d1 = base_screw_d, d2 = 9, h = 2.21);
        }
        // wall cable
        translate([0, 0, -1]) linear_extrude(base_t + 2) rrect(-8, -27, 16, 9, 3);
    }
}

// Captive 1/4"-20 nut on the back of the body. Printed with the body side up.
adapter_t = 9; unc_af = 11.4; unc_nut_t = 6; unc_d = 6.8;
module adapter() {
    difference() {
        cylinder(r = flange_r, h = adapter_t);
        translate([0, 0, -1]) cylinder(d = unc_d, h = adapter_t + 2);
        translate([0, 0, adapter_t - unc_nut_t]) cylinder(d = unc_af / cos(30), h = unc_nut_t + 1, $fn = 6);
        for (a = [45 : 90 : 315]) rotate([0, 0, a]) translate([flange_screw_r, 0, adapter_t - 7])
            cylinder(d = screw_pilot_d, h = 8);
    }
}

module aimed() {
    translate([0, 0, ball_h]) rotate([0, -pan, 0]) rotate([tilt, 0, 0]) translate([0, 0, -ball_h]) children();
}
module on_stalk() { translate([-back_c[0], -back_c[1], ball_h + stalk_len]) children(); }

if (part == "stalk") translate([0, 0, ball_r * cos(ball_flat)]) stalk();
else if (part == "base") base();
else if (part == "adapter") adapter();
else if (part == "ball_clash") {   // must render empty: mount against case, and case against wall
    intersection() {
        base();
        aimed() { translate([0, 0, ball_h]) stalk(); on_stalk() { body(); cover(); } }
    }
    intersection() {
        translate([-200, -200, -50]) cube([400, 400, 50]);
        aimed() on_stalk() { body(); cover(); }
    }
}
else if (part == "ball_assembly") {
    color("gainsboro") base();
    aimed() {
        color("lightsteelblue") translate([0, 0, ball_h]) stalk();
        on_stalk() { body(); pcb_mock(); %cover(); }
    }
}
