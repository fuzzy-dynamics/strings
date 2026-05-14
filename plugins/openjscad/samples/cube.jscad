// cube.jscad — three differently coloured boxes joined into one model.
// Demonstrates per-component colors via @jscad/modeling's colors.colorize().
const { primitives, transforms, colors } = require("@jscad/modeling");

function main() {
  const red   = colors.colorize([0.92, 0.32, 0.30, 1],
                  primitives.cuboid({ size: [30, 30, 30] }));
  const green = colors.colorize([0.40, 0.78, 0.45, 1],
                  transforms.translate([35,  0,  0],
                    primitives.cuboid({ size: [30, 30, 30] })));
  const blue  = colors.colorize([0.30, 0.55, 0.95, 1],
                  transforms.translate([17.5, 30, 17.5],
                    primitives.cuboid({ size: [30, 30, 30] })));
  return [red, green, blue];
}

module.exports = { main };
