"use strict";

// Tiny STL parser. Handles both binary and ASCII formats. Returns flat
// position arrays — every 9 floats = one triangle (no indexing).
//
// Binary STL layout:
//   80-byte header (any content)
//   uint32  triangle count
//   per-triangle:
//     3×float32  normal
//     3×3 float32  vertices
//     uint16   attribute byte count

const fs = require("fs");

function looksLikeBinary(buf) {
  if (buf.length < 84) return false;
  const claimedTri = buf.readUInt32LE(80);
  return buf.length === 84 + claimedTri * 50;
}

function parseBinary(buf) {
  const positions = [];
  const triCount = buf.readUInt32LE(80);
  let off = 84;
  for (let i = 0; i < triCount; i++) {
    off += 12; // skip normal
    for (let v = 0; v < 3; v++) {
      positions.push(
        buf.readFloatLE(off),
        buf.readFloatLE(off + 4),
        buf.readFloatLE(off + 8),
      );
      off += 12;
    }
    off += 2; // attribute byte count
  }
  return { positions };
}

function parseAscii(text) {
  const positions = [];
  // Use a single regex pass — much faster than line-by-line for large files.
  const re = /vertex\s+(-?[\d.eE+]+)\s+(-?[\d.eE+]+)\s+(-?[\d.eE+]+)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    positions.push(parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3]));
  }
  return { positions };
}

function parseStl(buf) {
  if (looksLikeBinary(buf)) return parseBinary(buf);
  // Some binary STLs start with "solid" too; double-check by looking for
  // "endloop" / "facet" markers, otherwise fall back to binary parse.
  const headText = buf.slice(0, Math.min(512, buf.length)).toString("ascii");
  if (/endloop|endfacet/i.test(headText)) {
    return parseAscii(buf.toString("utf8"));
  }
  return parseBinary(buf);
}

// Center mesh on its bounding-box midpoint and return:
//   { positions, a, b, c, length, type, triangle_count }
// where (a,b,c) are half-extents of the (centered) bounding box used as
// the ellipsoid axes for the flow solver.
function loadStl(absPath) {
  const buf = fs.readFileSync(absPath);
  const { positions } = parseStl(buf);
  if (positions.length < 9) {
    throw new Error("stl_empty: parser produced no triangles");
  }
  let xMin = Infinity, yMin = Infinity, zMin = Infinity;
  let xMax = -Infinity, yMax = -Infinity, zMax = -Infinity;
  for (let i = 0; i < positions.length; i += 3) {
    const x = positions[i], y = positions[i + 1], z = positions[i + 2];
    if (x < xMin) xMin = x; if (x > xMax) xMax = x;
    if (y < yMin) yMin = y; if (y > yMax) yMax = y;
    if (z < zMin) zMin = z; if (z > zMax) zMax = z;
  }
  const cx = (xMin + xMax) / 2, cy = (yMin + yMax) / 2, cz = (zMin + zMax) / 2;
  const centered = new Float32Array(positions.length);
  for (let i = 0; i < positions.length; i += 3) {
    centered[i]     = positions[i]     - cx;
    centered[i + 1] = positions[i + 1] - cy;
    centered[i + 2] = positions[i + 2] - cz;
  }
  const a = Math.max(1e-6, (xMax - xMin) / 2);
  const b = Math.max(1e-6, (yMax - yMin) / 2);
  const c = Math.max(1e-6, (zMax - zMin) / 2);

  return {
    positions: Array.from(centered),
    a, b, c,
    length: 2 * a,
    type: "stl",
    triangle_count: centered.length / 9,
  };
}

module.exports = { parseStl, loadStl };
