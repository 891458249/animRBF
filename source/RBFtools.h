// ---------------------------------------------------------------------
//
//  RBFtools.h
//
//  Created by ingo on 9/27/13.
//  Copyright (c) 2026 Drafter. All rights reserved.
//
// ---------------------------------------------------------------------

#ifndef __RBFtools__RBFtools__
#define __RBFtools__RBFtools__

#include <iostream>

#include <maya/MGlobal.h>
#include <maya/MPxLocatorNode.h>
#include <maya/MTypeId.h>

#include <maya/MDataBlock.h>
#include <maya/MDataHandle.h>

#include <maya/MFnCompoundAttribute.h>
#include <maya/MFnEnumAttribute.h>
#include <maya/MFnNumericAttribute.h>
#include <maya/MFnMatrixAttribute.h>
#include <maya/MFnMessageAttribute.h>
#include <maya/MFnTypedAttribute.h>
#include <maya/MRampAttribute.h>

#include <maya/MArrayDataBuilder.h>
#include <maya/MColor.h>
#include <maya/MDagPath.h>
#include <maya/MFloatArray.h>
#include <maya/MFnDependencyNode.h>
#include <maya/MFnIkJoint.h>
#include <maya/MMatrix.h>
#include <maya/MPlugArray.h>
#include <maya/MPoint.h>
#include <maya/MQuaternion.h>
#include <maya/MString.h>
#include <maya/MStringArray.h>
#include <maya/MTransformationMatrix.h>
#include <maya/MVectorArray.h>

#if MAYA_API_VERSION < 202400
#include <maya/MDrawContext.h>
#endif
#include <maya/MDrawRegistry.h>
#include <maya/MEventMessage.h>
#include "maya/MFnCamera.h"
#include "maya/MHWGeometryUtilities.h"
#include <maya/MPxDrawOverride.h>
#include <maya/MUserData.h>

#include "BRMatrix.h"
#include <vector>

class RBFtools : public MPxLocatorNode
{
public:
    RBFtools();
    virtual ~RBFtools();

    static void* creator();

    virtual bool isBounded() const;

    static MStatus initialize();

    virtual void postConstructor();

    virtual MStatus postConstructor_init_curveRamp(MObject &nodeObj,
                                                   MObject &rampObj,
                                                   int index,
                                                   float position,
                                                   float value,
                                                   int interpolation);

    virtual MStatus compute(const MPlug &plug, MDataBlock &data);

    virtual MStatus getPoseVectors(MDataBlock &data,
                                   std::vector<double> &driver,
                                   unsigned &poseCount,
                                   BRMatrix &poseData,
                                   BRMatrix &poseValues,
                                   MIntArray &poseModes,
                                   unsigned twistAxis,
                                   bool invert,
                                   unsigned driverId,
                                   std::vector<double>&normFactors);
    virtual MStatus getPoseData(MDataBlock &data,
                                std::vector<double> &driver,
                                unsigned &poseCount,
                                unsigned &solveCount,
                                BRMatrix &poseData,
                                BRMatrix &poseValues,
                                MIntArray &poseModes,
                                std::vector<double>&normFactors,
                                int inputEncoding,                 // M2.1a
                                const std::vector<short>& rotateOrders,  // M2.1a
                                unsigned &effectiveInDim);         // M2.1a output

    virtual double getRadiusValue();
    
