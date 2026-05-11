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
// Commit 0 (M_PER_POSE_SIGMA / M_BASE_POSE): see RBFtools.h for the
// math + backcompat contract. Both are top-level multi-double arrays
// running parallel to poses[] / output[] respectively.
MObject RBFtools::poseRadius;
MObject RBFtools::basePoseValue;
// M2.3: pure-data per-pose local Transform snapshot.
MObject RBFtools::poseLocalTransform;
MObject RBFtools::poseLocalTranslate;
MObject RBFtools::poseLocalQuat;
MObject RBFtools::poseLocalScale;
// M2.5: per-pose SwingTwist decomposition cache (runtime perf only).
// See addendum §M2.5 — NOT part of the JSON schema.
MObject RBFtools::poseSwingTwistCache;
MObject RBFtools::poseSwingQuat;
MObject RBFtools::poseTwistAngle;
MObject RBFtools::poseSwingWeight;
MObject RBFtools::poseTwistWeight;
MObject RBFtools::poseSigma;
// M_B24a1: driverSource compound (multi) + 4 子字段 + node-level outputEncoding.
MObject RBFtools::driverSource;
MObject RBFtools::driverSource_node;
MObject RBFtools::driverSource_attrs;
MObject RBFtools::driverSource_weight;
MObject RBFtools::driverSource_encoding;
MObject RBFtools::outputEncoding;
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
MObject RBFtools::outputQuaternionGroupStart;
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
      prevInputEncodingVal(0),         // M2.1a: Raw; matches inputEncoding default.
      qwaConfigWarningIssued(false),   // M2.2: fresh warnings on first config / edge hit.
      qwaClippedWarningIssued(false),
      qwaDegenerateWarningIssued(false),
      prevQuatGroupConfigHash(0),
      outputEncodingOverlapWarningIssued(false),  // M_P0_QUAT_RBF_OVERLAP_DISCLOSE
      // M_P0_TRAINING_AFFECTING_ATTRS (2026-05-10): -1 / NaN-ish
      // sentinels so the first compute() after node creation reads
      // the actual plug values, sets prev = current (no spurious
      // re-train), and the FIRST USER EDIT triggers retrain.
      prevKernelVal(-1),
      prevDistanceTypeVal(-1),
      prevRadiusTypeVal(-1),
      prevRadiusVal(-1.0),
      prevRegularizationVal(-1.0)
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

    // M_B24a1: node-level outputEncoding enum (Euler/Quaternion/ExpMap).
    // a1 forward-compat: schema declared + read path + DG dirty live;
    // actual inverse transform deferred to M_B24b business consumption.
    outputEncoding = eAttr.create("outputEncoding", "oenc", 0);
    eAttr.addField("Euler",      0);
    eAttr.addField("Quaternion", 1);
    eAttr.addField("ExpMap",     2);
    eAttr.setKeyable(false);
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

    // Commit 0 (M_PER_POSE_SIGMA): per-pose σ. multi double, default
    // 5.0 per pose. Parallel-indexed to poses[]. Sparse-safe: missing
    // index falls back to scalar radius via readPoseRadii().
    poseRadius = nAttr.create("poseRadius", "prad",
                              MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);
    nAttr.setDefault(5.0);
    nAttr.setMin(0.0);
    nAttr.setSoftMax(50.0);

    // Commit 0 (M_BASE_POSE): per-output-channel additive baseline
    // (driven side). multi double, default 0.0 (bit-identical legacy
    // behaviour for empty array). Length should track output[].
    basePoseValue = nAttr.create("basePoseValue", "bpv",
                                 MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);
    nAttr.setDefault(0.0);

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
    // on Linear / Thin Plate kernels where K[i,i] = φ(0) = 0.
    //
    // M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 (2026-05-11): default bumped
    // 1e-8 → 1e-5 based on user λ-sweep showing redundant production
    // rigs (22 poses × 9-dim Raw) need λ ≥ 1e-5 for well-posed K across
    // ALL 6 kernels. Previous default 1e-8 (v5 PART G.1 Step 2 / Chad
    // Vernon reference) was tuned for sparse / orthogonal pose sets
    // and silently kFailure'd on dense production rigs. New default
    // gives new nodes a well-posed starting point; existing rigs keep
    // their stored value but get auto-bumped to ≤ 1e-5 by the bounded
    // retry loop. Training-point bias at λ=1e-5 is ~0.1% (well below
    // rest-pose tolerance 1e-3). Standard well-conditioned RBF
    // training (Schaback 1995, Wendland 2004) operates in this λ
    // range; restoring it isn't "凑数" — it's correct math.
    regularization = nAttr.create("regularization", "reg", MFnNumericData::kDouble);
    nAttr.setKeyable(true);
    nAttr.setStorable(true);
    nAttr.setDefault(1.0e-5);
    nAttr.setMin(0.0);
    nAttr.setSoftMax(1.0e-3);

    // M2.2: output quaternion group starts. int multi; each stored value
    // S declares that output[S..S+3] forms a unit-quaternion group for
    // QWA aggregation. Implicit count = 4 per start (v5 addendum §M2.2
    // (B) schema simplification). Empty array = QWA dormant (zero
    // regression). Invalid entries (out-of-range, overlapping, scale
    // collision) are dropped at compute() time with a once-per-config
    // warning — never kFailure.
    outputQuaternionGroupStart = nAttr.create(
        "outputQuaternionGroupStart", "oqgs", MFnNumericData::kInt);
    nAttr.setArray(true);
    nAttr.setUsesArrayDataBuilder(true);
    nAttr.setKeyable(false);
    nAttr.setStorable(true);
    nAttr.setDefault(0);
    nAttr.setMin(0);

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

    // M2.3: per-pose local-Transform snapshot children. Pure data channel —
    // compute() never reads these; they exist for downstream JSON export
    // (M3) and engine-side bone-pose reconstruction (v5 PART D.5 / 铁律
    // B10). Decomposition is 10-dim (t + q + s); rotateOrder-independent
    // because quat extraction sidesteps Euler. See v5 addendum §M2.3.
    poseLocalTranslate = nAttr.create("poseLocalTranslate", "plt",
        MFnNumericData::k3Double);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(0.0, 0.0, 0.0);

    poseLocalQuat = nAttr.create("poseLocalQuat", "plq",
        MFnNumericData::k4Double);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(0.0, 0.0, 0.0, 1.0);   // identity quat, q_w canonical

    poseLocalScale = nAttr.create("poseLocalScale", "pls",
        MFnNumericData::k3Double);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(1.0, 1.0, 1.0);        // identity scale

    // M2.5: per-pose SwingTwist cache children. Runtime perf optimization
    // for SwingTwist-encoded nodes; not part of the JSON schema.
    // poseSigma=-1.0 doubles as a "cache populated" sentinel AND as a
    // per-pose sigma override slot (v5 PART E.10 forward-compat). See
    // addendum §M2.5 Cache vs Schema Boundary Contract.
    poseSwingQuat = nAttr.create("poseSwingQuat", "psq",
        MFnNumericData::k4Double);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(0.0, 0.0, 0.0, 1.0);   // identity quat

    poseTwistAngle = nAttr.create("poseTwistAngle", "pta",
        MFnNumericData::kDouble);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(0.0);

    poseSwingWeight = nAttr.create("poseSwingWeight", "psw",
        MFnNumericData::kDouble);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(1.0);

    poseTwistWeight = nAttr.create("poseTwistWeight", "ptw",
        MFnNumericData::kDouble);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(1.0);

    poseSigma = nAttr.create("poseSigma", "psg",
        MFnNumericData::kDouble);
    nAttr.setStorable(true);
    nAttr.setKeyable(false);
    nAttr.setDefault(-1.0);                 // sentinel = unpopulated / use global

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

    // M_B24a1: driverSource compound (multi). Per-driver companion
    // metadata for driverList[d] - same index binding. Build the 4
    // child fields in {} scopes so MFn local instances do not shadow
    // the surrounding cAttr/eAttr/nAttr/tAttr/mAttr (M2.5 cache
    // pattern). The compound parent setReadable(false) prevents
    // accidental cycle warnings (input-only).
    {
        MFnMessageAttribute mAttr_;
        driverSource_node = mAttr_.create("driverSource_node", "dsn");
        mAttr_.setStorable(true);
        mAttr_.setHidden(true);   // 加固 K.1-4: forward-compat, not user-facing
    }
    {
        MFnTypedAttribute tAttr_;
        MFnStringArrayData saData_;
        MObject defaultStrings_ = saData_.create(MStringArray());
        driverSource_attrs = tAttr_.create("driverSource_attrs", "dsa",
                                           MFnData::kStringArray, defaultStrings_);
        tAttr_.setStorable(true);
    }
    {
        MFnNumericAttribute nAttr_;
        driverSource_weight = nAttr_.create("driverSource_weight", "dsw",
                                             MFnNumericData::kDouble, 1.0);
        nAttr_.setStorable(true);
        nAttr_.setKeyable(true);
    }
    {
        MFnEnumAttribute eAttr_;
        driverSource_encoding = eAttr_.create("driverSource_encoding", "dse", 0);
        eAttr_.addField("Raw",        0);
        eAttr_.addField("Quaternion", 1);
        eAttr_.addField("BendRoll",   2);
        eAttr_.addField("ExpMap",     3);
        eAttr_.addField("SwingTwist", 4);
        eAttr_.setStorable(true);
    }
    driverSource = cAttr.create("driverSource", "drs");
    cAttr.setStorable(true);
    cAttr.setArray(true);
    cAttr.setUsesArrayDataBuilder(true);
    cAttr.setReadable(false);   // 加固 K.1-5: input-only, prevent cycle warnings
    cAttr.setWritable(true);
    cAttr.addChild(driverSource_node);
    cAttr.addChild(driverSource_attrs);
    cAttr.addChild(driverSource_weight);
    cAttr.addChild(driverSource_encoding);

    // M2.3: build the poseLocalTransform compound BEFORE nesting it
    // into poses[p], so the child registration order on the `poses`
    // compound is: poseInput, poseValue, poseLocalTransform. The
    // addChild calls below must happen AFTER poseLocalTransform is
    // assembled here — Maya evaluates addChild in the cAttr current
    // context; re-ordering would silently attach children to the
    // wrong parent.
    poseLocalTransform = cAttr.create("poseLocalTransform", "plxf");
    cAttr.setStorable(true);
    cAttr.setKeyable(false);
    cAttr.addChild(poseLocalTranslate);
    cAttr.addChild(poseLocalQuat);
    cAttr.addChild(poseLocalScale);

    // M2.5: build the poseSwingTwistCache compound BEFORE nesting it
    // into poses[p]. Same ordering rule as poseLocalTransform: the
    // addChild calls below must complete before `poses` cAttr nests
    // this compound. See addendum §M2.5.
    poseSwingTwistCache = cAttr.create("poseSwingTwistCache", "pstc");
    cAttr.setStorable(true);
    cAttr.setKeyable(false);
    cAttr.addChild(poseSwingQuat);
    cAttr.addChild(poseTwistAngle);
    cAttr.addChild(poseSwingWeight);
    cAttr.addChild(poseTwistWeight);
    cAttr.addChild(poseSigma);

    poses = cAttr.create("poses", "ps");
    cAttr.setKeyable(true);
    cAttr.setArray(true);
    cAttr.setUsesArrayDataBuilder(true);
    cAttr.addChild(poseInput);
    cAttr.addChild(poseValue);
    cAttr.addChild(poseLocalTransform);    // M2.3
    cAttr.addChild(poseSwingTwistCache);   // M2.5

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
    // M_B24a1: driverSource compound + 4 children. children must be
    // added BEFORE the compound (Maya schema order constraint).
    addAttribute(driverSource_node);
    addAttribute(driverSource_attrs);
    addAttribute(driverSource_weight);
    addAttribute(driverSource_encoding);
    addAttribute(driverSource);
    addAttribute(driverInput);
    addAttribute(pose);
    addAttribute(poseMatrix);
    addAttribute(poseParentMatrix);
    addAttribute(input);
    addAttribute(restInput);
    // Commit 0 (M_PER_POSE_SIGMA / M_BASE_POSE)
    addAttribute(poseRadius);
    addAttribute(basePoseValue);
    addAttribute(poses);
    addAttribute(poseInput);
    addAttribute(poseValue);
    // M2.3: local-Transform compound + children. No attributeAffects
    // because this is a pure data channel (compute() never reads it).
    addAttribute(poseLocalTranslate);
    addAttribute(poseLocalQuat);
    addAttribute(poseLocalScale);
    addAttribute(poseLocalTransform);
    // M2.5: SwingTwist cache compound + children. No attributeAffects
    // because the cache is a runtime perf optimization read inside
    // compute() but written by the Apply pipeline (see core.py
    // write_pose_swing_twist_cache). poseSigma=-1.0 is the sentinel
    // for "cache not populated" — compute() falls back to live
    // decomposeSwingTwist on miss. See addendum §M2.5.
    addAttribute(poseSwingQuat);
    addAttribute(poseTwistAngle);
    addAttribute(poseSwingWeight);
    addAttribute(poseTwistWeight);
    addAttribute(poseSigma);
    addAttribute(poseSwingTwistCache);
    addAttribute(output);
    addAttribute(baseValue);
    addAttribute(outputIsScale);
    addAttribute(clampEnabled);
    addAttribute(clampInflation);
    addAttribute(regularization);
    addAttribute(solverMethod);
    addAttribute(inputEncoding);
    addAttribute(outputEncoding);   // M_B24a1
    addAttribute(driverInputRotateOrder);
    addAttribute(outputQuaternionGroupStart);
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
    attributeAffects(RBFtools::outputEncoding, RBFtools::output);   // M_B24a1
    attributeAffects(RBFtools::driverInputRotateOrder, RBFtools::output);
    attributeAffects(RBFtools::outputQuaternionGroupStart, RBFtools::output);
    attributeAffects(RBFtools::radius, RBFtools::output);
    // Commit 0 (M_PER_POSE_SIGMA / M_BASE_POSE) — both feed compute().
    attributeAffects(RBFtools::poseRadius,    RBFtools::output);
    attributeAffects(RBFtools::basePoseValue, RBFtools::output);
    attributeAffects(RBFtools::centerAngle, RBFtools::output);
    attributeAffects(RBFtools::curveRamp, RBFtools::output);
    attributeAffects(RBFtools::direction, RBFtools::output);
    attributeAffects(RBFtools::distanceType, RBFtools::output);
    attributeAffects(RBFtools::driverIndex, RBFtools::output);
    attributeAffects(RBFtools::driverInput, RBFtools::output);
    // M_B24a1: driverSource compound 4 children -> output. compound
    // parent itself is NOT connected; child dirty propagates to
    // parent (same pattern as driverList: parent not in attrAffects).
    attributeAffects(RBFtools::driverSource_node,     RBFtools::output);
    attributeAffects(RBFtools::driverSource_attrs,    RBFtools::output);
    attributeAffects(RBFtools::driverSource_weight,   RBFtools::output);
    attributeAffects(RBFtools::driverSource_encoding, RBFtools::output);
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
    //
    // The retrain trigger for inputEncoding lives in the
    // M_P0_TRAINING_AFFECTING_ATTRS block below (deliberately AFTER
    // ``evalInput = evaluatePlug.asBool();`` so the
    // training-affecting-attr promotion to evalInput=true is not
    // clobbered by the read).
    bool inputEncodingChangedThisFrame = false;
    if (inputEncodingVal != prevInputEncodingVal)
    {
        inputEncodingWarningIssued = false;
        inputEncodingChangedThisFrame = true;
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

    // -----------------------------------------------------------------
    // M_P0_TRAINING_AFFECTING_ATTRS (2026-05-10): force re-train when
    // any attribute that influences the K matrix or the encoded pose
    // vectors changes. attributeAffects(<attr>, output) marks output
    // dirty but evalInput defaults to False; without this guard the
    // wMat trained under the OLD attribute value gets reused with
    // the NEW value at inference, producing mathematically inconsistent
    // results (rest-pose joint drift, distorted interpolation curves).
    //
    // Tracked attrs and the math they influence:
    //   kernel         → φ shape (every K[i,j] activation depends on it)
    //   distanceType   → d(p_i, p_j) metric (every K[i,j] depends on it)
    //   inputEncoding  → encoded pose vector dimension and content
    //   radius         → σ in φ(d, σ) when radiusType=Custom
    //   radiusType     → which σ source to use (mean / median / custom)
    //   regularization → λI injection into K diagonal
    //
    // Compare to existing prev-trackers in this file:
    //   prevSolverMethodVal   → only resets lastSolveMethod cache, NOT
    //                            evalInput (kernel SPD-ness is solver-
    //                            independent — correct historical
    //                            behaviour, kept).
    //   prevQuatGroupConfigHash → DOES set evalInput=true (cpp:1681)
    //   prevBaseValueArr / prevOutputIsScaleArr → DOES set evalInput
    //                            (cpp:1628)
    // -----------------------------------------------------------------
    bool trainingAttrChanged = false;
    if (kernelVal != prevKernelVal)
    {
        if (prevKernelVal != -1)  // skip first-compute spurious trigger
            trainingAttrChanged = true;
        prevKernelVal = kernelVal;
    }
    if (distanceTypeVal != prevDistanceTypeVal)
    {
        if (prevDistanceTypeVal != -1)
            trainingAttrChanged = true;
        prevDistanceTypeVal = distanceTypeVal;
    }
    if (radiusTypeVal != prevRadiusTypeVal)
    {
        if (prevRadiusTypeVal != -1)
            trainingAttrChanged = true;
        prevRadiusTypeVal = radiusTypeVal;
    }
    if (radiusVal != prevRadiusVal)
    {
        if (prevRadiusVal != -1.0)
            trainingAttrChanged = true;
        prevRadiusVal = radiusVal;
    }
    if (regularizationVal != prevRegularizationVal)
    {
        if (prevRegularizationVal != -1.0)
            trainingAttrChanged = true;
        prevRegularizationVal = regularizationVal;
    }
    // inputEncoding change — flag was set in the warning-reset block
    // above (cpp:1207-1220 area), where ``evalInput`` had not yet
    // been read from the plug. We promote to evalInput=true here so
    // the read at cpp:1227 does not clobber.
    if (inputEncodingChangedThisFrame)
        trainingAttrChanged = true;

    if (trainingAttrChanged)
        evalInput = true;

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
                // M2.1b: BendRoll (2) and SwingTwist (4) are now
                // implemented; placeholder branch removed. The non-
                // triple safety net remains — it catches user misconfig
                // regardless of which non-Raw encoding is selected.
                const bool nonTriple = (wantsEncoded && rawInDim % 3 != 0);

                if (nonTriple)
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
                                     (unsigned)twistAxisVal,
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

            // M1.3 + M2.1b: clip driver to the per-dim training-hull
            // bounding box. Bounds were cached by getPoseData /
            // getPoseVectors in raw (pre-normalize) space, so
            // `clampInflation` stays in user-visible units.
            //
            // M2.1b replaces the single `j % 4 == 3` rule with a
            // skip-mask built from (isMatrixMode, effectiveEncoding)
            // per addendum §M2.1b.5. Wrap-aware dims (Matrix-mode
            // twist, BendRoll roll, SwingTwist twist) are excluded
            // from linear clamping to preserve M1.1's wrap semantics.
            //
            // Defense: empty cache (first compute before any train) and
            // size-mismatch (driver dim changed but bounds stale) both
            // short-circuit, preserving behaviour rather than crashing.
            if (clampEnabledVal
                && !poseMinVec.empty()
                && poseMinVec.size() == driver.size()
                && poseMaxVec.size() == driver.size())
            {
                const size_t dim = driver.size();
                std::vector<bool> clampSkipMask(dim, false);
                if (!genericMode)
                {
                    for (size_t j = 0; j < dim; ++j)
                        if (j % 4 == 3) clampSkipMask[j] = true;
                }
                else if (effectiveEncoding == 2 /* BendRoll */)
                {
                    for (size_t j = 0; j < dim; ++j)
                        if (j % 3 == 0) clampSkipMask[j] = true;  // roll slot
                }
                else if (effectiveEncoding == 4 /* SwingTwist */)
                {
                    for (size_t j = 0; j < dim; ++j)
                        if (j % 5 == 4) clampSkipMask[j] = true;  // twist slot
                }
                for (size_t j = 0; j < dim; ++j)
                {
                    if (clampSkipMask[j]) continue;
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

            // M2.2: resolve the quaternion-group schema. Runs only in
            // Generic mode (QWA is an output-side concept; Matrix mode
            // output is one-hot blend weights with no quaternion
            // semantics). Produces (validStarts, isQuatMember); invalid
            // configurations emit a once-per-config warning without
            // halting the DG. See addendum §M2.2.MASK-INDEX for the
            // four downstream consumers of isQuatMember.
            std::vector<int> quatGroupStarts;
            std::vector<bool> isQuatMember(solveCount, false);
            if (genericMode && solveCount > 0)
            {
                // Read raw starts from the multi int array.
                std::vector<int> rawStarts;
                MArrayDataHandle qgsHandle =
                    data.inputArrayValue(outputQuaternionGroupStart, &status);
                if (status == MStatus::kSuccess)
                {
                    const unsigned cnt = qgsHandle.elementCount();
                    for (unsigned k = 0; k < cnt; ++k)
                    {
                        if (qgsHandle.jumpToArrayElement(k) == MStatus::kSuccess)
                            rawStarts.push_back(qgsHandle.inputValue().asInt());
                    }
                }

                // Config-hash: stable order-sensitive digest so user
                // edits to the quat-group spec reset the once-per-rig
                // warning flags (addendum §M2.2 (Q9)).
                size_t newHash = rawStarts.size();
                for (int s : rawStarts)
                    newHash = newHash * 131u + (size_t)(s + 1);
                if (newHash != prevQuatGroupConfigHash)
                {
                    qwaConfigWarningIssued = false;
                    qwaClippedWarningIssued = false;
                    qwaDegenerateWarningIssued = false;
                    // M_P0_QUAT_RBF_OVERLAP_DISCLOSE: a fresh quat-
                    // group config can re-trigger the overlap check.
                    outputEncodingOverlapWarningIssued = false;
                    prevQuatGroupConfigHash = newHash;
                    // Re-solve wMat: columns that just became quat
                    // members must be zeroed in the solver output,
                    // and columns that just left quat membership must
                    // get freshly solved. attributeAffects alone reuses
                    // the cached wMat, producing incorrect output until
                    // the next structural change; mirror the M1.2
                    // baseline dirty-tracker pattern.
                    evalInput = true;
                }

                bool anyInvalid = false;
                resolveQuaternionGroups(rawStarts, solveCount, outputIsScaleArr,
                                        quatGroupStarts, isQuatMember,
                                        anyInvalid);
                if (anyInvalid && !qwaConfigWarningIssued)
                {
                    MGlobal::displayWarning(thisName + MString(
                        ": outputQuaternionGroupStart contains invalid "
                        "entries (out-of-range, overlapping, or colliding "
                        "with outputIsScale). Those groups are disabled; "
                        "remaining groups run QWA normally."));
                    qwaConfigWarningIssued = true;
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

                // Commit 0b (M_PER_POSE_SIGMA): hoist poseRadius read
                // ABOVE the evalInput block so the SAME widths vector
                // feeds both training-time getActivations (K matrix
                // build) and inference-time getPoseWeights (per-pose
                // φ(dist, σ_j)). Math contract: training and inference
                // must share the basis function — using widths[i] in
                // both ensures K[j,j] · w_j evaluates to exactly 1.0
                // when the driver sits on pose j (modulo regularization).
                std::vector<double> perPoseWidths;
                {
                    MArrayDataHandle prHandle =
                        data.inputArrayValue(RBFtools::poseRadius);
                    unsigned prCount = prHandle.elementCount();
                    perPoseWidths.assign(poseCount, getRadiusValue());
                    for (unsigned p = 0; p < prCount; p ++)
                    {
                        unsigned idx = prHandle.elementIndex();
                        if (idx < poseCount)
                        {
                            double w = prHandle.inputValue().asDouble();
                            if (w > 0.0)
                                perPoseWidths[idx] = w;
                        }
                        if (p + 1 < prCount) prHandle.next();
                    }
                }

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
                    // activation values. Commit 0b: perPoseWidths is
                    // now hoisted above the evalInput block so the
                    // same vector feeds inference too.
                    getActivations(linMat, perPoseWidths,
                                   getRadiusValue(), kernelVal);

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
                        // M2.2: quaternion-group dims skip the scalar
                        // solve entirely — their output is produced by
                        // QWA (post-loop Power Iteration), not by
                        // K W = Y followed by linear combination. Using
                        // an all-zero RHS here leaves wMat's column at
                        // zero; the scalar path in getPoseWeights then
                        // contributes nothing to those output slots,
                        // and the QWA post-loop overwrites them with
                        // the Power-Iteration eigenvector.
                        if (c < isQuatMember.size() && isQuatMember[c])
                        {
                            yCols[c].assign(poseCount, 0.0);
                            continue;
                        }
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
                    // Audit chain at this solver block (newest first):
                    //   M_P0_RBF_POLYNOMIAL_AUGMENTATION (this commit)
                    //     supersedes ↑
                    //   M_P0_LAMBDA_RETRY_TIERED_CEIL (4a3cae4)
                    //     supersedes ↑
                    //   M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 (8e7a6d3)
                    //     supersedes ↑
                    //   M_P0_KERNEL_SWITCH_ROLLBACK_2 (91adfc9)
                    //     supersedes ↑
                    //   M_P0_AUTO_ADAPTIVE_LAMBDA (156af4c) +
                    //     M_P0_LAMBDA_CEIL_TIGHTEN (ee6d63f)
                    //
                    // M_P0_RBF_POLYNOMIAL_AUGMENTATION (2026-05-11):
                    // mathematically-correct CPD-kernel treatment via
                    // polynomial augmentation. Supersedes the bounded /
                    // tiered λ retry approach (8e7a6d3 + b16d117 +
                    // 4a3cae4 + fd5607b) that was a band-aid over a
                    // fundamental math defect.
                    //
                    // Why the previous retry-loop approach was wrong:
                    //   - Conditionally-positive-definite (CPD) kernels
                    //     — Linear / Thin Plate / Multi-Quadric /
                    //     Inverse Multi-Quadric — have a null-space in
                    //     the RBF interpolation operator K. No amount
                    //     of Tikhonov regularization (K + λI) eliminates
                    //     this null-space; raising λ only damps the
                    //     null-space contribution while distorting the
                    //     well-defined part. Result: visible joint
                    //     drift at the training-point invariant even
                    //     when the solver "succeeds" at the ceil λ.
                    //   - User λ = 1e-3 + MQB still drifted on the
                    //     reproducer rig: empirical confirmation that
                    //     λ ceil is the wrong dial.
                    //
                    // Correct math (Wendland 2004 §10, Schaback 1995,
                    // Wahba 1990): augment the system with a polynomial
                    // basis P of degree (m - 1) where m is the kernel's
                    // CPD order. The augmented system
                    //
                    //   [ K + λI   P  ] [ w ]   [ y ]
                    //   [ P^T      0  ] [ a ] = [ 0 ]
                    //
                    // is invertible (when P has full column rank, i.e.
                    // poses span general position) and provides the
                    // unique reproducing-kernel-Hilbert-space solution.
                    //
                    // Inference:
                    //   ŷ(x) = Σ_j w_j · φ(d(x, p_j); σ) + Σ_k a_k · p_k(x)
                    //
                    // Polynomial dim per kernel (getPolynomialDim):
                    //   Gaussian 1 / Gaussian 2  (strictly PD)     → 0
                    //   Linear  / MQB / IMQB     (CPD order m = 1) → 1
                    //   Thin Plate               (CPD order m = 2) → 1 + driverDim
                    //
                    // Solver branches on polyDim:
                    //   polyDim == 0 (Gaussian): K + λI is SPD;
                    //     try Cholesky tier 1 then GE tier 2 single-pass
                    //     (matches Oracle's two-tier dispatch).
                    //   polyDim > 0  (CPD): augmented (N + polyDim) ×
                    //     (N + polyDim) saddle-point matrix is indefinite
                    //     by construction (bottom-right 0 block), so
                    //     Cholesky is mathematically inapplicable; GE
                    //     only, single-pass per output column. The
                    //     trial-wMat pattern is preserved so a per-
                    //     column singularity cannot pollute partial
                    //     state.
                    //
                    // Failure → kFailure + displayError. Honest failure
                    // is preserved at the augmented system level: if
                    // (K + λI, P) jointly fail to be invertible, the
                    // pose set is genuinely degenerate (duplicate poses
                    // or all poses on a hyperplane → P rank-deficient)
                    // and the rigger needs to know rather than receive
                    // numerical garbage.
                    //
                    // The retry-loop approach is FULLY REMOVED:
                    //   - LAMBDA_CEIL_TIERED / MAX_RETRIES_TIERED constants
                    //     are gone.
                    //   - kIsStrictlyPDKernel ternary gate gone.
                    //   - while-loop retry block gone.
                    //   - Single λ injection at user value; correct
                    //     CPD math at any λ ≥ 0.
                    //
                    // See docs/排查/M_P0_KERNEL_SWITCH_ROLLBACK_index.md
                    // §0.5 + this commit's message for the full audit
                    // trail (ROLLBACK_2 → 8e7a6d3 → b16d117 → 4a3cae4 →
                    // fd5607b → this commit).
                    // -------------------------------------------------

                    // Driver dim is matPoses' column count post-encoding
                    // (= effectiveInDim for Generic mode; for Matrix
                    // mode it is 4 * driverCount per cpp:2279).
                    const int driverDim =
                        (int)matPoses.getColSize();
                    const int polyDim =
                        getPolynomialDim(kernelVal, driverDim);

                    wMat = BRMatrix();
                    wMat.setSize(poseCount, solveCount);
                    polyMat = BRMatrix();
                    // setSize must be > 0 on both axes; allocate a 1 ×
                    // solveCount sentinel when polyDim == 0 (Gaussian)
                    // so the matrix is constructible but never read
                    // by the inference path (polyDim == 0 branch in
                    // getPoseWeights skips the polynomial term).
                    polyMat.setSize(
                        (unsigned)(polyDim > 0 ? polyDim : 1),
                        solveCount);

                    const double userLambda = (regularizationVal > 0.0)
                                              ? regularizationVal : 0.0;
                    if (userLambda > 0.0)
                    {
                        for (unsigned dd = 0; dd < poseCount; ++dd)
                            linMat(dd, dd) += userLambda;
                    }

                    if (exposeDataVal > 2 && userLambda > 0.0)
                        linMat.show(thisName, "Activations + λI");

                    bool solved       = false;
                    int  lastSingular = -1;

                    if (polyDim == 0)
                    {
                        // -------------------------------------------------
                        // Strictly-PD path (Gaussian). Single-pass
                        // Cholesky tier 1 / GE tier 2 dispatch — Oracle
                        // RBFtools cpp:1865-1925 behaviour, no retry.
                        // -------------------------------------------------
                        if (solverMethodVal == 0
                            && lastSolveMethod == 0)
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
                                lastSolveMethod = 0;
                                solved          = true;
                                if (exposeDataVal > 2)
                                    MGlobal::displayInfo(
                                        thisName + MString(
                                            ": solver = Cholesky"));
                            }
                        }
                        if (!solved)
                        {
                            bool geOk = true;
                            BRMatrix wMatTrial;
                            wMatTrial.setSize(poseCount, solveCount);
                            for (c = 0; c < solveCount; c ++)
                            {
                                BRMatrix solveMat = linMat;
                                std::vector<double> w(poseCount, 0.0);
                                int singularIndex = -1;
                                bool ok = solveMat.solve(
                                    yCols[c], w.data(), singularIndex);
                                if (!ok)
                                {
                                    geOk = false;
                                    lastSingular = singularIndex;
                                    break;
                                }
                                for (i = 0; i < poseCount; i ++)
                                    wMatTrial(i, c) = w[i];
                            }
                            if (geOk)
                            {
                                wMat            = wMatTrial;
                                lastSolveMethod = 1;
                                solved          = true;
                                if (exposeDataVal > 2)
                                    MGlobal::displayInfo(
                                        thisName + MString(
                                            ": solver = GE (fallback)"));
                            }
                        }
                    }
                    else
                    {
                        // -------------------------------------------------
                        // CPD path (Linear / TPS / MQB / IMQB).
                        // Build (N + polyDim) × (N + polyDim) augmented
                        // saddle-point matrix
                        //   A = [ K + λI   P  ]
                        //       [ P^T      0  ]
                        // GE-only solve per output column (saddle-point
                        // matrices are indefinite by construction; the
                        // bottom-right 0 block guarantees Cholesky
                        // would fail).
                        // -------------------------------------------------
                        const unsigned augN =
                            poseCount + (unsigned)polyDim;
                        BRMatrix A;
                        A.setSize(augN, augN);
                        // Top-left N × N block: K + λI (copy from
                        // linMat which already has the λI injected).
                        for (unsigned ai = 0; ai < poseCount; ++ai)
                            for (unsigned aj = 0; aj < poseCount; ++aj)
                                A(ai, aj) = linMat(ai, aj);
                        // P block: A(i, N+k) = polyBasis(matPoses row i)[k]
                        // and its transpose A(N+k, i) = same.
                        std::vector<double> p_row;
                        for (unsigned ai = 0; ai < poseCount; ++ai)
                        {
                            polyBasis(matPoses.getRowVector(ai),
                                      polyDim, p_row);
                            for (int pk = 0; pk < polyDim; ++pk)
                            {
                                A(ai, poseCount + (unsigned)pk) =
                                    p_row[(size_t)pk];
                                A(poseCount + (unsigned)pk, ai) =
                                    p_row[(size_t)pk];
                            }
                        }
                        // Bottom-right polyDim × polyDim 0 block is
                        // already zero from BRMatrix::setSize.

                        if (exposeDataVal > 2)
                            A.show(thisName,
                                   "Augmented (K+lambdaI, P; P^T, 0)");

                        // Per-column GE solve with trial-wMat /
                        // trial-polyMat staging (mirrors the strictly-PD
                        // path's pollution-safety).
                        bool geOk = true;
                        BRMatrix wMatTrial;
                        wMatTrial.setSize(poseCount, solveCount);
                        BRMatrix polyMatTrial;
                        polyMatTrial.setSize((unsigned)polyDim, solveCount);
                        std::vector<double> y_aug(augN, 0.0);
                        std::vector<double> w_aug(augN, 0.0);
                        for (c = 0; c < solveCount; c ++)
                        {
                            BRMatrix solveMat = A;
                            // y_aug[0..N-1] = yCols[c]; y_aug[N..] = 0
                            for (unsigned ai = 0; ai < poseCount; ++ai)
                                y_aug[ai] =
                                    (ai < yCols[c].size())
                                    ? yCols[c][ai] : 0.0;
                            for (unsigned k = 0;
                                 k < (unsigned)polyDim; ++k)
                                y_aug[poseCount + k] = 0.0;
                            std::fill(w_aug.begin(),
                                      w_aug.end(), 0.0);
                            int singularIndex = -1;
                            bool ok = solveMat.solve(
                                y_aug, w_aug.data(), singularIndex);
                            if (!ok)
                            {
                                geOk = false;
                                lastSingular = singularIndex;
                                break;
                            }
                            for (i = 0; i < poseCount; i ++)
                                wMatTrial(i, c) = w_aug[i];
                            for (int pk = 0; pk < polyDim; ++pk)
                                polyMatTrial((unsigned)pk, c) =
                                    w_aug[poseCount + (unsigned)pk];
                        }
                        if (geOk)
                        {
                            wMat            = wMatTrial;
                            polyMat         = polyMatTrial;
                            lastSolveMethod = 1;
                            solved          = true;
                            if (exposeDataVal > 2)
                                MGlobal::displayInfo(
                                    thisName + MString(
                                        ": solver = augmented GE "
                                        "(polyDim ") +
                                    polyDim + ")");
                        }
                    }

                    if (!solved)
                    {
                        MGlobal::displayInfo("");
                        MGlobal::displayInfo(
                            thisName + MString(": RBF Error"));
                        MGlobal::displayInfo(
                            MString("RBF system singular at user "
                                    "lambda = ") + userLambda +
                            ", kernel index = " + kernelVal +
                            ", polyDim = " + polyDim + ".");
                        if (lastSingular >= 0)
                            MGlobal::displayInfo(
                                MString("Last singular pose index: ") +
                                lastSingular);
                        MGlobal::displayInfo(
                            "The pose set is genuinely degenerate: "
                            "either two or more poses are exact "
                            "duplicates in the encoded driver space, "
                            "or (for CPD kernels) the poses lie on a "
                            "hyperplane making the polynomial basis "
                            "rank-deficient.");
                        matDebug.show(thisName,
                            "Pose Input Values (Poses appear in rows)");
                        MGlobal::displayError(
                            MString("RBF decomposition failed at "
                                    "kernel index ") + kernelVal +
                            " with polyDim = " + polyDim +
                            "; remove duplicate poses or move poses "
                            "off a common hyperplane "
                            "(M_P0_RBF_POLYNOMIAL_AUGMENTATION).");
                        return MStatus::kFailure;
                    }

                    if (exposeDataVal > 2)
                        wMat.show(thisName, "Weight matrix");
                }

                // -----------------------------------------------
                // final weight calculation
                // -----------------------------------------------

                bool qwaAnyClipped = false;
                bool qwaAnyDegenerate = false;
                // M_P0_RBF_POLYNOMIAL_AUGMENTATION (2026-05-11): pass
                // polyMat + polyDim so getPoseWeights can add the
                // polynomial term to CPD-kernel inference. polyDim is
                // re-derived from kernelVal + matPoses cols here so
                // the inference side stays consistent with the
                // training-side dispatch above.
                const int polyDimInfer =
                    getPolynomialDim(kernelVal,
                                     (int)matPoses.getColSize());
                getPoseWeights(weightsArray,
                               matPoses,
                               inputNorms,
                               driver,
                               poseModes,
                               wMat,
                               perPoseWidths,         // Commit 0b
                               getRadiusValue(),      // fallback
                               distanceTypeVal,
                               (int)effectiveEncoding,
                               /*isMatrixMode*/ !genericMode,
                               kernelVal,
                               matValues,
                               quatGroupStarts,
                               isQuatMember,
                               qwaAnyClipped,
                               qwaAnyDegenerate,
                               polyMat,             // M_P0_RBF_POLYNOMIAL_AUGMENTATION
                               polyDimInfer);
                if (qwaAnyClipped && !qwaClippedWarningIssued)
                {
                    MGlobal::displayWarning(thisName + MString(
                        ": QWA negative kernel activation clipped to 0 "
                        "to preserve PSD property (addendum §M2.2 Q8). "
                        "This path is invoked only when quaternion groups "
                        "are active; scalar output is unaffected."));
                    qwaClippedWarningIssued = true;
                }
                if (qwaAnyDegenerate && !qwaDegenerateWarningIssued)
                {
                    MGlobal::displayWarning(thisName + MString(
                        ": QWA returned identity quaternion for at least "
                        "one group (zero-mass or non-convergent Power "
                        "Iteration). Addendum §M2.2 (E)."));
                    qwaDegenerateWarningIssued = true;
                }

                if (exposeDataVal == 2 || exposeDataVal == 4)
                    showArray(weightsArray, thisName + " : RBF Weights");

                // -----------------------------------------------
                // M_P0_QUATERNION_BACKEND_LAND (2026-05-10):
                // node-level outputEncoding inverse transform.
                // Generic mode only — Matrix mode's output is one-hot
                // pose weights, not Euler triples, so the encoding has
                // no semantic anchor there.
                //
                // Quaternion / ExpMap rebuild the per-channel weighted
                // sum that getPoseWeights produced into a quat-blended
                // value. BendRoll (2) / SwingTwist (4) fall through to
                // the legacy weighted sum and emit a once-per-rig
                // warning — backend support deferred to v5.x post-final
                // (each requires bespoke decomposition + composition
                // math distinct from the Quat / ExpMap pair).
                // -----------------------------------------------
                MPlug outEncRebuildPlug(thisNode, RBFtools::outputEncoding);
                short outEncRebuildVal = outEncRebuildPlug.asShort();
                if (genericMode && outEncRebuildVal != 0)
                {
                    // M_P0_OUTPUT_EXPMAP_FIX (2026-05-10): outputEncoding
                    // schema only registers {0=Euler, 1=Quaternion,
                    // 2=ExpMap} (cpp:295-298) — there is no BendRoll(2)
                    // / SwingTwist(4) slot at all on the output side
                    // (those are inputEncoding-only enum values). The
                    // ce136dd version had a `else if (!...Issued)` branch
                    // warning about deferred BendRoll/SwingTwist
                    // implementation; that branch was unreachable dead
                    // code and the user-facing message contradicted the
                    // schema. Removed; applyOutputEncodingBlend's own
                    // early-return handles the only legal "skip" case
                    // (outputEncoding == 0 / Euler).
                    MDoubleArray perPosePhi;
                    computePerPosePhi(perPosePhi,
                                      matPoses,
                                      inputNorms,
                                      driver,
                                      poseModes,
                                      perPoseWidths,
                                      getRadiusValue(),
                                      distanceTypeVal,
                                      (int)effectiveEncoding,
                                      /*isMatrixMode*/ !genericMode,
                                      kernelVal);
                    // rotateOrder = 0 (XYZ default). Per-driven-source
                    // rotateOrder schema (drivenInputRotateOrder) does
                    // not yet exist — see addendum
                    // §M_P0_QUATERNION_BACKEND_LAND for the v5.x
                    // forward pointer.
                    bool overlapWarning = false;
                    applyOutputEncodingBlend(weightsArray,
                                             perPosePhi,
                                             matValues,
                                             outEncRebuildVal,
                                             /*rotateOrder*/ 0,
                                             isQuatMember,
                                             overlapWarning);
                    // M_P0_QUAT_RBF_OVERLAP_DISCLOSE: once-per-rig
                    // disclosure when at least one B2 3-block was
                    // skipped because it intersects a B1 (QWA) 4-
                    // tuple. B1 takes precedence (Markley max-eigenvec
                    // is more robust than nlerp / ExpMap weighted sum
                    // for unit-quat output); this warning surfaces
                    // the silent skip to user disclosure level.
                    if (overlapWarning && !outputEncodingOverlapWarningIssued)
                    {
                        MGlobal::displayWarning(thisName + MString(
                            ": outputEncoding 3-block overlaps quaternion "
                            "group; skipped to preserve B1 QWA output. "
                            "Resolve by adjusting outputQuaternionGroupStart "
                            "or splitting the Euler 3-block off the quat "
                            "group's column range."));
                        outputEncodingOverlapWarningIssued = true;
                    }
                }

                // -----------------------------------------------
                // define the final values
                // -----------------------------------------------

                for (i = 0; i < weightsArray.length(); i ++)
                {
                    // M2.2: quaternion-group members carry the QWA
                    // Power-Iteration eigenvector components — they
                    // must NOT be reshaped by allowNegative /
                    // interpolateWeight / scale / baseline (those are
                    // scalar post-processing for delta weights).
                    // Preserve the value verbatim.
                    if (i < isQuatMember.size() && isQuatMember[i])
                        continue;

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

        // M_B24a1: read driverSource[d] companion metadata. Read path
        // verified + DG dirty kept alive; metadata semantic consumption
        // deferred to M_B24b business logic.
        // M_B24a1 placeholder: read path verified, metadata semantic
        // consumption deferred to M_B24b business logic. DO NOT remove
        // these reads — they keep DG dirty propagation alive even
        // before M_B24b lands.
        double srcWeight = 1.0;
        short  srcEncoding = 0;
        readDriverSourceMetadata(data, currentId, srcWeight, srcEncoding);
        (void)srcWeight; (void)srcEncoding;

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
                                  unsigned twistAxis,
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

    const bool encQuat       = (inputEncoding == 1);
    const bool encBendRoll   = (inputEncoding == 2);
    const bool encExpMap     = (inputEncoding == 3);
    const bool encSwingTwist = (inputEncoding == 4);
    // Resolve effective dim. Non-3-divisible inDim is the caller's
    // safety-net precondition; we still handle it defensively by
    // falling back to Raw semantics.
    const bool encAnyNonRaw = (encQuat || encBendRoll || encExpMap || encSwingTwist);
    const bool encActive = encAnyNonRaw && (inDim % 3 == 0) && (inDim > 0);
    const unsigned groups = encActive ? (inDim / 3) : 0;
    if (encQuat && encActive)
        effectiveInDim = groups * 4;
    else if (encSwingTwist && encActive)
        effectiveInDim = groups * 5;
    else
        effectiveInDim = inDim;  // BendRoll 3→3, ExpMap 3→3, Raw N→N

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
    else if (encBendRoll && encActive)
    {
        for (unsigned g = 0; g < groups; ++g)
        {
            double roll, bendH, bendV;
            encodeBendRoll(rawDriver[g*3+0], rawDriver[g*3+1], rawDriver[g*3+2],
                           groupRotateOrder(g), twistAxis, roll, bendH, bendV);
            driver[g*3+0] = roll;
            driver[g*3+1] = bendH;
            driver[g*3+2] = bendV;
        }
    }
    else if (encSwingTwist && encActive)
    {
        for (unsigned g = 0; g < groups; ++g)
        {
            double sx, sy, sz, sw, tw;
            encodeSwingTwist(rawDriver[g*3+0], rawDriver[g*3+1], rawDriver[g*3+2],
                             groupRotateOrder(g), twistAxis, sx, sy, sz, sw, tw);
            driver[g*5+0] = sx;
            driver[g*5+1] = sy;
            driver[g*5+2] = sz;
            driver[g*5+3] = sw;
            driver[g*5+4] = tw;
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
            else if (encBendRoll && encActive)
            {
                for (unsigned g = 0; g < groups; ++g)
                {
                    double roll, bendH, bendV;
                    encodeBendRoll(rawRow[g*3+0], rawRow[g*3+1], rawRow[g*3+2],
                                   groupRotateOrder(g), twistAxis,
                                   roll, bendH, bendV);
                    poseData(i, g*3+0) = roll;
                    poseData(i, g*3+1) = bendH;
                    poseData(i, g*3+2) = bendV;
                }
            }
            else if (encSwingTwist && encActive)
            {
                for (unsigned g = 0; g < groups; ++g)
                {
                    double sx, sy, sz, sw, tw;
                    encodeSwingTwist(rawRow[g*3+0], rawRow[g*3+1], rawRow[g*3+2],
                                     groupRotateOrder(g), twistAxis,
                                     sx, sy, sz, sw, tw);
                    poseData(i, g*5+0) = sx;
                    poseData(i, g*5+1) = sy;
                    poseData(i, g*5+2) = sz;
                    poseData(i, g*5+3) = sw;
                    poseData(i, g*5+4) = tw;
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
    //
    // M_P0_KERNEL_ALGO_AUDIT (2026-05-10): the legacy code path
    // honoured distType == 1 (Angle) ONLY when n == 3 (single
    // driver, single 3-vector). For multi-driver Raw setups
    // (n = 3K, K > 1) the Angle selection was silently dropped
    // and the path fell through to Euclidean — a multi-driver
    // bug that produced inconsistent UX (the same dropdown
    // choice meant different things at N=1 vs N>1).
    //
    // Fix: when n is a positive multiple of 3, aggregate per-3-
    // block angles via L2 (matches the Riemannian product-
    // manifold semantics used by the per-block quat / swing-twist
    // distance helpers). N=1 case is unchanged (single block →
    // single getAngle return).
    if (encoding == 0)
    {
        if (distType == 0)
            return getRadius(vec1, vec2);
        if (n == 3)
            return getAngle(vec1, vec2);
        if (n > 3 && n % 3 == 0)
        {
            // Per-3-block angle aggregation, L2.
            const size_t blocks = n / 3;
            double sumSq = 0.0;
            for (size_t k = 0; k < blocks; ++k)
            {
                const size_t base = k * 3;
                const std::vector<double> a = {
                    vec1[base + 0], vec1[base + 1], vec1[base + 2]};
                const std::vector<double> b = {
                    vec2[base + 0], vec2[base + 1], vec2[base + 2]};
                const double ang = getAngle(a, b);
                sumSq += ang * ang;
            }
            return sqrt(sumSq);
        }
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

    // BendRoll: per-3-block (roll, bendH, bendV) in ℝ³; plain
    // Euclidean is correct after normalizeColumns has balanced the
    // per-axis scales. (v5 PART G.4 / addendum §M2.1b.)
    if (encoding == 2)
        return getRadius(vec1, vec2);

    // SwingTwist: per-5-block composite (swing quat L2 + twist wrap).
    if (encoding == 4)
    {
        if (n >= 5 && n % 5 == 0)
            return getSwingTwistBlockDistance(vec1, vec2);
        return getRadius(vec1, vec2);  // defensive
    }

    // Unknown encoding: defensive fall-through. Mirrors the Raw
    // branch's multi-block Angle aggregation (M_P0_KERNEL_ALGO_AUDIT)
    // so an out-of-range encoding value still produces a consistent
    // distance shape across N=1 and N>1 driver setups.
    if (distType == 0)
        return getRadius(vec1, vec2);
    if (n == 3)
        return getAngle(vec1, vec2);
    if (n > 3 && n % 3 == 0)
    {
        const size_t blocks = n / 3;
        double sumSq = 0.0;
        for (size_t k = 0; k < blocks; ++k)
        {
            const size_t base = k * 3;
            const std::vector<double> a = {
                vec1[base + 0], vec1[base + 1], vec1[base + 2]};
            const std::vector<double> b = {
                vec2[base + 0], vec2[base + 1], vec2[base + 2]};
            const double ang = getAngle(a, b);
            sumSq += ang * ang;
        }
        return sqrt(sumSq);
    }
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
//      M_P0_QUATERNION_BACKEND_LAND (2026-05-10) — inverse of
//      encodeEulerToQuaternion. Maya's MQuaternion::asEulerRotation
//      returns the canonical XYZ Tait-Bryan extraction; reorderIt
//      then rewrites the same orientation under the requested
//      rotateOrder so the result matches the convention the encode
//      side used. Output (rx, ry, rz) is in radians.
//
void RBFtools::decodeQuaternionToEuler(double qx, double qy, double qz,
                                       double qw, short rotateOrder,
                                       double &rx, double &ry, double &rz)
{
    MQuaternion q(qx, qy, qz, qw);
    MEulerRotation e = q.asEulerRotation();
    MEulerRotation::RotationOrder order;
    switch (rotateOrder)
    {
        case 1:  order = MEulerRotation::kYZX; break;
        case 2:  order = MEulerRotation::kZXY; break;
        case 3:  order = MEulerRotation::kXZY; break;
        case 4:  order = MEulerRotation::kYXZ; break;
        case 5:  order = MEulerRotation::kZYX; break;
        case 0:
        default: order = MEulerRotation::kXYZ; break;
    }
    e.reorderIt(order);
    rx = e.x;
    ry = e.y;
    rz = e.z;
}


//
// Description:
//      M_P0_QUATERNION_BACKEND_LAND (2026-05-10) — inverse of
//      encodeQuaternionToExpMap, then to Euler. ExpMap → Quat uses
//      the standard q = (axis * sin(θ/2), cos(θ/2)) reconstruction
//      with a Taylor branch (sin(θ/2)/θ → 1/2) for the θ → 0
//      neighbourhood so log(identity) round-trips to (0, 0, 0)
//      without a divide-by-zero. The encode side canonicalises to
//      the q_w ≥ 0 hemisphere; the decode side reproduces a quat
//      with q_w = cos(θ/2) ≥ 0 for θ ∈ [0, π], matching that.
//
void RBFtools::decodeExpMapToEuler(double lx, double ly, double lz,
                                   short rotateOrder,
                                   double &rx, double &ry, double &rz)
{
    const double angle = sqrt(lx * lx + ly * ly + lz * lz);
    double qx, qy, qz, qw;
    if (angle < 1.0e-9)
    {
        // Taylor: sin(θ/2) / θ → 1/2 as θ → 0; cos(θ/2) → 1.
        qx = lx * 0.5;
        qy = ly * 0.5;
        qz = lz * 0.5;
        qw = 1.0;
    }
    else
    {
        const double half = angle * 0.5;
        const double s = sin(half) / angle;
        qx = lx * s;
        qy = ly * s;
        qz = lz * s;
        qw = cos(half);
    }
    decodeQuaternionToEuler(qx, qy, qz, qw, rotateOrder, rx, ry, rz);
}


//
// Description:
//      M_P0_QUATERNION_BACKEND_LAND (2026-05-10) — nlerp blend of
//      N unit quaternions weighted by RBF activations. Antipodal
//      correction picks the short-arc representative of each input
//      quat against the first one as the reference hemisphere; this
//      avoids the double-cover producing a near-zero average for
//      two inputs that geometrically agree but differ in sign. The
//      degenerate fallback (sum norm below 1e-9) returns the
//      reference quat verbatim — this only happens when all weights
//      collapse to zero or the inputs cancel exactly, both of which
//      already mean "no signal"; identity rotation is the safest
//      observable result.
//
//      nlerp (normalised linear interpolation) is the right blend
//      for RBF: associative, commutative, and gradient-continuous
//      under varying weights. SLERP would give constant angular
//      speed but loses gradient smoothness when the active pose set
//      changes; nlerp is what Maya-style rigging tools (Pose Space
//      Deformer, etc.) use in production.
//
void RBFtools::nlerpQuaternions(const std::vector<double> &qxs,
                                const std::vector<double> &qys,
                                const std::vector<double> &qzs,
                                const std::vector<double> &qws,
                                const std::vector<double> &weights,
                                double &outX, double &outY,
                                double &outZ, double &outW)
{
    const size_t n = qxs.size();
    if (n == 0)
    {
        outX = 0.0; outY = 0.0; outZ = 0.0; outW = 1.0;
        return;
    }
    const double rx = qxs[0], ry = qys[0], rz = qzs[0], rw = qws[0];
    double sumX = 0.0, sumY = 0.0, sumZ = 0.0, sumW = 0.0;
    for (size_t i = 0; i < n; ++i)
    {
        double qx = qxs[i], qy = qys[i], qz = qzs[i], qw = qws[i];
        // Short-arc selection against the reference.
        const double dot = qx * rx + qy * ry + qz * rz + qw * rw;
        if (dot < 0.0)
        {
            qx = -qx; qy = -qy; qz = -qz; qw = -qw;
        }
        const double w = (i < weights.size()) ? weights[i] : 0.0;
        sumX += w * qx;
        sumY += w * qy;
        sumZ += w * qz;
        sumW += w * qw;
    }
    const double norm = sqrt(sumX*sumX + sumY*sumY + sumZ*sumZ + sumW*sumW);
    if (norm < 1.0e-9)
    {
        outX = rx; outY = ry; outZ = rz; outW = rw;
        return;
    }
    const double inv = 1.0 / norm;
    outX = sumX * inv;
    outY = sumY * inv;
    outZ = sumZ * inv;
    outW = sumW * inv;
}


//
// Description:
//      M_P0_QUATERNION_BACKEND_LAND (2026-05-10) — replay the per-
//      pose distance + interpolateRbf loop without folding the
//      result into a per-channel weighted sum. getPoseWeights
//      already does exactly this on its way to the per-channel
//      accumulate; we cannot read those phi values back out because
//      the sum has been reduced. Re-running the loop keeps the math
//      identical (same dist / sigma / kernel inputs) so the per-pose
//      phi here matches what getPoseWeights used internally.
//
void RBFtools::computePerPosePhi(MDoubleArray &outPhi,
                                 BRMatrix poses,
                                 std::vector<double> norms,
                                 std::vector<double> driver,
                                 MIntArray poseModes,
                                 const std::vector<double> &widths,
                                 double widthFallback,
                                 int distType,
                                 int encoding,
                                 bool isMatrixMode,
                                 short kernelType)
{
    const unsigned int poseCount = poses.getRowSize();
    outPhi.setLength(poseCount);
    driver = normalizeVector(driver, norms);
    for (unsigned int i = 0; i < poseCount; ++i)
    {
        std::vector<double> dv = driver;
        std::vector<double> ps = poses.getRowVector(i);
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
        const double dist = getPoseDelta(dv, ps, distType, encoding,
                                          isMatrixMode);
        const double sigma_i =
            (i < widths.size() && widths[i] > 0.0)
                ? widths[i]
                : (widthFallback > 0.0 ? widthFallback : 1.0);
        outPhi.set(interpolateRbf(dist, sigma_i, kernelType), i);
    }
}


//
// Description:
//      M_P0_QUATERNION_BACKEND_LAND (2026-05-10) — overwrite the
//      Euler 3-blocks of weightsArray with quat-blended values.
//
//      For each contiguous 3-block (output[s..s+2]):
//        Quaternion (1): per-pose Euler → quat (encodeEulerToQuat),
//                        nlerp with per-pose phi (antipodal short-arc),
//                        decode back to Euler → overwrite [s..s+2].
//        ExpMap (3):     per-pose Euler → quat → ExpMap, weighted
//                        sum in ℝ³ (linear blend is the natural
//                        Lie-algebra interpolation), decode back to
//                        Euler → overwrite [s..s+2].
//
//      Channels not covered by a full 3-block (count % 3 != 0; tail
//      remainder) keep their legacy per-channel weighted sum. This
//      matches the assumption that Euler rotations are stored as
//      contiguous (rx, ry, rz) triples — which is how recall_pose
//      and add_pose write them.
//
//      rotateOrder is the node-level default for now; per-driven-source
//      rotateOrder schema (drivenInputRotateOrder) does not yet exist
//      and is deferred to v5.x.
//
void RBFtools::applyOutputEncodingBlend(MDoubleArray &weightsArray,
                                        const MDoubleArray &perPosePhi,
                                        const BRMatrix &poseVals,
                                        short outputEncoding,
                                        short rotateOrder,
                                        const std::vector<bool> &isQuatMember,
                                        bool &overlapWarning)
{
    // M_P0_OUTPUT_EXPMAP_FIX (2026-05-10): outputEncoding schema is
    // {0=Euler, 1=Quaternion, 2=ExpMap} (cpp:295-298) — node-level
    // outputEncoding has only three slots. The original ce136dd
    // dispatch used {1, 3} which mirrored inputEncoding's enum
    // ({0=Raw, 1=Quat, 2=BendRoll, 3=ExpMap, 4=SwingTwist}); under
    // that bug, picking ExpMap (value=2) silently fell through this
    // early return and degenerated to Raw weighted-sum semantics.
    // The fix here is purely renumbering: the math below for the
    // outputEncoding == 2 branch is the original ExpMap path,
    // unchanged.
    overlapWarning = false;
    if (outputEncoding != 1 && outputEncoding != 2) return;
    const unsigned int count = weightsArray.length();
    const unsigned int poseCount = perPosePhi.length();
    if (count == 0 || poseCount == 0) return;
    const unsigned int blocks = count / 3;
    if (blocks == 0) return;

    std::vector<double> wts(poseCount);
    for (unsigned int p = 0; p < poseCount; ++p)
        wts[p] = perPosePhi[p];

    // M_P0_QUAT_RBF_OVERLAP_DISCLOSE (2026-05-10): mask available
    // when the caller (compute()) passed isQuatMember sized to match
    // weightsArray. A B2 3-block whose [s..s+2] intersects any B1
    // member must be skipped — B1 (QWA Power Iteration on cpp:4310-
    // 4355) has already written its 4-tuple to those slots and a
    // subsequent nlerp / ExpMap weighted sum here would silently
    // overwrite that result. The skip is per-block (not per-element)
    // so partial-overlap blocks still preserve B1 fully; the entire
    // 3-block falls back to the legacy weighted-sum value that
    // getPoseWeights wrote (cpp:4300-4304), which for the Euler
    // remainder (column outside any quat group) is correct. See
    // §5.4.1 in docs/设计文档/RBFtools_v5_multi_quat_implementation.md.
    const bool haveMask = (isQuatMember.size() == count);

    for (unsigned int b = 0; b < blocks; ++b)
    {
        const unsigned int s = b * 3;

        // Skip B2 block whose [s..s+2] intersects a B1 quat member.
        if (haveMask)
        {
            bool overlaps = false;
            for (unsigned int k = 0; k < 3; ++k)
            {
                if (isQuatMember[s + k])
                {
                    overlaps = true;
                    break;
                }
            }
            if (overlaps)
            {
                overlapWarning = true;
                continue;
            }
        }

        if (outputEncoding == 1)
        {
            // Quaternion path: encode → nlerp → decode.
            std::vector<double> qxs(poseCount), qys(poseCount),
                                 qzs(poseCount), qws(poseCount);
            for (unsigned int p = 0; p < poseCount; ++p)
            {
                const double rx = poseVals(p, s + 0);
                const double ry = poseVals(p, s + 1);
                const double rz = poseVals(p, s + 2);
                double qx, qy, qz, qw;
                encodeEulerToQuaternion(rx, ry, rz, rotateOrder,
                                        qx, qy, qz, qw);
                qxs[p] = qx; qys[p] = qy; qzs[p] = qz; qws[p] = qw;
            }
            double oqx, oqy, oqz, oqw;
            nlerpQuaternions(qxs, qys, qzs, qws, wts,
                             oqx, oqy, oqz, oqw);
            double rx, ry, rz;
            decodeQuaternionToEuler(oqx, oqy, oqz, oqw, rotateOrder,
                                    rx, ry, rz);
            weightsArray.set(rx, s + 0);
            weightsArray.set(ry, s + 1);
            weightsArray.set(rz, s + 2);
        }
        else if (outputEncoding == 2)  // ExpMap (M_P0_OUTPUT_EXPMAP_FIX)
        {
            // ExpMap path: linear weighted sum in ℝ³.
            double sumLx = 0.0, sumLy = 0.0, sumLz = 0.0;
            for (unsigned int p = 0; p < poseCount; ++p)
            {
                const double rx = poseVals(p, s + 0);
                const double ry = poseVals(p, s + 1);
                const double rz = poseVals(p, s + 2);
                double qx, qy, qz, qw;
                encodeEulerToQuaternion(rx, ry, rz, rotateOrder,
                                        qx, qy, qz, qw);
                double lx, ly, lz;
                encodeQuaternionToExpMap(qx, qy, qz, qw, lx, ly, lz);
                const double w = wts[p];
                sumLx += w * lx;
                sumLy += w * ly;
                sumLz += w * lz;
            }
            double rx, ry, rz;
            decodeExpMapToEuler(sumLx, sumLy, sumLz, rotateOrder,
                                rx, ry, rz);
            weightsArray.set(rx, s + 0);
            weightsArray.set(ry, s + 1);
            weightsArray.set(rz, s + 2);
        }
    }
}


//
// Description:
//      Quaternion → log-map ∈ ℝ³ (v5 PART G.5). Canonicalises to the
//      q_w ≥ 0 hemisphere internally so callers do not need to worry
//      about the double cover. Uses a Taylor expansion for θ → 0 so
//      log(identity) returns (0, 0, 0) without a divide-by-zero.
//
//
// M2.1b — Swing-Twist decomposition. Implements v5 PART G.3. Axis is
// a principal axis (0=X, 1=Y, 2=Z); when the projection norm collapses
// below EPS0 the output degenerates to (identity swing, zero twist)
// per addendum §M2.1b option (B)①. The degenerate set is exactly
// {q : q_w = 0 AND q[axis] = 0} — measure-zero for unit quats, and
// geometrically corresponds to a pure-perpendicular swing by exactly
// π; callers should not expect round-trip recovery there.
//
void RBFtools::decomposeSwingTwist(double qx, double qy, double qz, double qw,
                                   unsigned twistAxis,
                                   double &sx, double &sy, double &sz,
                                   double &sw, double &twistAngle)
{
    double a = qx;
    if (twistAxis == 1)      a = qy;
    else if (twistAxis == 2) a = qz;

    const double normSq = qw * qw + a * a;
    const double EPS0 = 1.0e-12;
    if (normSq < EPS0)
    {
        // Degenerate: return (identity swing, zero twist).
        sx = 0.0; sy = 0.0; sz = 0.0; sw = 1.0;
        twistAngle = 0.0;
        return;
    }

    const double norm = sqrt(normSq);
    const double invNorm = 1.0 / norm;
    const double tw = qw * invNorm;
    // Twist quat xyz has only one non-zero component (along axis).
    double tx = 0.0, ty = 0.0, tz = 0.0;
    if (twistAxis == 0)      tx = a * invNorm;
    else if (twistAxis == 1) ty = a * invNorm;
    else                     tz = a * invNorm;

    // Swing = q · twist^{-1} = q · conj(twist). Hamilton product with
    // quats packed as (w, x, y, z).
    const double aw = qw, ax = qx, ay = qy, az = qz;
    const double bw =  tw, bx = -tx, by = -ty, bz = -tz;
    const double rw = aw*bw - ax*bx - ay*by - az*bz;
    const double rx = aw*bx + ax*bw + ay*bz - az*by;
    const double ry = aw*by - ax*bz + ay*bw + az*bx;
    const double rz = aw*bz + ax*by - ay*bx + az*bw;
    sx = rx; sy = ry; sz = rz; sw = rw;

    // Twist angle: τ = 2 * atan2(axis_comp_of_twist, twist_w). atan2 is
    // scale-invariant so we can use the unnormalised (a, qw) directly.
    twistAngle = 2.0 * atan2(a, qw);
}


//
// M_B24a1 — read companion metadata for driverList[d]. Defensive:
// returns default (weight=1.0, encoding=0) when driverSource[d] does
// not yet exist (legacy v5-pre-M_B24 nodes before Python lazy
// migration writes driverSource[]). a1 caller does NOT consume the
// returned values (forward-compat placeholder); read keeps the DG
// dirty edge alive for setAttr → compute() propagation.
//
void RBFtools::readDriverSourceMetadata(MDataBlock &data, unsigned d,
                                        double &weight, short &encoding)
{
    weight = 1.0;
    encoding = 0;
    MStatus status;
    MArrayDataHandle srcHandle = data.inputArrayValue(driverSource, &status);
    if (!status) return;
    status = srcHandle.jumpToArrayElement(d);
    if (!status) return;   // index does not exist — defensive fallback
    MDataHandle srcIdHandle = srcHandle.inputValue();
    weight   = srcIdHandle.child(driverSource_weight).asDouble();
    encoding = srcIdHandle.child(driverSource_encoding).asShort();
}


//
// M2.1b — BendRoll encoding. Stereographic projection of the swing
// quaternion to ℝ² in the plane perpendicular to the twist axis, plus
// the scalar twist. Layout: (roll, bendH, bendV) per group.
//
// Denominator is clamped to max(1 + s_w, ε) with ε = 1e-4 to keep the
// value finite near the stereographic pole (s_w → -1, swing angle → 2π).
// For typical rigs with swing angle < π/2, s_w > 0.7 and the clamp is
// unreachable. Test T14.a/b/c anchor the numerical envelope; the
// code contains no boundary branch — keep the hot path clean.
//
void RBFtools::encodeBendRoll(double rx, double ry, double rz,
                              short rotateOrder, unsigned twistAxis,
                              double &outRoll, double &outBendH, double &outBendV)
{
    double qx, qy, qz, qw;
    encodeEulerToQuaternion(rx, ry, rz, rotateOrder, qx, qy, qz, qw);

    double sx, sy, sz, sw, twistAngle;
    decomposeSwingTwist(qx, qy, qz, qw, twistAxis, sx, sy, sz, sw, twistAngle);

    // Pick the (h, v) axes orthogonal to the twist axis.
    //   X axis → (h=Y, v=Z): s_h = sy, s_v = sz
    //   Y axis → (h=Z, v=X): s_h = sz, s_v = sx
    //   Z axis → (h=X, v=Y): s_h = sx, s_v = sy
    double sh = sy, sv = sz;
    if (twistAxis == 1)      { sh = sz; sv = sx; }
    else if (twistAxis == 2) { sh = sx; sv = sy; }

    const double EPS = 1.0e-4;
    double swClamped = sw;
    if (swClamped < -1.0 + EPS) swClamped = -1.0 + EPS;
    const double denom = 1.0 + swClamped;  // ∈ [EPS, 2]

    outRoll  = twistAngle;
    outBendH = 2.0 * sh / denom;
    outBendV = 2.0 * sv / denom;
}


//
// M2.1b — SwingTwist encoding. Layout (sx, sy, sz, sw, twist) per
// group. The first four components form a standard unit quaternion.
//
void RBFtools::encodeSwingTwist(double rx, double ry, double rz,
                                short rotateOrder, unsigned twistAxis,
                                double &sx, double &sy, double &sz,
                                double &sw, double &twist)
{
    double qx, qy, qz, qw;
    encodeEulerToQuaternion(rx, ry, rz, rotateOrder, qx, qy, qz, qw);
    decomposeSwingTwist(qx, qy, qz, qw, twistAxis, sx, sy, sz, sw, twist);
}


//
// M2.1b — per-5-block composite distance for SwingTwist-encoded
// driver vectors. Per block:
//     d² = (1 - |q_swing1·q_swing2|)² + twistWrap(τ1, τ2)²
// Aggregated L2 across blocks. w_twist = 1.0 default (addendum
// §M2.1b option (D)①): column-wise L2 normalisation upstream
// balances the swing (dimensionless) vs twist (radians) scales.
//
//
// M2.2 — Power Iteration for the maximum-eigenvalue eigenvector of a
// 4x4 symmetric PSD matrix. M is row-major (M[i*4 + j]). The iteration
// seeds at (0, 0, 0, 1) — identity quaternion — because most
// QWA-relevant queries already cluster near rest orientation; a random
// seed would waste iterations drifting off axis.
//
// Convergence: |q_{k+1} - q_k| < tol  OR  |q_{k+1} . q_k| > 1 - tol^2.
// The dot-product check catches the sign-ambiguity oscillation that
// pure subtraction can miss when the eigenvector keeps flipping ±.
//
// Returns true on convergence. On return, outQ is unit-length and
// canonicalised to the q_w >= 0 hemisphere (v5 addendum §M2.2 (G),
// matching M2.1b SwingTwist sign convention).
//
// M4.5 will swap this for Eigen::SelfAdjointEigenSolver<Matrix4d>
// (see addendum §M2.2.M4.5-FORWARD).
//
bool RBFtools::powerIterationMaxEigenvec4x4(const double M[16],
                                            double outQ[4],
                                            int maxIter,
                                            double tol)
{
    // Local closure for a single Power Iteration run from a given seed.
    // Captures by-reference M + tol + maxIter. Mirrors the Python
    // reference's inner _run helper.
    auto runFromSeed = [&](const double seed[4], double qOut[4]) -> bool
    {
        double q[4] = {seed[0], seed[1], seed[2], seed[3]};
        const double n0 = sqrt(q[0]*q[0] + q[1]*q[1] + q[2]*q[2] + q[3]*q[3]);
        if (n0 < 1.0e-30) return false;
        q[0] /= n0; q[1] /= n0; q[2] /= n0; q[3] /= n0;

        for (int k = 0; k < maxIter; ++k)
        {
            double qp[4] = {0, 0, 0, 0};
            for (int i = 0; i < 4; ++i)
            {
                qp[i] = M[i*4 + 0] * q[0]
                      + M[i*4 + 1] * q[1]
                      + M[i*4 + 2] * q[2]
                      + M[i*4 + 3] * q[3];
            }
            const double norm = sqrt(qp[0]*qp[0] + qp[1]*qp[1]
                                   + qp[2]*qp[2] + qp[3]*qp[3]);
            if (norm < 1.0e-30) return false;
            qp[0] /= norm; qp[1] /= norm; qp[2] /= norm; qp[3] /= norm;

            const double dx = qp[0] - q[0], dy = qp[1] - q[1];
            const double dz = qp[2] - q[2], dw = qp[3] - q[3];
            const double delta = sqrt(dx*dx + dy*dy + dz*dz + dw*dw);
            const double dot = qp[0]*q[0] + qp[1]*q[1] + qp[2]*q[2] + qp[3]*q[3];

            q[0] = qp[0]; q[1] = qp[1]; q[2] = qp[2]; q[3] = qp[3];
            if (delta < tol || fabs(dot) > 1.0 - tol * tol)
            {
                qOut[0] = q[0]; qOut[1] = q[1];
                qOut[2] = q[2]; qOut[3] = q[3];
                return true;
            }
        }
        // Not converged within maxIter — return last iterate.
        qOut[0] = q[0]; qOut[1] = q[1]; qOut[2] = q[2]; qOut[3] = q[3];
        return false;
    };

    // Primary seed: identity quaternion (user design (F)①, biased
    // toward the rest-pose-typical case where QWA clusters near
    // (0,0,0,1) and convergence is fast).
    double result[4] = {0.0, 0.0, 0.0, 1.0};
    const double seed1[4] = {0.0, 0.0, 0.0, 1.0};
    bool converged = runFromSeed(seed1, result);

    if (!converged)
    {
        // Secondary seed: M · (1,1,1,1), which is guaranteed non-zero
        // for any non-trivial M (unless (1,1,1,1) lies in the null
        // space — extremely unlikely for practical QWA covariances).
        // Fallback to (½, ½, ½, ½) if that projection collapses.
        double seed2[4];
        seed2[0] = M[ 0] + M[ 1] + M[ 2] + M[ 3];
        seed2[1] = M[ 4] + M[ 5] + M[ 6] + M[ 7];
        seed2[2] = M[ 8] + M[ 9] + M[10] + M[11];
        seed2[3] = M[12] + M[13] + M[14] + M[15];
        const double n2 = sqrt(seed2[0]*seed2[0] + seed2[1]*seed2[1]
                             + seed2[2]*seed2[2] + seed2[3]*seed2[3]);
        if (n2 < 1.0e-30)
        {
            seed2[0] = 0.5; seed2[1] = 0.5; seed2[2] = 0.5; seed2[3] = 0.5;
        }
        converged = runFromSeed(seed2, result);
    }

    if (result[3] < 0.0)
    {
        result[0] = -result[0]; result[1] = -result[1];
        result[2] = -result[2]; result[3] = -result[3];
    }
    outQ[0] = result[0]; outQ[1] = result[1];
    outQ[2] = result[2]; outQ[3] = result[3];
    return converged;
}


//
// M2.2 — PSD-mass check + Power Iteration dispatch. Identity-quat
// fallback for (a) zero-mass matrices and (b) non-convergent iteration.
// Caller translates non-OK result codes into a once-per-rig warning
// via qwaDegenerateWarningIssued (addendum §M2.2 (E) + §M2.2 (Q6)).
//
RBFtools::QWAResult RBFtools::computeQWAForGroup(const double M[16],
                                                 double outQ[4])
{
    const double EPS_M = 1.0e-12;
    const double trace = M[0] + M[5] + M[10] + M[15];
    if (trace < EPS_M)
    {
        outQ[0] = 0.0; outQ[1] = 0.0; outQ[2] = 0.0; outQ[3] = 1.0;
        return QWA_ZERO_MASS;
    }

    const bool ok = powerIterationMaxEigenvec4x4(M, outQ);
    if (!ok) return QWA_NO_CONVERGE;
    return QWA_OK;
}


//
// M2.2 — validate raw user-provided quaternion group starts. Invalid
// entries (out-of-range, overlap, or colliding with an outputIsScale
// member on any of the four group slots) are dropped; the returned
// validStarts reflects the filtered set. `isQuatMember` is the
// single-source-of-truth mask used by the M1.2 subtract / M1.4 yCols
// skip / M1.2 add-back / QWA-overwrite sites per addendum §M2.2.Q9 +
// §M2.2.MASK-INDEX.
//
// `anyInvalid` flips to true iff at least one entry was dropped, so
// the caller can fire the once-per-rig config warning.
//
void RBFtools::resolveQuaternionGroups(const std::vector<int> &rawStarts,
                                       unsigned outputCount,
                                       const std::vector<bool> &outputIsScaleArr,
                                       std::vector<int> &validStarts,
                                       std::vector<bool> &isQuatMember,
                                       bool &anyInvalid)
{
    validStarts.clear();
    isQuatMember.assign(outputCount, false);
    anyInvalid = false;

    for (size_t r = 0; r < rawStarts.size(); ++r)
    {
        const int s = rawStarts[r];

        // Out-of-range.
        if (s < 0 || (unsigned)(s + 4) > outputCount)
        {
            anyInvalid = true;
            continue;
        }

        // Overlap with an already-accepted group.
        bool overlap = false;
        for (int k = 0; k < 4; ++k)
        {
            if (isQuatMember[(unsigned)(s + k)])
            {
                overlap = true;
                break;
            }
        }
        if (overlap)
        {
            anyInvalid = true;
            continue;
        }

        // Scale-channel conflict (addendum §M2.2 (D)①): if ANY of the
        // four slots is marked outputIsScale=true, reject the whole
        // group — both semantics are disabled there and the user must
        // explicitly resolve.
        bool scaleConflict = false;
        for (int k = 0; k < 4; ++k)
        {
            const unsigned idx = (unsigned)(s + k);
            if (idx < outputIsScaleArr.size() && outputIsScaleArr[idx])
            {
                scaleConflict = true;
                break;
            }
        }
        if (scaleConflict)
        {
            anyInvalid = true;
            continue;
        }

        // Accepted.
        for (int k = 0; k < 4; ++k)
            isQuatMember[(unsigned)(s + k)] = true;
        validStarts.push_back(s);
    }
}


double RBFtools::getSwingTwistBlockDistance(const std::vector<double> &v1,
                                            const std::vector<double> &v2)
{
    double sumSq = 0.0;
    const size_t blocks = v1.size() / 5;
    for (size_t k = 0; k < blocks; ++k)
    {
        const size_t base = k * 5;
        double dot = v1[base+0]*v2[base+0] + v1[base+1]*v2[base+1]
                   + v1[base+2]*v2[base+2] + v1[base+3]*v2[base+3];
        const double dSwing = 1.0 - fabs(dot);
        const double dTwist = twistWrap(v1[base+4], v2[base+4]);
        sumSq += dSwing * dSwing + dTwist * dTwist;
    }
    return sqrt(sumSq);
}


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
// Commit 0 (M_PER_POSE_SIGMA): vectorised overload.
//   widths        — per-pose σ (length == count expected). Empty
//                   vector triggers scalar-fallback path.
//   widthFallback — used when widths[i]/[j] is non-positive (sparse
//                   array hole) or when widths.empty().
// Math: K[i,j] uses σ_pair = (σ_i + σ_j) / 2 (arithmetic mean).
// Symmetry preserved => Cholesky path of M1.4 stays usable. Setting
// widths[*] to a constant c reproduces the scalar overload bit-for-
// bit (regression guard for legacy nodes during migration).
//
void RBFtools::getActivations(BRMatrix &mat,
                              const std::vector<double> &widths,
                              double widthFallback,
                              short kernelType)
{
    unsigned count = mat.getRowSize();

    if (widths.empty())
    {
        // Backcompat path — identical to scalar overload.
        getActivations(mat, widthFallback, kernelType);
        return;
    }

    auto pickSigma = [&](unsigned k) -> double
    {
        if (k < widths.size() && widths[k] > 0.0)
            return widths[k];
        return widthFallback > 0.0 ? widthFallback : 1.0;
    };

    unsigned int i, j;
    for (i = 0; i < count; i ++)
    {
        double sigma_i = pickSigma(i);
        for (j = 0; j < count; j ++)
        {
            double sigma_j   = pickSigma(j);
            double sigmaPair = 0.5 * (sigma_i + sigma_j);
            mat(i, j) = interpolateRbf(mat(i, j), sigmaPair, kernelType);
        }
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
// M_P0_KERNEL_ALGO_AUDIT (2026-05-10): kernel φ(d, w) catalog.
// Document the σ (width) semantics and PSD properties of each
// kernel so a reader does not need to reverse-engineer them
// from the math alone. Every kernel here is paired with the
// per-block / Riemannian distance metric chosen by getPoseDelta;
// the (kernel × distance) combination defines the K matrix shape.
//
// All formulas use d = pre-computed pairwise distance from
// getPoseDelta. The width parameter w is the user's "Radius"
// or per-pose σ (commit M_PER_POSE_SIGMA).
//
//   Type 0 — Linear:   φ(d) = d                       (φ(0) = 0)
//     PSD: NO. K[i,i] = 0 always; needs λ > 0 to solve.
//     Width: IGNORED (mathematical definition has no width).
//     UX note: the radius slider has no effect on Linear.
//
//   Type 1 — Gaussian 1:  φ(d) = exp(-d / w²)        (φ(0) = 1)
//     PSD: YES (positive definite kernel).
//     Width: w² is the spatial decay rate; LARGER w → smoother.
//     NOTE: this is NOT the canonical Gaussian (which has d²
//     in the exponent). It is an exponential-decay-of-distance
//     kernel preserved for backcompat. Use Gaussian 2 for true
//     bell-shape decay.
//
//   Type 2 — Gaussian 2:  φ(d) = exp(-d² / w²)       (φ(0) = 1)
//     PSD: YES (canonical Gaussian).
//     Width: w is the half-width at φ=e^-1 ≈ 0.37; LARGER w →
//     smoother. The internal 0.707 multiplier folds 1/√2 so the
//     exponent denominator becomes w² (not 2·w²).
//
//   Type 3 — Thin Plate:  φ(r) = r²·log(r), r=d/w    (φ(0) = 0)
//     PSD: conditionally negative-definite (works with λ > 0).
//     Width: w normalizes d before the TPS evaluation.
//     M_P0_KERNEL_ALGO_AUDIT: r ≤ 0 (including float-noise
//     negatives) returns 0.0 to preserve K's PSD structure.
//
//   Type 4 — Multi-Quadric:  φ(d) = √(d² + w²)      (φ(0) = w)
//     PSD: conditionally positive-definite.
//     Width: w is the chord shift; LARGER w → smoother.
//     NAME NOTE: schema labels this "Multi-Quadratic Biharmonic"
//     for backcompat; the formula is the standard Multi-Quadric
//     (MQ), not biharmonic MQ ((d²+w²)^1.5). The label is
//     historical and not changed to preserve existing rig schema.
//
//   Type 5 — Inverse Multi-Quadric:  φ(d) = 1/√(d² + w²)
//     PSD: positive definite.                       (φ(0) = 1/w)
//     Width: w is the chord shift; LARGER w → smoother.
//
// Auto-adaptive λ retry (M_P0_AUTO_ADAPTIVE_LAMBDA) handles all
// of the above PSD edge cases — kernels whose K is non-SPD at
// the user's λ get auto-bumped λ until Cholesky / GE succeed,
// so kernel choice no longer dictates "must set λ > 0 manually".
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
    // M_P0_KERNEL_SWITCH_ROLLBACK_1 (2026-05-11): TPS r<=0 reverted to
    // oracle (X:\RBFtools cpp:3806-3807) behavior `result = value`. The
    // M_P0_KERNEL_ALGO_AUDIT (2600d3e) change `result = 0.0` was intended
    // to defend K's PSD against normalizeColumns floating-point noise,
    // but user observation (kernel switch + manual Apply still drifts
    // across ALL kernels, not just TPS) combined with 3-way diff
    // (weightDriver omits TPS; Oracle returns value) shows the 0.0
    // defense was either unnecessary in oracle's normalize path, or
    // absorbed by GE elimination. See docs/排查/M_P0_KERNEL_SWITCH_ROLLBACK_index.md
    // §3.c for full analysis. Oracle commit anchor: e249ec0
    // (= 156af4c~1, see §0.5).
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
// M_P0_RBF_POLYNOMIAL_AUGMENTATION (2026-05-11): polynomial dimension
// for the given kernel. CPD kernels need polynomial augmentation of
// degree (m - 1) where m is the kernel's conditional-positive-definite
// order. Gaussian variants are strictly PD and need no augmentation.
//
// Kernel id (per cpp:212-218 schema):
//   0 = Linear                            CPD m = 1 → polyDim = 1
//   1 = Gaussian 1   (strictly PD)        polyDim = 0
//   2 = Gaussian 2   (strictly PD)        polyDim = 0
//   3 = Thin Plate                        CPD m = 2 → polyDim = 1 + d
//   4 = Multi-Quadric Biharmonic (MQB)    CPD m = 1 → polyDim = 1
//   5 = Inverse Multi-Quadric Biharmonic
//                                  (IMQB) CPD m = 1 → polyDim = 1
//
// User λ-sweep + visual repro confirmed kernels 0/3/4/5 all need
// augmentation under dense / redundant pose sets — the uniform 1e-5
// (8e7a6d3) and tiered 1e-3 (4a3cae4) ceil attempts were band-aids
// over a math defect. Polynomial augmentation is the mathematically
// correct treatment of CPD kernels per Wendland 2004 §10, Schaback
// 1995, and Wahba 1990.
//
int RBFtools::getPolynomialDim(short kernelType, int driverDim)
{
    if (kernelType == 1 || kernelType == 2) return 0;   // Gaussian
    if (kernelType == 3) return 1 + driverDim;          // TPS
    return 1;                                           // Linear / MQB / IMQB
}


//
// M_P0_RBF_POLYNOMIAL_AUGMENTATION (2026-05-11): evaluate the
// polynomial basis at the given (normalised) input. Output is
//   polyDim == 0   : empty
//   polyDim == 1   : [1.0]
//   polyDim > 1    : [1.0, vec[0], vec[1], ..., vec[polyDim - 2]]
//
// The same basis is used for (a) filling the P block of the augmented
// training matrix at each pose row, and (b) the polynomial term of
// inference at the current driver vector. Coordinate frame match
// (both normalised) is the caller's responsibility.
//
void RBFtools::polyBasis(const std::vector<double> &vec, int polyDim,
                         std::vector<double> &out)
{
    out.assign((size_t)(polyDim > 0 ? polyDim : 0), 0.0);
    if (polyDim == 0) return;
    out[0] = 1.0;
    if (polyDim == 1) return;
    const int linearTerms = polyDim - 1;
    for (int i = 0; i < linearTerms && (size_t)i < vec.size(); ++i)
        out[1 + i] = vec[i];
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
                                  const std::vector<double> &widths,
                                  double widthFallback,
                                  int distType,
                                  int encoding,
                                  bool isMatrixMode,
                                  short kernelType,
                                  const BRMatrix &poseVals,
                                  const std::vector<int> &quatGroupStarts,
                                  const std::vector<bool> &isQuatMember,
                                  bool &qwaAnyClippedOut,
                                  bool &qwaAnyDegenerateOut,
                                  const BRMatrix &polyMatArg,
                                  int polyDim)
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

    // M2.2: per-group 4x4 covariance accumulators. Only allocated when
    // the user has declared at least one quaternion group — rig default
    // (empty) skips this allocation entirely.
    const size_t gCount = quatGroupStarts.size();
    std::vector< std::vector<double> > Mmats(gCount, std::vector<double>(16, 0.0));
    qwaAnyClippedOut = false;
    qwaAnyDegenerateOut = false;
    const bool haveMask = (isQuatMember.size() == valueCount);

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
        // Commit 0b (M_PER_POSE_SIGMA): per-pose σ at inference. Must
        // match the σ used to BUILD K[*, i] during training so the
        // basis function is identical on both sides — otherwise the
        // sum_j w_j · φ(||x - c_j||, σ_j) loses the partition-of-unity
        // property at pose centres.
        double sigma_i =
            (i < widths.size() && widths[i] > 0.0)
                ? widths[i]
                : (widthFallback > 0.0 ? widthFallback : 1.0);
        const double phi = interpolateRbf(dist, sigma_i, kernelType);

        // Scalar accumulate. Dims flagged as quat-group members take
        // their value from the QWA post-loop instead; skip their scalar
        // sum entirely to avoid double-contribution.
        for (j = 0; j < valueCount; j ++)
        {
            if (haveMask && isQuatMember[j]) continue;
            out[j] += weightMat(i, j) * phi;
        }

        // M2.2 QWA accumulate. Negative kernel activations break the
        // PSD property of M (addendum §M2.2 (Q8)); clamp to 0 and raise
        // the once-per-rig warning flag on first clip. Standard (scalar)
        // path is unaffected — allowNegative semantics stay as-is.
        if (gCount > 0)
        {
            double phiQwa = phi;
            if (phiQwa < 0.0)
            {
                phiQwa = 0.0;
                qwaAnyClippedOut = true;
            }
            if (phiQwa > 0.0)
            {
                for (size_t g = 0; g < gCount; ++g)
                {
                    const int s = quatGroupStarts[g];
                    const double q0_ = poseVals(i, (unsigned)(s + 0));
                    const double q1_ = poseVals(i, (unsigned)(s + 1));
                    const double q2_ = poseVals(i, (unsigned)(s + 2));
                    const double q3_ = poseVals(i, (unsigned)(s + 3));
                    double *Mg = Mmats[g].data();
                    const double comp[4] = {q0_, q1_, q2_, q3_};
                    for (int a = 0; a < 4; ++a)
                    {
                        const double pa = phiQwa * comp[a];
                        for (int b = 0; b < 4; ++b)
                            Mg[a*4 + b] += pa * comp[b];
                    }
                }
            }
        }
    }

    // M_P0_RBF_POLYNOMIAL_AUGMENTATION (2026-05-11): polynomial term
    // of CPD-kernel inference. Adds Σ_k polyMat(k, j) * p_k(driver)
    // to each scalar output channel. polyDim == 0 (Gaussian) skips
    // this loop entirely — bit-identical to the pre-augmentation
    // single-kernel path.
    //
    // Coordinate frame match: the training-side P matrix was filled
    // from matPoses rows, which are post-normalizeColumns (cpp:2942
    // in getPoseData). Inference-side polyBasis is evaluated on the
    // normalised driver (line above this comment block: ``driver =
    // normalizeVector(driver, norms);``). Both sides share the same
    // coordinate frame so the augmented system's [w; a] solution
    // generalises correctly to the inference call.
    //
    // Quat-group dimensions (isQuatMember[j] == true) skip the
    // polynomial accumulate for the same reason they skipped the
    // RBF accumulate above — those dimensions are owned by the QWA
    // post-loop below and must not be double-contributed.
    if (polyDim > 0)
    {
        std::vector<double> p_x;
        polyBasis(driver, polyDim, p_x);
        for (j = 0; j < valueCount; ++j)
        {
            if (haveMask && isQuatMember[j]) continue;
            double polySum = 0.0;
            for (int k = 0; k < polyDim; ++k)
                polySum += polyMatArg((unsigned)k, j) * p_x[(size_t)k];
            out[j] += polySum;
        }
    }

    // M2.2: resolve each group's QWA. OK / ZERO_MASS / NO_CONVERGE
    // all translate to a valid write (OK = eigenvector; others =
    // identity). Non-OK results collapse into a single caller-side
    // warning flag — per-group verbosity is not helpful for rigger
    // debugging and could flood the log.
    for (size_t g = 0; g < gCount; ++g)
    {
        const int s = quatGroupStarts[g];
        double qOut[4];
        const QWAResult r = computeQWAForGroup(Mmats[g].data(), qOut);
        if (r != QWA_OK) qwaAnyDegenerateOut = true;
        out[(unsigned)(s + 0)] = qOut[0];
        out[(unsigned)(s + 1)] = qOut[1];
        out[(unsigned)(s + 2)] = qOut[2];
        out[(unsigned)(s + 3)] = qOut[3];
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

    // M_B24a1 + M_P0_QUATERNION_BACKEND_LAND (2026-05-10): the
    // actual outputEncoding inverse transform now lives in
    // compute() (the per-channel weighted sum is rebuilt via
    // applyOutputEncodingBlend before this method ever sees
    // weightsArray). The thread_local sink (加固 K.1-2) is
    // retained here purely to keep the legacy DG dirty edge proof
    // alive — MSVC O2 dead-read elimination would otherwise drop
    // the plug read in compute() too if both sites collapsed to
    // unused. The sink does no functional work; the real read +
    // dispatch is the one in compute().
    MPlug outEncPlug(thisNode, RBFtools::outputEncoding);
    short outEncVal = outEncPlug.asShort();
    if (outEncVal != 0) {
        // Forward-compat placeholder retained for DG-edge protection.
        static thread_local short s_outEncSink = 0;
        s_outEncSink = outEncVal;
        (void)s_outEncSink;
    }

    // Commit 0 (M_BASE_POSE): read basePoseValue array into a flat
    // std::vector<double> indexed by output channel. Empty array =>
    // all zeros => bit-identical legacy behaviour. Out-of-range
    // channels (basePoseValue shorter than count) treat as 0.0.
    std::vector<double> baseVals(count, 0.0);
    if (!inactive)
    {
        MArrayDataHandle bpvHandle =
            data.inputArrayValue(RBFtools::basePoseValue);
        unsigned bpvCount = bpvHandle.elementCount();
        for (unsigned k = 0; k < bpvCount; k ++)
        {
            unsigned idx = bpvHandle.elementIndex();
            if (idx < count)
                baseVals[idx] =
                    bpvHandle.inputValue().asDouble();
            if (k + 1 < bpvCount) bpvHandle.next();
        }
    }

    MArrayDataHandle outputHandle = data.outputArrayValue(output);
    MArrayDataBuilder outputBuilder(&data, output, count);
    for (i = 0; i < count; i ++)
    {
        MDataHandle outputIdHandle = outputBuilder.addElement((unsigned)ids[i]);
        if (!inactive)
            outputIdHandle.setDouble(weightsArray[i] + baseVals[i]);
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
