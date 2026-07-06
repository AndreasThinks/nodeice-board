// =============================================================================
// Nodeice Board - LED Matrix Case
// =============================================================================
// Two-part 3D-printable case for:
//   - 32x32 RGB LED matrix panel, P4 (128 x 128 x 14 mm), e.g. Pimoroni COM-B007
//   - Raspberry Pi (B form factor: Pi 3/4) + Adafruit RGB Matrix Bonnet
//   - HUB75 ribbon, 5V power, USB Meshtastic node, optional SMA antenna
//
// Parts (set `part` below or via -D on the command line):
//   "front"    - bezel frame; the panel drops in from behind
//   "rear"     - component box; its rim presses the panel against the bezel
//   "assembly" - both parts + panel/Pi ghosts, for a sanity check
//
// The panel is held by a sandwich: a 2 mm front lip (small enough to clear
// the outermost LED lenses of an edge-to-edge P4 panel) and the rear shell's
// rim pressing on the panel's plastic frame from behind. No reliance on the
// panel's rear mounting holes, which vary between manufacturers.
//
// Print: no supports needed. Front: bezel face down. Rear: back wall down.
// =============================================================================

part = "assembly"; // ["front", "rear", "assembly"]

/* [Panel] */
panel_size = 128.0;      // Panel width/height (32px x 4mm pitch)
panel_thickness = 14.0;  // Panel depth including plastic frame
panel_fit = 0.5;         // Clearance per side around the panel
bezel_lip = 2.0;         // How far the front lip overlaps the panel face
panel_rear_clear = 12.0; // Clearance behind panel for its connectors/cables

/* [Case] */
wall = 4.0;              // Main wall thickness
face_thickness = 2.5;    // Front bezel face thickness
back_thickness = 3.0;    // Rear back wall thickness
insert_depth = 12.0;     // How far the rear shell inserts into the front collar
insert_fit = 0.2;        // Clearance per side between collar and insert
corner_radius = 3.0;     // Outer corner rounding
pi_bonnet_stack = 38.0;  // Depth for Pi + bonnet + plugged HUB75 ribbon

/* [Raspberry Pi] */
pi_length = 85;          // Pi B form factor
pi_width = 56;
pi_hole_dx = 58;         // Mounting hole grid
pi_hole_dy = 49;
pi_post_height = 6;      // Standoff height
pi_ports_gap = 2.5;      // Gap between Pi USB ports and the inner wall

/* [Openings] */
usb_opening = [64, 20];        // Right wall: Pi USB/Ethernet (w x h)
power_opening = [52, 18];      // Bottom wall: bonnet DC jack / Pi power / HDMI
antenna_hole_d = 6.5;          // Top wall: SMA antenna passthrough (0 = none)
vent_slot = [24, 3];           // Back wall vent slots (w x h)
keyhole_spacing = 80;          // Wall-hanging keyholes, center to center

/* [Screws] */
// 4x M3 self-tapping screws, 2 per side (left/right), joining the shells
screw_pilot_d = 2.6;
screw_clear_d = 3.4;
screw_head_d = 6.4;
screw_y = 32;            // Screw offset from center along the side walls

/* [Hidden] */
$fn = 48;
eps = 0.01;

// -- Derived dimensions -------------------------------------------------------
cavity = panel_size + 2 * panel_fit;              // 129: panel pocket
outer = cavity + 2 * wall;                        // 137: case outer size
panel_back_z = face_thickness + panel_thickness + panel_fit; // where rear rim lands
front_depth = panel_back_z + insert_depth;        // total front part depth
insert_outer = cavity - 2 * insert_fit;           // rear insert outer size
insert_inner = insert_outer - 2 * wall;           // rear insert inner size
// Body cavity is narrower than the insert's outer face so the two wall
// rings overlap radially (they'd otherwise print as two loose pieces)
body_inner = insert_outer - 4;
rear_inner_depth = panel_rear_clear + pi_bonnet_stack; // rim to inner back wall
rear_total = rear_inner_depth + back_thickness;
screw_z_front = panel_back_z + insert_depth / 2;  // screw height in front coords
screw_z_rear = insert_depth / 2;                  // same, in rear coords

echo(str("Case outer: ", outer, " x ", outer,
         " x ", front_depth + rear_total - insert_depth, " mm"));

// -- Helpers -------------------------------------------------------------------

module rrect(size, r) {
    offset(r = r) square(size - 2 * r, center = true);
}

module shell_2d(size_outer, size_inner, r) {
    difference() {
        rrect(size_outer, r);
        rrect(size_inner, max(r - (size_outer - size_inner) / 2, 0.5));
    }
}

// A slot with rounded ends, centered, lying in the XY plane
module slot_2d(w, h) {
    hull() {
        translate([-(w - h) / 2, 0]) circle(d = h);
        translate([(w - h) / 2, 0]) circle(d = h);
    }
}

// =============================================================================
// FRONT PART
// =============================================================================
module front_part() {
    difference() {
        union() {
            // Bezel face with the display opening
            linear_extrude(face_thickness)
                difference() {
                    rrect(outer, corner_radius);
                    rrect(panel_size - 2 * bezel_lip, 1.5);
                }
            // Walls / collar
            linear_extrude(front_depth)
                shell_2d(outer, cavity, corner_radius);
        }

        // Bevel the bezel opening toward the viewer so the lip doesn't
        // shadow the outermost pixel row at shallow viewing angles:
        // opening is 124 at the panel face, widening to 127 at the front.
        hull() {
            translate([0, 0, -eps])
                linear_extrude(eps) rrect(panel_size - 1, 2);
            translate([0, 0, face_thickness])
                linear_extrude(eps) rrect(panel_size - 2 * bezel_lip, 1.5);
        }

        // Screw clearance holes + counterbores, 2 per side, left and right
        for (sx = [-1, 1], sy = [-1, 1]) {
            translate([sx * outer / 2, sy * screw_y, screw_z_front]) {
                rotate([0, sx * 90, 0]) {
                    cylinder(d = screw_clear_d, h = 2 * wall, center = true);
                    // Counterbore recessed 1.2 mm into the outer face
                    translate([0, 0, -1.2]) cylinder(d = screw_head_d, h = 4);
                }
            }
        }
    }
}