    static double getTwistAngle(MQuaternion q, unsigned int axis);
    // M2.1a: getDistances + getPoseDelta now carry (encoding, isMatrixMode)
    // so the kernel-matrix build and inference-time delta use the same
    // encoding-aware distance dispatch. Legacy (encoding=0 Raw, isMatrixMode
    // decided by caller) still reproduces v4 behaviour bit-for-bit.
    static BRMatrix getDistances(BRMatrix poseMat, int distType,
                                 int encoding, bool isMatrixMode);
    static double getPoseDelta(std::vector<double> vec1, std::vector<double> vec2,
                               int distType, int encoding, bool isMatrixMode);
    static double getRadius(std::vector<double> vec1, std::vector<double> vec2);
    static double getAngle(std::vector<double> vec1, std::vector<double> vec2);
    static double twistWrap(double tau1, double tau2);
    static double getMatrixModeLinearDistance(const std::vector<double> &vec1,
                                              const std::vector<double> &vec2);
    // M2.1a: Bug 2 fix — Matrix mode with distanceType==Angle now actually
    // uses arc angle on the xyz swing block (plus twist wrap), instead of
    // being silently forced to Euclidean.
    static double getMatrixModeAngleDistance(const std::vector<double> &vec1,
                                             const std::vector<double> &vec2);
    static double getQuatDistance(const std::vector<double> &q1,
                                  const std::vector<double> &q2);
    // M2.1a: per-4-block quaternion distance for Generic mode with
    // inputEncoding=Quaternion. Returns L2 aggregation over all blocks of
    // per-block (1 - |q1·q2|).
    static double getQuatBlockDistance(const std::vector<double> &v1,
                                       const std::vector<double> &v2);
    // M2.1a: Euler → Quaternion. rotateOrder matches Maya's native
    // rotateOrder enum {XYZ=0, YZX=1, ZXY=2, XZY=3, YXZ=4, ZYX=5}.
    // Returns (qx, qy, qz, qw) in the order expected by getQuatDistance.
    static void encodeEulerToQuaternion(double rx, double ry, double rz,
                                        short rotateOrder,
                                        double &qx, double &qy, double &qz,
                                        double &qw);
    // M2.1a: quaternion → log-map ∈ ℝ³ with Taylor fallback for θ → 0.
    // Takes the q_w ≥ 0 hemisphere representative internally to avoid the
    // double-cover discontinuity; caller does not need to canonicalize.
    static void encodeQuaternionToExpMap(double qx, double qy, double qz, double qw,
                                         double &lx, double &ly, double &lz);
    static void getActivations(BRMatrix &mat, double width, short kernelType);
    static double interpolateRbf(double value, double width, short kernelType);
    static std::vector<double> normalizeVector(std::vector<double> vec, std::vector<double> factors);
    static void getPoseWeights(MDoubleArray &out,
                               BRMatrix poses,
                               std::vector<double> norms,
                               std::vector<double> driver,
                               MIntArray poseModes,
                               BRMatrix weightMat,
                               double dist,
                               int distType,
                               int encoding,           // M2.1a
                               bool isMatrixMode,      // M2.1a
                               short kernelType);

    virtual double interpolateWeight(double value, int type);
    virtual double blendCurveWeight(double value);
    virtual void setOutputValues(MDoubleArray weightsArray, MDataBlock data, bool inactive);

    void showArray(MDoubleArray array, MString name);
    static void showArray(std::vector<double> array, MString name);
    void showVector(MVector vector, MString name);
    void showMatrix(MMatrix mat, MString name);

    static MTypeId id;

    static MString drawDbClassification;
    static MString drawRegistrantId;

public:
    // vector angle attributes (sorted)
    static MObject active;
    static MObject angle;
    static MObject centerAngle;
    static MObject color;
    static MObject colorR;
    static MObject colorG;
    static MObject colorB;
    static MObject curveRamp;
    static MObject direction;
    static MObject drawCenter;
    static MObject drawCone;
    static MObject drawWeight;
    static MObject driverMatrix;
    static MObject grow;
    static MObject interpolate;
    static MObject invert;
    static MObject outWeight;
    static MObject readerMatrix;
    static MObject size;
    static MObject translateMax;
    static MObject translateMin;
    static MObject twist;
    static MObject twistAngle;
    static MObject useRotate;
    static MObject useTranslate;

    // rbf attributes (sorted)
    static MObject allowNegative;
    static MObject baseValue;
    static MObject clampEnabled;
    static MObject clampInflation;
    static MObject outputIsScale;
    static MObject radius;
    static MObject regularization;
    static MObject solverMethod;
    static MObject inputEncoding;
    static MObject driverInputRotateOrder;
    static MObject colorDriver;
    static MObject colorDriverR;
    static MObject colorDriverG;
    static MObject colorDriverB;
    static MObject controlNode;
    static MObject distanceType;
    static MObject drawDriver;
    static MObject drawIndices;
    static MObject drawOrigin;
    static MObject drawPoses;
    static MObject drawTwist;
    static MObject driverIndex;
    static MObject driverInput;
    static MObject driverList;
    static MObject evaluate;
    static MObject exposeData;
    static MObject indexDist;
    static MObject input;
    static MObject kernel;
    static MObject mean;
    static MObject opposite;
    static MObject output;
    static MObject pose;
    static MObject poseAttributes;
    static MObject poseDrawTwist;
    static MObject poseDrawVector;
    static MObject poseInput;
    static MObject poseLength;
    static MObject poseMatrix;
    static MObject poseMode;
    static MObject poseParentMatrix;
    static MObject poseRotateOrder;
    static MObject poses;
    static MObject poseValue;
    static MObject poseValues;
    static MObject rbfMode;
    static MObject restInput;
    static MObject scale;
    static MObject type;
    static MObject radiusType;
    static MObject twistAxis;
    static MObject useInterpolation;
    static MObject variance;

    MRampAttribute curveAttr;

private:
    // vector angle
    double angleVal;
    double centerAngleVal;
    short dirVal;
    bool invVal;

