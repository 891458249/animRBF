// ---------------------------------------------------------------------
//
//  pluginMain.cpp
//
//  Created by ingo on 10/5/13.
//  Copyright (c) 2026 Drafter. All rights reserved.
//
// ---------------------------------------------------------------------

#include <string>
#include <maya/MDrawRegistry.h>
#include <maya/MFnPlugin.h>

static const std::string kVERSION = "4.0.1";

#include "RBFtools.h"

// ---------------------------------------------------------------------
// initialization
// ---------------------------------------------------------------------

MStatus initializePlugin(MObject obj)
{
    MStatus status;
    MFnPlugin plugin(obj, "Drafter", kVERSION.c_str(), "Any");

    status = plugin.registerNode("RBFtools",
                                 RBFtools::id,
                                 &RBFtools::creator,
                                 &RBFtools::initialize,
                                 MPxNode::kLocatorNode,
                                 &RBFtools::drawDbClassification);
    if (status != MStatus::kSuccess)
        status.perror("Register RBFtools command failed");

    status = MHWRender::MDrawRegistry::registerDrawOverrideCreator(RBFtools::drawDbClassification,
                                                                   RBFtools::drawRegistrantId,
                                                                   RBFtoolsOverride::Creator);
    if (status != MStatus::kSuccess)
        status.perror("Register DrawOverrideCreator for RBFtools command failed");

    return status;
}

MStatus uninitializePlugin(MObject obj)
{
    MStatus status;
    MFnPlugin plugin(obj, "Drafter", kVERSION.c_str(), "Any");

    status = MHWRender::MDrawRegistry::deregisterDrawOverrideCreator(RBFtools::drawDbClassification,
                                                                     RBFtools::drawRegistrantId);
    if (status != MStatus::kSuccess)
        status.perror("Deregister DrawOverrideCreator for RBFtools command failed");

    status = plugin.deregisterNode(RBFtools::id);

    if (status != MStatus::kSuccess)
        status.perror("Deregister RBFtools command failed");

    return status;
}

// ---------------------------------------------------------------------
// MIT License
//
// Copyright (c) 2026 Drafter
// RBFtools is under the terms of the MIT License
//
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:
//
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
// IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
// CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
// TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
// SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//
// Author: Drafter    d891458249@gmail.com
// ---------------------------------------------------------------------
