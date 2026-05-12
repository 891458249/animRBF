# -*- coding: utf-8 -*-
"""
Help text dictionary for all UI controls — English and Chinese.
"""

from __future__ import absolute_import

from RBFtools.ui.i18n import current_language

_EN = {
    # -- General --
    "active":
        "Enable or disable the node's computation. "
        "When unchecked, the node outputs zero / rest values.",

    "type":
        "Switch between two solver modes:\n"
        "  Vector Angle - single-axis angular / translational blending.\n"
        "  RBF - multi-dimensional pose-based interpolation.",

    "icon_size":
        "Scale factor for the viewport locator icon. "
        "Controls the cone display size in Vector Angle mode.\n\n"
        "This option is only available in Vector Angle mode.",

    # -- Vector Angle --
    "direction":
        "The primary axis used to measure the angle between driver and reader. "
        "X / Y / Z corresponds to the local axis of the driver transform.",

    "invert":
        "Flip the direction axis to measure from the opposite side. "
        "Useful when the driver rotates in the negative direction.",

    "use_rotate":
        "Enable rotation-based driving. The output weight is derived from "
        "the angular difference between the driver and reader matrices.",

    "angle":
        "The cone half-angle (in degrees) at which the output weight "
        "reaches zero. A larger angle means a wider influence range.",

    "center_angle":
        "An offset angle (in degrees) that shifts the center of the "
        "influence cone away from the rest direction.",

    "twist":
        "Enable an additional twist component along the primary axis. "
        "The twist weight is multiplied with the main angular weight.",

    "twist_angle":
        "The twist half-angle (in degrees) at which the twist weight "
        "reaches zero.",

    "use_translate":
        "Enable translation-based driving. The output weight is derived "
        "from the distance between driver and reader along the chosen axis.",

    "grow":
        "When enabled, the weight grows from 0 to 1 as the driver moves "
        "from min to max. When disabled, it shrinks from 1 to 0.",

    "translate_min":
        "The start position (in scene units) of the translation range.",

    "translate_max":
        "The end position (in scene units) of the translation range.",

    "interpolation":
        "The easing curve applied to the output weight:\n"
        "  Linear - constant rate\n"
        "  Slow - ease-in\n"
        "  Fast - ease-out\n"
        "  Smooth1/2 - ease-in-out (two levels)\n"
        "  Curve - custom ramp (edit in Attribute Editor)",

    "draw_cone":
        "Draw the influence cone in the viewport, visualising the "
        "angle range where the weight is non-zero.",

    "draw_center_cone":
        "Draw a second smaller cone representing the center angle offset.",

    "draw_weight":
        "Display a numeric weight label next to the locator in the viewport.",

    # -- RBF --
    "kernel":
        "The radial basis kernel function used to compute pose weights:\n"
        "  Linear - simple distance falloff\n"
        "  Gaussian 1/2 - bell curve (two sharpness levels)\n"
        "  Thin Plate - smooth, good for scattered data\n"
        "  Multi-Quadratic / Inverse - biharmonic variants",

    "radius_type":
        "How the RBF influence radius is calculated:\n"
        "  Mean Distance - average distance between poses\n"
        "  Variance / Std Dev - statistical spread measures\n"
        "  Custom - user-defined radius value",

    "radius":
        "Manual radius value (only editable when Radius Type = Custom). "
        "Smaller values = sharper transitions between poses.",

    "allow_neg":
        "Allow the solver to output negative weights. "
        "Disabling this clamps all weights to >= 0.",

    "rbf_scale":
        "A global multiplier applied to all output values.",

    "rbf_mode":
        "Choose the RBF sub-solver:\n"
        "  Generic - uses per-attribute distance (Euclidean or Angle).\n"
        "  Matrix - uses full transform matrices, supports twist decomposition.",

    "distance_type":
        "Distance metric for the Generic RBF solver:\n"
        "  Euclidean - straight-line distance in attribute space\n"
        "  Angle - angular distance (useful for rotation attributes)",

    "twist_axis":
        "The rotation axis used for twist decomposition "
        "in Matrix RBF mode (X / Y / Z).",

    "draw_origin":
        "Draw a circle at the origin in the viewport.",

    "draw_poses":
        "Draw lines from the origin to each stored pose direction.",

    "pose_length":
        "Visual length of pose direction lines in the viewport.",

    "draw_indices":
        "Display pose index numbers next to each pose marker.",

    "index_distance":
        "Offset distance for index labels from pose markers.",

    "draw_twist":
        "Visualize the twist component of each pose as an additional marker.",

    "opposite":
        "Mirror the pose directions to the opposite hemisphere.",

    "driver_index":
        "When multiple drivers are connected, select which driver's "
        "data to visualize in the viewport.",

    # -- Pose Editor --
    "auto_fill_bs":
        "When adding poses for a BlendShape driven node, "
        "automatically fill target weights as one-hot vectors "
        "(rest = all zeros, each pose = one target at 1.0).",

    "add_pose":
        "Capture the current scene values of the selected driver "
        "and driven attributes and add them as a new pose row.",

    "apply_poses":
        "Write all pose data from the table to the RBF node "
        "and trigger a solver recomputation.",

    "connect_poses":
        "Connect the driver inputs and driven outputs between "
        "the scene nodes and the RBF node.",

    "disconnect_poses":
        "Break all output connections from the RBF node to the driven node. "
        "This frees the driven attributes so you can manually adjust values "
        "to define new poses. Use Connect again when done.",

    "reload_poses":
        "Re-read all pose data from the RBF node in the scene "
        "and refresh the table display.",

    # -- Per-option: Type --
    "type_vector_angle":
        "Vector Angle mode uses a single axis to measure angular and/or "
        "translational distance between a driver and a reader transform.\n\n"
        "Best for simple setups like corrective blendshapes driven by "
        "a single joint rotation. Provides cone-based influence visualization.",

    "type_rbf":
        "RBF (Radial Basis Function) mode uses multi-dimensional pose-based "
        "interpolation to blend between stored poses.\n\n"
        "Best for complex setups where multiple attributes drive multiple "
        "outputs simultaneously. Supports both generic per-attribute distance "
        "and full transform matrix solving.",

    # -- Per-option: Direction --
    "direction_x":
        "Use the local X axis of the driver transform as the primary "
        "measurement direction.\n\n"
        "Typical use: shoulder joints that rotate primarily around X.",

    "direction_y":
        "Use the local Y axis of the driver transform as the primary "
        "measurement direction.\n\n"
        "Typical use: spine or neck joints that bend around Y.",

    "direction_z":
        "Use the local Z axis of the driver transform as the primary "
        "measurement direction.\n\n"
        "Typical use: limb joints that rotate primarily around Z.",

    # -- Per-option: Interpolation --
    "interp_linear":
        "Linear interpolation — constant rate of change.\n\n"
        "The weight changes at a uniform speed from 0 to 1. "
        "No easing, no acceleration. Simplest and most predictable.",

    "interp_slow":
        "Slow (ease-in) — starts slowly, accelerates toward the end.\n\n"
        "The weight ramps up gradually at first, then speeds up. "
        "Good for movements that need a gentle start.",

    "interp_fast":
        "Fast (ease-out) — starts quickly, decelerates toward the end.\n\n"
        "The weight changes rapidly at first, then slows down. "
        "Good for movements that need a snappy start.",

    "interp_smooth1":
        "Smooth 1 (ease-in-out) — slow start and end, faster in the middle.\n\n"
        "A gentle S-curve with moderate smoothing. Good general-purpose "
        "easing for natural-looking transitions.",

    "interp_smooth2":
        "Smooth 2 (ease-in-out, stronger) — more pronounced S-curve.\n\n"
        "Stronger easing than Smooth 1, with a flatter start and end. "
        "Use for softer, more cushioned transitions.",

    "interp_curve":
        "Curve — fully custom ramp curve.\n\n"
        "Open the Attribute Editor to edit the ramp shape directly. "
        "Provides complete control over the falloff profile.",

    # -- Per-option: Kernel --
    "kernel_linear":
        "Linear kernel: \xcf\x86(r) = r\n\n"
        "The simplest kernel — weight falls off linearly with distance. "
        "Produces sharp, tent-like transitions between poses. "
        "Radius Type is ignored (always uses direct distance).\n\n"
        "Pros: Fast, predictable.\n"
        "Cons: Not smooth at pose locations (C\u2070 continuity only).",

    "kernel_gaussian1":
        "Gaussian 1 kernel: \xcf\x86(r) = exp(-r\xc2\xb2)\n\n"
        "Standard bell-curve falloff. Each pose has a smooth, rounded "
        "region of influence that fades to zero. "
        "Radius controls the width of the bell curve.\n\n"
        "Pros: Smooth (C\u221e), well-behaved, most commonly used.\n"
        "Cons: Can produce near-zero weights far from any pose.",

    "kernel_gaussian2":
        "Gaussian 2 kernel: \xcf\x86(r) = exp(-r\xc2\xb2/2)\n\n"
        "A wider variant of the Gaussian bell curve. The '/2' denominator "
        "makes each pose's influence spread further before fading.\n\n"
        "Pros: Broader falloff, smoother blending across distant poses.\n"
        "Cons: Less localised — nearby poses may interfere more.",

    "kernel_thin_plate":
        "Thin Plate Spline kernel: \xcf\x86(r) = r\xc2\xb2 \xc2\xb7 ln(r)\n\n"
        "Inspired by the physical bending of a thin metal plate. "
        "Produces very smooth interpolation with minimal oscillation.\n\n"
        "Pros: Excellent for scattered data, minimal overshoot.\n"
        "Cons: Not strictly positive-definite — may need regularisation.",

    "kernel_multi_quadratic":
        "Multi-Quadratic Biharmonic kernel: \xcf\x86(r) = \u221a(1 + r\xc2\xb2)\n\n"
        "A biharmonic kernel that grows without bound. Produces globally "
        "smooth interpolation where distant poses still contribute.\n\n"
        "Pros: Very smooth, good for large pose sets.\n"
        "Cons: Distant poses may have too much influence; can be slow.",

    "kernel_inv_multi_quadratic":
        "Inverse Multi-Quadratic Biharmonic kernel: \xcf\x86(r) = 1/\u221a(1 + r\xc2\xb2)\n\n"
        "The inverse of the Multi-Quadratic. Influence decays toward zero "
        "for distant poses, providing more localised blending.\n\n"
        "Pros: Smooth and localised, always positive.\n"
        "Cons: May produce very small weights for distant poses.",

    # -- Per-option: Radius Type --
    "rtype_mean_distance":
        "Mean Distance — the radius is set to the average of all pairwise "
        "distances between stored poses.\n\n"
        "A robust automatic choice that adapts to the overall spread of "
        "your pose data. Works well in most situations.",

    "rtype_variance":
        "Variance — the radius is set to the statistical variance of "
        "inter-pose distances.\n\n"
        "Produces a wider radius than Mean Distance when poses are "
        "unevenly distributed. Use when poses are clustered.",

    "rtype_std_dev":
        "Standard Deviation — the radius is the square root of the variance.\n\n"
        "A balanced middle ground between Mean Distance and Variance. "
        "Often provides the most natural-looking transitions.",

    "rtype_custom":
        "Custom — manually set the radius value using the Radius spinner.\n\n"
        "Full control over the influence width. Smaller values produce "
        "sharper transitions; larger values produce smoother blending.\n"
        "Required for fine-tuning edge cases.",

    # -- Per-option: RBF Mode --
    "rbf_mode_generic":
        "Generic RBF — computes distance in per-attribute space.\n\n"
        "Each driver attribute (translate X, rotate Y, etc.) is treated "
        "as an independent dimension. Distance is measured using the "
        "chosen Distance Type (Euclidean or Angle).\n\n"
        "Best for: attribute-driven setups, non-transform drivers.",

    "rbf_mode_matrix":
        "Matrix RBF — computes distance using full 4x4 transform matrices.\n\n"
        "The driver's world-space matrix is decomposed for distance "
        "calculation, with optional twist decomposition along a chosen axis.\n\n"
        "Best for: transform-driven setups, joint-based rigs where "
        "rotation order matters.",

    # -- Per-option: Distance Type --
    "dist_euclidean":
        "Euclidean distance — straight-line distance in attribute space.\n\n"
        "d = sqrt(sum((a_i - b_i)^2))\n\n"
        "Standard distance metric. Works well for translation and "
        "general numeric attributes. May be less ideal for pure rotation "
        "attributes due to gimbal effects.",

    "dist_angle":
        "Angular distance — measures the angle between attribute vectors.\n\n"
        "Treats each set of driver attributes as a direction vector and "
        "computes the angle between them. Ideal for rotation-only drivers "
        "where magnitude doesn't matter, only direction.",

    # -- Per-option: Twist Axis --
    "twist_axis_x":
        "Decompose twist around the X axis.\n\n"
        "The rotation matrix is split into a twist component around X "
        "and a swing component perpendicular to X. "
        "Use for joints whose primary roll axis is X (e.g., forearm twist).",

    "twist_axis_y":
        "Decompose twist around the Y axis.\n\n"
        "The rotation matrix is split into a twist component around Y "
        "and a swing component perpendicular to Y. "
        "Use for joints whose primary roll axis is Y.",

    "twist_axis_z":
        "Decompose twist around the Z axis.\n\n"
        "The rotation matrix is split into a twist component around Z "
        "and a swing component perpendicular to Z. "
        "Use for joints whose primary roll axis is Z.",

    # -- M2.4a: M1.4 / M2.1a / M1.3 attrs --

    "regularization":
        "Tikhonov regularization strength (lambda).\n\n"
        "Added to the kernel matrix diagonal before solve to prevent "
        "near-singular configurations from blowing up the weight "
        "matrix. Default 1e-8 follows v5 PART G.1 Step 2; absolute "
        "units (NOT scale-adaptive) so it works on Linear / Thin "
        "Plate kernels where the diagonal is zero.",

    "solver_method":
        "Auto: Cholesky first; falls back to GE (Gaussian Elimination) "
        "on non-SPD kernel matrices.\n"
        "ForceGE: skips Cholesky entirely, useful for debugging or "
        "rigs that exhibit numeric quirks under Cholesky.\n\n"
        "M4.5 will extend this enum to {Auto, ForceCholesky, ForceQR, "
        "ForceLU, ForceSVD} once Eigen integration lands the full "
        "four-tier fallback chain.",

    "input_encoding":
        # M_HELPTEXT_INPUT_ENCODING (2026-04-29): expanded from the
        # 6-line summary to a full 5-encoding usage guide so the TD
        # can pick the right encoding without leaving the UI.
        "How driver attributes are encoded before distance computation. "
        "The right encoding choice is critical for natural RBF "
        "interpolation:\n\n"
        "1. Raw (Euler angles, channel-box values)\n"
        "  - Logic: reads rotateX/Y/Z directly from the channel box.\n"
        "  - Pros/Cons: simplest but NOT recommended for complex 3D "
        "rotation. Suffers from gimbal lock - when a bone rotates "
        "past 90 deg or flips, the X/Y/Z values jump discontinuously, "
        "RBF distance becomes wrong, and target bones snap "
        "unpredictably.\n"
        "  - Use case: single-axis hinges only (door axis, piston).\n\n"
        "2. Quaternion (w, x, y, z)\n"
        "  - Logic: convert rotation to a unit quaternion.\n"
        "  - Pros/Cons: gimbal-lock free + flip-free, but quaternions "
        "are 4D - Euclidean distance between 4D vectors is sometimes "
        "less linear than 3D in human perception.\n"
        "  - Use case: full 360-deg rotation controllers without "
        "swing/twist split needs.\n\n"
        "3. ExpMap (Exponential Map / log-quaternion) - * RBF favorite\n"
        "  - Logic: an elegant 3D rotation representation. The "
        "rotation is encoded as a 3D vector whose DIRECTION is the "
        "rotation axis and whose LENGTH is the angle.\n"
        "  - Pros/Cons: the BEST partner for RBF. Gimbal-lock-free "
        "like quaternions, 3D like Euler. Distance in ExpMap space "
        "matches our real-world feel for angular difference. "
        "Transitions are extremely smooth.\n"
        "  - Use case: the default pick for most non-linear "
        "many-to-many RBF deformation drivers - facial expressions, "
        "complex muscle helper bones.\n\n"
        "4. SwingTwist - * limb-rigging favorite\n"
        "  - Logic: decompose any rotation into two independent "
        "motions:\n"
        "      Swing - bone pointing direction (up/down/left/right, "
        "like a compass needle).\n"
        "      Twist - rotation along the bone's own axis.\n"
        "  - Pros/Cons: highly targeted. Rigging often needs to "
        "drive shoulder muscles 'only by upper-arm raise (Swing)' "
        "while 'ignoring upper-arm twist', or vice versa. SwingTwist "
        "isolates the relevant rotation channel.\n"
        "  - Use case: helper bones for shoulders, wrists, hips. "
        "E.g. take wrist Twist and drive forearm roll bones.\n\n"
        "5. BendRoll\n"
        "  - Logic: similar to SwingTwist but the algorithm "
        "emphasises separating axis-bending (Bend) from axis-rolling "
        "(Roll).\n"
        "  - Use case: spline IK, tentacles, spines, long-chain "
        "structures where local bend extraction is the goal.",

    # M_HELPTEXT_ENC_PER_KEY (2026-04-29): per-encoding help keys.
    # ComboHelpButton in rbf_section.py:233 uses key_map = ["enc_raw",
    # "enc_quaternion", "enc_bendroll", "enc_expmap", "enc_swingtwist"]
    # — _help_key_for_index returns the indexed key inside range, never
    # falling back to "input_encoding" for valid combo selections.
    # Without these keys get_help_text returns "" -> empty HelpBubble.
    # The five entries below mirror the d01a964 input_encoding long-
    # form guide split into per-encoding subsections so each combo
    # value shows the relevant content.
    "enc_raw":
        "Raw (Euler) — read driver bone's Rotate X/Y/Z Euler "
        "values directly.\n\n"
        "Pros: simplest.\n"
        "Cons: Gimbal lock — when bone rotation exceeds ~90° or "
        "flips, X/Y/Z values jump discontinuously, RBF distance "
        "becomes meaningless, driven bones explode.\n\n"
        "Use case: simple single-axis mechanical structures only "
        "(door hinges, pistons).",

    "enc_quaternion":
        "Quaternion — convert rotation to (w, x, y, z) "
        "quaternion.\n\n"
        "Pros: gimbal-lock free, handles 360° rotation correctly.\n"
        "Cons: 4D vector — Euclidean distance is less linearly "
        "intuitive than 3D.\n\n"
        "Use case: full-360 controllers without twist-decomposition "
        "needs.",

    "enc_bendroll":
        "BendRoll — decompose rotation into bend (axis "
        "perpendicular to bone) and roll (axis along the bone).\n\n"
        "Pros: similar to SwingTwist but optimized for bend/roll "
        "separation on certain axis combinations.\n\n"
        "Use case: spline IK / spine / tentacle-like long-chain "
        "rigs where local bend extraction is needed.",

    "enc_expmap":
        u"ExpMap (Exponential Map) — ★ RBF FAVORITE\n\n"
        "Represents rotation as a 3D vector: direction = rotation "
        "axis, length = rotation angle.\n\n"
        "Pros: gimbal-lock-free like Quaternion + only 3D like "
        "Euler. Distance in ExpMap space matches human angle "
        "perception. Smoothest interpolation.\n\n"
        "Use case: most multi-to-many non-linear RBF deformation "
        "drives (facial expressions, complex muscle helper bones) "
        "— first choice.",

    "enc_swingtwist":
        u"SwingTwist — ★ LIMB RIG FAVORITE\n\n"
        "Decompose rotation into:\n"
        u"  · Swing — bone direction (compass-like; "
        "up/down/left/right pointing)\n"
        u"  · Twist — bone self-axis rotation\n\n"
        "Pros: lets you isolate one axis. e.g. drive shoulder "
        "muscles by arm-up-amount (swing) while ignoring arm-twist "
        "(twist).\n\n"
        "Use case: shoulder, wrist, hip helper bones. e.g. extract "
        "wrist twist to drive forearm twist bones.",

    "clamp_enabled":
        "Clip live driver inputs to the per-dimension min/max bounds of "
        "the registered pose samples before kernel evaluation. Prevents "
        "out-of-training-range inputs from blowing up RBF activations.",

    "clamp_inflation":
        "Symmetric outward inflation as a fraction of the per-dim range. "
        "0.0 is hard clamp (PART G.7); small positive values give a "
        "softer hull to dampen edge-pop on near-boundary inputs.",

    "output_is_scale":
        "Mark this output channel as a SCALE component. Scale outputs "
        "anchor at 1.0 instead of the captured rest value, defending "
        "against t-pose mesh collapse when the captured baseline is 0.",

    # -- M2.4b: per-driver-group rotateOrder + quat group editors --

    "driver_rotate_order":
        "Per-driver-group rotateOrder for non-Raw input encodings.\n\n"
        "When inputEncoding != Raw, driver attributes are consumed in "
        "(rx, ry, rz) triples; each triple is one driver group whose "
        "Euler-to-quaternion conversion needs the matching rotateOrder. "
        "The list ordering is [group0, group1, ...] aligned with the "
        "driver inputs in left-to-right order.\n\n"
        "Use the +/- buttons to add/remove groups; enum values match "
        "Maya's native rotateOrder dropdown (xyz / yzx / zxy / xzy / "
        "yxz / zyx). Missing entries fall back to xyz.",

    "quat_group_start":
        "Output indices that start a 4-slot quaternion group (M2.2 "
        "QWA). Each entered start S declares output[S..S+3] is a unit "
        "quaternion that should be solved via quaternion-weighted "
        "average instead of scalar weighted sum.\n\n"
        "Invalid entries (out-of-range, overlapping, or colliding with "
        "an outputIsScale flag inside the 4-slot range) are dropped at "
        "compute() time with a one-time warning — the rig keeps "
        "evaluating; the dropped groups simply revert to scalar output.",

    # -- M_HELPBUBBLE_BATCH (2026-04-29): red-frame-area HelpButton
    # coverage. Each interactive widget in the Output Encoding /
    # RBF Pose Editor outer tabs / Driver Sources / Driven Targets
    # / Utility / Tools sections gets a long-form HelpButton bubble
    # describing function + typical usage + edge cases (decision E.1).
    "output_encoding":
        "Node-level output encoding for the driven values fed into "
        "the C++ output[] array.\n\n"
        "  · Euler — the default; raw 3-tuple Euler angles.\n"
        "  · Quaternion — driven groups represent unit quaternions; "
        "matches the inputEncoding=Quaternion flow on the input side.\n"
        "  · ExpMap — driven groups encoded as exponential map "
        "vectors; pairs with the per-driver-group rotateOrder for "
        "consistent reconstruction at evaluation time.\n\n"
        "Switch this to match the encoding your downstream rig "
        "expects. A mismatch here typically shows up as drift on "
        "extreme rotations rather than an outright break.",

    # -- M_P1_ENC_COMBO_FIX (2026-04-29): per-output-encoding keys
    # for the OutputEncodingCombo's ComboHelpButton. Mirrors
    # M_HELPTEXT_ENC_PER_KEY's input-encoding split — each item
    # gets its own bubble describing semantics + typical usage +
    # edge cases instead of the merged "output_encoding" blob.
    "output_enc_euler":
        "Output Encoding — Euler (default)\n\n"
        "Each driven attribute group is a raw Euler triple "
        "(rx, ry, rz). The C++ compute() weighted-sum is applied "
        "directly per channel; no quaternion or exp-map "
        "reconstruction step.\n\n"
        "★ Default for joint translate / rotate channels and any "
        "driven attribute that is NOT inherently rotational "
        "(blendshape weights, custom scalars, scale).\n\n"
        "Edge: gimbal-influenced extreme rotations on a single "
        "Euler triple can drift on multi-pose blends; switch to "
        "Quaternion or ExpMap for those cases.",

    "output_enc_quaternion":
        "Output Encoding — Quaternion\n\n"
        "Driven attribute groups are interpreted as unit "
        "quaternions (4 channels per group). C++ compute() runs a "
        "quaternion-weighted average (M2.2 QWA) instead of a "
        "scalar weighted sum, preserving rotation continuity "
        "across the unit hypersphere.\n\n"
        "Pairs naturally with inputEncoding=Quaternion and with "
        "the outputQuaternionGroupStart[] list that declares "
        "where each 4-slot group starts in the output array.\n\n"
        "Edge: groups whose 4-slot range collides with an "
        "outputIsScale flag are dropped at compute() with a "
        "one-time warning — the rig keeps evaluating, dropped "
        "groups simply revert to scalar output.",

    "output_enc_expmap":
        "Output Encoding — ExpMap (Exponential Map)\n\n"
        "Driven attribute groups are encoded as 3-component "
        "exp-map vectors. The C++ compute() interpolates in "
        "exp-map space and reconstructs rotations on read; works "
        "well for medium-range rotations without the gimbal "
        "artifacts of raw Euler.\n\n"
        "★ Useful when the driven side is a single rotational "
        "joint (twist corrective, bend joint) and you need "
        "smoother blend behaviour than Euler but don't want to "
        "spend the extra channel of a quaternion group.\n\n"
        "Edge: large rotations near the pi-radian shell can fold "
        "back through the origin — keep the per-pose rotation "
        "magnitudes inside |angle| < pi to avoid antipodal jumps.",

    "outer_tabs_overview":
        "Three-tab navigation for the RBF Pose Editor:\n"
        "  · DriverDriven — pick the driver bones / attrs and the "
        "driven joints / attrs the solver maps between. Edits here "
        "rebuild the per-pose schema.\n"
        "  · BaseDrivenPose — the rest / baseline output values per "
        "driven attr; subtracted from each pose so deltas are what "
        "the solver actually interpolates.\n"
        "  · Pose — the live pose grid: add new poses, recall / "
        "delete existing ones, edit per-row driver + driven "
        "samples.\n\n"
        "Switching tabs is non-destructive; all three views read "
        "from the same active node.",

    "source_tab_connect":
        "Wire the currently selected attrs from THIS tab's source "
        "(driver or driven) into the active node's "
        "input[] / output[] arrays.\n\n"
        "Path-A semantics — operates on the per-tab attribute list "
        "directly; no pose data is touched. Idempotent: clicking "
        "twice on the same selection reuses existing slots.\n\n"
        "When the panel-level Batch checkbox is on, Connect sweeps "
        "EVERY tab in the panel instead of just the active one — "
        "useful for re-applying the same attribute set to all "
        "drivers at once.",

    "source_tab_disconnect":
        "Tear down the input[] / output[] array slots wired by "
        "Connect for this tab's source.\n\n"
        "Walks the precise per-attribute connections so other "
        "tabs / unrelated nodes are untouched. After Disconnect "
        "the node still keeps its driverSource[] / drivenSource[] "
        "metadata entry — only the data path is broken; "
        "Add Driver / Add Driven is NOT undone.\n\n"
        "Batch checkbox: when on, Disconnect runs across every "
        "tab in the panel.",

    "source_tab_add_driver":
        "Append a new driver source tab to the active node and "
        "open it for attribute selection.\n\n"
        "Each driver source maps to one driverSource[] entry on the "
        "shape — a (node, attrs, weight, encoding) tuple with the "
        "driver's .message connected to driverSource_node.\n\n"
        "Pick the driver bone / control object first, then choose "
        "which of its attrs participate. Duplicate (bone, attr) "
        "pairs across sources are allowed but rarely useful.",

    "source_tab_add_driven":
        "Append a new driven source tab and open it for attribute "
        "selection.\n\n"
        "Each driven source maps to one drivenSource[] entry — the "
        "joint / control whose attrs the RBF compute will write "
        "into. Select all driven attrs the solver should drive on "
        "this object before clicking Connect.\n\n"
        "Driven attributes participate in the M2.4a per-attribute "
        "outputIsScale flag list; defaults to non-scale (translate / "
        "rotate / blendshape semantics).",

    "source_tab_batch_driver":
        "When checked, panel-level Connect / Disconnect operate on "
        "EVERY driver tab simultaneously instead of only the "
        "currently-active one.\n\n"
        "Use this to re-broadcast the same attribute set to a list "
        "of similarly-set-up driver bones (e.g. an arm chain) "
        "without click-cycling tabs. The Add Driver button is NOT "
        "affected — that always creates one new tab.\n\n"
        "Batch is a session-only flag; not persisted on the node.",

    "source_tab_batch_driven":
        "When checked, panel-level Connect / Disconnect operate on "
        "EVERY driven tab simultaneously instead of only the "
        "currently-active one.\n\n"
        "Useful when several driven joints share the same attr "
        "list (e.g. a row of corrective blendshapes). Add Driven "
        "always creates one new tab regardless of this flag.\n\n"
        "Batch is a session-only flag; not persisted on the node.",

    "btn_split_solver_per_joint":
        "Split this multi-driven RBF solver into one solver-per-"
        "joint copy.\n\n"
        "Useful for breaking up a heavy node when profiling shows "
        "compute() dominated by a single driver feeding many "
        "outputs that could evaluate independently. Each new node "
        "inherits the same driver topology + the subset of pose "
        "values relevant to its driven joint.\n\n"
        "Destructive on the original node — best run on a "
        "duplicate first to compare evaluation parity.",

    "cleanup_modes_overview":
        "Three cleanup modes share the Remove Unnecessary Datas "
        "button below; pick one before clicking it.\n\n"
        "  · Remove Connectionless Input — drops input[] slots "
        "with no upstream connection, then renumbers downstream "
        "data so pose vectors stay aligned.\n"
        "  · Remove Connectionless Output — same idea on the "
        "output side; useful after blendshape / joint pruning.\n"
        "  · Remove Redundant Pose — drops poses whose driver "
        "vector duplicates another pose's within tolerance.\n\n"
        "All three are destructive but reversible by undo.",

    "btn_remove_unnecessary_datas":
        "Run the cleanup mode selected above (one of: connection-"
        "less input, connectionless output, or redundant pose).\n\n"
        "The button reads the radio selection at click time, so "
        "you can switch modes between runs. Status output goes "
        "to the Maya Script Editor — review it before saving the "
        "scene; the cleanup may have changed the pose / attribute "
        "count.\n\n"
        "Single undo step; safe to repeat.",

    "btn_refresh_profile":
        "Run the per-node profiler and render the report inline.\n\n"
        "The profile is intentionally NOT auto-recomputed on node "
        "switch — large rigs can take a noticeable second to "
        "summarize, and the data is read-only context (pose count, "
        "input / output dimensionality, kernel / radius signature, "
        "per-driver weight totals).\n\n"
        "The report is a snapshot; click Refresh again after any "
        "structural edit (Add / Remove driver, pose changes) to "
        "see updated numbers.",
}

