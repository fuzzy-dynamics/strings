// gear.jscad — spur gear with body, teeth, and bolt heads in distinct colors.
const { primitives, transforms, booleans, colors } = require("@jscad/modeling");

function makeTooth(rOuter, rInner, toothWidth) {
  return primitives.cuboid({
    size: [rOuter - rInner + 2, toothWidth, 6],
    center: [(rOuter + rInner) / 2, 0, 0],
  });
}

function main() {
  const teethCount = 18;
  const rOuter = 28;
  const rInner = 22;

  // Body (steel-grey) with the centre hole drilled.
  const bodyRaw = primitives.cylinder({ radius: rInner, height: 6, segments: 64 });
  const hole = primitives.cylinder({ radius: 5, height: 8, segments: 32 });
  const body = colors.colorize([0.55, 0.58, 0.62, 1],
                 booleans.subtract(bodyRaw, hole));

  // Teeth (brass).
  const teeth = [];
  for (let i = 0; i < teethCount; i++) {
    const a = (i / teethCount) * Math.PI * 2;
    teeth.push(transforms.rotate([0, 0, a], makeTooth(rOuter, rInner, 4)));
  }
  const teethCol = colors.colorize([0.85, 0.65, 0.27, 1],
                     booleans.union(...teeth));

  // Decorative bolt heads (red) on the face of the gear.
  const bolts = [];
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const head = primitives.cylinder({ radius: 2, height: 1.5, segments: 16 });
    bolts.push(transforms.translate(
      [Math.cos(a) * 12, Math.sin(a) * 12, 3.5],
      head,
    ));
  }
  const boltsCol = colors.colorize([0.92, 0.32, 0.30, 1],
                     booleans.union(...bolts));

  return [body, teethCol, boltsCol];
}

module.exports = { main };
