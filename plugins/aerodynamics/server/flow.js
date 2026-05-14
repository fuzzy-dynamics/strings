"use strict";

// Analytical potential flow primitives + RK4 streamline tracer.
//
// Sphere-in-uniform-flow (Lamb 1932 §95): combines the free-stream U∞·x̂
// with a 3D doublet at the origin. The closed-form velocity field is:
//
//   φ(x,y,z) = U·x · (1 + R³ / (2r³))
//   v = ∇φ
//
// We implement v_x = ∂φ/∂x, v_y = ∂φ/∂y, v_z = ∂φ/∂z directly in Cartesian
// — no spherical-coordinate detour needed.

function sphereVelocity(x, y, z, U, R) {
  const r2 = x * x + y * y + z * z;
  if (r2 < R * R) return [0, 0, 0];                  // inside body — flow is zero
  const r = Math.sqrt(r2);
  const r3 = r2 * r;
  const r5 = r2 * r3;
  const R3 = R * R * R;
  return [
    U * (1 + R3 / (2 * r3) - 3 * x * x * R3 / (2 * r5)),
    U * (-3 * R3 * x * y / (2 * r5)),
    U * (-3 * R3 * x * z / (2 * r5)),
  ];
}

// Ellipsoid approximation: change-of-variables (xs,ys,zs) = (x/a, y/b, z/c)
// maps the ellipsoid to a unit sphere. The chain rule for the velocity
// then gives v_original = (v_unit_x / a, v_unit_y / b, v_unit_z / c).
// To preserve free-stream U in the original frame, we solve the unit-
// sphere problem with U_unit = U·a (so v_unit_x at infinity is U·a, and
// v_original_x = U·a / a = U). This gives correct asymptotic behaviour
// while keeping streamline deflection plausible for elongated bodies.
function ellipsoidVelocity(x, y, z, U, a, b, c) {
  const xs = x / a;
  const ys = y / b;
  const zs = z / c;
  const v = sphereVelocity(xs, ys, zs, U * a, 1.0);
  return [v[0] / a, v[1] / b, v[2] / c];
}

// ─── Empirical wake model ────────────────────────────────────────────────
//
// This is a *visual* wake — not Navier-Stokes. We define a smooth-ramp
// cylinder behind the body and add divergence-of-noise (curl-of-something)
// velocity perturbations to the potential flow inside it. The result is
// visually convincing chaotic streamlines past bluff bodies, costs zero
// PDE solve, and gives us a per-point `turbulence` scalar the iframe can
// use to tint streamlines red where the wake is strongest.

// Multi-octave sinusoidal "curl" noise. Not strictly divergence-free, but
// close enough for visualisation — and we tolerate small div(v) anyway
// since we're not enforcing mass conservation.
function curlNoise(p, scale) {
  const k1 = 0.34 / scale;
  const k2 = 0.83 / scale;
  const k3 = 1.67 / scale;
  const x = p[0], y = p[1], z = p[2];
  const a1 = Math.sin(y * k1 + 0.7)  * Math.cos(z * k1 + 1.1)
           + 0.55 * Math.sin(y * k2 + 1.7) * Math.cos(z * k2 + 0.4)
           + 0.32 * Math.sin(y * k3 + 0.3) * Math.cos(z * k3 + 2.1);
  const a2 = Math.sin(x * k1 + 1.7)  * Math.cos(z * k1 + 0.5)
           + 0.55 * Math.sin(x * k2 + 0.3) * Math.cos(z * k2 + 1.7)
           + 0.32 * Math.sin(x * k3 + 2.7) * Math.cos(z * k3 + 1.1);
  const a3 = Math.sin(x * k1 + 2.3)  * Math.cos(y * k1 + 1.5)
           + 0.55 * Math.sin(x * k2 + 0.9) * Math.cos(y * k2 + 0.7)
           + 0.32 * Math.sin(x * k3 + 1.3) * Math.cos(y * k3 + 0.5);
  return [a1, a2, a3];
}

