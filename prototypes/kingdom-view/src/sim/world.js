// The map: a clearing in Dawnmere Vale around the Ashen Throne, ringed by forest,
// with a pond and the Old Road that travelers walk up from the south edge.
// Tile (x, z): x grows east, z grows south. A tile's centre is (x + 0.5, z + 0.5).

export const W = 44;
export const H = 44;
export const T = { GRASS: 0, FOREST: 1, WATER: 2, ROAD: 3 };

// Centre of the Heartflame Brazier (tiles 21–22 × 13–14) in tile units.
export const BEACON = { x: 22, z: 14 };
// Travelers appear here, on the south edge of the map.
export const ENTRANCE = { x: 22, z: 43 };
export const REALM_RADIUS = { 1: 12, 2: 16.5 };

// The Old Road, in walking order from the map edge to the clearing.
export const ROAD = [
  [22, 43], [22, 42], [21, 42], [21, 41], [21, 40], [21, 39], [22, 39], [22, 38], [22, 37], [23, 37],
  [23, 36], [23, 35], [22, 35], [22, 34], [22, 33],
];

// 4-neighbours and 8-neighbours as [dx, dz] pairs.
export const N4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
export const N8 = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];

export const idx = (x, z) => z * W + x;
export const inBounds = (x, z) => x >= 0 && z >= 0 && x < W && z < H;
export const centre = (x, z) => ({ x: x + 0.5, z: z + 0.5 });
export const distToBeacon = (x, z) => Math.hypot(x + 0.5 - BEACON.x, z + 0.5 - BEACON.z);

export function makeTerrain() {
  const t = new Uint8Array(W * H);
  for (let z = 0; z < H; z++) {
    for (let x = 0; x < W; x++) {
      const cx = x + 0.5 - 22;
      const cz = z + 0.5 - 21;
      const ang = Math.atan2(cz, cx);
      const wobble = 1 + 0.07 * Math.sin(ang * 3 + 0.6) + 0.05 * Math.sin(ang * 7 + 2.1) + 0.03 * Math.sin(ang * 11 + 4);
      const r = Math.hypot(cx / 16, cz / 13.5);
      let type = r < wobble ? T.GRASS : T.FOREST;
      const px = x + 0.5 - 30.5;
      const pz = (z + 0.5 - 24.5) * 1.1;
      const pa = Math.atan2(pz, px);
      if (Math.hypot(px, pz) < 3.3 + 0.45 * Math.sin(pa * 3 + 1) + 0.25 * Math.sin(pa * 5)) type = T.WATER;
      t[idx(x, z)] = type;
    }
  }
  for (const [x, z] of ROAD) t[idx(x, z)] = T.ROAD;
  // Grass verges along the road, so lantern posts can stand beside it.
  for (const [x, z] of ROAD) {
    for (const [dx, dz] of N8) {
      const i = idx(x + dx, z + dz);
      if (inBounds(x + dx, z + dz) && t[i] === T.FOREST) t[i] = T.GRASS;
    }
  }
  return t;
}

