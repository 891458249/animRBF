# -*- coding: utf-8 -*-
"""
Immutable constants for RBF Tools.

**Zero Maya imports** — this file is pure Python data so it can be
safely imported at module collection time, in ``mayapy`` batch mode,
or inside unit tests that do not initialise a Maya session.

Enum label lists **must** match the C++ RBFtools node enum order
exactly (see ``source/RBFtools.h``  ``initialize()``).
"""

from __future__ import absolute_import

# ------------------------------------------------------------------
# Tool identity
# ------------------------------------------------------------------

TOOL_NAME    = "RBF Tools"
TOOL_VERSION = "4.1.0"

# ------------------------------------------------------------------
# Plugin / node
# ------------------------------------------------------------------

PLUGIN_NAME = "RBFtools"
NODE_TYPE   = "RBFtools"

# ------------------------------------------------------------------
# Window
# ------------------------------------------------------------------

WINDOW_OBJECT = "RBFToolsMainWindow"
WINDOW_TITLE  = "RBF Tools"
WINDOW_WIDTH  = 560
WINDOW_HEIGHT = 800

# ------------------------------------------------------------------
# optionVar keys
# ------------------------------------------------------------------

LANG_OPT_VAR          = "RBFtools_language"
AUTO_FILL_OPT_VAR     = "RBFtoolsAutoFillValues"
FILTER_VAR_TEMPLATE   = "RBFtools_filter_{role}_{key}"

# ------------------------------------------------------------------
# Node attribute enum labels (index == C++ enum value)
# ------------------------------------------------------------------

TYPE_LABELS = ["Vector Angle", "RBF"]

# C++ direction enum has 3 values only; negative axis is handled by
# the separate ``invert`` boolean attribute on the node.
DIRECTION_LABELS = ["X", "Y", "Z"]

INTERPOLATION_LABELS = [
    "Linear", "Slow", "Fast", "Smooth1", "Smooth2", "Curve",
]

# C++ kernel default = 1 (Gaussian 1).  Labels are verbatim from
# ``eAttr.addField(...)`` in RBFtools.cpp line 170-176.
KERNEL_LABELS = [
    "Linear",
    "Gaussian 1",
    "Gaussian 2",
    "Thin Plate",
    "Multi-Quadratic Biharmonic",
    "Inverse Multi-Quadratic Biharmonic",
]

RADIUS_TYPE_LABELS = [
    "Mean Distance", "Variance", "Standard Deviation", "Custom",
]

DISTANCE_TYPE_LABELS = ["Euclidean", "Angle"]

RBF_MODE_LABELS = ["Generic", "Matrix"]

TWIST_AXIS_LABELS = ["X", "Y", "Z"]

# ------------------------------------------------------------------
# Attribute filter defaults for the pose-editor lists
# ------------------------------------------------------------------

FILTER_DEFAULTS = {
    "Keyable":     1,
    "Readable":    1,
    "Writable":    1,
    "NonKeyable":  0,
    "Connected":   0,
    "Hidden":      0,
    "UserDefined": 0,
}

FILTER_KEYS = list(FILTER_DEFAULTS.keys())
