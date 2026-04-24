# ---------------------------------------------------------------------
# userSetup.py
#
# Automatically registers the RBF Tools top-level menu in Maya
# after the UI has finished initialising.
#
# This file is placed in the module's scripts/ folder and is
# picked up by Maya through the module path system.
# ---------------------------------------------------------------------

import maya.cmds as cmds
import maya.utils


def _deferred_menu_setup():
    """Create the RBF Tools menu after Maya's UI is ready."""
    try:
        import RBFtoolsMenu
        RBFtoolsMenu.create()
    except Exception as exc:
        cmds.warning("RBF Tools: Could not create menu - {}".format(exc))


# maya.utils.executeDeferred ensures the code runs after Maya's
# main window and menu bar are fully initialised.
maya.utils.executeDeferred(_deferred_menu_setup)