// =============================================================================
// REAR PART
// =============================================================================
module rear_part() {
    difference() {
        union() {
            // Insert section (slides into the front collar; rim presses panel)
            linear_extrude(insert_depth + eps)
                shell_2d(insert_outer, insert_inner, corner_radius - 1);

            // Body section
            translate([0, 0, insert_depth])
                linear_extrude(rear_inner_depth - insert_depth)
                    shell_2d(outer, body_inner, corner_radius);

            // Back wall
            translate([0, 0, rear_inner_depth])
                linear_extrude(back_thickness)
                    rrect(outer, corner_radius);

            // Screw bosses inside the insert walls
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx * (insert_inner / 2 - 2), sy * screw_y, screw_z_rear])
                    cube([8, 12, 10], center = true);

            // Pi mounting posts on the inner back wall
            pi_posts();
        }

        // Lead-in chamfer on the insert tip's outer edge for easy assembly
        difference() {
            translate([0, 0, -eps])
                linear_extrude(1.5 + eps) rrect(insert_outer + 10, 1);
            hull() {
                translate([0, 0, -2 * eps])
                    linear_extrude(eps) rrect(insert_outer - 1.6, corner_radius - 1);
                translate([0, 0, 1.5])
                    linear_extrude(eps) rrect(insert_outer + eps, corner_radius - 1);
            }
        }

        // Screw pilot holes (through insert wall + boss)
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * insert_outer / 2, sy * screw_y, screw_z_rear])
                rotate([0, sx * 90, 0])
                    cylinder(d = screw_pilot_d, h = 2 * (wall + 6), center = true);

        // Right wall: Pi USB / Ethernet opening
        usb_z = rear_inner_depth - pi_post_height - 1.6 - usb_opening[1];
        translate([outer / 2, pi_center_y(), usb_z + usb_opening[1] / 2])
            rotate([90, 0, 90])
                linear_extrude(2 * wall + 2, center = true)
                    slot_2d(usb_opening[0], usb_opening[1]);

        // Bottom wall: DC jack / Pi power / HDMI opening
        pwr_z = rear_inner_depth - pi_post_height - 2 - power_opening[1] / 2 - 8;
        translate([pi_center_x(), -outer / 2, pwr_z])
            rotate([90, 0, 0])
                linear_extrude(2 * wall + 2, center = true)
                    slot_2d(power_opening[0], power_opening[1]);

        // Top wall: SMA antenna passthrough for the Meshtastic node
        if (antenna_hole_d > 0)
            translate([-outer / 4, outer / 2, rear_inner_depth / 2 + insert_depth / 2])
                rotate([-90, 0, 0])
                    cylinder(d = antenna_hole_d, h = 2 * wall + 2, center = true);

        // Top wall: vent slots (heat rises)
        for (x = [-40, 0, 40])
            translate([x, outer / 2, rear_inner_depth - 12])
                rotate([90, 0, 0])
                    linear_extrude(2 * wall + 2, center = true)
                        slot_2d(vent_slot[0], vent_slot[1]);

        // Back wall: vent slot grid (kept clear of the Pi mounting area)
        for (y = [-48, -36, 36, 48], x = [-30, 0, 30])
            translate([x, y, rear_inner_depth - eps])
                linear_extrude(back_thickness + 1)
                    slot_2d(vent_slot[0], vent_slot[1]);

        // Back wall: keyholes for wall hanging (screw head d8, shaft slot d4)
        for (x = [-keyhole_spacing / 2, keyhole_spacing / 2])
            translate([x, 12, rear_inner_depth - eps])
                linear_extrude(back_thickness + 1) {
                    circle(d = 8);
                    translate([0, 5]) square([4, 10], center = true);
                }
    }
}

// Pi is offset so its ports face the right wall opening
function pi_center_x() = insert_inner / 2 - pi_ports_gap - pi_length / 2;
function pi_center_y() = 0;

module pi_posts() {
    for (dx = [-1, 1], dy = [-1, 1])
        translate([pi_center_x() + dx * pi_hole_dx / 2,
                   pi_center_y() + dy * pi_hole_dy / 2,
                   rear_inner_depth - pi_post_height])
            difference() {
                cylinder(d = 7, h = pi_post_height);
                translate([0, 0, -eps]) cylinder(d = 2.0, h = pi_post_height + 1);
            }
}

// =============================================================================
// ASSEMBLY (visual check only - not for printing)
// =============================================================================
module assembly() {
    color("SeaGreen") front_part();
    color("DimGray")
        translate([0, 0, panel_back_z])
            rear_part();
    // Panel ghost
    color("DarkSlateGray", 0.5)
        translate([0, 0, face_thickness])
            linear_extrude(panel_thickness) rrect(panel_size, 1);
    // Pi ghost
    color("Crimson", 0.5)
        translate([pi_center_x() - pi_length / 2,
                   pi_center_y() - pi_width / 2,
                   panel_back_z + rear_inner_depth - pi_post_height - 1.6])
            cube([pi_length, pi_width, 1.6]);
}

if (part == "front") front_part();
else if (part == "rear") rear_part();
else assembly();