_ZH = {
    # -- General --
    "active":
        u"\u542f\u7528\u6216\u7981\u7528\u8282\u70b9\u8ba1\u7b97\u3002"
        u"\u5173\u95ed\u65f6\u8282\u70b9\u8f93\u51fa\u96f6/\u4f11\u606f\u503c\u3002",

    "type":
        u"\u5207\u6362\u6c42\u89e3\u5668\u6a21\u5f0f:\n"
        u"  \u5411\u91cf\u89d2\u5ea6 \u2014 \u5355\u8f74\u89d2\u5ea6/\u5e73\u79fb\u6df7\u5408\u3002\n"
        u"  RBF \u2014 \u591a\u7ef4\u59ff\u6001\u63d2\u503c\u3002",

    "icon_size":
        u"\u89c6\u53e3\u5b9a\u4f4d\u5668\u56fe\u6807\u7684\u7f29\u653e\u7cfb\u6570\u3002"
        u"\u63a7\u5236\u5411\u91cf\u89d2\u5ea6\u6a21\u5f0f\u4e0b\u7684\u5706\u9525\u663e\u793a\u5927\u5c0f\u3002\n\n"
        u"\u6b64\u9009\u9879\u4ec5\u5728\u5411\u91cf\u89d2\u5ea6\u6a21\u5f0f\u4e0b\u53ef\u7528\u3002",

    # -- Vector Angle --
    "direction":
        u"\u7528\u4e8e\u6d4b\u91cf\u9a71\u52a8\u5668\u4e0e\u8bfb\u53d6\u5668\u4e4b\u95f4\u89d2\u5ea6\u7684\u4e3b\u8f74\u3002"
        u"X/Y/Z \u5bf9\u5e94\u9a71\u52a8\u53d8\u6362\u7684\u5c40\u90e8\u8f74\u3002",

    "invert":
        u"\u7ffb\u8f6c\u65b9\u5411\u8f74\uff0c\u4ece\u53cd\u65b9\u5411\u6d4b\u91cf\u3002"
        u"\u5f53\u9a71\u52a8\u5668\u5411\u8d1f\u65b9\u5411\u65cb\u8f6c\u65f6\u5f88\u6709\u7528\u3002",

    "use_rotate":
        u"\u542f\u7528\u57fa\u4e8e\u65cb\u8f6c\u7684\u9a71\u52a8\u3002"
        u"\u8f93\u51fa\u6743\u91cd\u7531\u9a71\u52a8\u5668\u4e0e\u8bfb\u53d6\u5668\u77e9\u9635\u7684\u89d2\u5ea6\u5dee\u5f02\u5f97\u51fa\u3002",

    "angle":
        u"\u5706\u9525\u534a\u89d2\uff08\u5ea6\uff09\uff0c\u5728\u6b64\u89d2\u5ea6\u5904\u8f93\u51fa\u6743\u91cd\u53d8\u4e3a\u96f6\u3002"
        u"\u89d2\u5ea6\u8d8a\u5927\uff0c\u5f71\u54cd\u8303\u56f4\u8d8a\u5bbd\u3002",

    "center_angle":
        u"\u504f\u79fb\u89d2\u5ea6\uff08\u5ea6\uff09\uff0c\u5c06\u5f71\u54cd\u5706\u9525\u7684\u4e2d\u5fc3\u4ece\u4f11\u606f\u65b9\u5411\u79fb\u5f00\u3002",

    "twist":
        u"\u542f\u7528\u6cbf\u4e3b\u8f74\u7684\u989d\u5916\u626d\u8f6c\u5206\u91cf\u3002"
        u"\u626d\u8f6c\u6743\u91cd\u4e0e\u4e3b\u89d2\u5ea6\u6743\u91cd\u76f8\u4e58\u3002",

    "twist_angle":
        u"\u626d\u8f6c\u534a\u89d2\uff08\u5ea6\uff09\uff0c\u5728\u6b64\u89d2\u5ea6\u5904\u626d\u8f6c\u6743\u91cd\u53d8\u4e3a\u96f6\u3002",

    "use_translate":
        u"\u542f\u7528\u57fa\u4e8e\u5e73\u79fb\u7684\u9a71\u52a8\u3002"
        u"\u8f93\u51fa\u6743\u91cd\u7531\u9a71\u52a8\u5668\u6cbf\u6307\u5b9a\u8f74\u7684\u8ddd\u79bb\u5f97\u51fa\u3002",

    "grow":
        u"\u542f\u7528\u65f6\uff0c\u6743\u91cd\u4ece min \u5230 max \u7531 0\u21921 \u589e\u957f\u3002"
        u"\u7981\u7528\u65f6\uff0c\u4ece 1\u21920 \u9012\u51cf\u3002",

    "translate_min":
        u"\u5e73\u79fb\u8303\u56f4\u7684\u8d77\u59cb\u4f4d\u7f6e\uff08\u573a\u666f\u5355\u4f4d\uff09\u3002",

    "translate_max":
        u"\u5e73\u79fb\u8303\u56f4\u7684\u7ed3\u675f\u4f4d\u7f6e\uff08\u573a\u666f\u5355\u4f4d\uff09\u3002",

    "interpolation":
        u"\u5e94\u7528\u4e8e\u8f93\u51fa\u6743\u91cd\u7684\u7f13\u52a8\u66f2\u7ebf:\n"
        u"  Linear \u2014 \u7ebf\u6027\n"
        u"  Slow \u2014 \u6162\u5165\n"
        u"  Fast \u2014 \u6162\u51fa\n"
        u"  Smooth1/2 \u2014 \u5e73\u6ed1\u8fc7\u6e21\n"
        u"  Curve \u2014 \u81ea\u5b9a\u4e49\u66f2\u7ebf\uff08\u5728\u5c5e\u6027\u7f16\u8f91\u5668\u4e2d\u7f16\u8f91\uff09",

    "draw_cone":
        u"\u5728\u89c6\u53e3\u4e2d\u7ed8\u5236\u5f71\u54cd\u5706\u9525\uff0c\u53ef\u89c6\u5316\u6743\u91cd\u975e\u96f6\u7684\u89d2\u5ea6\u8303\u56f4\u3002",

    "draw_center_cone":
        u"\u7ed8\u5236\u8868\u793a\u4e2d\u5fc3\u89d2\u5ea6\u504f\u79fb\u7684\u7b2c\u4e8c\u4e2a\u8f83\u5c0f\u5706\u9525\u3002",

    "draw_weight":
        u"\u5728\u89c6\u53e3\u4e2d\u5b9a\u4f4d\u5668\u65c1\u663e\u793a\u6570\u5b57\u6743\u91cd\u6807\u7b7e\u3002",

    # -- RBF --
    "kernel":
        u"RBF \u6838\u51fd\u6570:\n"
        u"  Linear \u2014 \u7b80\u5355\u8ddd\u79bb\u8870\u51cf\n"
        u"  Gaussian 1/2 \u2014 \u949f\u5f62\u66f2\u7ebf\n"
        u"  Thin Plate \u2014 \u5149\u6ed1\uff0c\u9002\u5408\u5206\u6563\u6570\u636e\n"
        u"  Multi-Quadratic / Inverse \u2014 \u53cc\u8c10\u53d8\u4f53",

    "radius_type":
        u"RBF \u5f71\u54cd\u534a\u5f84\u7684\u8ba1\u7b97\u65b9\u5f0f:\n"
        u"  Mean Distance \u2014 \u59ff\u6001\u95f4\u5e73\u5747\u8ddd\u79bb\n"
        u"  Variance / Std Dev \u2014 \u7edf\u8ba1\u79bb\u6563\u5ea6\n"
        u"  Custom \u2014 \u7528\u6237\u81ea\u5b9a\u4e49\u534a\u5f84\u503c",

    "radius":
        u"\u624b\u52a8\u534a\u5f84\u503c\uff08\u4ec5\u5728\u534a\u5f84\u7c7b\u578b = Custom \u65f6\u53ef\u7f16\u8f91\uff09\u3002"
        u"\u503c\u8d8a\u5c0f\uff0c\u59ff\u6001\u95f4\u8fc7\u6e21\u8d8a\u9510\u5229\u3002",

    "allow_neg":
        u"\u5141\u8bb8\u6c42\u89e3\u5668\u8f93\u51fa\u8d1f\u6743\u91cd\u3002"
        u"\u7981\u7528\u65f6\u6240\u6709\u6743\u91cd\u88ab\u9650\u5236\u4e3a \u2265 0\u3002",

    "rbf_scale":
        u"\u5e94\u7528\u4e8e\u6240\u6709\u8f93\u51fa\u503c\u7684\u5168\u5c40\u7f29\u653e\u7cfb\u6570\u3002",

    "rbf_mode":
        u"\u9009\u62e9 RBF \u5b50\u6c42\u89e3\u5668:\n"
        u"  Generic \u2014 \u4f7f\u7528\u6bcf\u5c5e\u6027\u8ddd\u79bb\uff08\u6b27\u6c0f\u6216\u89d2\u5ea6\uff09\u3002\n"
        u"  Matrix \u2014 \u4f7f\u7528\u5b8c\u6574\u53d8\u6362\u77e9\u9635\uff0c\u652f\u6301\u626d\u8f6c\u5206\u89e3\u3002",

    "distance_type":
        u"Generic RBF \u7684\u8ddd\u79bb\u5ea6\u91cf:\n"
        u"  Euclidean \u2014 \u5c5e\u6027\u7a7a\u95f4\u4e2d\u7684\u76f4\u7ebf\u8ddd\u79bb\n"
        u"  Angle \u2014 \u89d2\u8ddd\u79bb\uff08\u9002\u5408\u65cb\u8f6c\u5c5e\u6027\uff09",

    "twist_axis":
        u"Matrix RBF \u6a21\u5f0f\u4e0b\u626d\u8f6c\u5206\u89e3\u4f7f\u7528\u7684\u65cb\u8f6c\u8f74 (X/Y/Z)\u3002",

    "draw_origin":
        u"\u5728\u89c6\u53e3\u4e2d\u539f\u70b9\u5904\u7ed8\u5236\u4e00\u4e2a\u5706\u3002",

    "draw_poses":
        u"\u4ece\u539f\u70b9\u5230\u6bcf\u4e2a\u5b58\u50a8\u59ff\u6001\u65b9\u5411\u7ed8\u5236\u7ebf\u6761\u3002",

    "pose_length":
        u"\u89c6\u53e3\u4e2d\u59ff\u6001\u65b9\u5411\u7ebf\u7684\u89c6\u89c9\u957f\u5ea6\u3002",

    "draw_indices":
        u"\u5728\u6bcf\u4e2a\u59ff\u6001\u6807\u8bb0\u65c1\u663e\u793a\u59ff\u6001\u7d22\u5f15\u7f16\u53f7\u3002",

    "index_distance":
        u"\u7d22\u5f15\u6807\u7b7e\u4e0e\u59ff\u6001\u6807\u8bb0\u7684\u504f\u79fb\u8ddd\u79bb\u3002",

    "draw_twist":
        u"\u4ee5\u989d\u5916\u6807\u8bb0\u53ef\u89c6\u5316\u6bcf\u4e2a\u59ff\u6001\u7684\u626d\u8f6c\u5206\u91cf\u3002",

    "opposite":
        u"\u5c06\u59ff\u6001\u65b9\u5411\u955c\u50cf\u5230\u76f8\u53cd\u7684\u534a\u7403\u3002",

    "driver_index":
        u"\u5f53\u8fde\u63a5\u4e86\u591a\u4e2a\u9a71\u52a8\u5668\u65f6\uff0c"
        u"\u9009\u62e9\u5728\u89c6\u53e3\u4e2d\u53ef\u89c6\u5316\u54ea\u4e2a\u9a71\u52a8\u5668\u7684\u6570\u636e\u3002",

    # -- Pose Editor --
    "auto_fill_bs":
        u"\u4e3a BlendShape \u88ab\u9a71\u52a8\u8282\u70b9\u6dfb\u52a0\u59ff\u6001\u65f6\uff0c"
        u"\u81ea\u52a8\u586b\u5145\u76ee\u6807\u6743\u91cd\u4e3a one-hot \u5411\u91cf\u3002",

    "add_pose":
        u"\u6355\u6349\u5f53\u524d\u573a\u666f\u4e2d\u9009\u5b9a\u7684\u9a71\u52a8/\u88ab\u9a71\u52a8\u5c5e\u6027\u503c\uff0c"
        u"\u4f5c\u4e3a\u65b0\u59ff\u6001\u884c\u6dfb\u52a0\u3002",

    "apply_poses":
        u"\u5c06\u8868\u683c\u4e2d\u7684\u6240\u6709\u59ff\u6001\u6570\u636e\u5199\u5165 RBF \u8282\u70b9\uff0c"
        u"\u5e76\u89e6\u53d1\u6c42\u89e3\u5668\u91cd\u65b0\u8ba1\u7b97\u3002",

    "connect_poses":
        u"\u5c06\u573a\u666f\u8282\u70b9\u7684\u9a71\u52a8\u8f93\u5165\u548c\u88ab\u9a71\u52a8\u8f93\u51fa\u4e0e RBF \u8282\u70b9\u8fde\u63a5\u3002",

    "disconnect_poses":
        u"\u65ad\u5f00 RBF \u8282\u70b9\u5230\u88ab\u9a71\u52a8\u8282\u70b9\u7684\u6240\u6709\u8f93\u51fa\u8fde\u63a5\u3002"
        u"\u8fd9\u6837\u60a8\u53ef\u4ee5\u624b\u52a8\u8c03\u8282\u88ab\u9a71\u52a8\u5c5e\u6027\u6765\u5b9a\u4e49\u65b0\u59ff\u6001\u3002"
        u"\u5b8c\u6210\u540e\u518d\u6b21\u70b9\u51fb\u8fde\u63a5\u5373\u53ef\u3002",

    "reload_poses":
        u"\u4ece\u573a\u666f\u4e2d\u7684 RBF \u8282\u70b9\u91cd\u65b0\u8bfb\u53d6\u6240\u6709\u59ff\u6001\u6570\u636e\uff0c"
        u"\u5237\u65b0\u8868\u683c\u663e\u793a\u3002",

    # -- Per-option: Type --
    "type_vector_angle":
        u"\u5411\u91cf\u89d2\u5ea6\u6a21\u5f0f\u4f7f\u7528\u5355\u8f74\u6765\u6d4b\u91cf\u9a71\u52a8\u5668\u4e0e\u8bfb\u53d6\u5668\u53d8\u6362\u4e4b\u95f4\u7684\u89d2\u5ea6\u548c/\u6216\u5e73\u79fb\u8ddd\u79bb\u3002\n\n"
        u"\u6700\u9002\u5408\u7b80\u5355\u8bbe\u7f6e\uff0c\u4f8b\u5982\u7531\u5355\u4e2a\u5173\u8282\u65cb\u8f6c\u9a71\u52a8\u7684\u4fee\u6b63\u6df7\u5408\u53d8\u5f62\u3002\u63d0\u4f9b\u5706\u9525\u5f71\u54cd\u8303\u56f4\u53ef\u89c6\u5316\u3002",

    "type_rbf":
        u"RBF\uff08\u5f84\u5411\u57fa\u51fd\u6570\uff09\u6a21\u5f0f\u4f7f\u7528\u591a\u7ef4\u59ff\u6001\u63d2\u503c\u5728\u5b58\u50a8\u7684\u59ff\u6001\u4e4b\u95f4\u8fdb\u884c\u6df7\u5408\u3002\n\n"
        u"\u6700\u9002\u5408\u591a\u4e2a\u5c5e\u6027\u540c\u65f6\u9a71\u52a8\u591a\u4e2a\u8f93\u51fa\u7684\u590d\u6742\u8bbe\u7f6e\u3002\u652f\u6301\u901a\u7528\u9010\u5c5e\u6027\u8ddd\u79bb\u548c\u5b8c\u6574\u53d8\u6362\u77e9\u9635\u6c42\u89e3\u3002",

    # -- Per-option: Direction --
    "direction_x":
        u"\u4f7f\u7528\u9a71\u52a8\u53d8\u6362\u7684\u5c40\u90e8 X \u8f74\u4f5c\u4e3a\u4e3b\u8981\u6d4b\u91cf\u65b9\u5411\u3002\n\n"
        u"\u5178\u578b\u7528\u9014\uff1a\u4e3b\u8981\u56f4\u7ed5 X \u8f74\u65cb\u8f6c\u7684\u80a9\u5173\u8282\u3002",

    "direction_y":
        u"\u4f7f\u7528\u9a71\u52a8\u53d8\u6362\u7684\u5c40\u90e8 Y \u8f74\u4f5c\u4e3a\u4e3b\u8981\u6d4b\u91cf\u65b9\u5411\u3002\n\n"
        u"\u5178\u578b\u7528\u9014\uff1a\u56f4\u7ed5 Y \u8f74\u5f2f\u66f2\u7684\u810a\u67f1\u6216\u9888\u90e8\u5173\u8282\u3002",

    "direction_z":
        u"\u4f7f\u7528\u9a71\u52a8\u53d8\u6362\u7684\u5c40\u90e8 Z \u8f74\u4f5c\u4e3a\u4e3b\u8981\u6d4b\u91cf\u65b9\u5411\u3002\n\n"
        u"\u5178\u578b\u7528\u9014\uff1a\u4e3b\u8981\u56f4\u7ed5 Z \u8f74\u65cb\u8f6c\u7684\u80a2\u4f53\u5173\u8282\u3002",

    # -- Per-option: Interpolation --
    "interp_linear":
        u"\u7ebf\u6027\u63d2\u503c - \u6052\u5b9a\u53d8\u5316\u7387\u3002\n\n"
        u"\u6743\u91cd\u4ece 0 \u5230 1 \u4ee5\u5747\u5300\u901f\u5ea6\u53d8\u5316\u3002\u65e0\u7f13\u52a8\uff0c\u65e0\u52a0\u901f\u3002\u6700\u7b80\u5355\u4e14\u6700\u53ef\u9884\u6d4b\u3002",

    "interp_slow":
        u"\u6162\u901f\uff08\u7f13\u5165\uff09- \u5f00\u59cb\u7f13\u6162\uff0c\u5411\u672b\u5c3e\u52a0\u901f\u3002\n\n"
        u"\u6743\u91cd\u8d77\u521d\u7f13\u6162\u4e0a\u5347\uff0c\u7136\u540e\u52a0\u901f\u3002\u9002\u5408\u9700\u8981\u5e73\u7f13\u5f00\u59cb\u7684\u8fd0\u52a8\u3002",

    "interp_fast":
        u"\u5feb\u901f\uff08\u7f13\u51fa\uff09- \u5f00\u59cb\u5feb\u901f\uff0c\u5411\u672b\u5c3e\u51cf\u901f\u3002\n\n"
        u"\u6743\u91cd\u8d77\u521d\u5feb\u901f\u53d8\u5316\uff0c\u7136\u540e\u51cf\u6162\u3002\u9002\u5408\u9700\u8981\u5feb\u901f\u542f\u52a8\u7684\u8fd0\u52a8\u3002",

    "interp_smooth1":
        u"\u5e73\u6ed1 1\uff08\u7f13\u5165\u7f13\u51fa\uff09- \u5f00\u59cb\u548c\u7ed3\u675f\u7f13\u6162\uff0c\u4e2d\u95f4\u8f83\u5feb\u3002\n\n"
        u"\u6e29\u548c\u7684 S \u66f2\u7ebf\uff0c\u5177\u6709\u9002\u5ea6\u5e73\u6ed1\u3002\u901a\u7528\u7684\u7f13\u52a8\u9009\u62e9\uff0c\u9002\u5408\u81ea\u7136\u8fc7\u6e21\u3002",

    "interp_smooth2":
        u"\u5e73\u6ed1 2\uff08\u7f13\u5165\u7f13\u51fa\uff0c\u66f4\u5f3a\uff09- \u66f4\u660e\u663e\u7684 S \u66f2\u7ebf\u3002\n\n"
        u"\u6bd4\u5e73\u6ed1 1 \u66f4\u5f3a\u7684\u7f13\u52a8\u6548\u679c\uff0c\u5f00\u59cb\u548c\u7ed3\u675f\u66f4\u5e73\u5766\u3002\u7528\u4e8e\u66f4\u67d4\u548c\u7684\u8fc7\u6e21\u3002",

    "interp_curve":
        u"\u66f2\u7ebf - \u5b8c\u5168\u81ea\u5b9a\u4e49\u6e10\u53d8\u66f2\u7ebf\u3002\n\n"
        u"\u6253\u5f00\u5c5e\u6027\u7f16\u8f91\u5668\u76f4\u63a5\u7f16\u8f91\u6e10\u53d8\u5f62\u72b6\u3002\u63d0\u4f9b\u5bf9\u8870\u51cf\u66f2\u7ebf\u7684\u5b8c\u5168\u63a7\u5236\u3002",

    # -- Per-option: Kernel --
    "kernel_linear":
        u"\u7ebf\u6027\u6838\u51fd\u6570: \u03c6(r) = r\n\n"
        u"\u6700\u7b80\u5355\u7684\u6838\u51fd\u6570 - \u6743\u91cd\u968f\u8ddd\u79bb\u7ebf\u6027\u8870\u51cf\u3002\u5728\u59ff\u6001\u4e4b\u95f4\u4ea7\u751f\u5c16\u9510\u7684\u5e10\u7bf7\u72b6\u8fc7\u6e21\u3002"
        u"\u534a\u5f84\u7c7b\u578b\u88ab\u5ffd\u7565\uff08\u59cb\u7ec8\u4f7f\u7528\u76f4\u63a5\u8ddd\u79bb\uff09\u3002\n\n"
        u"\u4f18\u70b9\uff1a\u5feb\u901f\u3001\u53ef\u9884\u6d4b\u3002\n"
        u"\u7f3a\u70b9\uff1a\u5728\u59ff\u6001\u4f4d\u7f6e\u4e0d\u5149\u6ed1\uff08\u4ec5 C\u2070 \u8fde\u7eed\u6027\uff09\u3002",

    "kernel_gaussian1":
        u"\u9ad8\u65af 1 \u6838\u51fd\u6570: \u03c6(r) = exp(-r\xb2)\n\n"
        u"\u6807\u51c6\u949f\u5f62\u66f2\u7ebf\u8870\u51cf\u3002\u6bcf\u4e2a\u59ff\u6001\u5177\u6709\u5e73\u6ed1\u3001\u5706\u6da6\u7684\u5f71\u54cd\u533a\u57df\uff0c\u9010\u6e10\u8870\u51cf\u4e3a\u96f6\u3002"
        u"\u534a\u5f84\u63a7\u5236\u949f\u5f62\u66f2\u7ebf\u7684\u5bbd\u5ea6\u3002\n\n"
        u"\u4f18\u70b9\uff1a\u5149\u6ed1\uff08C\u221e\uff09\uff0c\u8868\u73b0\u826f\u597d\uff0c\u6700\u5e38\u7528\u3002\n"
        u"\u7f3a\u70b9\uff1a\u8fdc\u79bb\u6240\u6709\u59ff\u6001\u65f6\u53ef\u80fd\u4ea7\u751f\u63a5\u8fd1\u96f6\u7684\u6743\u91cd\u3002",

    "kernel_gaussian2":
        u"\u9ad8\u65af 2 \u6838\u51fd\u6570: \u03c6(r) = exp(-r\xb2/2)\n\n"
        u"\u9ad8\u65af\u949f\u5f62\u66f2\u7ebf\u7684\u66f4\u5bbd\u53d8\u4f53\u3002'/2' \u5206\u6bcd\u4f7f\u6bcf\u4e2a\u59ff\u6001\u7684\u5f71\u54cd\u6269\u5c55\u66f4\u8fdc\u3002\n\n"
        u"\u4f18\u70b9\uff1a\u66f4\u5bbd\u7684\u8870\u51cf\uff0c\u8de8\u8fdc\u8ddd\u79bb\u59ff\u6001\u66f4\u5e73\u6ed1\u7684\u6df7\u5408\u3002\n"
        u"\u7f3a\u70b9\uff1a\u5c40\u90e8\u6027\u8f83\u5dee - \u76f8\u90bb\u59ff\u6001\u53ef\u80fd\u5e72\u6270\u66f4\u591a\u3002",

    "kernel_thin_plate":
        u"\u8584\u677f\u6837\u6761\u6838\u51fd\u6570: \u03c6(r) = r\xb2 \xb7 ln(r)\n\n"
        u"\u7075\u611f\u6765\u81ea\u8584\u91d1\u5c5e\u677f\u7684\u7269\u7406\u5f2f\u66f2\u3002\u4ea7\u751f\u975e\u5e38\u5e73\u6ed1\u7684\u63d2\u503c\uff0c\u632f\u8361\u6700\u5c0f\u3002\n\n"
        u"\u4f18\u70b9\uff1a\u975e\u5e38\u9002\u5408\u5206\u6563\u6570\u636e\uff0c\u6700\u5c0f\u8fc7\u51b2\u3002\n"
        u"\u7f3a\u70b9\uff1a\u975e\u4e25\u683c\u6b63\u5b9a - \u53ef\u80fd\u9700\u8981\u6b63\u5219\u5316\u3002",

    "kernel_multi_quadratic":
        u"\u591a\u91cd\u4e8c\u6b21\u53cc\u8c03\u548c\u6838\u51fd\u6570: \u03c6(r) = \u221a(1 + r\xb2)\n\n"
        u"\u4e00\u79cd\u65e0\u9650\u589e\u957f\u7684\u53cc\u8c03\u548c\u6838\u51fd\u6570\u3002\u4ea7\u751f\u5168\u5c40\u5e73\u6ed1\u7684\u63d2\u503c\uff0c\u8fdc\u8ddd\u79bb\u59ff\u6001\u4ecd\u6709\u8d21\u732e\u3002\n\n"
        u"\u4f18\u70b9\uff1a\u975e\u5e38\u5e73\u6ed1\uff0c\u9002\u5408\u5927\u578b\u59ff\u6001\u96c6\u3002\n"
        u"\u7f3a\u70b9\uff1a\u8fdc\u8ddd\u79bb\u59ff\u6001\u53ef\u80fd\u5f71\u54cd\u8fc7\u5927\uff1b\u53ef\u80fd\u8f83\u6162\u3002",

    "kernel_inv_multi_quadratic":
        u"\u9006\u591a\u91cd\u4e8c\u6b21\u53cc\u8c03\u548c\u6838\u51fd\u6570: \u03c6(r) = 1/\u221a(1 + r\xb2)\n\n"
        u"\u591a\u91cd\u4e8c\u6b21\u7684\u9006\u3002\u8fdc\u8ddd\u79bb\u59ff\u6001\u7684\u5f71\u54cd\u8870\u51cf\u4e3a\u96f6\uff0c\u63d0\u4f9b\u66f4\u5c40\u90e8\u7684\u6df7\u5408\u3002\n\n"
        u"\u4f18\u70b9\uff1a\u5149\u6ed1\u4e14\u5c40\u90e8\u5316\uff0c\u59cb\u7ec8\u4e3a\u6b63\u3002\n"
        u"\u7f3a\u70b9\uff1a\u8fdc\u8ddd\u79bb\u59ff\u6001\u53ef\u80fd\u4ea7\u751f\u975e\u5e38\u5c0f\u7684\u6743\u91cd\u3002",

    # -- Per-option: Radius Type --
    "rtype_mean_distance":
        u"\u5e73\u5747\u8ddd\u79bb - \u534a\u5f84\u8bbe\u7f6e\u4e3a\u6240\u6709\u59ff\u6001\u4e4b\u95f4\u6210\u5bf9\u8ddd\u79bb\u7684\u5e73\u5747\u503c\u3002\n\n"
        u"\u4e00\u79cd\u7a33\u5065\u7684\u81ea\u52a8\u9009\u62e9\uff0c\u9002\u5e94\u59ff\u6001\u6570\u636e\u7684\u6574\u4f53\u5206\u5e03\u3002\u5728\u5927\u591a\u6570\u60c5\u51b5\u4e0b\u6548\u679c\u826f\u597d\u3002",

    "rtype_variance":
        u"\u65b9\u5dee - \u534a\u5f84\u8bbe\u7f6e\u4e3a\u59ff\u6001\u95f4\u8ddd\u79bb\u7684\u7edf\u8ba1\u65b9\u5dee\u3002\n\n"
        u"\u5f53\u59ff\u6001\u5206\u5e03\u4e0d\u5747\u5300\u65f6\uff0c\u4ea7\u751f\u6bd4\u5e73\u5747\u8ddd\u79bb\u66f4\u5bbd\u7684\u534a\u5f84\u3002\u9002\u5408\u59ff\u6001\u805a\u96c6\u7684\u60c5\u51b5\u3002",

    "rtype_std_dev":
        u"\u6807\u51c6\u5dee - \u534a\u5f84\u4e3a\u65b9\u5dee\u7684\u5e73\u65b9\u6839\u3002\n\n"
        u"\u4ecb\u4e8e\u5e73\u5747\u8ddd\u79bb\u548c\u65b9\u5dee\u4e4b\u95f4\u7684\u5e73\u8861\u9009\u62e9\u3002\u901a\u5e38\u63d0\u4f9b\u6700\u81ea\u7136\u7684\u8fc7\u6e21\u6548\u679c\u3002",

    "rtype_custom":
        u"\u81ea\u5b9a\u4e49 - \u4f7f\u7528\u534a\u5f84\u5fae\u8c03\u5668\u624b\u52a8\u8bbe\u7f6e\u534a\u5f84\u503c\u3002\n\n"
        u"\u5b8c\u5168\u63a7\u5236\u5f71\u54cd\u5bbd\u5ea6\u3002\u8f83\u5c0f\u7684\u503c\u4ea7\u751f\u66f4\u9510\u5229\u7684\u8fc7\u6e21\uff1b\u8f83\u5927\u7684\u503c\u4ea7\u751f\u66f4\u5e73\u6ed1\u7684\u6df7\u5408\u3002\n"
        u"\u7528\u4e8e\u5fae\u8c03\u8fb9\u7f18\u60c5\u51b5\u3002",

    # -- Per-option: RBF Mode --
    "rbf_mode_generic":
        u"\u901a\u7528 RBF - \u5728\u9010\u5c5e\u6027\u7a7a\u95f4\u4e2d\u8ba1\u7b97\u8ddd\u79bb\u3002\n\n"
        u"\u6bcf\u4e2a\u9a71\u52a8\u5c5e\u6027\uff08\u5e73\u79fb X\u3001\u65cb\u8f6c Y \u7b49\uff09\u88ab\u89c6\u4e3a\u72ec\u7acb\u7ef4\u5ea6\u3002\u4f7f\u7528\u9009\u5b9a\u7684\u8ddd\u79bb\u7c7b\u578b"
        u"\uff08\u6b27\u51e0\u91cc\u5f97\u6216\u89d2\u5ea6\uff09\u6d4b\u91cf\u8ddd\u79bb\u3002\n\n"
        u"\u6700\u9002\u5408\uff1a\u5c5e\u6027\u9a71\u52a8\u8bbe\u7f6e\u3001\u975e\u53d8\u6362\u9a71\u52a8\u5668\u3002",

    "rbf_mode_matrix":
        u"\u77e9\u9635 RBF - \u4f7f\u7528\u5b8c\u6574 4\u00d74 \u53d8\u6362\u77e9\u9635\u8ba1\u7b97\u8ddd\u79bb\u3002\n\n"
        u"\u9a71\u52a8\u5668\u7684\u4e16\u754c\u7a7a\u95f4\u77e9\u9635\u88ab\u5206\u89e3\u7528\u4e8e\u8ddd\u79bb\u8ba1\u7b97\uff0c\u53ef\u9009\u6cbf\u6307\u5b9a\u8f74\u8fdb\u884c\u626d\u8f6c\u5206\u89e3\u3002\n\n"
        u"\u6700\u9002\u5408\uff1a\u53d8\u6362\u9a71\u52a8\u8bbe\u7f6e\u3001\u57fa\u4e8e\u5173\u8282\u7684\u7ed1\u5b9a\uff08\u65cb\u8f6c\u987a\u5e8f\u5f88\u91cd\u8981\u7684\u60c5\u51b5\uff09\u3002",

    # -- Per-option: Distance Type --
    "dist_euclidean":
        u"\u6b27\u51e0\u91cc\u5f97\u8ddd\u79bb - \u5c5e\u6027\u7a7a\u95f4\u4e2d\u7684\u76f4\u7ebf\u8ddd\u79bb\u3002\n\n"
        u"d = \u221a(\u03a3(a_i - b_i)\xb2)\n\n"
        u"\u6807\u51c6\u8ddd\u79bb\u5ea6\u91cf\u3002\u9002\u5408\u5e73\u79fb\u548c\u4e00\u822c\u6570\u503c\u5c5e\u6027\u3002\u7531\u4e8e\u4e07\u5411\u9501\u6548\u5e94\uff0c\u53ef\u80fd\u4e0d\u592a\u9002\u5408\u7eaf\u65cb\u8f6c\u5c5e\u6027\u3002",

    "dist_angle":
        u"\u89d2\u8ddd\u79bb - \u6d4b\u91cf\u5c5e\u6027\u5411\u91cf\u4e4b\u95f4\u7684\u89d2\u5ea6\u3002\n\n"
        u"\u5c06\u6bcf\u7ec4\u9a71\u52a8\u5c5e\u6027\u89c6\u4e3a\u65b9\u5411\u5411\u91cf\u5e76\u8ba1\u7b97\u5b83\u4eec\u4e4b\u95f4\u7684\u89d2\u5ea6\u3002"
        u"\u9002\u5408\u4ec5\u65cb\u8f6c\u7684\u9a71\u52a8\u5668\uff0c\u5176\u4e2d\u5927\u5c0f\u65e0\u5173\u7d27\u8981\uff0c\u53ea\u5173\u6ce8\u65b9\u5411\u3002",

    # -- Per-option: Twist Axis --
    "twist_axis_x":
        u"\u56f4\u7ed5 X \u8f74\u5206\u89e3\u626d\u8f6c\u3002\n\n"
        u"\u65cb\u8f6c\u77e9\u9635\u88ab\u5206\u89e3\u4e3a\u56f4\u7ed5 X \u7684\u626d\u8f6c\u5206\u91cf\u548c\u5782\u76f4\u4e8e X \u7684\u6446\u52a8\u5206\u91cf\u3002"
        u"\u9002\u7528\u4e8e\u4e3b\u8981\u6eda\u52a8\u8f74\u4e3a X \u7684\u5173\u8282\uff08\u5982\u524d\u81c2\u626d\u8f6c\uff09\u3002",

    "twist_axis_y":
        u"\u56f4\u7ed5 Y \u8f74\u5206\u89e3\u626d\u8f6c\u3002\n\n"
        u"\u65cb\u8f6c\u77e9\u9635\u88ab\u5206\u89e3\u4e3a\u56f4\u7ed5 Y \u7684\u626d\u8f6c\u5206\u91cf\u548c\u5782\u76f4\u4e8e Y \u7684\u6446\u52a8\u5206\u91cf\u3002"
        u"\u9002\u7528\u4e8e\u4e3b\u8981\u6eda\u52a8\u8f74\u4e3a Y \u7684\u5173\u8282\u3002",

    "twist_axis_z":
        u"\u56f4\u7ed5 Z \u8f74\u5206\u89e3\u626d\u8f6c\u3002\n\n"
        u"\u65cb\u8f6c\u77e9\u9635\u88ab\u5206\u89e3\u4e3a\u56f4\u7ed5 Z \u7684\u626d\u8f6c\u5206\u91cf\u548c\u5782\u76f4\u4e8e Z \u7684\u6446\u52a8\u5206\u91cf\u3002"
        u"\u9002\u7528\u4e8e\u4e3b\u8981\u6eda\u52a8\u8f74\u4e3a Z \u7684\u5173\u8282\u3002",

    # -- M2.4a --

    "regularization":
        u"Tikhonov \u6b63\u5219\u5316\u5f3a\u5ea6 (lambda)\u3002\n\n"
        u"\u6c42\u89e3\u524d\u52a0\u5728\u6838\u77e9\u9635\u5bf9\u89d2\u7ebf\u4e0a\uff0c\u9632\u8fd1\u5947\u5f02\u73af\u5883\u4e0b\u6743\u91cd\u77e9\u9635\u7206\u53d1\u3002"
        u"\u9ed8\u8ba4 1e-8\uff08v5 PART G.1\uff09\uff0c\u7edd\u5bf9\u503c\u4e0d\u968f\u6838\u77e9\u9635\u5c3a\u5ea6\u81ea\u9002\u5e94\u3002",

    "solver_method":
        u"Auto\uff1aCholesky \u4f18\u5148\uff0c\u975e SPD \u77e9\u9635\u56de\u9000 GE\u3002\n"
        u"ForceGE\uff1a\u8df3\u8fc7 Cholesky\uff0c\u8c03\u8bd5\u7528\u3002\n\n"
        u"M4.5 \u5f15\u5165 Eigen \u540e\u6269\u5c55\u4e3a 5 \u6863\u5b8c\u6574 fallback\u3002",

    "input_encoding":
        # M_HELPTEXT_INPUT_ENCODING (2026-04-29): full 5-encoding
        # usage guide replacing the prior 7-line summary.
        u"\u4ee5\u4e0b\u662f\u8fd9\u4e94\u79cd\u8f93\u5165\u7684\u8be6\u7ec6\u533a\u522b\u548c\u9002\u7528\u573a\u666f:\n\n"
        u"1. Raw(\u539f\u59cb\u6570\u636e / \u6b27\u62c9\u89d2)\n"
        u"  \u00b7 \u903b\u8f91:\u76f4\u63a5\u8bfb\u53d6\u9aa8\u9abc\u901a\u9053\u76d2\u91cc\u7684 Rotate X\u3001Y\u3001Z \u7684\u6b27\u62c9\u89d2"
        u"\u6570\u503c\u3002\n"
        u"  \u00b7 \u4f18\u7f3a\u70b9:\u6700\u7b80\u5355\u7c97\u66b4,\u4f46\u6781\u5176\u4e0d\u63a8\u8350\u7528\u4e8e\u590d\u6742\u7684\u7a7a\u95f4\u65cb\u8f6c\u3002"
        u"\u56e0\u4e3a\u5b83\u4f1a\u53d7\u5230\u4e07\u5411\u8282\u6b7b\u9501(Gimbal Lock)\u7684\u5f71\u54cd\u3002\u5f53\u9aa8\u9abc\u65cb\u8f6c"
        u"\u8d85\u8fc7 90 \u5ea6\u6216\u53d1\u751f\u7ffb\u8f6c\u65f6,X\u3001Y\u3001Z \u7684\u6570\u503c\u4f1a\u53d1\u751f\u5267\u70c8\u8df3\u53d8,"
        u"\u5bfc\u81f4 RBF \u7b97\u51fa\u7684'\u8ddd\u79bb'\u5b8c\u5168\u9519\u8bef,\u76ee\u6807\u9aa8\u9abc\u4f1a\u77ac\u95f4\u4e71\u98de\u3002\n"
        u"  \u00b7 \u9002\u7528\u573a\u666f:\u53ea\u505a\u5355\u8f74\u65cb\u8f6c\u7684\u7b80\u5355\u673a\u68b0\u7ed3\u6784(\u5982\u5355\u5411\u95e8\u8f74\u3001"
        u"\u6d3b\u585e)\u3002\n\n"
        u"2. Quaternion(\u56db\u5143\u6570)\n"
        u"  \u00b7 \u903b\u8f91:\u5c06\u65cb\u8f6c\u8f6c\u6362\u4e3a\u56db\u5143\u6570(w, x, y, z)\u8fdb\u884c\u8ba1\u7b97\u3002\n"
        u"  \u00b7 \u4f18\u7f3a\u70b9:\u5b8c\u7f8e\u89e3\u51b3\u4e86\u4e07\u5411\u8282\u6b7b\u9501\u548c\u7ffb\u8f6c\u95ee\u9898\u3002\u4f46\u5728 RBF \u4e2d,"
        u"\u56db\u5143\u6570\u662f 4 \u7ef4\u5411\u91cf,\u8ba1\u7b97\u4e24\u4e2a 4 \u7ef4\u5411\u91cf\u7684\u6b27\u6c0f\u8ddd\u79bb\u6709\u65f6\u4e0d\u5982 "
        u"3 \u7ef4\u5411\u91cf\u5728\u76f4\u89c9\u4e0a\u90a3\u4e48\u7ebf\u6027\u3002\n"
        u"  \u00b7 \u9002\u7528\u573a\u666f:\u9700\u8981\u5168\u7a7a\u95f4 360 \u5ea6\u65e0\u6b7b\u89d2\u65cb\u8f6c\u7684\u63a7\u5236\u5668,"
        u"\u4e14\u4e0d\u6d89\u53ca\u590d\u6742\u7684\u626d\u66f2\u62c6\u5206\u65f6\u3002\n\n"
        u"3. ExpMap(\u6307\u6570\u6620\u5c04)\u2014 \u2605 RBF \u6700\u5e38\u7528\n"
        u"  \u00b7 \u903b\u8f91:\u6781\u5176\u4f18\u96c5\u7684 3D \u65cb\u8f6c\u8868\u793a\u6cd5\u3002\u5c06\u65cb\u8f6c\u8868\u793a\u4e3a\u4e00\u4e2a "
        u"3D \u5411\u91cf,\u5411\u91cf\u7684\u65b9\u5411\u4ee3\u8868\u65cb\u8f6c\u8f74,\u5411\u91cf\u7684\u957f\u5ea6\u4ee3\u8868\u65cb\u8f6c\u7684\u89d2\u5ea6\u3002\n"
        u"  \u00b7 \u4f18\u7f3a\u70b9:RBF \u7cfb\u7edf\u7684\u6700\u4f73\u642d\u6863!\u65e2\u50cf\u56db\u5143\u6570\u4e00\u6837\u6ca1\u6709\u4e07\u5411"
        u"\u8282\u6b7b\u9501,\u53c8\u50cf\u6b27\u62c9\u89d2\u4e00\u6837\u53ea\u6709 3 \u4e2a\u7ef4\u5ea6\u3002\u5728 ExpMap \u7a7a\u95f4\u4e2d"
        u"\u8ba1\u7b97\u4e24\u4e2a\u59ff\u6001\u7684'\u8ddd\u79bb',\u975e\u5e38\u7b26\u5408\u73b0\u5b9e\u4e2d\u5bf9\u89d2\u5ea6\u5dee\u5f02\u7684\u611f\u77e5\u3002"
        u"\u8fc7\u6e21\u6781\u5176\u5e73\u6ed1\u3002\n"
        u"  \u00b7 \u9002\u7528\u573a\u666f:\u5927\u591a\u6570\u591a\u5bf9\u591a\u3001\u975e\u7ebf\u6027\u7684 RBF \u5f62\u53d8\u9a71\u52a8"
        u"(\u5982\u9762\u90e8\u8868\u60c5\u3001\u590d\u6742\u7684\u808c\u8089\u8f85\u52a9\u9aa8\u9abc)\u7684\u9996\u9009\u3002\n\n"
        u"4. SwingTwist(\u6446\u52a8\u4e0e\u626d\u66f2)\u2014 \u2605 \u80a2\u4f53\u7ed1\u5b9a\u6700\u5e38\u7528\n"
        u"  \u00b7 \u903b\u8f91:\u5c06\u590d\u6742\u7684\u65cb\u8f6c\u62c6\u89e3\u4e3a\u4e24\u4e2a\u72ec\u7acb\u7684\u8fd0\u52a8:\n"
        u"      Swing(\u6446\u52a8):\u9aa8\u9abc\u50cf\u5706\u89c4\u4e00\u6837\u6307\u5411\u4e0a\u3001\u4e0b\u3001\u5de6\u3001\u53f3"
        u"\u7684\u65b9\u5411\u3002\n"
        u"      Twist(\u626d\u66f2/\u81ea\u8f6c):\u9aa8\u9abc\u6cbf\u7740\u81ea\u8eab\u7684\u8f74\u7ebf\u65cb\u8f6c\u3002\n"
        u"  \u00b7 \u4f18\u7f3a\u70b9:\u6781\u5177\u9488\u5bf9\u6027\u3002\u7ed1\u5b9a\u4e2d\u5e38\u9700'\u53ea\u6839\u636e\u5927\u81c2\u62ac\u8d77\u7684\u9ad8\u5ea6"
        u"(Swing)\u9a71\u52a8\u80a9\u8180\u808c\u8089',\u800c'\u5ffd\u7565\u5927\u81c2\u7684\u81ea\u8f6c(Twist)',"
        u"\u6216\u8005\u53cd\u8fc7\u6765\u3002SwingTwist \u53ef\u4ee5\u5265\u79bb\u4e0d\u9700\u8981\u7684\u65cb\u8f6c\u4fe1\u606f\u3002\n"
        u"  \u00b7 \u9002\u7528\u573a\u666f:\u80a9\u8180\u3001\u624b\u8155\u3001\u5927\u817f\u6839\u90e8(Hip)\u7684\u8f85\u52a9\u9aa8\u9abc\u9a71\u52a8\u3002"
        u"\u6bd4\u5982\u63d0\u53d6\u624b\u8155\u7684 Twist \u53bb\u9a71\u52a8\u5c0f\u81c2\u7684\u7ffb\u8f6c\u9aa8\u9abc\u3002\n\n"
        u"5. BendRoll(\u5f2f\u66f2\u4e0e\u7ffb\u6eda)\n"
        u"  \u00b7 \u903b\u8f91:\u7c7b\u4f3c\u4e8e SwingTwist,\u4f46\u7b97\u6cd5\u66f4\u4fa7\u91cd\u4e8e\u5c06\u4e3b\u8f74\u7684\u5f2f\u66f2"
        u"(Bend)\u548c\u6cbf\u8f74\u7684\u7ffb\u6eda(Roll)\u5206\u79bb\u5f00\u6765\u3002\n"
        u"  \u00b7 \u9002\u7528\u573a\u666f:\u901a\u5e38\u7528\u4e8e\u6837\u6761\u7ebf IK(Spline IK)\u6216\u89e6\u624b\u3001"
        u"\u810a\u690e\u7b49\u957f\u6761\u72b6\u7ed3\u6784\u7684\u7ed1\u5b9a,\u63d0\u53d6\u5c40\u90e8\u7684\u5f2f\u66f2\u7a0b\u5ea6\u3002",

    # M_HELPTEXT_ENC_PER_KEY (2026-04-29): ZH per-encoding mirror.
    # \u2605 U+2605 / \u00b7 U+00B7 / \u4e07\u5411\u8282\u6b7b\u9501 / RBF \u6700\u5e38\u7528 / \u80a2\u4f53\u7ed1\u5b9a\u6700\u5e38\u7528
    # \u2014 verbatim Chinese rigging vocabulary preserved from d01a964.
    "enc_raw":
        u"Raw(\u539f\u59cb\u6570\u636e / \u6b27\u62c9\u89d2)\u2014 "
        u"\u76f4\u63a5\u8bfb\u53d6\u9aa8\u9abc\u901a\u9053\u76d2\u91cc\u7684 "
        u"Rotate X\u3001Y\u3001Z \u7684\u6b27\u62c9\u89d2\u6570\u503c\u3002\n\n"
        u"\u4f18\u70b9:\u6700\u7b80\u5355\u3002\n"
        u"\u7f3a\u70b9:\u4e07\u5411\u8282\u6b7b\u9501(Gimbal Lock)\u2014"
        u"\u9aa8\u9abc\u65cb\u8f6c\u8d85\u8fc7 \u224890\u00b0 \u6216\u53d1\u751f"
        u"\u7ffb\u8f6c\u65f6,X/Y/Z \u6570\u503c\u5267\u70c8\u8df3\u53d8,"
        u"RBF \u8ddd\u79bb\u5b8c\u5168\u9519\u8bef,\u9a71\u52a8\u9aa8\u9abc"
        u"\u4f1a\u77ac\u95f4\u4e71\u98de\u3002\n\n"
        u"\u9002\u7528\u573a\u666f:\u53ea\u505a\u5355\u8f74\u65cb\u8f6c\u7684"
        u"\u7b80\u5355\u673a\u68b0\u7ed3\u6784(\u5982\u5355\u5411\u95e8\u8f74"
        u"\u3001\u6d3b\u585e)\u3002",

    "enc_quaternion":
        u"Quaternion(\u56db\u5143\u6570)\u2014 \u5c06\u65cb\u8f6c\u8f6c\u6362"
        u"\u4e3a (w, x, y, z) \u56db\u5143\u6570\u3002\n\n"
        u"\u4f18\u70b9:\u5b8c\u7f8e\u89e3\u51b3\u4e07\u5411\u8282\u6b7b\u9501"
        u"\u548c\u7ffb\u8f6c\u95ee\u9898,\u652f\u6301 360\u00b0 \u65cb\u8f6c"
        u"\u3002\n"
        u"\u7f3a\u70b9:4 \u7ef4\u5411\u91cf\u2014\u6b27\u6c0f\u8ddd\u79bb"
        u"\u5728\u76f4\u89c9\u7ebf\u6027\u4e0a\u4e0d\u5982 3 \u7ef4\u3002\n\n"
        u"\u9002\u7528\u573a\u666f:\u9700\u8981\u5168\u7a7a\u95f4 360\u00b0 "
        u"\u65e0\u6b7b\u89d2\u65cb\u8f6c\u7684\u63a7\u5236\u5668,"
        u"\u4e14\u4e0d\u6d89\u53ca\u590d\u6742\u7684\u626d\u66f2\u62c6\u5206"
        u"\u65f6\u3002",

    "enc_bendroll":
        u"BendRoll(\u5f2f\u66f2\u4e0e\u7ffb\u6eda)\u2014 \u5c06\u65cb\u8f6c"
        u"\u62c6\u89e3\u4e3a\u5f2f\u66f2(Bend,\u4e0e\u9aa8\u9abc\u8f74"
        u"\u5782\u76f4)\u548c\u7ffb\u6eda(Roll,\u6cbf\u9aa8\u9abc\u8f74)"
        u"\u3002\n\n"
        u"\u4f18\u70b9:\u7c7b\u4f3c SwingTwist,\u4f46\u7b97\u6cd5\u66f4"
        u"\u4fa7\u91cd\u4e8e bend/roll \u5206\u79bb\u3002\n\n"
        u"\u9002\u7528\u573a\u666f:\u6837\u6761\u7ebf IK(Spline IK)\u3001"
        u"\u810a\u690e\u3001\u89e6\u624b\u7b49\u957f\u6761\u72b6\u7ed3\u6784"
        u"\u7684\u7ed1\u5b9a,\u63d0\u53d6\u5c40\u90e8\u7684\u5f2f\u66f2\u7a0b"
        u"\u5ea6\u3002",

    "enc_expmap":
        u"ExpMap(\u6307\u6570\u6620\u5c04)\u2014 \u2605 RBF \u6700\u5e38\u7528"
        u"\n\n"
        u"\u5c06\u65cb\u8f6c\u8868\u793a\u4e3a\u4e00\u4e2a 3D \u5411\u91cf:"
        u"\u65b9\u5411 = \u65cb\u8f6c\u8f74,\u957f\u5ea6 = \u65cb\u8f6c\u89d2"
        u"\u5ea6\u3002\n\n"
        u"\u4f18\u70b9:\u65e2\u50cf Quaternion \u4e00\u6837\u6ca1\u6709\u4e07"
        u"\u5411\u8282\u6b7b\u9501,\u53c8\u50cf\u6b27\u62c9\u89d2\u4e00\u6837"
        u"\u53ea\u6709 3 \u4e2a\u7ef4\u5ea6\u3002ExpMap \u7a7a\u95f4\u4e2d"
        u"\u7684\u8ddd\u79bb\u7b26\u5408\u4eba\u7c7b\u5bf9\u89d2\u5ea6\u5dee"
        u"\u5f02\u7684\u611f\u77e5,\u8fc7\u6e21\u6781\u5176\u5e73\u6ed1"
        u"\u3002\n\n"
        u"\u9002\u7528\u573a\u666f:\u5927\u591a\u6570\u591a\u5bf9\u591a\u3001"
        u"\u975e\u7ebf\u6027\u7684 RBF \u5f62\u53d8\u9a71\u52a8(\u5982\u9762"
        u"\u90e8\u8868\u60c5\u3001\u590d\u6742\u7684\u808c\u8089\u8f85\u52a9"
        u"\u9aa8\u9abc)\u7684\u9996\u9009\u3002",

    "enc_swingtwist":
        u"SwingTwist(\u6446\u52a8\u4e0e\u626d\u66f2)\u2014 \u2605 \u80a2"
        u"\u4f53\u7ed1\u5b9a\u6700\u5e38\u7528\n\n"
        u"\u5c06\u590d\u6742\u7684\u65cb\u8f6c\u62c6\u89e3\u4e3a:\n"
        u"  \u00b7 Swing(\u6446\u52a8)\u2014\u9aa8\u9abc\u50cf\u5706\u89c4"
        u"\u4e00\u6837\u6307\u5411\u4e0a/\u4e0b/\u5de6/\u53f3\u3002\n"
        u"  \u00b7 Twist(\u626d\u66f2/\u81ea\u8f6c)\u2014\u9aa8\u9abc\u6cbf"
        u"\u7740\u81ea\u8eab\u8f74\u7ebf\u65cb\u8f6c\u3002\n\n"
        u"\u4f18\u70b9:\u53ef\u5265\u79bb\u4e0d\u9700\u8981\u7684\u65cb\u8f6c"
        u"\u4fe1\u606f\u3002\u4f8b:\u53ea\u6839\u636e\u5927\u81c2\u62ac\u8d77"
        u"\u7684\u9ad8\u5ea6(Swing)\u9a71\u52a8\u80a9\u8180\u808c\u8089,"
        u"\u5ffd\u7565\u5927\u81c2\u7684\u81ea\u8f6c(Twist)\u3002\n\n"
        u"\u9002\u7528\u573a\u666f:\u80a9\u8180\u3001\u624b\u8155\u3001\u5927"
        u"\u817f\u6839\u90e8(Hip)\u7684\u8f85\u52a9\u9aa8\u9abc\u9a71\u52a8"
        u"\u3002\u4f8b:\u63d0\u53d6\u624b\u8155\u7684 Twist \u53bb\u9a71"
        u"\u52a8\u5c0f\u81c2\u7684\u7ffb\u8f6c\u9aa8\u9abc\u3002",

    "clamp_enabled":
        u"\u5728 kernel \u8ba1\u7b97\u524d\u5c06\u9a71\u52a8\u8f93\u5165\u949b\u5236\u5230\u8bad\u7ec3\u59ff\u6001\u96c6\u7684\u6bcf\u7ef4\u8fb9\u754c\u3002"
        u"\u9632\u6b62\u8d85\u51fa\u8bad\u7ec3\u8303\u56f4\u7684\u8f93\u5165\u5f15\u8d77 RBF \u6fc0\u6d3b\u7206\u53d1\u3002",

    "clamp_inflation":
        u"\u949b\u5236\u8fb9\u754c\u5411\u5916\u81a8\u80c0\u7684\u6bd4\u4f8b\uff080-1\uff09\u3002"
        u"0.0 \u4e3a\u786c\u949b\u5236\uff08PART G.7\uff09\uff1b\u6b63\u503c\u63d0\u4f9b\u8f6f\u8fb9\u754c\u4ee5\u51cf\u8f7b\u8fb9\u7f18\u8df3\u53d8\u3002",

    "output_is_scale":
        u"\u5c06\u8be5\u8f93\u51fa\u901a\u9053\u6807\u8bb0\u4e3a\u7f29\u653e\u5206\u91cf\u3002"
        u"\u7f29\u653e\u8f93\u51fa anchor \u4e3a 1.0\uff0c\u9632\u6b62\u6355\u83b7\u57fa\u7ebf\u4e3a 0 \u65f6\u5728 t-pose \u4e0b mesh \u584c\u9677\u3002",

    # -- M2.4b --

    "driver_rotate_order":
        u"\u975e Raw \u8f93\u5165\u7f16\u7801\u4e0b\u7684\u6bcf\u9a71\u52a8\u7ec4 rotateOrder\u3002\n\n"
        u"\u5f53 inputEncoding \u975e Raw\uff0c\u9a71\u52a8\u5c5e\u6027\u4ee5 (rx, ry, rz) \u4e09\u5143\u7ec4\u6d88\u8d39\uff1b"
        u"\u6bcf\u4e2a\u4e09\u5143\u7ec4\u662f\u4e00\u4e2a\u9a71\u52a8\u7ec4\uff0c\u5176 Euler\u2192\u56db\u5143\u6570\u8f6c\u6362\u9700\u8981\u5bf9\u5e94 rotateOrder\u3002"
        u"\u5217\u8868\u987a\u5e8f [group0, group1, ...] \u4e0e\u9a71\u52a8\u8f93\u5165\u4ece\u5de6\u5230\u53f3\u5bf9\u9f50\u3002\n\n"
        u"\u4f7f\u7528 +/- \u6309\u94ae\u589e\u5220\u7ec4\uff1benum \u503c\u5bf9\u9f50 Maya \u539f\u751f rotateOrder \u4e0b\u62c9\u6846 "
        u"(xyz / yzx / zxy / xzy / yxz / zyx)\u3002\u7f3a\u5931\u6761\u76ee fall-back \u5230 xyz\u3002",

    "quat_group_start":
        u"\u542f\u52a8 4-slot \u56db\u5143\u6570\u7ec4\u7684\u8f93\u51fa\u7d22\u5f15\uff08M2.2 QWA\uff09\u3002"
        u"\u6bcf\u4e2a\u8f93\u5165\u7684\u8d77\u59cb S \u58f0\u660e output[S..S+3] \u662f\u5355\u4f4d\u56db\u5143\u6570\uff0c"
        u"\u5e94\u8d70\u56db\u5143\u6570\u52a0\u6743\u5e73\u5747\u800c\u975e\u6807\u91cf\u52a0\u6743\u548c\u3002\n\n"
        u"\u65e0\u6548\u6761\u76ee\uff08\u8d8a\u754c / \u91cd\u53e0 / \u4e0e 4-slot \u8303\u56f4\u5185 outputIsScale flag \u51b2\u7a81\uff09\u5728 compute() "
        u"\u65f6\u88ab\u4e22\u5f03\u4e0e\u4e00\u6b21\u6027 warning\u2014\u2014rig \u7ee7\u7eed\u8fd0\u884c\uff0c\u88ab\u4e22\u7684\u7ec4\u4ec5\u9000\u56de\u6807\u91cf\u8f93\u51fa\u3002",

    # -- M_HELPBUBBLE_BATCH (2026-04-29) \u2014 ZH parity --
    "output_encoding":
        u"\u8282\u70b9\u7ea7\u8f93\u51fa\u7f16\u7801\uff0c\u51b3\u5b9a driven \u503c\u5982\u4f55\u5199\u5165 C++ output[] \u6570\u7ec4\u3002\n\n"
        u"  \u00b7 Euler \u2014 \u9ed8\u8ba4\uff1b\u539f\u59cb 3 \u5143 Euler \u89d2\u3002\n"
        u"  \u00b7 Quaternion \u2014 driven \u7ec4\u6309\u5355\u4f4d\u56db\u5143\u6570\u89e3\u91ca\uff1b\u4e0e input \u7aef "
        u"inputEncoding=Quaternion \u6d41\u7a0b\u5bf9\u9f50\u3002\n"
        u"  \u00b7 ExpMap \u2014 driven \u7ec4\u6309\u6307\u6570\u6620\u5c04\u5411\u91cf\u7f16\u7801\uff1b\u4e0e per-driver-group "
        u"rotateOrder \u914d\u5408\uff0c\u786e\u4fdd\u8bc4\u4f30\u65f6\u4e00\u81f4\u91cd\u5efa\u3002\n\n"
        u"\u5207\u6362\u4ee5\u5339\u914d\u4e0b\u6e38\u7ed1\u5b9a\u9884\u671f\u7f16\u7801\u3002\u8bbe\u7f6e\u9519\u4f4d\u901a\u5e38\u5728\u6781\u7aef\u65cb\u8f6c\u4e0b\u8868\u73b0\u4e3a\u6f02\u79fb\u800c"
        u"\u975e\u76f4\u63a5\u62a5\u9519\u3002",

    # -- M_P1_ENC_COMBO_FIX (2026-04-29) \u2014 ZH parity --
    "output_enc_euler":
        u"\u8f93\u51fa\u7f16\u7801 \u2014 Euler\uff08\u9ed8\u8ba4\uff09\n\n"
        u"\u6bcf\u4e2a driven \u5c5e\u6027\u7ec4\u662f\u539f\u59cb Euler \u4e09\u5143\u7ec4 (rx, ry, rz)\u3002"
        u"C++ compute() \u52a0\u6743\u548c\u6309\u901a\u9053\u76f4\u63a5\u7d2f\u52a0\uff0c\u4e0d\u505a\u56db\u5143\u6570 / exp-map \u91cd\u5efa\u3002\n\n"
        u"\u2605 \u5173\u8282 translate / rotate \u901a\u9053\u53ca\u975e\u65cb\u8f6c\u6027 driven \u5c5e\u6027"
        u"\uff08blendshape \u6743\u91cd\u3001\u81ea\u5b9a\u4e49\u6807\u91cf\u3001scale\uff09\u7684\u9ed8\u8ba4\u9009\u62e9\u3002\n\n"
        u"\u8fb9\u754c\uff1a\u5355 Euler \u4e09\u5143\u7ec4\u5728\u4e07\u5411\u8282\u9644\u8fd1\u6781\u7aef\u65cb\u8f6c\u4e0b\u505a\u591a pose \u6df7\u5408\u53ef\u80fd\u6f02\u79fb\uff1b"
        u"\u6b64\u65f6\u6362 Quaternion \u6216 ExpMap \u7f16\u7801\u3002",

    "output_enc_quaternion":
        u"\u8f93\u51fa\u7f16\u7801 \u2014 Quaternion\uff08\u56db\u5143\u6570\uff09\n\n"
        u"driven \u5c5e\u6027\u7ec4\u6309\u5355\u4f4d\u56db\u5143\u6570\u89e3\u91ca\uff08\u6bcf\u7ec4 4 \u901a\u9053\uff09\u3002C++ compute() "
        u"\u8d70\u56db\u5143\u6570\u52a0\u6743\u5e73\u5747\uff08M2.2 QWA\uff09\u800c\u975e\u6807\u91cf\u52a0\u6743\u548c\uff0c\u6cbf\u5355\u4f4d\u8d85\u7403\u9762\u4fdd\u6301\u65cb\u8f6c\u8fde\u7eed\u6027\u3002\n\n"
        u"\u4e0e inputEncoding=Quaternion \u81ea\u7136\u914d\u5957\uff0c\u5e76\u4f9d\u8d56 "
        u"outputQuaternionGroupStart[] \u5217\u8868\u58f0\u660e\u8f93\u51fa\u6570\u7ec4\u4e2d\u6bcf\u4e2a 4-slot \u7ec4\u7684\u8d77\u59cb\u4f4d\u7f6e\u3002\n\n"
        u"\u8fb9\u754c\uff1a4-slot \u8303\u56f4\u4e0e outputIsScale flag \u51b2\u7a81\u7684\u7ec4\u5728 compute() \u65f6\u88ab\u4e22\u5f03 + "
        u"\u4e00\u6b21\u6027 warning\u2014\u2014rig \u7ee7\u7eed\u8fd0\u884c\uff0c\u88ab\u4e22\u7684\u7ec4\u9000\u56de\u6807\u91cf\u8f93\u51fa\u3002",

    "output_enc_expmap":
        u"\u8f93\u51fa\u7f16\u7801 \u2014 ExpMap\uff08\u6307\u6570\u6620\u5c04\uff09\n\n"
        u"driven \u5c5e\u6027\u7ec4\u7f16\u7801\u4e3a 3 \u5206\u91cf exp-map \u5411\u91cf\u3002C++ compute() \u5728 exp-map "
        u"\u7a7a\u95f4\u63d2\u503c\u5e76\u5728\u8bfb\u53d6\u65f6\u91cd\u5efa\u65cb\u8f6c\uff1b\u5bf9\u4e2d\u7b49\u5e45\u5ea6\u65cb\u8f6c\u6548\u679c\u597d\uff0c\u4e14\u65e0 raw Euler "
        u"\u7684\u4e07\u5411\u8282\u4f2a\u50cf\u3002\n\n"
        u"\u2605 \u9002\u7528\u4e8e driven \u4fa7\u662f\u5355\u4e00\u65cb\u8f6c\u5173\u8282\u7684\u573a\u666f\uff08twist \u6821\u6b63\u3001\u5f2f\u66f2\u5173\u8282\uff09\uff0c"
        u"\u9700\u8981\u6bd4 Euler \u66f4\u5e73\u6ed1\u7684\u6df7\u5408\u4f46\u4e0d\u60f3\u4ed8\u56db\u5143\u6570\u7ec4\u7684\u989d\u5916\u901a\u9053\u5f00\u9500\u3002\n\n"
        u"\u8fb9\u754c\uff1a\u63a5\u8fd1 pi \u5f27\u5ea6\u7403\u58f3\u7684\u5927\u5e45\u65cb\u8f6c\u4f1a\u7ed5\u539f\u70b9\u6298\u56de\u2014\u2014\u4fdd\u6301\u6bcf pose \u65cb\u8f6c\u5e45\u503c "
        u"|angle| < pi \u4ee5\u907f\u514d\u5bf9\u6781\u8df3\u53d8\u3002",

    "outer_tabs_overview":
        u"RBF Pose Editor \u4e09\u6807\u7b7e\u9875\u5bfc\u822a\uff1a\n"
        u"  \u00b7 DriverDriven \u2014 \u9009\u62e9\u9a71\u52a8\u9aa8\u9abc/\u5c5e\u6027 + \u88ab\u9a71\u52a8\u5173\u8282/\u5c5e\u6027\uff0c"
        u"\u51b3\u5b9a solver \u7684\u8f93\u5165\u8f93\u51fa\u7ef4\u5ea6\u3002\u6b64\u5904\u7f16\u8f91\u4f1a\u91cd\u5efa pose \u6a21\u5f0f\u3002\n"
        u"  \u00b7 BaseDrivenPose \u2014 \u6bcf\u4e2a driven \u5c5e\u6027\u7684\u57fa\u7ebf/\u4f11\u6b62\u503c\uff1b\u4ece\u6bcf\u4e2a pose"
        u"\u4e2d\u51cf\u53bb\u540e\u624d\u662f solver \u5b9e\u9645\u63d2\u503c\u7684 delta\u3002\n"
        u"  \u00b7 Pose \u2014 \u5b9e\u65f6 pose \u7f51\u683c\uff1a\u589e\u52a0 / \u53ec\u56de / \u5220\u9664 pose\u3001"
        u"\u9010\u884c\u7f16\u8f91 driver + driven \u91c7\u6837\u503c\u3002\n\n"
        u"\u6807\u7b7e\u5207\u6362\u65e0\u7834\u574f\u6027\uff0c\u4e09\u4e2a\u89c6\u56fe\u5171\u4eab\u540c\u4e00\u6d3b\u52a8\u8282\u70b9\u3002",

    "source_tab_connect":
        u"\u5c06\u672c\u6807\u7b7e\u9875\u6240\u9009\u5c5e\u6027\uff08driver \u6216 driven\uff09\u8fde\u63a5\u5230\u6d3b\u52a8\u8282\u70b9\u7684 "
        u"input[] / output[] \u6570\u7ec4\u3002\n\n"
        u"Path-A \u8bed\u4e49\u2014\u2014\u76f4\u63a5\u64cd\u4f5c\u6bcf\u6807\u7b7e\u9875\u7684\u5c5e\u6027\u5217\u8868\uff0cpose \u6570\u636e\u4e0d\u88ab\u89e6\u78b0\u3002"
        u"\u5e42\u7b49\uff1a\u540c\u4e00\u9009\u62e9\u91cd\u590d\u70b9\u51fb\u590d\u7528\u65e2\u6709\u69fd\u4f4d\u3002\n\n"
        u"\u9762\u677f\u7ea7 Batch \u590d\u9009\u6846\u542f\u7528\u65f6\uff0cConnect \u6a2a\u626b\u9762\u677f\u91cc**\u6bcf\u4e00\u4e2a**\u6807\u7b7e\u9875"
        u"\u800c\u975e\u4ec5\u5f53\u524d\u6d3b\u52a8\u6807\u7b7e\u2014\u2014\u4fbf\u4e8e\u540c\u4e00\u5c5e\u6027\u96c6\u4e00\u6b21\u5e7f\u64ad\u5230\u5168\u90e8\u9a71\u52a8\u3002",

    "source_tab_disconnect":
        u"\u62c6\u9664 Connect \u4e3a\u672c\u6807\u7b7e\u9875\u6e90\u5efa\u7acb\u7684 input[] / output[] \u6570\u636e\u8fde\u63a5\u3002\n\n"
        u"\u6309\u7cbe\u786e\u6bcf\u5c5e\u6027\u7ea7\u522b\u8d70\u94fe\u8def\uff0c\u5176\u5b83\u6807\u7b7e\u9875 / \u4e0d\u76f8\u5173\u8282\u70b9\u4e0d\u53d7\u5f71\u54cd\u3002"
        u"Disconnect \u540e\u8282\u70b9\u4ecd\u4fdd\u7559 driverSource[] / drivenSource[] \u5143\u6570\u636e\u6761\u76ee"
        u"\u2014\u2014\u4ec5\u6570\u636e\u94fe\u8def\u88ab\u65ad\uff1bAdd Driver / Add Driven \u4e0d\u4f1a\u88ab\u64a4\u9500\u3002\n\n"
        u"Batch \u590d\u9009\u6846\u542f\u7528\u65f6\uff0cDisconnect \u6a2a\u626b\u9762\u677f\u91cc\u6bcf\u4e00\u4e2a\u6807\u7b7e\u9875\u3002",

    "source_tab_add_driver":
        u"\u5728\u6d3b\u52a8\u8282\u70b9\u8ffd\u52a0\u4e00\u4e2a\u65b0\u7684 driver \u6e90\u6807\u7b7e\u9875\u5e76\u6253\u5f00\u5c5e\u6027\u9009\u62e9\u3002\n\n"
        u"\u6bcf\u4e2a driver \u6e90\u5bf9\u5e94 shape \u4e0a\u4e00\u6761 driverSource[]\u2014\u2014\u4e00\u4e2a "
        u"(node, attrs, weight, encoding) \u5143\u7ec4\uff0cdriver \u7684 .message \u8fde\u5230 "
        u"driverSource_node\u3002\n\n"
        u"\u5148\u9009 driver \u9aa8\u9abc / \u63a7\u5236\u5668\u5bf9\u8c61\uff0c\u518d\u9009\u5176\u53c2\u4e0e\u7684\u5c5e\u6027\u3002\u5141\u8bb8\u8de8\u6e90\u91cd\u590d "
        u"(bone, attr) \u5bf9\uff0c\u4f46\u901a\u5e38\u65e0\u610f\u4e49\u3002",

    "source_tab_add_driven":
        u"\u8ffd\u52a0\u4e00\u4e2a\u65b0\u7684 driven \u6e90\u6807\u7b7e\u9875\u5e76\u6253\u5f00\u5c5e\u6027\u9009\u62e9\u3002\n\n"
        u"\u6bcf\u4e2a driven \u6e90\u5bf9\u5e94\u4e00\u6761 drivenSource[]\u2014\u2014RBF compute \u5c06\u5411\u5176\u5c5e\u6027"
        u"\u5199\u5165\u7ed3\u679c\u7684\u5173\u8282 / \u63a7\u5236\u5668\u3002\u70b9 Connect \u524d\u9009\u597d\u8be5\u5bf9\u8c61\u4e0a solver "
        u"\u5e94\u9a71\u52a8\u7684\u6240\u6709 driven \u5c5e\u6027\u3002\n\n"
        u"Driven \u5c5e\u6027\u53c2\u4e0e M2.4a \u7684 per-attribute outputIsScale \u6807\u8bb0\u5217\u8868\uff1b"
        u"\u9ed8\u8ba4\u975e scale\uff08translate / rotate / blendshape \u8bed\u4e49\uff09\u3002",

    "source_tab_batch_driver":
        u"\u52fe\u9009\u65f6\uff0c\u9762\u677f\u7ea7 Connect / Disconnect \u540c\u65f6\u4f5c\u7528\u4e8e**\u6bcf\u4e00\u4e2a** driver "
        u"\u6807\u7b7e\u9875\uff0c\u800c\u975e\u4ec5\u5f53\u524d\u6d3b\u52a8\u6807\u7b7e\u3002\n\n"
        u"\u7528\u4e8e\u628a\u540c\u4e00\u5c5e\u6027\u96c6\u4e00\u6b21\u6027\u5e7f\u64ad\u5230\u7ed3\u6784\u76f8\u4f3c\u7684\u591a\u6839 driver \u9aa8\uff08\u5982\u624b\u81c2\u94fe\uff09\uff0c"
        u"\u7701\u53bb\u9010\u6807\u7b7e\u5207\u6362\u3002Add Driver \u6309\u94ae**\u4e0d**\u53d7\u6b64 flag \u5f71\u54cd\u2014\u2014\u59cb\u7ec8\u65b0\u5efa\u4e00\u4e2a\u6807\u7b7e\u3002\n\n"
        u"Batch \u4ec5\u4f1a\u8bdd\u7ea7 flag\uff0c\u4e0d\u6301\u4e45\u5316\u5728\u8282\u70b9\u4e0a\u3002",

    "source_tab_batch_driven":
        u"\u52fe\u9009\u65f6\uff0c\u9762\u677f\u7ea7 Connect / Disconnect \u540c\u65f6\u4f5c\u7528\u4e8e**\u6bcf\u4e00\u4e2a** driven "
        u"\u6807\u7b7e\u9875\uff0c\u800c\u975e\u4ec5\u5f53\u524d\u6d3b\u52a8\u6807\u7b7e\u3002\n\n"
        u"\u9002\u5408\u591a\u6839\u5171\u4eab\u540c\u4e00\u5c5e\u6027\u5217\u8868\u7684 driven \u5173\u8282\uff08\u5982\u4e00\u6392\u77eb\u6b63 blendshape\uff09\u3002"
        u"Add Driven \u4e0d\u53d7\u5f71\u54cd\u2014\u2014\u59cb\u7ec8\u65b0\u5efa\u4e00\u4e2a\u6807\u7b7e\u3002\n\n"
        u"Batch \u4ec5\u4f1a\u8bdd\u7ea7 flag\uff0c\u4e0d\u6301\u4e45\u5316\u5728\u8282\u70b9\u4e0a\u3002",

    "btn_split_solver_per_joint":
        u"\u5c06\u8fd9\u4e2a\u591a driven \u7684 RBF solver \u62c6\u6210\u6bcf\u4e2a joint \u4e00\u4efd\u72ec\u7acb solver\u3002\n\n"
        u"\u7528\u4e8e\u6027\u80fd\u62c6\u5206\uff1a\u5f53 profile \u663e\u793a compute() \u88ab\u5355\u4e00 driver \u9988\u9001\u5927\u91cf"
        u"\u4e92\u4e0d\u76f8\u5e72\u8f93\u51fa\u65f6\uff0c\u72ec\u7acb\u8bc4\u4f30\u80fd\u5e76\u884c\u3002\u65b0\u8282\u70b9\u7ee7\u627f\u76f8\u540c\u7684 driver \u62d3\u6251 + "
        u"\u4e0e\u5176 driven joint \u76f8\u5173\u7684 pose \u5b50\u96c6\u3002\n\n"
        u"\u5bf9\u539f\u8282\u70b9\u5177\u7834\u574f\u6027\u2014\u2014\u5efa\u8bae\u5148\u590d\u5236\u540e\u5bf9\u6bd4\u8bc4\u4f30\u7b49\u4ef7\u3002",

    "cleanup_modes_overview":
        u"\u4e09\u79cd\u6e05\u7406\u6a21\u5f0f\u5171\u7528\u4e0b\u65b9 Remove Unnecessary Datas \u6309\u94ae\uff1b\u70b9\u51fb\u524d\u5148\u9009\u4e00\u79cd\u3002\n\n"
        u"  \u00b7 Remove Connectionless Input \u2014 \u4e22\u5f03\u6ca1\u6709\u4e0a\u6e38\u8fde\u63a5\u7684 input[] \u69fd\uff0c"
        u"\u5e76\u5bf9\u4e0b\u6e38\u6570\u636e\u91cd\u65b0\u7f16\u53f7\u4ee5\u4fdd pose \u5411\u91cf\u5bf9\u9f50\u3002\n"
        u"  \u00b7 Remove Connectionless Output \u2014 output \u7aef\u540c\u7406\uff1b\u5e38\u7528\u4e8e "
        u"blendshape / joint \u4fee\u526a\u540e\u3002\n"
        u"  \u00b7 Remove Redundant Pose \u2014 \u4e22\u5f03 driver \u5411\u91cf\u4e0e\u4ed6\u8005\u5728\u5bb9\u5dee\u5185\u91cd\u590d"
        u"\u7684 pose\u3002\n\n"
        u"\u4e09\u8005\u7686\u7834\u574f\u6027\u4f46\u53ef undo \u64a4\u56de\u3002",

    "btn_remove_unnecessary_datas":
        u"\u8fd0\u884c\u4e0a\u9762\u9009\u4e2d\u7684\u6e05\u7406\u6a21\u5f0f\uff08connectionless input / output / "
        u"redundant pose \u4e09\u9009\u4e00\uff09\u3002\n\n"
        u"\u6309\u94ae\u5728\u70b9\u51fb\u65f6\u8bfb\u53d6\u5355\u9009\u9879\uff0c\u56e0\u6b64\u53ef\u5728\u4e0d\u540c\u6a21\u5f0f\u95f4\u5207\u6362\u91cd\u590d\u8fd0\u884c\u3002\u72b6\u6001\u8f93\u51fa"
        u"\u6253\u5230 Maya Script Editor\u2014\u2014\u4fdd\u5b58\u573a\u666f\u524d\u8bf7\u5ba1\u67e5\uff1b\u6e05\u7406\u53ef\u80fd\u6539\u53d8 pose / "
        u"\u5c5e\u6027\u6570\u91cf\u3002\n\n"
        u"\u5355\u6b65 undo\uff0c\u53ef\u91cd\u590d\u6267\u884c\u3002",

    "btn_refresh_profile":
        u"\u8fd0\u884c\u8282\u70b9 profiler \u5e76\u5c06\u62a5\u544a\u5c31\u5730\u6e32\u67d3\u3002\n\n"
        u"profile \u6545\u610f**\u4e0d**\u5728\u8282\u70b9\u5207\u6362\u65f6\u81ea\u52a8\u91cd\u7b97\u2014\u2014\u5927\u578b rig \u6c47\u603b\u4f1a\u6709\u53ef\u89c1\u5ef6\u8fdf\uff0c"
        u"\u4e14\u6570\u636e\u662f\u53ea\u8bfb\u4e0a\u4e0b\u6587\uff08pose \u6570\u3001input/output \u7ef4\u5ea6\u3001kernel/radius \u7b7e\u540d\u3001"
        u"per-driver \u6743\u91cd\u603b\u548c\uff09\u3002\n\n"
        u"\u62a5\u544a\u662f\u5feb\u7167\uff1b\u4efb\u4f55\u7ed3\u6784\u7f16\u8f91\uff08\u589e\u5220 driver\u3001pose \u6539\u52a8\uff09\u540e\u518d\u6b21\u70b9 Refresh "
        u"\u4ee5\u67e5\u770b\u66f4\u65b0\u6570\u636e\u3002",
}

_TABLES = {"en": _EN, "zh": _ZH}


def get_help_text(key):
    """Return the help text for *key* in the current UI language."""
    lang = current_language()
    table = _TABLES.get(lang, _EN)
    return table.get(key, _EN.get(key, ""))
