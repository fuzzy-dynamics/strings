"use strict";

// Procedural body generators. Each returns:
//   { positions: number[], indices: number[], a, b, c, length }
// where (a,b,c) are the half-axes of the equivalent ellipsoid the flow
// solver should use.

function buildRevolution(profile, segU, segV, length) {
  const positions = [];
  const indices = [];
  for (let i = 0; i <= segU; i++) {
    const t = i / segU;
    const x = -length / 2 + length * t;
    const r = profile(t);
    for (let j = 0; j <= segV; j++) {
      const theta = (j / segV) * Math.PI * 2;
      positions.push(x, r * Math.sin(theta), r * Math.cos(theta));
    }
  }
  for (let i = 0; i < segU; i++) {
    for (let j = 0; j < segV; j++) {
      const a = i * (segV + 1) + j;
      const b = a + 1;
      const c = a + (segV + 1);
      const d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
  }
  return { positions, indices };
}

// Streamlined teardrop: smooth nose, blunt tail. Loosely based on the
// Sears–Haack body (minimum-wave-drag profile) but with a softer exponent.
function teardrop(opts = {}) {
  const length = opts.length || 30;
  const Rmax = opts.maxRadius || 6;
  const segU = opts.segU || 64;
  const segV = opts.segV || 32;
  const profile = (t) => {
    // t in [0,1]; map to symmetric s in [-1,1]
    const s = 2 * t - 1;
    const env = Math.pow(Math.max(0, 1 - s * s), 0.65);
    // bias mass slightly toward the front (t≈0.4) to look like the image
    const skew = 1 + 0.18 * (1 - s) * (1 + s); // 1 at edges, 1.18 at midpoint
    return Rmax * env * skew * 0.92;
  };
  const mesh = buildRevolution(profile, segU, segV, length);
  return {
    ...mesh,
    a: length * 0.5,
    b: Rmax,
    c: Rmax,
    length,
    type: "teardrop",
  };
}

// Sphere — segmented mesh for visual quality.
function sphere(opts = {}) {
  const R = opts.radius || 6;
  const segU = opts.segU || 32;
  const segV = opts.segV || 32;
  // Use UV sphere = revolution with sin(πt) profile.
  const profile = (t) => R * Math.sin(Math.PI * t);
  const mesh = buildRevolution(profile, segU, segV, 2 * R);
  return { ...mesh, a: R, b: R, c: R, length: 2 * R, type: "sphere" };
}

// Generic ellipsoid (a, b, c half-axes).
function ellipsoid(opts = {}) {
  const a = opts.a || 12;
  const b = opts.b || 5;
  const c = opts.c || 6;
  const segU = opts.segU || 48;
  const segV = opts.segV || 32;
  const positions = [];
  const indices = [];
  for (let i = 0; i <= segU; i++) {
    const u = (i / segU) * Math.PI;
    const sinU = Math.sin(u);
    const cosU = Math.cos(u);
    for (let j = 0; j <= segV; j++) {
      const v = (j / segV) * Math.PI * 2;
      positions.push(a * cosU, b * sinU * Math.sin(v), c * sinU * Math.cos(v));
    }
  }
  for (let i = 0; i < segU; i++) {
    for (let j = 0; j < segV; j++) {
      const ai = i * (segV + 1) + j;
      const bi = ai + 1;
      const ci = ai + (segV + 1);
      const di = ci + 1;
      indices.push(ai, ci, bi, bi, ci, di);
    }
  }
  return { positions, indices, a, b, c, length: 2 * a, type: "ellipsoid" };
}

module.exports = { teardrop, sphere, ellipsoid };
