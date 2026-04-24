// ---------------------------------------------------------------------
//
//  BRMatrix.h
//
//  Created by ingo on 12/7/16.
//  Copyright (c) 2026 Drafter. All rights reserved.
//
// ---------------------------------------------------------------------

#ifndef __SHAPESTools__BRMatrix__
#define __SHAPESTools__BRMatrix__

#include <vector>

#include <maya/MGlobal.h>

class BRMatrix
{
public:
    BRMatrix();
    BRMatrix(const BRMatrix &inMat);
    virtual ~BRMatrix();

    void setSize(unsigned rowSize, unsigned colCount);
    unsigned getRowSize() const;
    unsigned getColSize() const;

    std::vector<double> getRowVector(unsigned row);
    std::vector<double> getColumnVector(unsigned col);
    double* getColumnVector(double *vec, int col);
    
    std::vector<double> normsColumn();
    double norm(std::vector<double> vec);
    void normalizeColumns(std::vector<double> factor);
    
    double mean();
    double variance();

    BRMatrix& operator=(const BRMatrix &inMat);
    BRMatrix operator*(const BRMatrix &inMat);
    BRMatrix& operator*=(const BRMatrix &inMat);
    BRMatrix transpose();

    double& operator()(const unsigned &row, const unsigned &col);
    const double& operator()(const unsigned &row, const unsigned &col) const;

    bool solve(std::vector<double> y, double w[], int &singularIndex);

    // M1.4: Cholesky A = L Lᵀ for SPD matrices. In-place on the lower
    // triangle; the upper triangle is zeroed. Returns false as soon as
    // a non-positive diagonal is encountered (matrix is not SPD — the
    // caller is expected to fall back to the GE solver). See v5 PART
    // D.1 / G.1 Step 2 and addendum 2026-04-24 §M1.4.
    bool cholesky();

    // Solve L Lᵀ x = b by two triangular sweeps (forward then back).
    // PRECONDITION: cholesky() returned true on this matrix. Calling
    // this on an un-decomposed matrix produces garbage.
    void choleskySolve(const std::vector<double> &b,
                       std::vector<double> &x) const;

    void show(MString node, MString dataName);
    void showVector(std::vector<double> v, MString name);

private:
    std::vector<std::vector<double> > mat;
    unsigned rows;
    unsigned cols;
};

#endif

// ---------------------------------------------------------------------
// MIT License
//
// Copyright (c) 2026 Drafter
// weightDriver is under the terms of the MIT License
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
