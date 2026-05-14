// sphere.jscad — sphere with 6 colored "spokes" radiating outward.
// Each spoke gets a distinct color via colorize().
const { primitives, transforms, colors } = require("@jscad/modeling");

function main() {
  const core = colors.colorize([0.85, 0.85, 0.85, 1],
                 primitives.sphere({ radius: 15, segments: 64 }));

  const PALETTE = [
    [0.94, 0.42, 0.36, 1],
    [0.96, 0.74, 0.31, 1],
    [0.55, 0.84, 0.39, 1],
    [0.32, 0.78, 0.74, 1],
    [0.42, 0.55, 0.95, 1],
    [0.74, 0.42, 0.85, 1],
  ];

  const spokes = [];
  const N = PALETTE.length;
  for (let i = 0; i < N; i++) {
    const a = (i / N) * Math.PI * 2;
    const cyl = primitives.cylinder({ radius: 3, height: 30, segments: 24 });
    const placed = transforms.translate([Math.cos(a) * 22, Math.sin(a) * 22, 0],
                     transforms.rotate([Math.PI / 2, 0, a], cyl));
    spokes.push(colors.colorize(PALETTE[i], placed));
  }

  return [core, ...spokes];
}

module.exports = { main };