    // rbf
    short distanceTypeVal;
    bool evalInput;
    bool genericMode;
    unsigned globalPoseCount;
    MIntArray poseMatrixIds;
    short typeVal;
    short kernelVal;
    double radiusVal;
    short radiusTypeVal;
    double meanVal;
    double varianceVal;

    BRMatrix matPoses;
    BRMatrix matValues;
    BRMatrix matDebug;
    double meanDist;
    MIntArray poseModes;
    BRMatrix wMat;
    
    std::vector<double> inputNorms;

    // M1.2: cached baseline / isScale snapshot. compute() compares current
    // plug values against these on entry; any change trips evalInput = true
    // so the weight matrix is re-solved against the shifted Y targets.
    std::vector<double> prevBaseValueArr;
    std::vector<bool>   prevOutputIsScaleArr;

    // M1.3: per-dimension raw-space bounds snapshot. Refilled inside the
    // evalInput==true training path in getPoseData / getPoseVectors, read
    // by compute() on every tick to clip live driver values onto the
    // training hull. No dirty tracker — clamp is inference-only and does
    // not participate in the weight solve.
    std::vector<double> poseMinVec;
    std::vector<double> poseMaxVec;

    // M1.4: last successful solver tier. 0 = Cholesky, 1 = GE (fallback).
    // Cross-compute hint: next training attempt prefers the method that
    // worked last time, avoiding a wasted Cholesky probe on kernels that
    // are known non-SPD (Linear / Thin Plate without enough λ).
    // Lifetime: preserved across compute; NOT reset on evalInput==true
    // (kernel SPD-ness is a property of the kernel type, not pose data);
    // reset to 0 only when solverMethod enum changes.
    short lastSolveMethod;
    short prevSolverMethodVal;

    // M2.1a: once-per-rig warning flag for the two safety-net fall-back
    // paths (inDim not a multiple of 3 under a non-Raw encoding, or
    // BendRoll / Swing-Twist placeholder hit before M2.1b lands). Reset
    // when the user changes inputEncoding so each new configuration gets
    // a fresh warning chance; otherwise a single rig would flood the log
    // on every DG evaluation.
    bool  inputEncodingWarningIssued;
    short prevInputEncodingVal;
};

// ---------------------------------------------------------------------
//
// Viewport 2.0
//
// ---------------------------------------------------------------------

class RBFtoolsData : public MUserData
{
public:
#if MAYA_API_VERSION > 20200300
    RBFtoolsData() : MUserData() {}
#else
    RBFtoolsData() : MUserData(false) {}
#endif
    virtual ~RBFtoolsData() {}

    bool activeVal;
    double angleVal;
    double centerAngleVal;
    double colorDriverRVal;
    double colorDriverGVal;
    double colorDriverBVal;
    double colorRVal;
    double colorGVal;
    double colorBVal;
    short dirVal;
    bool drawCenterVal;
    bool drawConeVal;
    bool drawDriverVal;
    bool drawIndicesVal;
    bool drawOriginVal;
    bool drawPosesVal;
    bool drawTwistVal;
    bool drawWeightVal;
    int driverIndexVal;
    double indexDistVal;
    int invVal;
    double poseLengthVal;
    short rbfModeVal;
    double sizeVal;
    short typeVal;
    double weightVal;
};

class RBFtoolsOverride : public MHWRender::MPxDrawOverride
{
public:
    static MHWRender::MPxDrawOverride* Creator(const MObject& obj)
    {
        return new RBFtoolsOverride(obj);
    }
    virtual ~RBFtoolsOverride();
    
    virtual MHWRender::DrawAPI supportedDrawAPIs() const;

    virtual bool isBounded(const MDagPath &objPath,
                           const MDagPath &cameraPath) const { return true; };

    virtual MBoundingBox boundingBox(const MDagPath &objPath,
                                     const MDagPath &cameraPath) const;

    virtual MUserData* prepareForDraw(const MDagPath &objPath,
                                      const MDagPath &cameraPath,
                                      const MHWRender::MFrameContext& frameContext,
                                      MUserData *oldData);

    virtual bool hasUIDrawables() const { return true; };

    virtual void addUIDrawables(const MDagPath &objPath,
                                MHWRender::MUIDrawManager &drawManager,
                                const MHWRender::MFrameContext &frameContext,
                                const MUserData *data);

#if MAYA_API_VERSION < 202400
    static void draw(const MHWRender::MDrawContext &context, const MUserData *data);
#endif

public:
    MVector viewVector;

private:
    RBFtoolsOverride(const MObject& obj);
    static void OnModelEditorChanged(void *clientData);

    RBFtools*  fRBFtools;
    MCallbackId fModelEditorChangedCbId;
};

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
