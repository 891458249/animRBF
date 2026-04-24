cmake_minimum_required(VERSION 3.12)
project(RBFtools)

# — Maya 2022 devkit path (adjust to your local installation) —
# Common paths:
#   Windows: C:/Program Files/Autodesk/Maya2022/devkit
#   or an extracted devkit directory
set(MAYA_DEVKIT_PATH "" CACHE PATH "Path to Maya 2022 devkit")

if(NOT MAYA_DEVKIT_PATH OR NOT EXISTS "${MAYA_DEVKIT_PATH}")
    message(FATAL_ERROR
        "Set MAYA_DEVKIT_PATH to your Maya 2022 devkit, e.g.:\n"
        "  cmake -DMAYA_DEVKIT_PATH=\"C:/Program Files/Autodesk/Maya2022\" ..")
endif()

set(MAYA_INCLUDE "${MAYA_DEVKIT_PATH}/include")
set(MAYA_LIB     "${MAYA_DEVKIT_PATH}/lib")

# Verify paths
if(NOT EXISTS "${MAYA_INCLUDE}/maya/MGlobal.h")
    message(FATAL_ERROR "Cannot find maya/MGlobal.h in ${MAYA_INCLUDE}")
endif()

add_library(RBFtools SHARED
    pluginMain.cpp
    RBFtools.cpp
    BRMatrix.cpp
)

target_include_directories(RBFtools PRIVATE "${MAYA_INCLUDE}")
target_link_directories(RBFtools PRIVATE "${MAYA_LIB}")

target_compile_definitions(RBFtools PRIVATE
    NT_PLUGIN
    REQUIRE_IOSTREAM
    _BOOL
)

# Maya 2022 uses MSVC v142 (VS2019), C++14
target_compile_features(RBFtools PRIVATE cxx_std_14)

target_link_libraries(RBFtools PRIVATE
    OpenMaya
    OpenMayaUI
    OpenMayaAnim
    OpenMayaRender
    Foundation
)

# Output as .mll
set_target_properties(RBFtools PROPERTIES
    SUFFIX ".mll"
    PREFIX ""
    OUTPUT_NAME "RBFtools"
)