// Smooth weight: 0 in front of body, ramps to 1 in the wake cylinder, then
// decays exponentially far downstream. Cylinder is centred on the
// body's x-axis, length ~3a, radius ~2·max(b,c).
function wakeWeight(p, a, b, c) {
  const x = p[0], y = p[1], z = p[2];
  if (x < 0.6 * a) return 0;
  const r = Math.sqrt(y * y + z * z);
  const rMax = 2.0 * Math.max(b, c);
  if (r > rMax) return 0;
  // Build-up: smoothstep over [0.6a, 1.6a]
  const xt = Math.min(1, Math.max(0, (x - 0.6 * a) / (1.0 * a)));
  const xRamp = xt * xt * (3 - 2 * xt);
  // Lateral falloff: full at axis, zero at rMax
  const rt = 1 - r / rMax;
  const rRamp = rt * rt;
  // Far-downstream decay (turbulence dissipates eventually)
  const decay = Math.exp(-Math.max(0, x - 2.5 * a) / (2.0 * a));
  return xRamp * rRamp * decay;
}

// Combined velocity: potential flow + wake-region curl noise.
// Returns [vx, vy, vz, turbulence] where turbulence ∈ [0, 1] is the
// effective wake intensity at that point.
function velocityWithWake(x, y, z, U, a, b, c, wakeAmplitude) {
  const v = ellipsoidVelocity(x, y, z, U, a, b, c);
  const w = wakeWeight([x, y, z], a, b, c);
  if (w === 0) return [v[0], v[1], v[2], 0];
  const scale = Math.max(b, c);
  const n = curlNoise([x, y, z], scale);
  const amp = wakeAmplitude * U;
  const noiseMag = Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
  const turb = Math.min(1, w * (amp * noiseMag) / U);
  return [
    v[0] + w * amp * n[0],
    v[1] + w * amp * n[1],
    v[2] + w * amp * n[2],
    turb,
  ];
}

// RK4 integrator. `velocityFn(p)` returns [vx,vy,vz] (3-tuple) or
// [vx,vy,vz,turb] (4-tuple). The 4th element, when present, is sampled at
// the start-of-step to populate the per-point `turbs` array.
// Stops when x crosses `xLimit` (downstream) or maxSteps is exhausted.
function traceStreamline(velocityFn, start, dt, maxSteps, xLimit) {
  const positions = [];
  const speeds = [];
  const turbs = [];
  let pos = start.slice();
  for (let step = 0; step < maxSteps; step++) {
    const k1 = velocityFn(pos);
    const speed = Math.sqrt(k1[0] * k1[0] + k1[1] * k1[1] + k1[2] * k1[2]);
    positions.push(pos[0], pos[1], pos[2]);
    speeds.push(speed);
    turbs.push(k1.length >= 4 ? k1[3] : 0);

    if (speed < 1e-6) break;

    const p2 = [
      pos[0] + (dt / 2) * k1[0],
      pos[1] + (dt / 2) * k1[1],
      pos[2] + (dt / 2) * k1[2],
    ];
    const k2 = velocityFn(p2);
    const p3 = [
      pos[0] + (dt / 2) * k2[0],
      pos[1] + (dt / 2) * k2[1],
      pos[2] + (dt / 2) * k2[2],
    ];
    const k3 = velocityFn(p3);
    const p4 = [
      pos[0] + dt * k3[0],
      pos[1] + dt * k3[1],
      pos[2] + dt * k3[2],
    ];
    const k4 = velocityFn(p4);

    pos[0] += (dt / 6) * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]);
    pos[1] += (dt / 6) * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]);
    pos[2] += (dt / 6) * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]);

    if (pos[0] > xLimit) break;
  }
  return { positions, speeds, turbs };
}

module.exports = {
  sphereVelocity,
  ellipsoidVelocity,
  velocityWithWake,
  curlNoise,
  wakeWeight,
  traceStreamline,
};
