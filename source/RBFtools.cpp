// ---------------------------------------------------------------------
//
//  RBFtools.cpp
//
//  Created by ingo on 9/27/13.
//  Copyright (c) 2026 Drafter. All rights reserved.
//
// ---------------------------------------------------------------------

#include "RBFtools.h"

#include "math.h"

#ifdef _WIN64
#define M_PI 3.1415926535897932384626433832795
#endif

#define DOUBLE_EPSILON 2.2204460492503131e-16

const float DEGTORAD = (float)(M_PI / 180);
const float RADTODEG = (float)(180 / M_PI);


MTypeId RBFtools::id(0x0011C1C5);


// -----------------------------------------------
// vector angle attributes (sorted by category)
// -----------------------------------------------

// input
MObject RBFtools::driverMatrix;
MObject RBFtools::readerMatrix;
// controls
MObject RBFtools::active;
MObject RBFtools::angle;
MObject RBFtools::centerAngle;
MObject RBFtools::curveRamp;
MObject RBFtools::direction;
MObject RBFtools::grow;
MObject RBFtools::interpolate;
MObject RBFtools::invert;
MObject RBFtools::translateMax;
MObject RBFtools::translateMin;
MObject RBFtools::twist;
MObject RBFtools::twistAngle;
MObject RBFtools::useRotate;
MObject RBFtools::useTranslate;
// display
MObject RBFtools::color;
MObject RBFtools::colorR;
MObject RBFtools::colorG;
MObject RBFtools::colorB;
MObject RBFtools::drawCenter;
MObject RBFtools::drawCone;
MObject RBFtools::drawWeight;
MObject RBFtools::size;
// output
MObject RBFtools::outWeight;


// -----------------------------------------------
// rbf attributes (sorted by category)
// -----------------------------------------------

// input
MObject RBFtools::controlNode;
MObject RBFtools::driverInput;
MObject RBFtools::driverList;
MObject RBFtools::input;
MObject RBFtools::pose;
MObject RBFtools::poseAttributes;
MObject RBFtools::poseInput;
MObject RBFtools::poseMatrix;
MObject RBFtools::poseMode;
MObject RBFtools::poseParentMatrix;
MObject RBFtools::poseRotateOrder;
MObject RBFtools::poses;
MObject RBFtools::poseValue;
MObject RBFtools::poseValues;
MObject RBFtools::restInput;
// controls
MObject RBFtools::allowNegative;
MObject RBFtools::baseValue;
MObject RBFtools::clampEnabled;
MObject RBFtools::clampInflation;
MObject RBFtools::outputIsScale;
MObject RBFtools::regularization;
MObject RBFtools::solverMethod;
MObject RBFtools::inputEncoding;
MObject RBFtools::driverInputRotateOrder;
MObject RBFtools::radiusType;
MObject RBFtools::radius;
MObject RBFtools::distanceType;
MObject RBFtools::evaluate;
MObject RBFtools::kernel;
MObject RBFtools::opposite;
MObject RBFtools::rbfMode;
MObject RBFtools::twistAxis;
MObject RBFtools::type;
MObject RBFtools::useInterpolation;
MObject RBFtools::mean;
MObject RBFtools::variance;
// display
MObject RBFtools::colorDriver;
MObject RBFtools::colorDriverR;
MObject RBFtools::colorDriverG;
MObject RBFtools::colorDriverB;
MObject RBFtools::drawDriver;
MObject RBFtools::drawIndices;
MObject RBFtools::drawOrigin;
MObject RBFtools::drawPoses;
MObject RBFtools::drawTwist;
MObject RBFtools::driverIndex;
MObject RBFtools::indexDist;
MObject RBFtools::poseDrawTwist;
MObject RBFtools::poseDrawVector;
MObject RBFtools::poseLength;
MObject RBFtools::scale;
// output
MObject RBFtools::output;

// special
MObject RBFtools::exposeData;

// ---------------------------------------------------------------------
// creator
// ---------------------------------------------------------------------

RBFtools::RBFtools()
    : lastSolveMethod(0),              // M1.4: Cholesky tried first on fresh node.
      prevSolverMethodVal(0),          // M1.4: Auto; matches solverMethod default.
      inputEncodingWarningIssued(false), // M2.1a: fresh warning on first fall-back.
      prevInputEncodingVal(0)          // M2.1a: Raw; matches inputEncoding default.
{}

RBFtools::~RBFtools()
{}

void* RBFtools::creator()
{
    return new RBFtools();
}

bool RBFtools::isBounded() const
{
    return false;
}

// ---------------------------------------------------------------------
// initialize the attributes
// ---------------------------------------------------------------------

MStatus RBFtools::initialize()
{
    //
    // MFnEnumAttribute
    //

    MFnEnumAttribute eAttr;

    direction = eAttr.create("direction", "dir", 0);
    eAttr.addField("X", 0);
    eAttr.addField("Y", 1);
    eAttr.addField("Z", 2);
    eAttr.setKeyable(true);

    distanceType = eAttr.create("distanceType", "dist", 0);
    eAttr.addField("Euclidean", 0);
    eAttr.addField("Angle", 1);
    eAttr.setKeyable(true);

    interpolate = eAttr.create("interpolation", "int", 0);
    eAttr.addField("Linear", 0);
    eAttr.addField("Slow", 1);
    eAttr.addField("Fast", 2);
    eAttr.addField("Smooth1", 3);
    eAttr.addField("Smooth2", 4);
    eAttr.addField("Curve", 5);
    eAttr.setKeyable(true);

    kernel = eAttr.create("kernel", "kn", 1);
    eAttr.addField("Linear", 0);
    eAttr.addField("Gaussian 1", 1);
    eAttr.addField("Gaussian 2", 2);
    eAttr.addField("Thin Plate", 3);
    eAttr.addField("Multi-Quadratic Biharmonic", 4);
    eAttr.addField("Inverse Multi-Quadratic Biharmonic", 5);
    // Set the attribute to be hidden and non-keyable because the
    // evaluation needs to get updated when switching the kernel type.
    // The automatic update is tied to the control in the attribute
    // editor. But since the channel box doesn't allow for such a
    // command execution the attribute is hidden from the channel box
    // to force the editing through the attribute editor.
    eAttr.setKeyable(false);
    eAttr.setHidden(true);

    poseMode = eAttr.create("poseMode", "pmd", 0);
    eAttr.addField("Rotate/Twist", 0);
    eAttr.addField("Rotate", 1);
    eAttr.addField("Twist", 2);

    poseRotateOrder = eAttr.create("controlPoseRotateOrder", "cpro", 0);
    eAttr.addField("xyz", 0);
    eAttr.addField("yzx", 1);
    eAttr.addField("zxy", 2);
    eAttr.addField("xzy", 3);
    eAttr.addField("yxz", 4);
    eAttr.addField("zyx", 5);

    rbfMode = eAttr.create("rbfMode", "rbfm", 0);
    eAttr.addField("Generic", 0);
    eAttr.addField("Matrix", 1);
    eAttr.setKeyable(false);
    eAttr.setHidden(true);

    twistAxis = eAttr.create("twistAxis", "tax", 0);
    eAttr.addField("X", 0);
    eAttr.addField("Y", 1);
    eAttr.addField("Z", 2);
    eAttr.setKeyable(false);

    type = eAttr.create("type", "typ", 0);
    eAttr.addField("Vector Angle", 0);
    eAttr.addField("RBF", 1);
    eAttr.setKeyable(true);
    
    radiusType = eAttr.create("radiusType", "radt", 0);
    eAttr.addField("Mean Distance", 0);
    eAttr.addField("Variance", 1);
    eAttr.addField("Standard Deviation", 2);
    eAttr.addField("Custom", 3);
    eAttr.setKeyable(true);

    // M1.4: explicit solver selection. Auto runs Cholesky first and
    // falls back to GE on non-SPD matrices; ForceGE is a debug escape
    // hatch that bypasses Cholesky entirely. M4.5 will extend this enum
    // to {Auto, ForceCholesky, ForceQR, ForceLU, ForceSVD} once Eigen
    // integration lands the full four-tier chain (v5 PART D.1).
    solverMethod = eAttr.create("solverMethod", "slvm", 0);
    eAttr.addField("Auto", 0);
    eAttr.addField("ForceGE", 1);
    eAttr.setKeyable(true);
    eAttr.setStorable(true);

    // M2.1a: input encoding for Generic mode. Field values aligned to
    // v5 PART C.2.2. Default Raw for zero regression on v4 rigs.
    // BendRoll (2) and Swing-Twist (4) are declared but placeholder —
    // compute() falls back to Raw with a once-per-rig warning until
    // M2.1b lands their actual encode paths. Matrix mode ignores this
    // attribute entirely (see addendum §M2.1a item 8).
    inputEncoding = eAttr.create("inputEncoding", "ienc", 0);
    eAttr.addField("Raw",        0);
    eAttr.addField("Quaternion", 1);
    eAttr.addField("BendRoll",   2);
    eAttr.addField("ExpMap",     3);
    eAttr.addField("SwingTwist", 4);
    eAttr.setKeyable(true);
    eAttr.setStorable(true);

    // M2.1a: per-driver-group rotate order. Multi enum aligned to Maya's
    // native rotateOrder enum so users may connect
    //   driver.rotateOrder → RBFtools.driverInputRotateOrder[k]
    // directly. Missing indices default to XYZ(0). Ignored when
    // inputEncoding == Raw.
    driverInputRotateOrder = eAttr.create("driverInputRotateOrder", "diro", 0);
    eAttr.addField("xyz", 0);
    eAttr.addField("yzx", 1);
    eAttr.addField("zxy", 2);
    eAttr.addField("xzy", 3);
    eAttr.addField("yxz", 4);
    eAttr.addField("zyx", 5);
    eAttr.setArray(true);
    eAttr.setUsesArrayDataBuilder(true);
    eAttr.setKeyable(false);
    eAttr.setStorable(true);

    //
    // MFnNumericAttribute
    //

    MFnNumericAttribute nAttr;

    active = nAttr.create("active", "ac", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    allowNegative = nAttr.create("allowNegativeWeights", "anw", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    angle = nAttr.create("angle", "an", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.01);
    nAttr.setMax(180.0);
    nAttr.setDefault(45.0);

    radius = nAttr.create("radius", "rad", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setDefault(0.0);
    nAttr.setMin(0.0);
    nAttr.setSoftMax(1.0);

    centerAngle = nAttr.create("centerAngle", "ca", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setMax(180.0);
    nAttr.setDefault(0.0);

    colorDriverR = nAttr.create("driverColorR", "dcr", MFnNumericData::kDouble);
    nAttr.setKeyable(false);
    nAttr.setMin(0.0);
    nAttr.setMax(1.0);
    nAttr.setDefault(0.1);

    colorDriverG = nAttr.create("driverColorG", "dcg", MFnNumericData::kDouble);
    nAttr.setKeyable(false);
    nAttr.setMin(0.0);
    nAttr.setMax(1.0);
    nAttr.setDefault(0.7);

    colorDriverB = nAttr.create("driverColorB", "dcb", MFnNumericData::kDouble);
    nAttr.setKeyable(false);
    nAttr.setMin(0.0);
    nAttr.setMax(1.0);
    nAttr.setDefault(0.0);

    colorR = nAttr.create("iconColorR", "icr", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setMax(1.0);
    nAttr.setDefault(1.0);

    colorG = nAttr.create("iconColorG", "icg", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setMax(1.0);
    nAttr.setDefault(0.8);

    colorB = nAttr.create("iconColorB", "icb", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setMax(1.0);
    nAttr.setDefault(0.2);

    drawCenter = nAttr.create("drawCenterCone", "dcc", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(false);

    drawCone = nAttr.create("drawCone", "dc", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    drawDriver = nAttr.create("drawDriver", "dd", MFnNumericData::kBoolean);
    nAttr.setKeyable(false);
    nAttr.setHidden(true);
    nAttr.setDefault(false);

    drawIndices = nAttr.create("drawIndices", "did", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    drawOrigin = nAttr.create("drawOrigin", "dor", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    drawPoses = nAttr.create("drawPoses", "dp", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    drawTwist = nAttr.create("drawTwist", "dt", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(false);

    drawWeight = nAttr.create("drawWeight", "dw", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    driverIndex = nAttr.create("driverIndex", "dvi", MFnNumericData::kInt);
    nAttr.setKeyable(false);
    nAttr.setHidden(true);
    nAttr.setDefault(0);

    evaluate = nAttr.create("evaluate", "e", MFnNumericData::kBoolean);
    nAttr.setKeyable(false);
    nAttr.setHidden(true);
    nAttr.setDefault(false);

    exposeData = nAttr.create("exposeData", "exd", MFnNumericData::kInt);
    nAttr.setKeyable(true);
    nAttr.setHidden(true);
    nAttr.setDefault(0);

    grow = nAttr.create("grow", "gr", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    indexDist = nAttr.create("indexDistance", "idd", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setDefault(0.1);

    input = nAttr.create("input", "i", MFnNumericData::kDouble);
    nAttr.setWritable(true);
    nAttr.setKeyable(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);

    invert = nAttr.create("invert", "iv", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(false);

    opposite = nAttr.create("opposite", "op", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(false);

    output = nAttr.create("output", "o", MFnNumericData::kDouble);
    nAttr.setWritable(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);

    // M1.2: per-output-dimension baseline. Only consulted in Generic mode.
    // Subtracted from poseValue[i][c] before the weight solve; added back to
    // the final output[c] after kernel evaluation. See v5 PART C.2.4 / G.1.
    baseValue = nAttr.create("baseValue", "bv", MFnNumericData::kDouble);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);
    nAttr.setKeyable(false);
    nAttr.setStorable(true);
    nAttr.setDefault(0.0);

    // M1.2: per-output-dimension scale-channel flag. When true, the training
    // baseline is forced to 1.0 regardless of baseValue[c] — this protects
    // scale channels from being trained with a 0.0 baseline and collapsing
    // the mesh on t-pose. See v5 铁律 B6.
    outputIsScale = nAttr.create("outputIsScale", "ois", MFnNumericData::kBoolean);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);
    nAttr.setKeyable(false);
    nAttr.setStorable(true);
    nAttr.setDefault(false);

    // M1.3: Driver Clamp master switch. Default off for zero regression on
    // v4 rigs — users opt in per node. See v5 PART C.2.3 / 铁律 B5 and
    // addendum 2026-04-24 §M1.3.
    clampEnabled = nAttr.create("clampEnabled", "cle", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setStorable(true);
    nAttr.setDefault(false);

    // M1.3: symmetric outward inflation as a fraction of the per-dim range.
    // 0.0 is v5 PART G.7's hard clamp; small positive values give a softer
    // hull to dampen edge-pop on out-of-training-range inputs.
    clampInflation = nAttr.create("clampInflation", "cli", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setStorable(true);
    nAttr.setDefault(0.0);
    nAttr.setMin(0.0);
    nAttr.setSoftMax(1.0);

    // M1.4: Tikhonov regularization strength added directly to the kernel
    // matrix diagonal before solve. Absolute units (not adapted to tr(K)/N)
    // per addendum 2026-04-24 §M1.4 — scale-adaptive forms silently fail
    // on Linear / Thin Plate kernels where K[i,i] = φ(0) = 0. Default 1e-8
    // follows v5 PART G.1 Step 2 and Chad Vernon's reference solver.
    regularization = nAttr.create("regularization", "reg", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setStorable(true);
    nAttr.setDefault(1.0e-8);
    nAttr.setMin(0.0);
    nAttr.setSoftMax(1.0e-3);

    outWeight = nAttr.create("outWeight", "ow", MFnNumericData::kDouble);
    nAttr.setWritable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(0.0);

    poseDrawTwist = nAttr.create("poseDrawTwist", "pdt", MFnNumericData::kDouble);
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setHidden(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);

    poseDrawVector = nAttr.create("poseDrawVector", "pdv", MFnNumericData::k3Double);
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setHidden(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);

    poseInput = nAttr.create("poseInput", "pi", MFnNumericData::kDouble);
    nAttr.setWritable(true);
    nAttr.setKeyable(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);

    poseLength = nAttr.create("poseLength", "pl", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setDefault(1.0);

    poseValue = nAttr.create("poseValue", "pv", MFnNumericData::kDouble);
    nAttr.setWritable(true);
    nAttr.setKeyable(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);

    restInput = nAttr.create("restInput", "rin", MFnNumericData::kDouble);
    nAttr.setWritable(true);
    nAttr.setKeyable(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);

    scale = nAttr.create("scale", "sc", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setDefault(1.0);

    size = nAttr.create("iconSize", "is", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setSoftMax(50.0);
    nAttr.setDefault(1.0);

    translateMax = nAttr.create("translateMax", "tmax", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setDefault(0.0);

    translateMin = nAttr.create("translateMin", "tmin", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.0);
    nAttr.setDefault(0.0);

    twist = nAttr.create("twist", "tw", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(false);

    twistAngle = nAttr.create("twistAngle", "ta", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setMin(0.01);
    nAttr.setMax(180.0);
    nAttr.setDefault(90.0);

    useInterpolation = nAttr.create("useInterpolation", "uint", MFnNumericData::kBoolean);
    nAttr.setKeyable(false);
    nAttr.setHidden(true);

    useRotate = nAttr.create("useRotate", "ur", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(true);

    useTranslate = nAttr.create("useTranslate", "ut", MFnNumericData::kBoolean);
    nAttr.setKeyable(true);
    nAttr.setDefault(false);
    
    mean = nAttr.create("meanDistance", "md", MFnNumericData::kDouble);
    nAttr.setKeyable(false);
    nAttr.setHidden(true);
    nAttr.setDefault(0.0);
    
    variance = nAttr.create("variance", "var", MFnNumericData::kDouble);
    nAttr.setKeyable(false);
    nAttr.setHidden(true);
    nAttr.setDefault(0.0);

    //
    // MFnMessageAttribute
    //

    MFnMessageAttribute msgAttr;

    controlNode = msgAttr.create("controlNode", "cn");

    //
    // MFnMatrixAttribute
    //

    MFnMatrixAttribute mAttr;

    driverInput = mAttr.create("driverInput", "di");
    mAttr.setHidden(true);
    driverMatrix = mAttr.create("driverMatrix", "dm");
    mAttr.setHidden(true);
    poseMatrix = mAttr.create("poseMatrix", "pmat");
    mAttr.setHidden(true);
    poseParentMatrix = mAttr.create("poseParentMatrix", "ppmat");
    mAttr.setHidden(true);
    readerMatrix = mAttr.create("readerMatrix", "rm");
    mAttr.setHidden(true);

    //
    // MFnTypedAttribute
    //

    MFnTypedAttribute tAttr;

    poseAttributes = tAttr.create("controlPoseAttributes", "cpa", MFnData::kStringArray);
    poseValues = tAttr.create("controlPoseValues", "cpv", MFnData::kDoubleArray);

    //
    // MFnCompoundAttribute
    //

    MFnCompoundAttribute cAttr;

    color = cAttr.create("iconColor", "ic");
    cAttr.setKeyable(true);
    cAttr.addChild(colorR);
    cAttr.addChild(colorG);
    cAttr.addChild(colorB);

    colorDriver = cAttr.create("driverColor", "dco");
    cAttr.setKeyable(false);
    cAttr.setHidden(true);
    cAttr.addChild(colorDriverR);
    cAttr.addChild(colorDriverG);
    cAttr.addChild(colorDriverB);

    pose = cAttr.create("pose", "p");
    cAttr.setArray(true);
    cAttr.setUsesArrayDataBuilder(true);
    cAttr.addChild(poseMatrix);
    cAttr.addChild(poseParentMatrix);
    cAttr.addChild(poseMode);
    cAttr.addChild(poseAttributes);
    cAttr.addChild(poseValues);
    cAttr.addChild(poseRotateOrder);

    driverList = cAttr.create("driverList", "dl");
    cAttr.setHidden(true);
    cAttr.setArray(true);
    cAttr.setUsesArrayDataBuilder(true);
    cAttr.addChild(driverInput);
    cAttr.addChild(controlNode);
    cAttr.addChild(pose);

    poses = cAttr.create("poses", "ps");
    cAttr.setKeyable(true);
    cAttr.setArray(true);
    cAttr.setUsesArrayDataBuilder(true);
    cAttr.addChild(poseInput);
    cAttr.addChild(poseValue);

    //
    // MRampAttribute
    //

    MRampAttribute rAttr;

    curveRamp = rAttr.createCurveRamp("blendCurve", "bc");

    // -----------------------------------------------------------------
    // add attributes (order matters)
    // -----------------------------------------------------------------

    addAttribute(active);
    addAttribute(type);
    addAttribute(direction);
    addAttribute(invert);
    addAttribute(useRotate);
    addAttribute(angle);
    addAttribute(centerAngle);
    addAttribute(twist);
    addAttribute(twistAngle);
    addAttribute(useTranslate);
    addAttribute(grow);
    addAttribute(translateMin);
    addAttribute(translateMax);
    addAttribute(interpolate);
    addAttribute(curveRamp);
    addAttribute(size);
    addAttribute(color);
    addAttribute(drawCone);
    addAttribute(drawCenter);
    addAttribute(drawWeight);
    addAttribute(outWeight);
    addAttribute(readerMatrix);
    addAttribute(driverMatrix);
    addAttribute(driverList);
    addAttribute(driverInput);
    addAttribute(pose);
    addAttribute(poseMatrix);
    addAttribute(poseParentMatrix);
    addAttribute(input);
    addAttribute(restInput);
    addAttribute(poses);
    addAttribute(poseInput);
    addAttribute(poseValue);
    addAttribute(output);
    addAttribute(baseValue);
    addAttribute(outputIsScale);
    addAttribute(clampEnabled);
    addAttribute(clampInflation);
    addAttribute(regularization);
    addAttribute(solverMethod);
    addAttribute(inputEncoding);
    addAttribute(driverInputRotateOrder);
    addAttribute(poseMode);
    addAttribute(twistAxis);
    addAttribute(opposite);
    addAttribute(poseAttributes);
    addAttribute(poseValues);
    addAttribute(poseRotateOrder);
    addAttribute(rbfMode);
    addAttribute(evaluate);
    addAttribute(kernel);
    addAttribute(radiusType);
    addAttribute(radius);
    addAttribute(useInterpolation);
    addAttribute(allowNegative);
    addAttribute(scale);
    addAttribute(distanceType);
    addAttribute(drawOrigin);
    addAttribute(drawDriver);
    addAttribute(drawPoses);
    addAttribute(drawIndices);
    addAttribute(drawTwist);
    addAttribute(poseLength);
    addAttribute(indexDist);
    addAttribute(driverIndex);
    addAttribute(colorDriver);
    addAttribute(controlNode);
    addAttribute(poseDrawVector);
    addAttribute(poseDrawTwist);
    addAttribute(exposeData);
    addAttribute(mean);
    addAttribute(variance);

    // -----------------------------------------------------------------
    // affects
    // -----------------------------------------------------------------

    attributeAffects(RBFtools::active, RBFtools::output);
    attributeAffects(RBFtools::allowNegative, RBFtools::output);
    attributeAffects(RBFtools::angle, RBFtools::output);
    attributeAffects(RBFtools::baseValue, RBFtools::output);
    attributeAffects(RBFtools::outputIsScale, RBFtools::output);
    attributeAffects(RBFtools::clampEnabled, RBFtools::output);
    attributeAffects(RBFtools::clampInflation, RBFtools::output);
    attributeAffects(RBFtools::regularization, RBFtools::output);
    attributeAffects(RBFtools::solverMethod, RBFtools::output);
    attributeAffects(RBFtools::inputEncoding, RBFtools::output);
    attributeAffects(RBFtools::driverInputRotateOrder, RBFtools::output);
    attributeAffects(RBFtools::radius, RBFtools::output);
    attributeAffects(RBFtools::centerAngle, RBFtools::output);
    attributeAffects(RBFtools::curveRamp, RBFtools::output);
    attributeAffects(RBFtools::direction, RBFtools::output);
    attributeAffects(RBFtools::distanceType, RBFtools::output);
    attributeAffects(RBFtools::driverIndex, RBFtools::output);
    attributeAffects(RBFtools::driverInput, RBFtools::output);
    attributeAffects(RBFtools::driverMatrix, RBFtools::output);
    attributeAffects(RBFtools::evaluate, RBFtools::output);
    attributeAffects(RBFtools::grow, RBFtools::output);
    attributeAffects(RBFtools::input, RBFtools::output);
    attributeAffects(RBFtools::interpolate, RBFtools::output);
    attributeAffects(RBFtools::invert, RBFtools::output);
    attributeAffects(RBFtools::kernel, RBFtools::output);
    attributeAffects(RBFtools::opposite, RBFtools::output);
    attributeAffects(RBFtools::poseInput, RBFtools::output);
    attributeAffects(RBFtools::poseMatrix, RBFtools::output);
    attributeAffects(RBFtools::poseMode, RBFtools::output);
    attributeAffects(RBFtools::poseParentMatrix, RBFtools::output);
    attributeAffects(RBFtools::poseValue, RBFtools::output);
    attributeAffects(RBFtools::scale, RBFtools::output);
    attributeAffects(RBFtools::rbfMode, RBFtools::output);
    attributeAffects(RBFtools::readerMatrix, RBFtools::output);
    attributeAffects(RBFtools::restInput, RBFtools::output);
    attributeAffects(RBFtools::translateMax, RBFtools::output);
    attributeAffects(RBFtools::translateMin, RBFtools::output);
    attributeAffects(RBFtools::twist, RBFtools::output);
    attributeAffects(RBFtools::twistAngle, RBFtools::output);
    attributeAffects(RBFtools::twistAxis, RBFtools::output);
    attributeAffects(RBFtools::type, RBFtools::output);
    attributeAffects(RBFtools::radiusType, RBFtools::output);
    attributeAffects(RBFtools::useInterpolation, RBFtools::output);
    attributeAffects(RBFtools::useRotate, RBFtools::output);
    attributeAffects(RBFtools::useTranslate, RBFtools::output);

    // -----------------------------------------------------------------
    // affects also the legacy outWeight plug
    // (to not break compatibility)
    // -----------------------------------------------------------------
    attributeAffects(RBFtools::active, RBFtools::outWeight);
    attributeAffects(RBFtools::angle, RBFtools::outWeight);
    attributeAffects(RBFtools::centerAngle, RBFtools::outWeight);
    attributeAffects(RBFtools::curveRamp, RBFtools::outWeight);
    attributeAffects(RBFtools::direction, RBFtools::outWeight);
    attributeAffects(RBFtools::driverMatrix, RBFtools::outWeight);
    attributeAffects(RBFtools::interpolate, RBFtools::outWeight);
    attributeAffects(RBFtools::invert, RBFtools::outWeight);
    attributeAffects(RBFtools::grow, RBFtools::outWeight);
    attributeAffects(RBFtools::readerMatrix, RBFtools::outWeight);
    attributeAffects(RBFtools::translateMax, RBFtools::outWeight);
    attributeAffects(RBFtools::translateMin, RBFtools::outWeight);
    attributeAffects(RBFtools::twist, RBFtools::outWeight);
    attributeAffects(RBFtools::twistAngle, RBFtools::outWeight);
    attributeAffects(RBFtools::type, RBFtools::outWeight);
    attributeAffects(RBFtools::useRotate, RBFtools::outWeight);
    attributeAffects(RBFtools::useTranslate, RBFtools::outWeight);

    return MStatus::kSuccess;
}


void RBFtools::postConstructor()
{
    MObject thisNode = this->thisMObject();
    MFnDependencyNode nodeFn(thisNode);
    nodeFn.setName("RBFtoolsShape#");

    // initialize the curve ramp
    postConstructor_init_curveRamp(thisNode, curveRamp, 0, 0.0f, 0.0f, 3);
    postConstructor_init_curveRamp(thisNode, curveRamp, 1, 1.0f, 1.0f, 3);

    // -----------------------------------------------------------------
    // hide the default attributes
    // -----------------------------------------------------------------

    MPlug attrPlug(thisNode, RBFtools::localPositionX);
    attrPlug.setChannelBox(false);
    attrPlug.setAttribute(RBFtools::localPositionY);
    attrPlug.setChannelBox(false);
    attrPlug.setAttribute(RBFtools::localPositionZ);
    attrPlug.setChannelBox(false);
    attrPlug.setAttribute(RBFtools::localScaleX);
    attrPlug.setChannelBox(false);
    attrPlug.setAttribute(RBFtools::localScaleY);
    attrPlug.setChannelBox(false);
    attrPlug.setAttribute(RBFtools::localScaleZ);
    attrPlug.setChannelBox(false);
}


MStatus RBFtools::postConstructor_init_curveRamp(MObject &nodeObj,
                                                     MObject &rampObj,
                                                     int index,
                                                     float position,
                                                     float value,
                                                     int interpolation)
{
    MStatus status;

    MPlug rampPlug(nodeObj, rampObj);
    MPlug elementPlug = rampPlug.elementByLogicalIndex((unsigned)index, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);
    MPlug positionPlug = elementPlug.child(0, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);
    status = positionPlug.setFloat(position);
    CHECK_MSTATUS_AND_RETURN_IT(status);
    MPlug valuePlug = elementPlug.child(1);
    status = valuePlug.setFloat(value);
    CHECK_MSTATUS_AND_RETURN_IT(status);
    MPlug interpolationPlug = elementPlug.child(2);
    interpolationPlug.setInt(interpolation);

    return status;
}


// ---------------------------------------------------------------------
// compute function
// ---------------------------------------------------------------------

MStatus RBFtools::compute(const MPlug &plug, MDataBlock &data)
{
    MStatus status = MStatus::kSuccess;

    MObject thisNode = this->thisMObject();
    MFnDependencyNode thisFn(thisNode);
    MString thisName = thisFn.name();

    // -----------------------------------------------------------------
    // get the attributes
    // -----------------------------------------------------------------

    MPlug activePlug(thisNode, RBFtools::active);
    MPlug allowNegativePlug(thisNode, RBFtools::allowNegative);
    MPlug anglePlug(thisNode, RBFtools::angle);
    MPlug radiusPlug(thisNode, RBFtools::radius);
    MPlug centerAnglePlug(thisNode, RBFtools::centerAngle);
    MPlug dirPlug(thisNode, RBFtools::direction);
    MPlug distanceTypePlug(thisNode, RBFtools::distanceType);
    MPlug driverIndexPlug(thisNode, RBFtools::driverIndex);
    MPlug evaluatePlug(thisNode, RBFtools::evaluate);
    MPlug exposeDataPlug(thisNode, RBFtools::exposeData);
    MPlug interpolatePlug(thisNode, RBFtools::interpolate);
    MPlug invPlug(thisNode, RBFtools::invert);
    MPlug useMaxPlug(thisNode, RBFtools::grow);
    MPlug kernelPlug(thisNode, RBFtools::kernel);
    MPlug oppositePlug(thisNode, RBFtools::opposite);
    MPlug rbfModePlug(thisNode, RBFtools::rbfMode);
    MPlug scalePlug(thisNode, RBFtools::scale);
    MPlug translateMaxPlug(thisNode, RBFtools::translateMax);
    MPlug translateMinPlug(thisNode, RBFtools::translateMin);
    MPlug twistPlug(thisNode, RBFtools::twist);
    MPlug twistAnglePlug(thisNode, RBFtools::twistAngle);
    MPlug twistAxisPlug(thisNode, RBFtools::twistAxis);
    MPlug typePlug(thisNode, RBFtools::type);
    MPlug radiusTypePlug(thisNode, RBFtools::radiusType);
    MPlug useInterpolationPlug(thisNode, RBFtools::useInterpolation);
    MPlug useRotatePlug(thisNode, RBFtools::useRotate);
    MPlug useTranslatePlug(thisNode, RBFtools::useTranslate);
    MPlug meanPlug(thisNode, RBFtools::mean);
    MPlug variancePlug(thisNode, RBFtools::variance);

    bool activeVal = activePlug.asBool();
    bool allowNegativeVal = allowNegativePlug.asBool();
    // M1.3: Driver Clamp plug reads. Non-array scalars, no dirty tracker
    // needed — clamp is inference-only and does not enter the weight solve.
    MPlug clampEnabledPlug(thisNode, RBFtools::clampEnabled);
    MPlug clampInflationPlug(thisNode, RBFtools::clampInflation);
    bool clampEnabledVal = clampEnabledPlug.asBool();
    double clampInflationVal = clampInflationPlug.asDouble();
    // M1.4: solver configuration. Both participate in the train path;
    // regularization changes require a re-solve (attributeAffects handles
    // this — λ is folded into linMat, which is a local, not a cache).
    MPlug regularizationPlug(thisNode, RBFtools::regularization);
    MPlug solverMethodPlug(thisNode, RBFtools::solverMethod);
    double regularizationVal = regularizationPlug.asDouble();
    short  solverMethodVal   = solverMethodPlug.asShort();
    // M2.1a: inputEncoding + per-driver-group rotate order. Read early
    // so the safety net can remap BendRoll/SwingTwist -> Raw with a
    // single warning before any encoding math runs.
    MPlug inputEncodingPlug(thisNode, RBFtools::inputEncoding);
    short inputEncodingVal = inputEncodingPlug.asShort();
    std::vector<short> driverRotateOrders;
    {
        MStatus dstat;
        MArrayDataHandle droHandle =
            data.inputArrayValue(driverInputRotateOrder, &dstat);
        if (dstat == MStatus::kSuccess)
        {
            unsigned cnt = droHandle.elementCount();
            for (unsigned k = 0; k < cnt; ++k)
            {
                if (droHandle.jumpToArrayElement(k) == MStatus::kSuccess)
                {
                    unsigned idx = droHandle.elementIndex();
                    if (idx >= driverRotateOrders.size())
                        driverRotateOrders.resize(idx + 1, 0);
                    driverRotateOrders[idx] =
                        droHandle.inputValue().asShort();
                }
            }
        }
    }
    // Reset the once-per-rig warning flag whenever the user changes
    // encoding — they should get a fresh warning if the new mode also
    // trips the safety net.
    if (inputEncodingVal != prevInputEncodingVal)
    {
        inputEncodingWarningIssued = false;
        prevInputEncodingVal = inputEncodingVal;
    }
    angleVal = anglePlug.asDouble();
    radiusVal = radiusPlug.asDouble();
    centerAngleVal = centerAnglePlug.asDouble();
    dirVal = dirPlug.asShort();
    distanceTypeVal = distanceTypePlug.asShort();
    int driverIndexVal = driverIndexPlug.asInt();
    evalInput = evaluatePlug.asBool();
    int exposeDataVal = exposeDataPlug.asInt();
    bool growVal = useMaxPlug.asBool();
    short interVal = interpolatePlug.asShort();
    invVal = invPlug.asBool();
    kernelVal = kernelPlug.asShort();
    bool oppositeVal = oppositePlug.asBool();
    double scaleVal = scalePlug.asDouble();
    double twistAngleVal = twistAnglePlug.asDouble();
    short twistAxisVal = twistAxisPlug.asShort();
    bool twistVal = twistPlug.asBool();
    double translateMaxVal = translateMaxPlug.asDouble();
    double translateMinVal = translateMinPlug.asDouble();
    bool useInterpolationVal = useInterpolationPlug.asBool();
    bool useRotateVal = useRotatePlug.asBool();
    bool useTranslateVal = useTranslatePlug.asBool();
    typeVal = typePlug.asShort();
    radiusTypeVal = radiusTypePlug.asShort();
    meanVal = meanPlug.asDouble();
    varianceVal = variancePlug.asDouble();

    curveAttr = MRampAttribute(thisNode, curveRamp, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);

    if (((plug == output && typeVal != 0) || (plug == outWeight && typeVal == 0)) && activeVal)
    {
        // Deactivate the node if the state is set to HasNoEffect.
        MDataHandle stateData = data.inputValue(state, &status);
        if (stateData.asShort() == 1)
            return status;

        // -------------------------------------------------------------
        // main calculation
        // -------------------------------------------------------------

        MDoubleArray weightsArray;
        unsigned poseCount = 1;

        // -------------------------------------------------------------
        // vector angle
        // -------------------------------------------------------------

        if (typeVal == 0)
        {
            // ---------------------------------------------------------
            // get the general matrix data handles
            // ---------------------------------------------------------

            MDataHandle readerHandle = data.inputValue(readerMatrix, &status);
            CHECK_MSTATUS_AND_RETURN_IT(status);
            MMatrix readerMat = readerHandle.asMatrix();

            MDataHandle driverHandle = data.inputValue(driverMatrix, &status);
            CHECK_MSTATUS_AND_RETURN_IT(status);
            MMatrix driverMat = driverHandle.asMatrix();

            MTransformationMatrix transMatReader = readerMat;
            MTransformationMatrix transMatDriver = driverMat;

            MVector readerPos = transMatReader.getTranslation(MSpace::kWorld);
            MVector driverPos = transMatDriver.getTranslation(MSpace::kWorld);

            MVector driverMVec = driverPos - readerPos;

            weightsArray.setLength(poseCount);

            // ---------------------------------------------------------
            // define the target vector
            // ---------------------------------------------------------

            MPoint targetPos;
            MVector upMVec;

            double axis = 1.0;
            if (invVal)
                axis = -1.0;

            if (dirVal == 0)
            {
                targetPos = MPoint(axis, 0.0, 0.0);
                upMVec = MVector(0.0, 1.0, 0.0);
            }
            else if (dirVal == 1)
            {
                targetPos = MPoint(0.0, axis, 0.0);
                upMVec = MVector(1.0, 0.0, 0.0);
            }
            else
            {
                targetPos = MPoint(0.0, 0.0, axis);
                upMVec = MVector(1.0, 0.0, 0.0);
            }

            targetPos *= readerMat;

            MVector targetMVec = targetPos - readerPos;
            MMatrix relativeMat = readerMat * driverMat.inverse();

            // ---------------------------------------------------------
            // calculate the twist value
            // ---------------------------------------------------------

            double twistWeightVal = 1.0;

            if (twistVal)
            {
                MVector twistMVec = upMVec * relativeMat;
                twistMVec.normalize();

                double twistAngle = twistMVec.angle(upMVec);
                twistAngle = twistAngle * RADTODEG;

                twistWeightVal = 1 - twistAngle / twistAngleVal;
            }

            // ---------------------------------------------------------
            // calculate the translate value
            // ---------------------------------------------------------

            double translateVal = 1;

            if (useTranslateVal)
            {
                MTransformationMatrix transMatRelative = relativeMat;
                MVector transMVec = transMatRelative.getTranslation(MSpace::kWorld);
                double distance = transMVec.length();
                if (distance <= translateMinVal)
                    translateVal = 1;
                else if (distance >= translateMaxVal)
                    translateVal = 0;
                else
                {
                    translateVal = 1 - ((distance - translateMinVal)
                                   / (translateMaxVal - translateMinVal));
                }

                if (growVal)
                    translateVal = 1 - translateVal;
            }

            // ---------------------------------------------------------
            // calculate the vectors and resulting angle
            // ---------------------------------------------------------

            double weightVal = 1;

            if (useRotateVal)
            {
                double offsetAngle = targetMVec.angle(driverMVec);
                offsetAngle = offsetAngle * RADTODEG;

                weightVal = 1 - offsetAngle / angleVal;

                weightVal *= twistWeightVal;

                // Make sure that the center angle is always smaller
                // than the angle.
                if (angleVal <= centerAngleVal)
                    centerAngleVal = angleVal - 0.1;

                // Create another value from the center angle to
                // calculate an offset factor for widening the center
                // range.
                double centerVal = (angleVal - centerAngleVal) / angleVal;
                weightVal /= centerVal;
            }

            weightVal *= translateVal;

            // Clamp the value to a 0-1 range.
            if (weightVal <= 0)
                weightVal = 0;
            else if (weightVal >= 1)
                weightVal = 1;

            // ---------------------------------------------------------
            // apply the interpolation
            // ---------------------------------------------------------

            weightVal = interpolateWeight(weightVal, interVal);

            // ---------------------------------------------------------
            // set the output values
            // ---------------------------------------------------------

            // Pass the weight to the array output.
            weightsArray.set(weightVal, 0);

            // Pass the weight to the legacy outWeight plug.
            MDataHandle outWeightHandle = data.outputValue(outWeight);
            outWeightHandle.setDouble(weightsArray[0]);
        }

        // -------------------------------------------------------------
        // radial basis function
        // -------------------------------------------------------------

        else
        {
            unsigned int i, c;

            std::vector<double> driver;
            unsigned int solveCount;
            unsigned int driverCount = 0;

            // ---------------------------------------------------------
            // Check the rbf mode.
            // Any connected input assumes generic mode which is mainly
            // for switching the display of the locator.
            // ---------------------------------------------------------

            MPlug inputPlug(thisNode, RBFtools::input);
            MIntArray inputIds;
            inputPlug.getExistingArrayAttributeIndices(inputIds, &status);
            CHECK_MSTATUS_AND_RETURN_IT(status);

            // Set generic mode to be the default.
            genericMode = true;
            if (inputIds.length())
            {
                MDataHandle rbfModeHandle = data.outputValue(rbfMode);
                rbfModeHandle.set(0);
                genericMode = true;
            }
            else
            {
                MDataHandle rbfModeHandle = data.outputValue(rbfMode);
                rbfModeHandle.set(1);
                genericMode = false;
            }

            // ---------------------------------------------------------
            // get the pose data based on the mode
            // ---------------------------------------------------------

            // M2.1a: resolve effective encoding via safety net BEFORE
            // calling getPoseData. BendRoll (2) / SwingTwist (4) are
            // declared but not implemented — they fall back to Raw with
            // a once-per-rig warning. A non-Raw encoding on inDim that
            // is not a multiple of 3 also falls back to Raw with a
            // distinct warning. This preserves the v5 contract that the
            // rig never stops DG evaluation due to an unimplemented /
            // misconfigured encoding; users see a loud warning in the
            // Script Editor and can correct or accept the Raw fallback.
            //
            // Declared at the outer (RBF else-branch) scope so the later
            // getDistances / getPoseWeights call sites can see it.
            short effectiveEncoding = inputEncodingVal;
            if (genericMode)
            {
                const unsigned rawInDim = inputIds.length();
                const bool wantsEncoded = (inputEncodingVal != 0);
                const bool placeholder = (inputEncodingVal == 2 ||
                                          inputEncodingVal == 4);
                const bool nonTriple = (wantsEncoded && rawInDim % 3 != 0);

                if (placeholder)
                {
                    if (!inputEncodingWarningIssued)
                    {
                        MGlobal::displayWarning(thisName + MString(
                            ": inputEncoding ") +
                            (inputEncodingVal == 2 ? "BendRoll" : "SwingTwist") +
                            " lands in M2.1b; falling back to Raw.");
                        inputEncodingWarningIssued = true;
                    }
                    effectiveEncoding = 0;
                }
                else if (nonTriple)
                {
                    if (!inputEncodingWarningIssued)
                    {
                        MGlobal::displayWarning(thisName + MString(
                            ": inputEncoding requires driver inputs in "
                            "(rx, ry, rz) triples; inDim=") + int(rawInDim) +
                            " is not a multiple of 3. Falling back to Raw.");
                        inputEncodingWarningIssued = true;
                    }
                    effectiveEncoding = 0;
                }

                unsigned driverSize = rawInDim;
                driver.resize(driverSize);

                unsigned effInDim = 0;
                status = getPoseData(data,
                                     driver,
                                     poseCount,
                                     solveCount,
                                     matPoses,
                                     matValues,
                                     poseModes,
                                     inputNorms,
                                     (int)effectiveEncoding,
                                     driverRotateOrders,
                                     effInDim);
                CHECK_MSTATUS_AND_RETURN_IT(status);
            }
            else
            {
                // get the driver indices
                MPlug driverPlug(thisNode, RBFtools::driverList);
                MIntArray driverIds;
                driverPlug.getExistingArrayAttributeIndices(driverIds, &status);
                CHECK_MSTATUS_AND_RETURN_IT(status);

                driverCount = driverIds.length();
                driver.resize(4 * driverCount);

                status = getPoseVectors(data,
                                        driver,
                                        poseCount,
                                        matPoses,
                                        matValues,
                                        poseModes,
                                        (unsigned)twistAxisVal,
                                        oppositeVal,
                                        (unsigned)driverIndexVal,
                                        inputNorms);
                CHECK_MSTATUS_AND_RETURN_IT(status);

                // M2.1a Bug 2 fix: honour the user's distanceType choice
                // in Matrix mode. The former `distanceTypeVal = 0` override
                // silently forced Euclidean; now Angle routes through
                // getMatrixModeAngleDistance via getPoseDelta's
                // isMatrixMode branch (M1.1 addendum §Bug 2).

                // Matrix mode ignores inputEncoding per (F)① contract.
                // Normalise effectiveEncoding to 0 so the downstream
                // getDistances / getPoseWeights calls never receive a
                // mixed (isMatrixMode=true, encoding≠0) pair.
                effectiveEncoding = 0;

                solveCount = poseCount;
            }

            // M1.3: clip driver to the per-dim training-hull bounding box.
            // Bounds were cached by getPoseData / getPoseVectors in raw
            // (pre-normalize) space, so `clampInflation` is in user scene
            // units — not normalized units. Matrix mode skips the twist
            // slot (j % 4 == 3) because twist is a wrap-aware circular
            // quantity (see v5 addendum 2026-04-24 §M1.1) and linear
            // clamping would freeze the wrap corrections M1.1 fixed.
            // Defense: empty cache (first compute before any train) and
            // size-mismatch (driver dim changed but bounds stale) both
            // short-circuit to preserve current behaviour rather than
            // crash on an index out of range.
            if (clampEnabledVal
                && !poseMinVec.empty()
                && poseMinVec.size() == driver.size()
                && poseMaxVec.size() == driver.size())
            {
                for (size_t j = 0; j < driver.size(); ++j)
                {
                    if (!genericMode && (j % 4 == 3))
                        continue;
                    const double r = poseMaxVec[j] - poseMinVec[j];
                    const double lo = poseMinVec[j] - clampInflationVal * r;
                    const double hi = poseMaxVec[j] + clampInflationVal * r;
                    if (driver[j] < lo) driver[j] = lo;
                    else if (driver[j] > hi) driver[j] = hi;
                }
            }

            // M1.2: read per-output baseline + isScale arrays aligned to
            // solveCount. Generic mode subtracts the per-dim anchor before
            // the weight solve and re-adds it after inference; Matrix mode
            // (blendShape blend-weight output) has no baseline semantics
            // and leaves the arrays zeroed/false. Sparse index handling
            // mirrors getPoseData's jumpToElement pattern.
            std::vector<double> baseValueArr(solveCount, 0.0);
            std::vector<bool>   outputIsScaleArr(solveCount, false);
            if (genericMode && solveCount > 0)
            {
                MArrayDataHandle bvHandle = data.inputArrayValue(baseValue, &status);
                if (status == MStatus::kSuccess)
                {
                    for (unsigned int jj = 0; jj < solveCount; ++jj)
                    {
                        if (bvHandle.jumpToElement(jj) == MStatus::kSuccess)
                            baseValueArr[jj] = bvHandle.inputValue().asDouble();
                    }
                }
                MArrayDataHandle isHandle = data.inputArrayValue(outputIsScale, &status);
                if (status == MStatus::kSuccess)
                {
                    for (unsigned int jj = 0; jj < solveCount; ++jj)
                    {
                        if (isHandle.jumpToElement(jj) == MStatus::kSuccess)
                            outputIsScaleArr[jj] = isHandle.inputValue().asBool();
                    }
                }

                // Trip a re-solve when the baseline spec changed since last
                // compute. attributeAffects alone would reuse the cached
                // wMat and produce incorrect output after the user edits
                // baseValue / outputIsScale live.
                if (baseValueArr != prevBaseValueArr ||
                    outputIsScaleArr != prevOutputIsScaleArr)
                {
                    evalInput = true;
                    prevBaseValueArr = baseValueArr;
                    prevOutputIsScaleArr = outputIsScaleArr;
                }
            }

            // Store the pose values for debugging.
            // The original values get normalized before solving
            // therefore, a copy needs to be kept for when the solve
            // fails.
            matDebug = matPoses;

            if (exposeDataVal == 1 || exposeDataVal == 4)
            {
                matPoses.show(thisName, "Poses (normalized)");
                matValues.show(thisName, "Values");
                //BRMatrix().showVector(driver, "driver");
            }

            // ---------------------------------------------------------
            // rbf calculation
            // ---------------------------------------------------------

            if (poseCount != 0)
            {
                // Set the default values for the output.
                weightsArray.setLength(solveCount);
                for (i = 0; i < solveCount; i ++)
                    weightsArray.set(0.0, i);

                if (evalInput)
                {
                    // MGlobal::displayInfo("Initialize matrices");
                                        
                    // -------------------------------------------------
                    // distances
                    // -------------------------------------------------

                    // Create a distance matrix from all poses and
                    // calculate the mean and standard deviation for the
                    // rbf function.
                    BRMatrix linMat;
                    linMat = getDistances(matPoses, distanceTypeVal,
                                          (int)effectiveEncoding,
                                          /*isMatrixMode*/ !genericMode);
                    meanVal = linMat.mean();
                    varianceVal = linMat.variance();
                    
                    // Store the mean distance and variance on the
                    // hidden attributes to be able to access them when
                    // the radius type changes.
                    meanPlug.setValue(meanVal);
                    variancePlug.setValue(varianceVal);

                    if (exposeDataVal > 2)
                    {
                        linMat.show(thisName, "Distance matrix");
                        MGlobal::displayInfo(MString("Mean distance: ") + meanVal);
                        MGlobal::displayInfo(MString("Variance: ") + varianceVal);
                    }
                    
                    // -------------------------------------------------
                    // activations
                    // -------------------------------------------------

                    // Transform the distance matrix to include the
                    // activation values.
                    getActivations(linMat, getRadiusValue(), kernelVal);

                    if (exposeDataVal > 2)
                        linMat.show(thisName, "Activations");

                    // -------------------------------------------------
                    // M1.4: Tikhonov regularization. Inject λI in place
                    // into linMat BEFORE any solver copy, so both the
                    // Cholesky probe and the GE fallback share the same
                    // regularized operator. Absolute λ (addendum §M1.4):
                    // scale-adaptive forms silently fail on Linear / TP
                    // kernels where K[i,i] = φ(0) = 0.
                    // -------------------------------------------------

                    if (regularizationVal > 0.0)
                    {
                        for (unsigned dd = 0; dd < poseCount; ++dd)
                            linMat(dd, dd) += regularizationVal;
                    }

                    if (exposeDataVal > 2 && regularizationVal > 0.0)
                        linMat.show(thisName, "Activations + λI");

                    // -------------------------------------------------
                    // M1.4: reset the solver-tier cache when the user
                    // flipped Auto <-> ForceGE. Kernel SPD-ness is a
                    // property of the kernel, not the solver selection,
                    // so we do NOT clear this on evalInput==true alone.
                    // -------------------------------------------------

                    if (solverMethodVal != prevSolverMethodVal)
                    {
                        lastSolveMethod = 0;
                        prevSolverMethodVal = solverMethodVal;
                    }

                    // -------------------------------------------------
                    // Collect per-dimension target vectors with M1.2
                    // baseline subtracted. Done once before solver
                    // dispatch so Cholesky and GE paths share the same
                    // RHS list.
                    // -------------------------------------------------

                    std::vector< std::vector<double> > yCols(solveCount);
                    for (c = 0; c < solveCount; c ++)
                    {
                        yCols[c] = matValues.getColumnVector(c);
                        if (genericMode)
                        {
                            const double anchor = outputIsScaleArr[c] ? 1.0 : baseValueArr[c];
                            if (anchor != 0.0)
                            {
                                for (size_t yr = 0; yr < yCols[c].size(); ++yr)
                                    yCols[c][yr] -= anchor;
                            }
                        }
                    }

                    // -------------------------------------------------
                    // solve for each dimension (M1.4 tiered dispatch)
                    // -------------------------------------------------

                    wMat = BRMatrix();
                    wMat.setSize(poseCount, solveCount);

                    bool usedCholesky = false;

                    // Tier 1 — Cholesky. Attempted only in Auto mode and
                    // when the last successful method was Cholesky (or
                    // this is the first train since solverMethod flipped).
                    // One decomposition amortizes over all output dims:
                    // O(N³/3) + m·O(N²), vs GE's m·O(N³).
                    if (solverMethodVal == 0 && lastSolveMethod == 0)
                    {
                        BRMatrix chol = linMat;
                        if (chol.cholesky())
                        {
                            std::vector<double> x;
                            for (c = 0; c < solveCount; c ++)
                            {
                                chol.choleskySolve(yCols[c], x);
                                for (i = 0; i < poseCount; i ++)
                                    wMat(i, c) = x[i];
                            }
                            usedCholesky = true;
                            lastSolveMethod = 0;
                            if (exposeDataVal > 2)
                                MGlobal::displayInfo(
                                    thisName + MString(": solver = Cholesky"));
                        }
                    }

                    // Tier 2 — GE fallback. Triggered by ForceGE, a failed
                    // Cholesky probe, or sticky lastSolveMethod == 1 on a
                    // known non-SPD kernel. Per-dim solve is unavoidable
                    // here because BRMatrix::solve is destructive.
                    if (!usedCholesky)
                    {
                        for (c = 0; c < solveCount; c ++)
                        {
                            BRMatrix solveMat = linMat;
                            double* w = new double[poseCount];
                            int singularIndex;
                            bool solved = solveMat.solve(yCols[c], w, singularIndex);
                            if (!solved)
                            {
                                MGlobal::displayInfo("");
                                MGlobal::displayInfo(thisName + MString(": RBF Error"));
                                MGlobal::displayInfo(MString("Value error for pose at index: ") + singularIndex);
                                MGlobal::displayInfo("The pose has no unique values and matches another pose.");
                                matDebug.show(thisName, "Pose Input Values (Poses appear in rows)");
                                MGlobal::displayError("RBF decomposition failed. See script editor for details.");
                                delete[] w;
                                return MStatus::kFailure;
                            }

                            for (i = 0; i < poseCount; i ++)
                                wMat(i, c) = w[i];

                            delete[] w;
                        }
                        lastSolveMethod = 1;
                        if (exposeDataVal > 2)
                            MGlobal::displayInfo(
                                thisName + MString(": solver = GE (fallback)"));
                    }

                    if (exposeDataVal > 2)
                        wMat.show(thisName, "Weight matrix");
                }

                // -----------------------------------------------
                // final weight calculation
                // -----------------------------------------------

                getPoseWeights(weightsArray,
                               matPoses,
                               inputNorms,
                               driver,
                               poseModes,
                               wMat,
                               getRadiusValue(),
                               distanceTypeVal,
                               (int)effectiveEncoding,
                               /*isMatrixMode*/ !genericMode,
                               kernelVal);

                if (exposeDataVal == 2 || exposeDataVal == 4)
                    showArray(weightsArray, thisName + " : RBF Weights");

                // -----------------------------------------------
                // define the final values
                // -----------------------------------------------

                for (i = 0; i < weightsArray.length(); i ++)
                {
                    double value = weightsArray[i];

                    if (value < 0.0 && !allowNegativeVal)
                        value = 0.0;

                    if (useInterpolationVal)
                        value = interpolateWeight(value, interVal);

                    value *= scaleVal;

                    // M1.2: add per-dimension anchor back in Generic mode,
                    // *after* allowNegative / interpolateWeight / scale so
                    // those legacy controls keep shaping the delta (not the
                    // absolute output). Matrix-mode weightsArray indexes
                    // poses, not output dims, so no add-back.
                    if (genericMode && i < outputIsScaleArr.size())
                    {
                        value += outputIsScaleArr[i] ? 1.0 : baseValueArr[i];
                    }

                    // Set the final weight.
                    weightsArray.set(value, i);
                }
            }
            // In case there are no poses generate a default value at
            // the output.
            else
            {
                weightsArray.setLength(1);
                weightsArray.set(1.0, 0);
            }
        }

        // -----------------------------------------------
        // pass the pose value to the output
        // -----------------------------------------------

        setOutputValues(weightsArray, data, false);

        data.setClean(plug);
    }
    else if (plug == output && !activeVal)
    {
        setOutputValues(MDoubleArray(1, 0.0), data, true);

        data.setClean(plug);
    }

    return MStatus::kSuccess;
}


//
// Description:
//      Collect all driver and pose relevant data.
//      RBF Matrix Mode (when using SHAPES)
//
// Input Arguments:
//      data            The MPxNode dataBlock.
//      driver          The array of driver values. Each driver has four
//                      values: the vector and the twist value. The
//                      array length is numberOfDrivers * 4.
//      poseCount       The number of poses.
//      poseData        The matrix containing all poses.
//      poseVals        The matrix of pose values.
//      poseModes       The array containing the the mode per pose.
//      twistAxisVal    The twist axis.
//      invertAxes      True, if the axis should be inverted.
//      driverId        The index of the driver for drawing.
//
// Return Value:
//      MStatus
//
MStatus RBFtools::getPoseVectors(MDataBlock &data,
                                     std::vector<double> &driver,
                                     unsigned &poseCount,
                                     BRMatrix &poseData,
                                     BRMatrix &poseVals,
                                     MIntArray &poseModes,
                                     unsigned twistAxisVal,
                                     bool invertAxes,
                                     unsigned driverId,
                                     std::vector<double>&normFactors)
{
    MStatus status = MStatus::kSuccess;

    MObject thisNode = this->thisMObject();

    unsigned int d, i, p;
    unsigned increment = 0;

    // -----------------------------------------------------------------
    // create the base vector
    // -----------------------------------------------------------------

    MVector baseVec(1.0, 0.0, 0.0);
    // Define the reference vector base.
    if (twistAxisVal == 1)
        baseVec = MVector(0.0, 1.0, 0.0);
    else if (twistAxisVal == 2)
        baseVec = MVector(0.0, 0.0, 1.0);

    if (invertAxes)
        baseVec *= -1;

    // -----------------------------------------------------------------
    // get the driver list handle
    // -----------------------------------------------------------------

    MArrayDataHandle driverListHandle = data.inputArrayValue(driverList, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);
    unsigned driverCount = driverListHandle.elementCount();

    // This plug is necessary to get the connected node for the parent
    // matrix and dag type since the MDataHandle cannot be used for
    // this.
    MPlug driverListPlug(thisNode, RBFtools::driverList);

    // -----------------------------------------------------------------
    // process for each driver
    // -----------------------------------------------------------------

    for (d = 0; d < driverCount; d ++)
    {
        status = driverListHandle.jumpToArrayElement(d);
        CHECK_MSTATUS_AND_RETURN_IT(status);
        unsigned currentId = driverListHandle.elementIndex();

        MDataHandle driverListIdHandle = driverListHandle.inputValue();

        // -------------------------------------------------------------
        // get the attributes
        // -------------------------------------------------------------

        MDataHandle driverInputHandle = driverListIdHandle.child(driverInput);
        MMatrix driverMat = driverInputHandle.asMatrix();

        MDataHandle poseHandle = driverListIdHandle.child(pose);
        MArrayDataHandle poseArrayHandle(poseHandle, &status);
        CHECK_MSTATUS_AND_RETURN_IT(status);

        // -------------------------------------------------------------
        // get the parent matrix and joint orientation
        // -------------------------------------------------------------

        MPlug driverListIdPlug = driverListPlug.elementByLogicalIndex(currentId);
        MPlug driverInputPlug = driverListIdPlug.child(driverInput);
        MPlug posePlug = driverListIdPlug.child(pose);

        // Check if the driver node is connected.
        // Cancel if not connected.
        MPlugArray plugConn;
        driverInputPlug.connectedTo(plugConn, true, false, &status);
        CHECK_MSTATUS_AND_RETURN_IT(status);
        if (!plugConn.length())
            return status;

        // Retrieve the dag path of the driver node to get the parent
        // matrix.
        MDagPath dagPath;
        MDagPath::getAPathTo(plugConn[0].node(), dagPath);
        MMatrix driverParentMatInv = dagPath.exclusiveMatrixInverse();

        // In case the driver node is a joint the joint orientation
        // needs to be considered as well.
        MMatrix jointOrientMatInv;
        if (dagPath.hasFn(MFn::kJoint))
        {
            MFnIkJoint joint(dagPath);
            MQuaternion jointOrientQuat;
            joint.getOrientation(jointOrientQuat);
            jointOrientMatInv = jointOrientQuat.asMatrix().inverse();
        }

        // Build a local transform matrix.
        MTransformationMatrix transMatDriver = driverMat * driverParentMatInv * jointOrientMatInv;

        MQuaternion quatDriver = transMatDriver.rotation();

        // -------------------------------------------------------------
        // create the driver vector
        // -------------------------------------------------------------

        MVector driverMVec = baseVec * transMatDriver.asMatrix();
        MVector driverMVecDraw = baseVec * driverMat;

        // -------------------------------------------------------------
        // set the driver vector and twist
        // -------------------------------------------------------------

        driver[0 + increment] = driverMVec.x;
        driver[1 + increment] = driverMVec.y;
        driver[2 + increment] = driverMVec.z;
        driver[3 + increment] = getTwistAngle(quatDriver, twistAxisVal);

        // -------------------------------------------------------------
        // get the pose array indices and set the matrices
        // -------------------------------------------------------------

        // Do this only for the first driver because even if there is
        // more than one driver all other drivers should have the same
        // amount of poses and data values.
        if (d == 0)
        {
            posePlug.getExistingArrayAttributeIndices(poseMatrixIds, &status);
            CHECK_MSTATUS_AND_RETURN_IT(status);

            poseCount = poseMatrixIds.length();

            if (poseCount != globalPoseCount)
            {
                globalPoseCount = poseCount;
                evalInput = true;
            }

            // ---------------------------------------------------------
            // prepare the data matrices
            // ---------------------------------------------------------

            // Prepare the matrix to hold the pose vectors.
            // Assign an empty matrix to clear pre-existing data.
            poseData = BRMatrix();
            poseData.setSize(poseCount, 4 * driverCount);

            // Prepare the matrix to hold the pose values.
            // Assign an empty matrix to clear pre-existing data.
            poseVals = BRMatrix();
            poseVals.setSize(poseCount, poseCount);
        }

        // -------------------------------------------------------------
        // get the pose matrices and define the pose vectors
        // -------------------------------------------------------------

        if (poseCount)
        {
            // ---------------------------------------------------------
            // prepare the data matrices
            // ---------------------------------------------------------

            MVectorArray poseVectors;
            poseVectors.setLength(poseCount);
            MDoubleArray poseTwist;
            poseTwist.setLength(poseCount);
            MVectorArray poseVectorsDraw;
            poseVectorsDraw.setLength(poseCount);

            // Copy the previous pose modes for comparison to see
            // if the matrices need to get updated.
            MIntArray poseModesPrev = poseModes;

            // Clear pre-existing pose modes.
            poseModes.clear();
            poseModes.setLength(poseCount);

            // ---------------------------------------------------------
            // get the pose data
            // ---------------------------------------------------------

            for (i = 0; i < poseCount; i ++)
            {
                status = poseArrayHandle.jumpToArrayElement(i);
                CHECK_MSTATUS_AND_RETURN_IT(status);

                MDataHandle poseIdHandle = poseArrayHandle.inputValue();
                MDataHandle poseMatrixHandle = poseIdHandle.child(poseMatrix);
                MMatrix poseMat = poseMatrixHandle.asMatrix();

                MDataHandle parentMatrixHandle = poseIdHandle.child(poseParentMatrix);
                MMatrix parentMat = parentMatrixHandle.asMatrix();

                MMatrix poseMatRel = poseMat * parentMat.inverse() * jointOrientMatInv;

                // -----------------------------------------------------
                // pose mode
                // -----------------------------------------------------

                MDataHandle poseModeHandle = poseIdHandle.child(poseMode);
                int poseModeValue = poseModeHandle.asShort();
                poseModes.set(poseModeValue, i);

                // Evaluation for the processing the matrices always
                // needs to be active when the pose mode for a pose
                // changes.
                if (poseModesPrev.length() && poseModeValue != poseModesPrev[i])
                    evalInput = true;

                // -----------------------------------------------------
                // pose vectors
                // -----------------------------------------------------

                MVector poseVec = baseVec * poseMatRel;
                poseVectors.set(poseVec, i);

                MVector poseVecDraw = baseVec * poseMat;
                poseVectorsDraw.set(poseVecDraw, i);

                // -----------------------------------------------------
                // pose vector and twist angle
                // -----------------------------------------------------

                MTransformationMatrix transMatPose = poseMatRel;
                MQuaternion quatPose = transMatPose.rotation();

                if (poseModes[i] != 2)
                {
                    poseData(i, 0 + increment) = poseVec.x;
                    poseData(i, 1 + increment) = poseVec.y;
                    poseData(i, 2 + increment) = poseVec.z;
                }

                poseData(i, 3 + increment) = 0.0;
                poseTwist.set(0.0, i);
                if (poseModes[i] != 1)
                {
                    double twistVal = getTwistAngle(quatPose, twistAxisVal);
                    poseData(i, 3 + increment) = twistVal;
                    poseTwist.set(twistVal, i);
                }

                // -----------------------------------------------------
                // pose values
                // -----------------------------------------------------

                // Create the vector for the pose values.
                if (d == 0)
                {
                    for (p = 0; p < poseCount; p ++)
                    {
                        poseVals(i, p) = 0;
                        if (i == p)
                            poseVals(i, p) = 1;
                    }
                }
            }

            // ---------------------------------------------------------
            // fill the array for drawing
            // ---------------------------------------------------------

            if (d == driverId)
            {
                // Copy the pose vectors and twist values for the VP 2.0
                // display.
                MArrayDataHandle pvHandle = data.outputArrayValue(poseDrawVector);
                MArrayDataBuilder pvBuilder(&data, poseDrawVector, poseCount + 1);
                MArrayDataHandle ptHandle = data.outputArrayValue(poseDrawTwist);
                MArrayDataBuilder ptBuilder(&data, poseDrawTwist, poseCount + 1);
                for (i = 0; i < poseCount; i ++)
                {
                    MDataHandle pvIdHandle = pvBuilder.addElement((unsigned)poseMatrixIds[i]);
                    pvIdHandle.set3Double(poseVectorsDraw[i].x, poseVectorsDraw[i].y, poseVectorsDraw[i].z);
                    pvHandle.set(pvBuilder);
                    pvHandle.setAllClean();

                    MDataHandle ptIdHandle = ptBuilder.addElement((unsigned)poseMatrixIds[i]);
                    ptIdHandle.setDouble(poseData(i, 3 + increment));
                    ptHandle.set(ptBuilder);
                    ptHandle.setAllClean();
                }
                // Add the driver vector.
                MDataHandle pvIdHandle = pvBuilder.addElement((unsigned)poseMatrixIds[poseCount - 1] + 1);
                pvIdHandle.set3Double(driverMVecDraw.x, driverMVecDraw.y, driverMVecDraw.z);
                pvHandle.set(pvBuilder);
                pvHandle.setAllClean();

                // Add the driver twist.
                MDataHandle ptIdHandle = ptBuilder.addElement((unsigned)poseMatrixIds[poseCount - 1] + 1);
                ptIdHandle.setDouble(driver[3 + increment]);
                ptHandle.set(ptBuilder);
                ptHandle.setAllClean();
            }
        }

        increment += 4;
    }

    // -------------------------------------------------
    // M1.3: per-dimension bounds snapshot (raw space, pre-normalize).
    // Matrix-mode layout is [vx, vy, vz, twist] * driverCount; compute()
    // will skip the twist slot (j % 4 == 3) at clamp-apply time, but
    // bounds are still populated uniformly here for simplicity.
    // -------------------------------------------------

    {
        const unsigned dim = 4 * driverCount;
        poseMinVec.assign(dim, 0.0);
        poseMaxVec.assign(dim, 0.0);
        if (poseCount > 0)
        {
            for (unsigned j = 0; j < dim; ++j)
            {
                double lo = poseData(0, j);
                double hi = lo;
                for (unsigned i = 1; i < poseCount; ++i)
                {
                    const double v = poseData(i, j);
                    if (v < lo) lo = v;
                    if (v > hi) hi = v;
                }
                poseMinVec[j] = lo;
                poseMaxVec[j] = hi;
            }
        }
    }

    // -------------------------------------------------
    // normalization
    // -------------------------------------------------

    // Get the normalization factors.
    normFactors = poseData.normsColumn();
    // Normalize the pose matrix.
    poseData.normalizeColumns(normFactors);

    return status;
}


//
// Description:
//      Collect all driver and pose relevant data.
//      Generic Mode
//
// Input Arguments:
//      data            The MPxNode dataBlock.
//      driver          The array of driver values.
//      poseCount       The number of poses.
//      solveCount      The number of outputs to generate values for.
//      poseData        The matrix containing all poses.
//      poseVals        The matrix of pose values.
//      poseModes       The array containing the the mode per pose.
//
// Return Value:
//      MStatus
//
MStatus RBFtools::getPoseData(MDataBlock &data,
                                  std::vector<double> &driver,
                                  unsigned &poseCount,
                                  unsigned &solveCount,
                                  BRMatrix &poseData,
                                  BRMatrix &poseVals,
                                  MIntArray &poseModes,
                                  std::vector<double>&normFactors,
                                  int inputEncoding,
                                  const std::vector<short>& rotateOrders,
                                  unsigned &effectiveInDim)
{
    MStatus status = MStatus::kSuccess;

    MObject thisNode = this->thisMObject();

    unsigned int i, j;

    // -----------------------------------------------------------------
    // get the number of outputs
    // -----------------------------------------------------------------

    MPlug outputPlug(thisNode, RBFtools::output);
    MIntArray outputIds;
    outputPlug.getExistingArrayAttributeIndices(outputIds, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);
    solveCount = outputIds.length();

    // -----------------------------------------------------------------
    // get the attributes
    // -----------------------------------------------------------------

    MPlug inputPlug(thisNode, RBFtools::input);
    MPlug restInputPlug(thisNode, RBFtools::restInput);
    MPlug posesPlug(thisNode, RBFtools::poses);

    // -----------------------------------------------------------------
    // get the data handles
    // -----------------------------------------------------------------

    MArrayDataHandle inputHandle = data.inputArrayValue(input, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);

    MArrayDataHandle restInputHandle = data.inputArrayValue(restInput, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);

    MArrayDataHandle posesHandle = data.inputArrayValue(poses, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);

    // -----------------------------------------------------------------
    // get the array ids
    // -----------------------------------------------------------------

    MIntArray inputIds;
    MIntArray restInputIds;
    MIntArray poseIds;

    inputPlug.getExistingArrayAttributeIndices(inputIds, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);

    restInputPlug.getExistingArrayAttributeIndices(restInputIds, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);

    posesPlug.getExistingArrayAttributeIndices(poseIds, &status);
    CHECK_MSTATUS_AND_RETURN_IT(status);

    unsigned inDim = inputIds.length();
    unsigned restDim = restInputIds.length();

    poseCount = poseIds.length();
    // Store the original pose count before the count gets modified
    // because of a missing 0 index.
    // The original index list is important when querying the last index
    // of the array, see below *).
    unsigned poseCountOriginal = poseCount;

    // Make sure to start at a pose index of 0.
    // Because Maya creates sparse arrays it's possible that the first
    // pose gets lost when a rest pose is present which only contains
    // zero values.
    if (poseCount != 0 && poseIds[0] != 0)
    {
        poseIds.insert(0, 0);
        poseCount ++;
    }
    // Problem: *)
    // When loading a scene with the RBFtools node the index count
    // of the poses plug (compound array attribute) matches the number
    // of poses, whereas once the scene gets evaluated the plug array
    // contains an additional empty (next available) index.
    // Since the correct number of poses needs to be known for creating
    // the matrices, the last index gets checked. If the child
    // attributes have elements in case of a freshly loaded scene, the
    // pose count doesn't need to be altered. But when the scene already
    // has been evaluated the children of the last index don't have any
    // elements and therefore can be ignored.
    status = posesHandle.jumpToArrayElement(poseCountOriginal - 1);
    CHECK_MSTATUS_AND_RETURN_IT(status);
    MDataHandle lastIdHandle = posesHandle.inputValue();
    MDataHandle lastInputHandle = lastIdHandle.child(poseInput);
    MArrayDataHandle lastInputArrayHandle(lastInputHandle);
    unsigned lastInCount = lastInputArrayHandle.elementCount();
    if (lastInCount == 0)
        poseCount --;

    // Check for any pose connections. In case the pose attributes are
    // connected all data need to get re-evaluated, which slows down the
    // calculation.
    unsigned int numConnChildren = posesPlug.numConnectedChildren();
    if (numConnChildren != 0 || poseCount != globalPoseCount)
        evalInput = true;

    // Clear the indices for setting the output array values because
    // valid indices get appended.
    poseMatrixIds.clear();

    // -----------------------------------------------------------------
    // fill the driver and rest vector (raw, pre-encoding)
    // -----------------------------------------------------------------

    std::vector<double> rest;
    rest.resize(inDim);

    std::vector<double> rawDriver;
    rawDriver.resize(inDim);

    for (i = 0; i < inDim; i ++)
    {
        status = inputHandle.jumpToArrayElement(i);
        CHECK_MSTATUS_AND_RETURN_IT(status);
        rawDriver[i] = inputHandle.inputValue().asDouble();

        // get the rest input
        if (i < restDim)
        {
            status = restInputHandle.jumpToArrayElement(i);
            CHECK_MSTATUS_AND_RETURN_IT(status);
            rest[i] = restInputHandle.inputValue().asDouble();
        }
        else
            rest[i] = 0.0;

        if (distanceTypeVal)
            rawDriver[i] -= rest[i];
        else
            rest[i] = 0.0;
    }

    // -----------------------------------------------------------------
    // M2.1a — encode driver vector
    //
    // Raw (0): pass-through, effectiveInDim = inDim.
    // Quaternion (1): (rx, ry, rz) -> (qx, qy, qz, qw), 3-in/4-out per
    //                 group; effectiveInDim = (inDim/3) * 4.
    // ExpMap (3): (rx, ry, rz) -> log-quat ∈ ℝ³, 3-in/3-out per group;
    //             effectiveInDim stays inDim (but values are transformed).
    // BendRoll (2) / SwingTwist (4): caller (compute()) remaps encoding
    //             to 0 via the safety net before we get here. If they
    //             still reach, fall through to Raw semantics.
    //
    // Rest subtraction (distType==Angle) was already applied to rawDriver
    // above; encoding consumes the rest-subtracted value.
    //
    // Lambda: encode a single (rx, ry, rz) group at (raw[off..off+2])
    // into (out[offOut..offOut+k-1]) per the active encoding.
    // -----------------------------------------------------------------

    const bool encQuat   = (inputEncoding == 1);
    const bool encExpMap = (inputEncoding == 3);
    // Resolve effective dim. Non-3-divisible inDim is the caller's
    // safety-net precondition; we still handle it defensively by
    // falling back to Raw semantics.
    const bool encActive = (encQuat || encExpMap) && (inDim % 3 == 0) && (inDim > 0);
    const unsigned groups = encActive ? (inDim / 3) : 0;
    if (encQuat && encActive)
        effectiveInDim = groups * 4;
    else
        effectiveInDim = inDim;

    auto groupRotateOrder = [&](unsigned g) -> short {
        if (g < rotateOrders.size()) return rotateOrders[g];
        return 0;  // XYZ default
    };

    driver.assign(effectiveInDim, 0.0);
    if (encQuat && encActive)
    {
        for (unsigned g = 0; g < groups; ++g)
        {
            double qx, qy, qz, qw;
            encodeEulerToQuaternion(rawDriver[g*3+0], rawDriver[g*3+1], rawDriver[g*3+2],
                                    groupRotateOrder(g), qx, qy, qz, qw);
            driver[g*4+0] = qx;
            driver[g*4+1] = qy;
            driver[g*4+2] = qz;
            driver[g*4+3] = qw;
        }
    }
    else if (encExpMap && encActive)
    {
        for (unsigned g = 0; g < groups; ++g)
        {
            double qx, qy, qz, qw;
            encodeEulerToQuaternion(rawDriver[g*3+0], rawDriver[g*3+1], rawDriver[g*3+2],
                                    groupRotateOrder(g), qx, qy, qz, qw);
            double lx, ly, lz;
            encodeQuaternionToExpMap(qx, qy, qz, qw, lx, ly, lz);
            driver[g*3+0] = lx;
            driver[g*3+1] = ly;
            driver[g*3+2] = lz;
        }
    }
    else
    {
        // Raw: pass-through.
        for (unsigned k = 0; k < inDim; ++k)
            driver[k] = rawDriver[k];
    }

    // -----------------------------------------------------------------
    // get the pose data
    // -----------------------------------------------------------------

    if (poseCount != 0 && evalInput)
    {
        globalPoseCount = poseCount;

        // Prepare the matrix to hold the pose vectors.
        // Assign an empty matrix to clear pre-existing data.
        // M2.1a: sized to effective (post-encoding) dim so downstream
        // solver/clamp consume encoded space consistently with driver.
        poseData = BRMatrix();
        poseData.setSize(poseCount, effectiveInDim);

        // Prepare the matrix to hold the pose values.
        // Assign an empty matrix to clear pre-existing data.
        poseVals = BRMatrix();
        poseVals.setSize(poseCount, solveCount);

        // Clear pre-existing mode modes.
        poseModes.clear();
        poseModes.setLength(poseCount);

        // M2.1a: temp row for raw values read before per-row encoding.
        std::vector<double> rawRow;
        rawRow.resize(inDim);

        for (i = 0; i < poseCount; i ++)
        {
            poseMatrixIds.append((int)i);

            // M2.1a: pre-fill rawRow with the all-zero pose default
            // (rest-subtracted), matching v4 semantics for sparse arrays.
            for (j = 0; j < inDim; j ++)
                rawRow[j] = 0.0 - rest[j];
            for (j = 0; j < solveCount; j ++)
                poseVals(i, j) = 0.0;

            // ---------------------------------------------------------
            // pose positions
            // ---------------------------------------------------------

            status = posesHandle.jumpToArrayElement(i);
            if (status == MStatus::kSuccess)
            {
                MDataHandle posesIdHandle = posesHandle.inputValue();
                MDataHandle poseInputHandle = posesIdHandle.child(poseInput);
                MArrayDataHandle poseInputArrayHandle(poseInputHandle);

                unsigned poseInputCount = poseInputArrayHandle.elementCount();

                for (j = 0; j < inDim; j ++)
                {
                    // Handle the special case of sparse arrays which
                    // might hold less data than is needed.
                    if (poseInputCount != 0)
                    {
                        status = poseInputArrayHandle.jumpToElement(j);
                        if (status == MStatus::kSuccess)
                            rawRow[j] = poseInputArrayHandle.inputValue().asDouble() - rest[j];
                    }
                }

                // -----------------------------------------------
                // pose values
                // -----------------------------------------------

                MDataHandle poseValueHandle = posesIdHandle.child(poseValue);
                MArrayDataHandle poseValueArrayHandle(poseValueHandle);

                unsigned valueCount = poseValueArrayHandle.elementCount();

                for (j = 0; j < solveCount; j ++)
                {
                    // Handle the special case of sparse arrays which
                    // might hold less data than is needed.
                    if (valueCount != 0)
                    {
                        status = poseValueArrayHandle.jumpToElement(j);
                        if (status == MStatus::kSuccess)
                            poseVals(i, j) = poseValueArrayHandle.inputValue().asDouble();
                    }
                }
            }

            // -----------------------------------------------
            // M2.1a — write encoded row into poseData(i, :)
            //
            // Same encoding ladder as the driver block above. Encoded
            // pose rows sit in the same space as the encoded driver, so
            // bounds, normalization, kernel activation, and distance
            // dispatch all operate in a single consistent coordinate
            // system.
            // -----------------------------------------------

            if (encQuat && encActive)
            {
                for (unsigned g = 0; g < groups; ++g)
                {
                    double qx, qy, qz, qw;
                    encodeEulerToQuaternion(rawRow[g*3+0], rawRow[g*3+1], rawRow[g*3+2],
                                            groupRotateOrder(g), qx, qy, qz, qw);
                    poseData(i, g*4+0) = qx;
                    poseData(i, g*4+1) = qy;
                    poseData(i, g*4+2) = qz;
                    poseData(i, g*4+3) = qw;
                }
            }
            else if (encExpMap && encActive)
            {
                for (unsigned g = 0; g < groups; ++g)
                {
                    double qx, qy, qz, qw;
                    encodeEulerToQuaternion(rawRow[g*3+0], rawRow[g*3+1], rawRow[g*3+2],
                                            groupRotateOrder(g), qx, qy, qz, qw);
                    double lx, ly, lz;
                    encodeQuaternionToExpMap(qx, qy, qz, qw, lx, ly, lz);
                    poseData(i, g*3+0) = lx;
                    poseData(i, g*3+1) = ly;
                    poseData(i, g*3+2) = lz;
                }
            }
            else
            {
                for (unsigned k = 0; k < inDim; ++k)
                    poseData(i, k) = rawRow[k];
            }

            // -----------------------------------------------
            // pose modes
            // -----------------------------------------------

            // Set the pose mode value. This is not necessary for
            // generic mode, but only to make the data for both modes
            // consistent.
            poseModes.set(0, i);
        }

        // -------------------------------------------------
        // M1.3: per-dimension bounds snapshot (effective/encoded space).
        // Must run BEFORE normalizeColumns so inflation stays in the
        // user-visible coord system for that encoding. For Raw this is
        // user scene units; for Quaternion this is [-1, 1] quat space;
        // for ExpMap this is rotation-vector radians.
        // -------------------------------------------------

        poseMinVec.assign(effectiveInDim, 0.0);
        poseMaxVec.assign(effectiveInDim, 0.0);
        for (j = 0; j < effectiveInDim; j ++)
        {
            double lo = poseData(0, j);
            double hi = lo;
            for (i = 1; i < poseCount; i ++)
            {
                const double v = poseData(i, j);
                if (v < lo) lo = v;
                if (v > hi) hi = v;
            }
            poseMinVec[j] = lo;
            poseMaxVec[j] = hi;
        }

        // -------------------------------------------------
        // normalization
        // -------------------------------------------------

        // Get the normalization factors.
        normFactors = poseData.normsColumn();
        // Normalize the pose matrix.
        poseData.normalizeColumns(normFactors);
    }

    return MStatus::kSuccess;
}


//
// Description:
//      Calculate the linear distance between two vectors.
//
// Input Arguments:
//      vec1            The first vector.
//      vec2            The second vector.
//
// Return Value:
//      double          The linear distance.
//
double RBFtools::getRadiusValue()
{
    if (radiusTypeVal == 0)
        return meanVal;
    else if (radiusTypeVal == 1)
        return varianceVal;
    else if (radiusTypeVal == 2)
        return sqrt(varianceVal);
    else
        return radiusVal;
}


//
// Description:
//      Calculate the twist angle based on the given rotate order.
//
// Input Arguments:
//      q               The quaternion to get the twist angle from.
//      axis            The twist axis.
//
// Return Value:
//      double          The twist angle.
//
double RBFtools::getTwistAngle(MQuaternion q, unsigned int axis)
{
    double axisComponent = q.x;
    if (axis == 1)
        axisComponent = q.y;
    else if (axis == 2)
        axisComponent = q.z;
    return 2.0 * atan2(axisComponent, q.w);
}


//
// Description:
//      Build a matrix containing the distance values between all poses.
//
// Input Arguments:
//      poseMat         The matrix containing all poses.
//      distType        The distance type (linear/angle).
//
// Return Value:
//      BRMatrix        The distance matrix.
//
BRMatrix RBFtools::getDistances(BRMatrix poseMat, int distType,
                                int encoding, bool isMatrixMode)
{
    unsigned count = poseMat.getRowSize();

    unsigned int i, j;

    BRMatrix distMat;
    distMat.setSize(count, count);

    for (i = 0; i < count; i ++)
    {
        for (j = 0; j < count; j ++)
        {
            double dist = getPoseDelta(poseMat.getRowVector(i),
                                       poseMat.getRowVector(j),
                                       distType, encoding, isMatrixMode);
            distMat(i, j) = dist;
        }
    }

    return distMat;
}


//
// Description:
//      Return the distance between the two given vectors, dispatched by
//      (isMatrixMode, encoding, distType) per v5 PART C.2.2 + addendum
//      2026-04-24 §M2.1a. Matrix mode owns its dispatch (ignores the
//      encoding arg, honours distType=0/1 via linear vs angle Matrix-mode
//      helpers — the §Bug 2 fix). Generic mode dispatches on encoding:
//      Raw preserves v4 legacy behaviour; Quaternion uses per-4-block
//      1-|q1·q2| aggregated L2; ExpMap uses ℝ³ Euclidean. BendRoll and
//      Swing-Twist are expected to be remapped to Raw by the caller
//      BEFORE reaching this function (see compute() safety net).
//
// Input Arguments:
//      vec1, vec2          Pose vectors.
//      distType            0 = linear/euclidean, 1 = angle.
//      encoding            v5 inputEncoding enum value (Generic mode).
//      isMatrixMode        True when caller is in Matrix (blendShape) mode.
//
double RBFtools::getPoseDelta(std::vector<double> vec1, std::vector<double> vec2,
                              int distType, int encoding, bool isMatrixMode)
{
    const size_t n = vec1.size();
    if (n != vec2.size())
        return getRadius(vec1, vec2);  // defensive

    // -----------------------------------------------------------------
    // Matrix mode: layout is [vx, vy, vz, twist] * driverCount. The
    // encoding arg is ignored per (F)① contract.
    // -----------------------------------------------------------------
    if (isMatrixMode)
    {
        if (n >= 4 && n % 4 == 0)
        {
            // M2.1a Bug 2 fix: when the user selects distanceType == Angle
            // on a Matrix-mode node, honour it — previously this path
            // silently fell through to Euclidean because getPoseData
            // forced distanceTypeVal = 0 and getPoseDelta had no angle
            // branch for 4k vectors. See M1.1 addendum §Bug 2.
            return (distType == 0)
                ? getMatrixModeLinearDistance(vec1, vec2)
                : getMatrixModeAngleDistance(vec1, vec2);
        }
        return getRadius(vec1, vec2);
    }

    // -----------------------------------------------------------------
    // Generic mode: encoding owns the dispatch.
    // -----------------------------------------------------------------

    // Raw (v4 legacy + BendRoll/SwingTwist placeholder target).
    if (encoding == 0)
    {
        if (distType == 0)
            return getRadius(vec1, vec2);
        if (n == 3)
            return getAngle(vec1, vec2);
        return getRadius(vec1, vec2);
    }

    // Quaternion: per-4-block 1-|dot| aggregated L2.
    if (encoding == 1)
    {
        if (n >= 4 && n % 4 == 0)
            return getQuatBlockDistance(vec1, vec2);
        return getRadius(vec1, vec2);  // defensive
    }

    // ExpMap: per-3-block log-quat lives in ℝ³; plain Euclidean is the
    // natural distance. (v5 PART G.5.)
    if (encoding == 3)
        return getRadius(vec1, vec2);

    // BendRoll (2) and SwingTwist (4): caller MUST have remapped to Raw
    // via the safety net. This branch is unreachable under a correct
    // caller; fall back to Raw semantics to stay defensive.
    if (distType == 0)
        return getRadius(vec1, vec2);
    if (n == 3)
        return getAngle(vec1, vec2);
    return getRadius(vec1, vec2);
}


//
// Description:
//      Angle-based distance for Matrix-mode driver vectors packed as
//      [vx, vy, vz, twist] * driverCount. Per-block: arc angle on the
//      swing S² unit vector + wrap-aware twist delta, L2-combined. All
//      blocks L2-aggregated. This is the Bug 2 fix — M1.1 addendum
//      2026-04-24 defers this to M2.1, and here it lands.
//
double RBFtools::getMatrixModeAngleDistance(const std::vector<double> &vec1,
                                            const std::vector<double> &vec2)
{
    double sumSq = 0.0;
    const size_t blocks = vec1.size() / 4;
    for (size_t k = 0; k < blocks; ++k)
    {
        const size_t base = k * 4;
        // Swing block: take MVector::angle on the xyz triple (unsigned
        // [0, pi]; numerically stable for unit vectors).
        const std::vector<double> a = {vec1[base+0], vec1[base+1], vec1[base+2]};
        const std::vector<double> b = {vec2[base+0], vec2[base+1], vec2[base+2]};
        const double axisAngle = getAngle(a, b);
        // Twist block: reuse M1.1's wrap helper.
        const double w = twistWrap(vec1[base+3], vec2[base+3]);
        sumSq += axisAngle * axisAngle + w * w;
    }
    return sqrt(sumSq);
}


//
// Description:
//      Per-4-block quaternion distance for Generic mode with
//      inputEncoding == Quaternion. Each block is treated as a unit
//      quaternion (qx, qy, qz, qw); per-block distance is 1 - |q1·q2|
//      (v5 PART G.2), aggregated as L2 across blocks. Mirrors the
//      Matrix-mode angle aggregation shape but operates on 4D quat
//      blocks instead of (axis,twist) pairs.
//
double RBFtools::getQuatBlockDistance(const std::vector<double> &v1,
                                      const std::vector<double> &v2)
{
    double sumSq = 0.0;
    const size_t blocks = v1.size() / 4;
    for (size_t k = 0; k < blocks; ++k)
    {
        const size_t base = k * 4;
        double dot = v1[base+0]*v2[base+0] + v1[base+1]*v2[base+1]
                   + v1[base+2]*v2[base+2] + v1[base+3]*v2[base+3];
        const double d = 1.0 - fabs(dot);
        sumSq += d * d;
    }
    return sqrt(sumSq);
}


//
// Description:
//      Euler → Quaternion. rotateOrder matches Maya's native rotateOrder
//      enum {XYZ=0, YZX=1, ZXY=2, XZY=3, YXZ=4, ZYX=5}. Output quaternion
//      is right-handed (same convention as MTransformationMatrix::rotation).
//      Implementation goes through per-axis unit quaternions and composes
//      them in rotateOrder-appropriate order.
//
void RBFtools::encodeEulerToQuaternion(double rx, double ry, double rz,
                                       short rotateOrder,
                                       double &qx, double &qy, double &qz,
                                       double &qw)
{
    const double hx = rx * 0.5, hy = ry * 0.5, hz = rz * 0.5;
    const double cx = cos(hx), sx = sin(hx);
    const double cy = cos(hy), sy = sin(hy);
    const double cz = cos(hz), sz = sin(hz);

    // Per-axis unit quaternions (w first for clarity in composition).
    struct Q { double w, x, y, z; };
    const Q qX = {cx, sx, 0.0, 0.0};
    const Q qY = {cy, 0.0, sy, 0.0};
    const Q qZ = {cz, 0.0, 0.0, sz};

    auto mul = [](const Q &a, const Q &b) -> Q {
        return {
            a.w*b.w - a.x*b.x - a.y*b.y - a.z*b.z,
            a.w*b.x + a.x*b.w + a.y*b.z - a.z*b.y,
            a.w*b.y - a.x*b.z + a.y*b.w + a.z*b.x,
            a.w*b.z + a.x*b.y - a.y*b.x + a.z*b.w,
        };
    };

    // Maya applies rotations in the rotateOrder sequence; the resulting
    // orientation equals the product in the SAME order (local-frame
    // intrinsic: first letter applied first -> leftmost in product).
    Q out{1.0, 0.0, 0.0, 0.0};
    switch (rotateOrder)
    {
        case 1: out = mul(mul(qY, qZ), qX); break;  // YZX
        case 2: out = mul(mul(qZ, qX), qY); break;  // ZXY
        case 3: out = mul(mul(qX, qZ), qY); break;  // XZY
        case 4: out = mul(mul(qY, qX), qZ); break;  // YXZ
        case 5: out = mul(mul(qZ, qY), qX); break;  // ZYX
        case 0:
        default: out = mul(mul(qX, qY), qZ); break; // XYZ (Maya default)
    }
    qx = out.x; qy = out.y; qz = out.z; qw = out.w;
}


//
// Description:
//      Quaternion → log-map ∈ ℝ³ (v5 PART G.5). Canonicalises to the
//      q_w ≥ 0 hemisphere internally so callers do not need to worry
//      about the double cover. Uses a Taylor expansion for θ → 0 so
//      log(identity) returns (0, 0, 0) without a divide-by-zero.
//
void RBFtools::encodeQuaternionToExpMap(double qx, double qy, double qz, double qw,
                                        double &lx, double &ly, double &lz)
{
    // Canonicalise to q_w >= 0 — q and -q represent the same rotation,
    // and the log map is odd, so flipping the sign chooses the shorter
    // rotation.
    if (qw < 0.0) { qx = -qx; qy = -qy; qz = -qz; qw = -qw; }

    // Clamp q_w for safety before acos; tiny overshoots above 1.0 show
    // up with non-normalised quaternions from upstream plugs.
    if (qw > 1.0) qw = 1.0;
    if (qw < -1.0) qw = -1.0;

    const double sinHalf = sqrt(1.0 - qw * qw);       // = sin(theta/2)
    const double halfTheta = acos(qw);                // = theta/2 in [0, pi]

    // Near-identity branch: log(q) ≈ (qx, qy, qz). The full expression
    // is (halfTheta / sinHalf) * (qx, qy, qz); as halfTheta -> 0 the
    // ratio -> 1 (sinc-style), so the near-identity xyz IS the log.
    const double EPS = 1.0e-8;
    double scale;
    if (sinHalf < EPS)
        scale = 1.0;
    else
        scale = halfTheta / sinHalf;

    lx = scale * qx;
    ly = scale * qy;
    lz = scale * qz;
}


//
// Description:
//      Calculate the linear distance between two vectors.
//
// Input Arguments:
//      vec1            The first vector.
//      vec2            The second vector.
//
// Return Value:
//      double          The linear distance.
//
double RBFtools::getRadius(std::vector<double> vec1, std::vector<double> vec2)
{
    size_t count = vec1.size();

    double sum = 0.0;
    for (unsigned i = 0; i < count; i ++)
        sum += pow(vec1[i] - vec2[i], 2);
    return sqrt(sum);
}


//
// Description:
//      Calculate the angle between two vectors.
//
// Input Arguments:
//      vec1            The first vector.
//      vec2            The second vector.
//
// Return Value:
//      double          The angle value.
//
double RBFtools::getAngle(std::vector<double> vec1, std::vector<double> vec2)
{
    // WHY: vec is a 3-D axis vector, and MVector::angle returns unsigned [0, pi] already —
    // no |q . q| absolute-value concern applies here (the v5 PART D.3 note assumed a 4-D
    // quaternion input that this code path does not actually receive). For quaternion inputs
    // arriving via the M2.1 encoding work, use getQuatDistance instead.
    MVector v1(vec1[0], vec1[1], vec1[2]);
    MVector v2(vec2[0], vec2[1], vec2[2]);
    return v1.angle(v2);
}


//
// Description:
//      Fold a twist-angle delta onto the 2*pi circle so +179 deg vs -179 deg
//      is measured as ~2 deg instead of ~358 deg. Input taus are the output
//      of getTwistAngle (2 * atan2), whose range is (-2*pi, 2*pi].
//
double RBFtools::twistWrap(double tau1, double tau2)
{
    const double TWO_PI = 2.0 * M_PI;
    double d = fabs(tau1 - tau2);
    d = fmod(d, TWO_PI);
    if (d > M_PI)
        d = TWO_PI - d;
    return d;
}


//
// Description:
//      Wrap-aware L2 distance for Matrix-mode driver vectors packed as
//      [vx, vy, vz, twist] * driverCount. xyz keeps chord (Euclidean)
//      semantics to preserve existing radius calibration; only the twist
//      component is folded onto a 2*pi circle. Aggregation across driver
//      blocks is L2.
//
double RBFtools::getMatrixModeLinearDistance(const std::vector<double> &vec1,
                                             const std::vector<double> &vec2)
{
    double sumSq = 0.0;
    const size_t blocks = vec1.size() / 4;
    for (size_t k = 0; k < blocks; ++k)
    {
        const size_t base = k * 4;
        for (size_t i = 0; i < 3; ++i)
        {
            const double d = vec1[base + i] - vec2[base + i];
            sumSq += d * d;
        }
        const double w = twistWrap(vec1[base + 3], vec2[base + 3]);
        sumSq += w * w;
    }
    return sqrt(sumSq);
}


//
// Description:
//      Quaternion distance d(q1, q2) = 1 - |q1 . q2| (v5 PART G.2). The
//      absolute value collapses the q == -q double cover so antipodal
//      quaternions register as identical rotations.
//
// NOTE (M1.1): Declared + implemented alongside the other distance helpers
// but INTENTIONALLY UNWIRED. The M2.1 Quaternion input encoding is the first
// caller; wiring it now would also implicitly fix the v5 addendum 2026-04-24
// "Bug 2" (Matrix+Angle silent fallback to Euclidean), which the user has
// scoped out of this commit to keep blast radius minimal.
//
double RBFtools::getQuatDistance(const std::vector<double> &q1,
                                 const std::vector<double> &q2)
{
    double dot = 0.0;
    const size_t n = (q1.size() < q2.size() ? q1.size() : q2.size());
    const size_t stop = (n < 4 ? n : 4);
    for (size_t i = 0; i < stop; ++i)
        dot += q1[i] * q2[i];
    return 1.0 - fabs(dot);
}


//
// Description:
//      Calculate the RBF activation values.
//
// Input Arguments:
//      mat             The matrix with the activation values.
//      width           The activation width.
//      kernelType      The interpolation function.
//
// Return Value:
//      None
//
void RBFtools::getActivations(BRMatrix &mat, double width, short kernelType)
{
    unsigned count = mat.getRowSize();

    unsigned int i, j;

    for (i = 0; i < count; i ++)
    {
        for (j = 0; j < count; j ++)
            mat(i, j) = interpolateRbf(mat(i, j), width, kernelType);
    }
}


//
// Description:
//      Interpolation function for processing the weight values.
//
// Input Arguments:
//      value           The value to interpolate.
//      width           The activation width.
//      kernelType      The interpolation function.
//
// Return Value:
//      double          The new interpolated value.
//
double RBFtools::interpolateRbf(double value, double width, short kernelType)
{
    double result = 0.0;
    
    if (width == 0.0)
        width = 1.0;
    
    // linear
    result = value;
    
    // gaussian 1
    if (kernelType == 1)
    {
        width = 1.0 / width;
        double sigma = -(width * width);
        result = exp(sigma * value);
    }
    // gaussian 2
    else if (kernelType == 2)
    {
        width *= 0.707;
        result = exp(-(value * value) / (2.0 * width * width));
    }
    // thin plate
    else if (kernelType == 3)
    {
        value /= width;
        if (value > 0)
            result = value * value * log(value);
        else
            result = value;
    }
    // multi quadratic
    else if (kernelType == 4)
    {
        result = sqrt((value * value) + (width * width));
    }
    // inverse multi quadratic
    else if (kernelType == 5)
    {
        result = 1.0 / sqrt((value * value) + (width * width));
    }

    return result;
}


//
// Description:
//      Normalize the given vector with the given factors.
//
// Input Arguments:
//      vec             The vector to normalize.
//      factor          The vector or factors.
//
// Return Value:
//      vector          The normalized vector.
//
std::vector<double> RBFtools::normalizeVector(std::vector<double> vec, std::vector<double> factors)
{
    if (vec.size() != factors.size())
        return vec;

    for (unsigned i = 0; i < vec.size(); i ++)
    {
        if (factors[i] > 0)
            vec[i] /= factors[i];
    }

    return vec;
}
//
// Description:
//      Calculate the individual output weights based on the current
//      driver values in relation to the stored poses. This is the main
//      part of the RBF calculation but a rather simple process as it
//      just gets the distances of the driver to the stored poses and
//      calculates the weighted output values based on the weight matrix
//      built during initialization.
//
// Input Arguments:
//      out             The array of output weight values.
//      poses           The matrix containing all poses.
//      norms           The normalization factors for each column.
//      driver          The array of driver values.
//      poseModes       The array containing the the mode per pose.
//      weightMat       The matrix with the RBF weights.
//      width           The average distance between the poses.
//      distType        The distance type (linear/angle).
//      kernelType      The interpolation function.
//
// Return Value:
//      None
//
void RBFtools::getPoseWeights(MDoubleArray &out,
                                  BRMatrix poses,
                                  std::vector<double> norms,
                                  std::vector<double> driver,
                                  MIntArray poseModes,
                                  BRMatrix weightMat,
                                  double width,
                                  int distType,
                                  int encoding,
                                  bool isMatrixMode,
                                  short kernelType)
{
    unsigned int poseCount = poses.getRowSize();
    unsigned int valueCount = out.length();

    // Make sure that the weight matrix has the correct dimensions.
    // This has become necessary with introducing multiple drivers in
    // matrix mode.
    if (weightMat.getRowSize() != poseCount || weightMat.getColSize() != valueCount)
        return;

    driver = normalizeVector(driver, norms);

    unsigned int i, j;

    for (i = 0; i < poseCount; i ++)
    {
        double dist = 0.0;
        std::vector<double> dv = driver;
        std::vector<double> ps = poses.getRowVector(i);

        // M2.1a: poseMode axis/twist masking is a Matrix-mode concept
        // (layout guarantees indices 0..3 exist per driver). Skip it in
        // Generic mode where the layout is encoding-dependent.
        if (isMatrixMode && dv.size() >= 4)
        {
            if (poseModes[i] == 1)
                dv[3] = 0.0;
            else if (poseModes[i] == 2)
            {
                dv[0] = 0.0;
                dv[1] = 0.0;
                dv[2] = 0.0;
            }
        }

        dist = getPoseDelta(dv, ps, distType, encoding, isMatrixMode);

        for (j = 0; j < valueCount; j ++)
            out[j] += weightMat(i, j) * interpolateRbf(dist, width, kernelType);
    }
}


//
// Description:
//      Pass the weight values to the outputs.
//
// Input Arguments:
//      weightsArray    The array of output weight values.
//      data            The MPxNode dataBlock.
//      inactive        True, if the node is enabled.
//
// Return Value:
//      None
//
void RBFtools::setOutputValues(MDoubleArray weightsArray, MDataBlock data, bool inactive)
{
    MStatus status = MStatus::kSuccess;
    
    MObject thisNode = this->thisMObject();
    
    unsigned int i;

    // In generic mode pose and output indices are not related.
    // The ordering of the output always starts at 0 with an increment
    // of 1, no matter if pose indices are missing.
    // In matrix mode pose and output indices are matching, due to the
    // square dimensions of blendshape usage.
    unsigned count = 0;
    MIntArray ids;
    if (genericMode)
    {
        if (!inactive)
        {
            count = weightsArray.length();
            ids.setLength(count);
            for (i = 0; i < count; i ++)
                ids.set((int)i, i);
        }
        else
        {
            MPlug outputPlug(thisNode, RBFtools::output);
            outputPlug.getExistingArrayAttributeIndices(ids, &status);
            if (status != MStatus::kSuccess)
                return;
            count = ids.length();
        }
    }
    else
    {
        count = poseMatrixIds.length();
        ids = poseMatrixIds;
    }

    MArrayDataHandle outputHandle = data.outputArrayValue(output);
    MArrayDataBuilder outputBuilder(&data, output, count);
    for (i = 0; i < count; i ++)
    {
        MDataHandle outputIdHandle = outputBuilder.addElement((unsigned)ids[i]);
        if (!inactive)
            outputIdHandle.setDouble(weightsArray[i]);
        else
            outputIdHandle.setDouble(0.0);

        // If the node is set up for rbf but switched back to vector
        // angle all other output weights need to be set to 0.
        if (weightsArray.length() == 1 && i > 0)
            outputIdHandle.setDouble(0.0);

        outputHandle.set(outputBuilder);
    }
    outputHandle.setAllClean();
}


//
// Description:
//      Modify the output weight value by the chosen interpolation type.
//
// Input Arguments:
//      value           The value to interpolate.
//      type            The type of interpolation.
//
// Return Value:
//      double          The new interpolated value.
//
double RBFtools::interpolateWeight(double value, int type)
{
    // slow - inverse quadratic
    if (type == 1)
        value = 1 - pow((1 - value), 2.0);
    // fast - quadratic
    else if (type == 2)
        value = 1 - pow((1 - value), 1 / 2.0);
    // smooth1 - smoothstep
    else if (type == 3)
        value = value * value * (3 - 2 * value);
    // smooth2 - smootherstep
    else if (type == 4)
        value = value * value * value * (value * (value * 6 - 15) + 10);
    else if (type == 5)
        value = blendCurveWeight(value);

    return value;
}


//
// Description:
//      Return the blend curve weight value at the given position.
//
// Input Arguments:
//      value           The input value of the blend curve.
//
// Return Value:
//      double          The blend curve output value.
//
double RBFtools::blendCurveWeight(double value)
{
    float curveValue;
    curveAttr.getValueAtPosition((float)value, curveValue);
    value = curveValue;

    return value;
}


// ---------------------------------------------------------------------
// Helper functions to display the various data elements of the RBF
// calculation process.
// ---------------------------------------------------------------------
void RBFtools::showArray(MDoubleArray array, MString name)
{
    unsigned int i;

    MString s(name + ":\n");

    for (i = 0; i < array.length(); i++)
        s += MString(" ") + array[i];

    MGlobal::displayInfo(s);
}

void RBFtools::showArray(std::vector<double> array, MString name)
{
    unsigned int i;

    MString s(name + ":\n");

    for (i = 0; i < array.size(); i++)
        s += MString(" ") + array[i];

    MGlobal::displayInfo(s);
}

void RBFtools::showVector(MVector vector, MString name)
{
    unsigned int i;

    MString s(name + ":\n");

    for (i = 0; i < 3; i++)
        s += MString(" ") + vector[i];

    MGlobal::displayInfo(s);
}

void RBFtools::showMatrix(MMatrix mat, MString name)
{
    unsigned int i, j;

    MString s(name + ":\n");

    for (i = 0; i < 4; i++)
    {
        for (j = 0; j < 4; j++)
            s += MString(" ") + mat[i][j];

        s += MString("\n");
    }

    MGlobal::displayInfo(s);
}


// ---------------------------------------------------------------------
//
// Viewport 2.0
//
// ---------------------------------------------------------------------

MString RBFtools::drawDbClassification("drawdb/geometry/RBFtools");
MString RBFtools::drawRegistrantId("RBFtoolsNodePlugin");

// By setting isAlwaysDirty to false in MPxDrawOverride constructor, the
// draw override will be updated (via prepareForDraw()) only when the
// node is marked dirty via DG evaluation or dirty propagation.
// Additional callback is also added to explicitly mark the node as
// being dirty (via MRenderer::setGeometryDrawDirty()) for certain
// circumstances.
// Note that the draw callback in MPxDrawOverride constructor is set to
// NULL in order to achieve better performance.

RBFtoolsOverride::RBFtoolsOverride(const MObject &obj)
: MHWRender::MPxDrawOverride(obj, NULL, true)
{
    fModelEditorChangedCbId = MEventMessage::addEventCallback("modelEditorChanged",
                                                              OnModelEditorChanged, this);

    MStatus status;
    MFnDependencyNode node(obj, &status);
    fRBFtools = status ? dynamic_cast<RBFtools*>(node.userNode()) : NULL;
}


RBFtoolsOverride::~RBFtoolsOverride()
{
    fRBFtools = NULL;

    if (fModelEditorChangedCbId != 0)
    {
        MMessage::removeCallback(fModelEditorChangedCbId);
        fModelEditorChangedCbId = 0;
    }
}


void RBFtoolsOverride::OnModelEditorChanged(void *clientData)
{
    RBFtoolsOverride *ovr = static_cast<RBFtoolsOverride*>(clientData);
    if (ovr && ovr->fRBFtools)
    {
        MHWRender::MRenderer::setGeometryDrawDirty(ovr->fRBFtools->thisMObject());
    }
}


MHWRender::DrawAPI RBFtoolsOverride::supportedDrawAPIs() const
{
    return (MHWRender::kOpenGL | MHWRender::kDirectX11 | MHWRender::kOpenGLCoreProfile);
}


MBoundingBox RBFtoolsOverride::boundingBox(const MDagPath &objPath,
                                               const MDagPath &cameraPath) const
{
    MStatus status;
    MObject thisNode = objPath.node(&status);
    MPlug sizePlug(thisNode, RBFtools::size);
    double sizeMult = sizePlug.asDouble();
    MPlug typePlug(thisNode, RBFtools::type);
    short typeVal = typePlug.asShort();

    int xCorner = 0;
    if (typeVal == 1)
        xCorner = -1;

    MPoint corner1 = MPoint(xCorner, -1, -1);
    MPoint corner2 = MPoint(1, 1, 1);

    corner1 = corner1 * sizeMult;
    corner2 = corner2 * sizeMult;

    return MBoundingBox(corner1, corner2);
}


MUserData* RBFtoolsOverride::prepareForDraw(const MDagPath &objPath,
                                                const MDagPath &cameraPath,
                                                const MHWRender::MFrameContext &frameContext,
                                                MUserData *oldData)
{
    RBFtoolsData* data = dynamic_cast<RBFtoolsData*>(oldData);
    if (!data)
        data = new RBFtoolsData();

    // -----------------------------------------------
    // get the attributes
    // -----------------------------------------------

    MStatus status;
    MObject thisNode = objPath.node(&status);

    MPlug activePlug(thisNode, RBFtools::active);
    MPlug anglePlug(thisNode, RBFtools::angle);
    MPlug centerAnglePlug(thisNode, RBFtools::centerAngle);
    MPlug colorDriverRPlug(thisNode, RBFtools::colorDriverR);
    MPlug colorDriverGPlug(thisNode, RBFtools::colorDriverG);
    MPlug colorDriverBPlug(thisNode, RBFtools::colorDriverB);
    MPlug colorRPlug(thisNode, RBFtools::colorR);
    MPlug colorGPlug(thisNode, RBFtools::colorG);
    MPlug colorBPlug(thisNode, RBFtools::colorB);
    MPlug dirPlug(thisNode, RBFtools::direction);
    MPlug drawCenterPlug(thisNode, RBFtools::drawCenter);
    MPlug drawConePlug(thisNode, RBFtools::drawCone);
    MPlug drawDriverPlug(thisNode, RBFtools::drawDriver);
    MPlug drawIndicesPlug(thisNode, RBFtools::drawIndices);
    MPlug drawOriginPlug(thisNode, RBFtools::drawOrigin);
    MPlug drawPosesPlug(thisNode, RBFtools::drawPoses);
    MPlug drawTwistPlug(thisNode, RBFtools::drawTwist);
    MPlug drawWeightPlug(thisNode, RBFtools::drawWeight);
    MPlug driverIndexPlug(thisNode, RBFtools::driverIndex);
    MPlug indexDistPlug(thisNode, RBFtools::indexDist);
    MPlug invertPlug(thisNode, RBFtools::invert);
    MPlug poseLengthPlug(thisNode, RBFtools::poseLength);
    MPlug rbfModePlug(thisNode, RBFtools::rbfMode);
    MPlug sizePlug(thisNode, RBFtools::size);
    MPlug typePlug(thisNode, RBFtools::type);
    MPlug weightPlug(thisNode, RBFtools::outWeight);

    data->activeVal = activePlug.asBool();
    data->angleVal = anglePlug.asDouble();
    data->centerAngleVal = centerAnglePlug.asDouble();
    data->dirVal = dirPlug.asShort();
    data->drawCenterVal = drawCenterPlug.asBool();
    data->drawConeVal = drawConePlug.asBool();
    data->drawDriverVal = drawDriverPlug.asBool();
    data->drawIndicesVal = drawIndicesPlug.asBool();
    data->drawOriginVal = drawOriginPlug.asBool();
    data->drawPosesVal = drawPosesPlug.asBool();
    data->drawTwistVal = drawTwistPlug.asBool();
    data->drawWeightVal = drawWeightPlug.asBool();
    data->driverIndexVal = driverIndexPlug.asInt();
    data->indexDistVal = indexDistPlug.asDouble();
    data->invVal = invertPlug.asBool();
    data->poseLengthVal = poseLengthPlug.asDouble();
    data->rbfModeVal = rbfModePlug.asShort();
    data->sizeVal = sizePlug.asDouble();
    data->typeVal = typePlug.asShort();
    data->weightVal = weightPlug.asDouble();

    MHWRender::DisplayStatus stat = MHWRender::MGeometryUtilities::displayStatus(objPath);

    MColor lineColor;
    if (stat == MHWRender::kLead)
        lineColor = MColor(0.26f, 1.0f, 0.64f);
    else if (stat == MHWRender::kActive)
        lineColor = MColor(1.0f, 1.0f, 1.0f);
    else if (stat == MHWRender::kActiveAffected)
        lineColor = MColor(0.78f, 0.0f, 0.78f);
    else if (stat == MHWRender::kTemplate)
        lineColor = MColor(0.47f, 0.47f, 0.47f);
    else if (stat == MHWRender::kActiveTemplate)
        lineColor = MColor(1.0f, 0.47f, 0.47f);
    else
        lineColor = MColor((float)colorRPlug.asDouble(), (float)colorGPlug.asDouble(), (float)colorBPlug.asDouble());

    data->colorRVal = lineColor.r;
    data->colorGVal = lineColor.g;
    data->colorBVal = lineColor.b;

    data->colorDriverRVal = colorDriverRPlug.asDouble();
    data->colorDriverGVal = colorDriverGPlug.asDouble();
    data->colorDriverBVal = colorDriverBPlug.asDouble();

    // Make sure that the center angle is always smaller then the angle.
    if (data->angleVal <= data->centerAngleVal)
        data->centerAngleVal = data->angleVal - 0.1;

    MFnCamera camFn(cameraPath);
    viewVector = camFn.viewDirection(MSpace::kWorld);

    return data;
}


void RBFtoolsOverride::addUIDrawables(const MDagPath &objPath,
                                          MHWRender::MUIDrawManager &drawManager,
                                          const MHWRender::MFrameContext &frameContext,
                                          const MUserData *data)
{
    MStatus status;

    MObject thisNode = objPath.node(&status);

    // Get the user draw data.
    const RBFtoolsData* wdData = dynamic_cast<const RBFtoolsData*>(data);
    if (!wdData)
        return;

    if (!wdData->activeVal)
        return;

    unsigned int i;

    MColor lineColor((float)wdData->colorRVal, (float)wdData->colorGVal, (float)wdData->colorBVal, 1.0f);
    MColor driverColor((float)wdData->colorDriverRVal, (float)wdData->colorDriverGVal, (float)wdData->colorDriverBVal, 1.0f);

    // -----------------------------------------------------------------
    // vector angle cone
    // -----------------------------------------------------------------

    if (wdData->typeVal == 0)
    {
        // -------------------------------------------------------------
        // get the driver node name
        // -------------------------------------------------------------

        MString driverName;
        MPlug driverPlug(thisNode, RBFtools::driverMatrix);
        if (driverPlug.isConnected())
        {
            MPlugArray sourcePlug;
            driverPlug.connectedTo(sourcePlug, true, false);
            driverName = sourcePlug[0].name();
            MStringArray items;
            driverName.split('.', items);
            driverName = items[0];
        }

        // -------------------------------------------------------------
        // draw lines
        // -------------------------------------------------------------

        if (wdData->drawConeVal)
        {
            drawManager.beginDrawable();

            drawManager.setColor(lineColor);

            MPoint base;
            MVector direction;

            // Modify the angle and size values if the cone should be
            // drawn past 90 degrees.
            double drawAngle = wdData->angleVal;
            double drawPos = wdData->sizeVal;
            int drawDir = -1;
            if (wdData->invVal)
            {
                drawPos *= -1.0;
                drawDir *= -1;
            }
            if (wdData->angleVal > 90.0)
            {
                drawAngle = 180.0 - wdData->angleVal + 0.000000001;
                drawPos *= -1.0;
                drawDir *= -1;
            }

            double angleRadians = drawAngle * DEGTORAD;
            double radius = sin(angleRadians);
            double height = (radius / tan(angleRadians)) * drawPos;

            if (wdData->dirVal == 0)
            {
                base = MPoint(height, 0.0, 0.0, 1.0);
                direction = MVector(drawDir, 0.0, 0.0);
            }
            else if (wdData->dirVal == 1)
            {
                base = MPoint(0.0, height, 0.0, 1.0);
                direction = MVector(0.0, drawDir, 0.0);
            }
            else
            {
                base = MPoint(0.0, 0.0, height, 1.0);
                direction = MVector(0.0, 0.0, drawDir);
            }

            drawManager.cone(base, direction, radius * wdData->sizeVal, height * (drawDir * -1.0));

            drawManager.endDrawable();
        }

        if (wdData->drawCenterVal && wdData->drawConeVal)
        {
            drawManager.beginDrawable();

            drawManager.setColor(lineColor);

            MPoint base;
            MVector direction;

            // Modify the angle and size values if the cone should be
            // drawn past 90 degrees.
            double drawAngle = wdData->centerAngleVal;
            double drawPos = wdData->sizeVal;
            int drawDir = -1;
            if (wdData->invVal)
            {
                drawPos *= -1.0;
                drawDir *= -1;
            }
            if (wdData->centerAngleVal > 90.0)
            {
                drawAngle = 180.0 - wdData->centerAngleVal;
                drawPos *= -1.0;
                drawDir *= -1;
            }

            double angleRadians = (drawAngle + 0.000000001) * DEGTORAD;
            double radius = sin(angleRadians);
            double height = (radius / tan(angleRadians)) * drawPos;

            if (wdData->dirVal == 0)
            {
                base = MPoint(height, 0.0, 0.0, 1.0);
                direction = MVector(drawDir, 0.0, 0.0);
            }
            else if (wdData->dirVal == 1)
            {
                base = MPoint(0.0, height, 0.0, 1.0);
                direction = MVector(0.0, drawDir, 0.0);
            }
            else
            {
                base = MPoint(0.0, 0.0, height, 1.0);
                direction = MVector(0.0, 0.0, drawDir);
            }

            drawManager.cone(base, direction, radius * wdData->sizeVal, height * (drawDir * -1.0));

            drawManager.endDrawable();
        }

        // -------------------------------------------------------------
        // draw weight value
        // -------------------------------------------------------------

        if (wdData->drawWeightVal)
        {
            drawManager.beginDrawable();

            drawManager.setColor(lineColor);

            double drawPos = wdData->sizeVal;
            if (wdData->invVal)
                drawPos *= -1.0;

            MPoint drawPoint;
            if (wdData->dirVal == 0)
                drawPoint = MPoint(drawPos, 0.0, 0.0);
            else if (wdData->dirVal == 1)
                drawPoint = MPoint(0.0, drawPos, 0.0);
            else
                drawPoint = MPoint(0.0, 0.0, drawPos);

            char info[512];
    #ifdef _WIN64
            sprintf_s(info, "%s %.3f", driverName.asChar(), wdData->weightVal);
    #else
            sprintf(info, "%s %.3f", driverName.asChar(), wdData->weightVal);
    #endif

            if (wdData->invVal == false)
                drawManager.text(drawPoint, info, MHWRender::MUIDrawManager::kLeft);
            else
                drawManager.text(drawPoint, info, MHWRender::MUIDrawManager::kRight);

            drawManager.endDrawable();
        }
    }

    // -----------------------------------------------------------------
    // rbf sphere
    // -----------------------------------------------------------------

    // draw the rbf elements only when in transform mode
    else if (wdData->rbfModeVal == 1)
    {
        double lineSize = wdData->poseLengthVal * wdData->sizeVal;

        // -------------------------------------------------------------
        // get the pose vectors
        // -------------------------------------------------------------

        MPlug poseDrawVectorPlug(thisNode, RBFtools::poseDrawVector);
        MPlug poseDrawTwistPlug(thisNode, RBFtools::poseDrawTwist);
        MIntArray poseIds;
        poseDrawVectorPlug.getExistingArrayAttributeIndices(poseIds, &status);
        if (status != MStatus::kSuccess || !poseIds.length())
            return;

        // Remove the driver vector at the end of the array for the pose
        // count.
        unsigned int poseIdsSize = poseIds.length();
        unsigned int poseCount = poseIdsSize - 1;
        MVectorArray poseVectors;
        poseVectors.setLength(poseCount);
        MDoubleArray poseTwist;
        poseTwist.setLength(poseCount);

        for (i = 0; i < poseCount; i ++)
        {
            MPlug posePlug = poseDrawVectorPlug.elementByLogicalIndex((unsigned)poseIds[i]);
            MDataHandle poseHandle = posePlug.asMDataHandle();
            double3 &poseValues = poseHandle.asDouble3();
            poseVectors.set(MVector(poseValues[0], poseValues[1], poseValues[2]), i);

            MPlug twistPlug = poseDrawTwistPlug.elementByLogicalIndex((unsigned)poseIds[i]);
            MDataHandle twistHandle = twistPlug.asMDataHandle();
            poseTwist.set(twistHandle.asDouble(), i);
        }

        // Get the values for the driver vector.
        MPlug posePlug = poseDrawVectorPlug.elementByLogicalIndex((unsigned)poseIds[poseIdsSize - 1]);
        MDataHandle poseHandle = posePlug.asMDataHandle();
        double3 &driverValues = poseHandle.asDouble3();

        MPlug twistPlug = poseDrawTwistPlug.elementByLogicalIndex((unsigned)poseIds[poseIdsSize - 1]);
        MDataHandle twistHandle = twistPlug.asMDataHandle();
        double driverTwist = twistHandle.asDouble();

        // -------------------------------------------------------------
        // draw
        // -------------------------------------------------------------

        if (wdData->drawOriginVal)
        {
            drawManager.beginDrawable();
            drawManager.setColor(lineColor);

            drawManager.circle(MPoint(0.0, 0.0, 0.0), viewVector, 1.0 * wdData->sizeVal);

            drawManager.endDrawable();
        }

        if (wdData->drawDriverVal)
        {
            drawManager.beginDrawable();
            drawManager.setColor(driverColor);

            MVector dv = MVector(driverValues[0], driverValues[1], driverValues[2]);
            dv.normalize();
            MPoint point(dv.x * lineSize, dv.y * lineSize, dv.z * lineSize);
            drawManager.line(MPoint(0.0, 0.0, 0.0), point);

            drawManager.circle(point, viewVector, 0.05 * wdData->sizeVal, true);

            if (wdData->drawTwistVal)
            {
                dv *= 0.9 + wdData->indexDistVal;

                point = MPoint(dv.x * lineSize, dv.y * lineSize, dv.z * lineSize);

                char info[64];
            #ifdef _WIN64
                sprintf_s(info, "%.2f", driverTwist * RADTODEG);
            #else
                sprintf(info, "%.2f", driverTwist * RADTODEG);
            #endif

                drawManager.text(point, info, MHWRender::MUIDrawManager::kRight);
            }

            drawManager.endDrawable();
        }

        if (wdData->drawPosesVal)
        {
            if (poseCount != 0)
            {
                drawManager.beginDrawable();
                drawManager.setColor(lineColor);

                for (i = 0; i < poseCount; i ++)
                {
                    MVector pv = poseVectors[i];
                    pv.normalize();
                    MPoint point(pv.x * lineSize, pv.y * lineSize, pv.z * lineSize);
                    drawManager.line(MPoint(0.0, 0.0, 0.0), point);

                    drawManager.circle(point, viewVector, 0.03 * wdData->sizeVal, true);

                    if (wdData->drawTwistVal)
                    {
                        pv *= 0.9 + wdData->indexDistVal;

                        point = MPoint(pv.x * lineSize, pv.y * lineSize, pv.z * lineSize);

                        char info[64];
                    #ifdef _WIN64
                        sprintf_s(info, "%.2f", poseTwist[i] * RADTODEG);
                    #else
                        sprintf(info, "%.2f", poseTwist[i] * RADTODEG);
                    #endif

                        drawManager.text(point, info, MHWRender::MUIDrawManager::kRight);
                    }
                }

                drawManager.endDrawable();
            }
        }

        if (wdData->drawIndicesVal)
        {
            if (poseCount != 0)
            {
                drawManager.beginDrawable();
                drawManager.setColor(lineColor);

                for (i = 0; i < poseCount; i ++)
                {
                    MVector pv = poseVectors[i];
                    pv.normalize();
                    pv *= 1.03 + wdData->indexDistVal;

                    MPoint point(pv.x * lineSize, pv.y * lineSize, pv.z * lineSize);

                    char info[64];
                #ifdef _WIN64
                    sprintf_s(info, "%i", poseIds[i]);
                #else
                    sprintf(info, "%i", poseIds[i]);
                #endif

                    drawManager.text(point, info, MHWRender::MUIDrawManager::kCenter);
                }

                drawManager.endDrawable();
            }
        }
    }
}

#if MAYA_API_VERSION < 202400
void RBFtoolsOverride::draw(const MHWRender::MDrawContext &context, const MUserData *data)
{
}
#endif

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
