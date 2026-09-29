// Ground, pond, cobbles, grass and the forest ring. The clearing is flat; the forest floor rolls a
// little; the pond is a dip in the ground under a water plane, so its shore follows the tiles.
import * as THREE from 'three';
import { W, H, T, idx, inBounds } from '../sim/world.js';
import { TYPES } from '../sim/catalog.js';
import { P } from './palette.js';
import { veilify, HALF } from './veil.js';
import { hashRand } from './kit.js';

const EXT = 20; // forest margin beyond the map, in tiles
const SIZE = W + EXT * 2;

const c = hex => new THREE.Color(hex);
const GRASS = [c(P.grassMid), c(P.grassLight), c(P.grassMuted), c('#A9C46A')];
const FOREST_FLOOR = [c('#4F6B45'), c('#5A7249'), c('#465F42')];
const PATH_BED = c('#CDB68A');
const ROAD_BED = c('#B89C72');
const BANK = c('#6F7F58');
const SOIL = c('#5E4B38');

function terrainAt(game, x, z) {
  if (!inBounds(x, z)) return T.FOREST;
  return game.terrain[idx(x, z)];
}

function noise2(x, z) {
  return Math.sin(x * 0.61 + z * 0.23) * 0.5 + Math.sin(x * 0.17 - z * 0.47) * 0.35 + Math.sin(x * 1.3 + z * 1.1) * 0.15;
}

export class Terrain {
  constructor(scene, game, { shadows = true } = {}) {
    this.scene = scene;
    this.game = game;
    this.version = -1;
    const geo = new THREE.PlaneGeometry(SIZE, SIZE, SIZE, SIZE).rotateX(-Math.PI / 2);
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(geo.attributes.position.count * 3), 3));
    this.ground = new THREE.Mesh(geo, veilify(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, metalness: 0, flatShading: true })));
    this.ground.receiveShadow = shadows;
    scene.add(this.ground);
    this.shapeGround();
    this.buildWater();
    this.buildForest(shadows);
    this.buildPondLife();
    this.cobbles = null;
    this.grass = null;
    this.sync(true);
  }

  // Vertex (i, j) sits on the tile corner (i − EXT, j − EXT) in tile units.
  shapeGround() {
    const pos = this.ground.geometry.attributes.position;
    const game = this.game;
    for (let v = 0; v < pos.count; v++) {
      const i = v % (SIZE + 1);
      const j = Math.floor(v / (SIZE + 1));
      const tx = i - EXT;
      const tz = j - EXT;
      const around = [[tx - 1, tz - 1], [tx, tz - 1], [tx - 1, tz], [tx, tz]].map(([x, z]) => terrainAt(game, x, z));
      const water = around.filter(t => t === T.WATER).length;
      const forest = around.filter(t => t === T.FOREST).length;
      let y = 0;
      if (water === 4) y = -0.55;
      else if (water) y = -0.18 * water;
      else if (forest === 4) y = 0.12 + noise2(tx, tz) * 0.14;
      else if (forest) y = 0.04 * forest;
      pos.setY(v, y);
      pos.setX(v, tx - HALF);
      pos.setZ(v, tz - HALF);
    }
    pos.needsUpdate = true;
    this.ground.geometry.computeVertexNormals();
  }

  colourGround() {
    const game = this.game;
    const pos = this.ground.geometry.attributes.position;
    const col = this.ground.geometry.attributes.color;
    const tmp = new THREE.Color();
    for (let v = 0; v < pos.count; v++) {
      const i = v % (SIZE + 1);
      const j = Math.floor(v / (SIZE + 1));
      const tx = i - EXT;
      const tz = j - EXT;
      const around = [[tx - 1, tz - 1], [tx, tz - 1], [tx - 1, tz], [tx, tz]];
      tmp.setRGB(0, 0, 0);
      for (const [x, z] of around) {
        const t = terrainAt(game, x, z);
        const h = (Math.abs(noise2(x * 3.1, z * 2.7)) * 4) | 0;
        let tc;
        if (t === T.FOREST) tc = FOREST_FLOOR[h % 3];
        else if (t === T.WATER) tc = BANK;
        else if (t === T.ROAD) tc = ROAD_BED;
        else if (game.surface[idx(x, z)]) tc = PATH_BED;
        else {
          const o = game.objectAt(x, z);
          tc = o && (o.type === 'field_turnip' || o.type === 'field_wheat') ? SOIL : GRASS[h % 4];
        }
        tmp.r += tc.r / 4; tmp.g += tc.g / 4; tmp.b += tc.b / 4;
      }
      col.setXYZ(v, tmp.r, tmp.g, tmp.b);
    }
    col.needsUpdate = true;
  }

  buildWater() {
    let x0 = W, x1 = 0, z0 = H, z1 = 0;
    for (let z = 0; z < H; z++) for (let x = 0; x < W; x++) if (this.game.terrain[idx(x, z)] === T.WATER) {
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); z0 = Math.min(z0, z); z1 = Math.max(z1, z);
    }
    const w = x1 - x0 + 3;
    const d = z1 - z0 + 3;
    const geo = new THREE.PlaneGeometry(w, d, w * 3, d * 3).rotateX(-Math.PI / 2);
    this.waterUniforms = { uWaterTime: { value: 0 } };
    const mat = veilify(new THREE.MeshStandardMaterial({ color: '#4E8C8A', roughness: 0.12, metalness: 0.05, transparent: true, opacity: 0.9 }));
    const inner = mat.onBeforeCompile;
    mat.onBeforeCompile = shader => {
      inner(shader);
      shader.uniforms.uWaterTime = this.waterUniforms.uWaterTime;
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\nuniform float uWaterTime;\nvarying vec2 vWaterXZ;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWaterXZ = (modelMatrix * vec4(position, 1.0)).xz;');
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', '#include <common>\nuniform float uWaterTime;\nvarying vec2 vWaterXZ;')
        .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        {
          vec2 p = vWaterXZ * 2.3;
          float a = sin(p.x * 1.7 + uWaterTime * 1.3) + sin(p.y * 2.1 - uWaterTime * 1.1) + sin((p.x + p.y) * 1.3 + uWaterTime * 0.7);
          float b = cos(p.x * 1.9 - uWaterTime * 0.9) + cos(p.y * 1.6 + uWaterTime * 1.4);
          normal = normalize(normal + (viewMatrix * vec4(a * 0.045, 0.0, b * 0.045, 0.0)).xyz);
        }`);
    };
    this.water = new THREE.Mesh(geo, mat);
    this.water.position.set(x0 - 1 + w / 2 - HALF, -0.16, z0 - 1 + d / 2 - HALF);
    this.water.receiveShadow = true;
    this.scene.add(this.water);
  }

  buildPondLife() {
    const game = this.game;
    const R = hashRand(77);
    const pads = [];
    const lotus = [];
    const reeds = [];
    for (let z = 0; z < H; z++) for (let x = 0; x < W; x++) {
      const t = game.terrain[idx(x, z)];
      if (t === T.WATER) {
        const shore = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => terrainAt(game, x + dx, z + dz) !== T.WATER);
        if (R() < (shore ? 0.55 : 0.2)) {
          const p = [x + 0.5 + (R() - 0.5) * 0.6 - HALF, z + 0.5 + (R() - 0.5) * 0.6 - HALF, 0.18 + R() * 0.12, R() * 6];
          pads.push(p);
          if (R() < 0.35) lotus.push(p);
        }
      } else if (t === T.GRASS && [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => terrainAt(game, x + dx, z + dz) === T.WATER)) {
        if (R() < 0.6) for (let k = 0; k < 3; k++) reeds.push([x + R() - HALF, z + R() - HALF, 0.4 + R() * 0.4]);
      }
    }
    const padMat = veilify(new THREE.MeshStandardMaterial({ color: '#5E9A5A', roughness: 0.8, flatShading: true }));
    const padGeo = new THREE.CylinderGeometry(1, 1, 0.02, 9, 1, false, 0.3, Math.PI * 2 - 0.6);
    const padMesh = new THREE.InstancedMesh(padGeo, padMat, pads.length);
    const m = new THREE.Matrix4();
    pads.forEach(([x, z, r, a], i) => padMesh.setMatrixAt(i, m.compose(new THREE.Vector3(x, -0.13, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(0, a, 0)), new THREE.Vector3(r, 1, r))));
    this.scene.add(padMesh);
    const lotusMesh = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.1, 0), veilify(new THREE.MeshStandardMaterial({ color: P.lotus, roughness: 0.6, flatShading: true })), lotus.length);
    lotus.forEach(([x, z], i) => lotusMesh.setMatrixAt(i, m.compose(new THREE.Vector3(x + 0.05, -0.07, z), new THREE.Quaternion(), new THREE.Vector3(1, 0.7, 1))));
    this.scene.add(lotusMesh);
    const reedGeo = new THREE.ConeGeometry(0.025, 1, 4).translate(0, 0.5, 0);
    const reedMesh = new THREE.InstancedMesh(reedGeo, veilify(new THREE.MeshStandardMaterial({ color: '#7E9A55', roughness: 1, flatShading: true })), reeds.length);
    reeds.forEach(([x, z, h], i) => reedMesh.setMatrixAt(i, m.compose(new THREE.Vector3(x, 0, z), new THREE.Quaternion().setFromEuler(new THREE.Euler((R() - 0.5) * 0.3, 0, (R() - 0.5) * 0.3)), new THREE.Vector3(1, h, 1))));
    this.scene.add(reedMesh);
  }

  buildForest(shadows) {
    const game = this.game;
    const R = hashRand(2024);
    const round = [];
    const pines = [];
    const bushes = [];
    const shrooms = [];
    for (let z = -EXT; z < H + EXT; z++) {
      for (let x = -EXT; x < W + EXT; x++) {
        if (terrainAt(game, x, z) !== T.FOREST) continue;
        // Keep the far margin sparser: fog hides it anyway.
        const outside = x < 0 || z < 0 || x >= W || z >= H;
        const edgeDist = Math.min(x + EXT, z + EXT, W + EXT - 1 - x, H + EXT - 1 - z);
        if (outside && R() < 0.35) continue;
        if (edgeDist < 2 && R() < 0.6) continue;
        const nearClearing = !outside && [[1, 0], [-1, 0], [0, 1], [0, -1], [2, 0], [-2, 0], [0, 2], [0, -2]].some(([dx, dz]) => { const t = terrainAt(game, x + dx, z + dz); return t === T.GRASS || t === T.ROAD; });
        const px = x + 0.5 + (R() - 0.5) * 0.7 - HALF;
        const pz = z + 0.5 + (R() - 0.5) * 0.7 - HALF;
        const s = (nearClearing ? 0.9 : 1.1) + R() * 0.8;
        if (R() < 0.34) pines.push([px, pz, s * 1.05, R()]);
        else round.push([px, pz, s, R()]);
        if (nearClearing && R() < 0.5) bushes.push([x + R() - HALF, z + R() - HALF, 0.4 + R() * 0.35, R()]);
        if (nearClearing && R() < 0.06) shrooms.push([x + 0.5 - HALF, z + 0.5 - HALF, 0.8 + R() * 0.6, R()]);
      }
    }
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const e = new THREE.Euler();
    const v = new THREE.Vector3();
    const sc = new THREE.Vector3();
    const inst = (geo, mat, list, place) => {
      const mesh = new THREE.InstancedMesh(geo, mat, list.length);
      const col = new THREE.Color();
      list.forEach((item, i) => {
        place(item, col);
        mesh.setMatrixAt(i, m.compose(v, q, sc));
        mesh.setColorAt(i, col);
      });
      mesh.castShadow = shadows;
      mesh.receiveShadow = shadows;
      this.scene.add(mesh);
      return mesh;
    };
    const trunkMat = veilify(new THREE.MeshStandardMaterial({ color: '#FFFFFF', roughness: 1, flatShading: true }));
    const leafMat = veilify(new THREE.MeshStandardMaterial({ color: '#FFFFFF', roughness: 0.95, flatShading: true }));
    const trunkGeo = new THREE.CylinderGeometry(0.1, 0.16, 1, 6).translate(0, 0.5, 0);
    const canopyGeo = new THREE.IcosahedronGeometry(0.75, 1);
    const pineGeo = mergePine();
    const leafCols = [c(P.foliageLight), c(P.foliageDark), c('#4F8A6A'), c('#5E9460'), c(P.foliageDeep)];
    inst(trunkGeo, trunkMat, [...round, ...pines], ([x, z, s], col) => {
      v.set(x, 0, z); q.identity(); sc.set(s, s * 1.3, s); col.set(P.woodDark);
    });
    inst(canopyGeo, leafMat, round, ([x, z, s, r], col) => {
      v.set(x, 1.2 * s + 0.35, z); q.setFromEuler(e.set(0, r * 6, 0)); sc.set(s * (0.9 + r * 0.3), s * (0.95 + r * 0.25), s * (0.9 + r * 0.3));
      col.copy(leafCols[Math.floor(r * 4)]);
    });
    inst(pineGeo, leafMat, pines, ([x, z, s, r], col) => {
      v.set(x, 0.5 * s, z); q.setFromEuler(e.set(0, r * 6, 0)); sc.set(s * 0.9, s * 1.15, s * 0.9);
      col.copy(leafCols[1 + Math.floor(r * 4) % 4]);
    });
    inst(new THREE.IcosahedronGeometry(0.5, 0), leafMat, bushes, ([x, z, s, r], col) => {
      v.set(x, s * 0.3, z); q.setFromEuler(e.set(0, r * 6, 0)); sc.set(s, s * 0.7, s);
      col.copy(leafCols[Math.floor(r * 3) + 1]);
    });
    // Giant mushrooms at the forest edge; their caps glow faintly at night.
    const stemMat = veilify(new THREE.MeshStandardMaterial({ color: '#EDE3CF', roughness: 0.9, flatShading: true }));
    inst(new THREE.CylinderGeometry(0.08, 0.13, 1, 7).translate(0, 0.5, 0), stemMat, shrooms, ([x, z, s], col) => { v.set(x, 0, z); q.identity(); sc.set(s, s, s); col.set('#FFFFFF'); });
    this.shroomCaps = new THREE.InstancedMesh(new THREE.SphereGeometry(0.42, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshBasicMaterial({ color: '#FFFFFF' }), shrooms.length);
    shrooms.forEach(([x, z, s, r], i) => {
      this.shroomCaps.setMatrixAt(i, m.compose(v.set(x, s * 0.95, z), q.identity(), sc.set(s, s * 0.8, s)));
      this.shroomCaps.setColorAt(i, new THREE.Color(r < 0.5 ? '#D7B068' : '#C99AD8'));
    });
    this.scene.add(this.shroomCaps);
    this.shroomSpots = shrooms.map(([x, z, s]) => ({ x, y: s * 0.9, z }));
  }

  // Cobbles on paths and the road, grass tufts and wildflowers on open grass.
  sync(force = false) {
    const game = this.game;
    if (!force && game.version === this.version) return;
    this.version = game.version;
    this.colourGround();
    if (this.cobbles) { this.scene.remove(this.cobbles); this.cobbles.dispose(); }
    if (this.grass) { this.scene.remove(this.grass); this.grass.dispose(); }
    if (this.blooms) { this.scene.remove(this.blooms); this.blooms.dispose(); }
    const stones = [];
    const tufts = [];
    const blooms = [];
    for (let z = 0; z < H; z++) for (let x = 0; x < W; x++) {
      const R = hashRand(x * 131 + z * 17 + 5);
      const t = game.terrain[idx(x, z)];
      const o = game.objectAt(x, z);
      if (t === T.ROAD || game.surface[idx(x, z)]) {
        const road = t === T.ROAD;
        const n = road ? 3 : 5;
        for (let k = 0; k < n; k++) {
          const sx = road ? (R() - 0.5) * 0.8 : ((k % 2) - 0.5) * 0.48 + (R() - 0.5) * 0.1;
          const sz = road ? (R() - 0.5) * 0.8 : (Math.floor(k / 2) % 2 - 0.5) * 0.48 + (R() - 0.5) * 0.1;
          const size = road ? 0.16 + R() * 0.1 : (k === 4 ? 0.14 : 0.22 + R() * 0.04);
          stones.push([x + 0.5 + (k === 4 && !road ? (R() - 0.5) * 0.2 : sx) - HALF, z + 0.5 + (k === 4 && !road ? (R() - 0.5) * 0.2 : sz) - HALF, size, R(), road]);
        }
      } else if (t === T.GRASS && (!o || TYPES[o.type].walkable)) {
        const n = 2 + Math.floor(R() * 3);
        for (let k = 0; k < n; k++) tufts.push([x + R() - HALF, z + R() - HALF, 0.6 + R() * 0.7, R()]);
        if (R() < 0.18) blooms.push([x + R() - HALF, z + R() - HALF, R()]);
      }
    }
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const e = new THREE.Euler();
    const col = new THREE.Color();
    const stoneMat = veilify(new THREE.MeshStandardMaterial({ color: '#FFFFFF', roughness: 0.9, flatShading: true }));
    this.cobbles = new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1.08, 0.08, 6), stoneMat, Math.max(1, stones.length));
    const stoneCols = [c(P.stoneWarm), c(P.stoneCream), c(P.sand), c('#D8C8A4')];
    const roadCols = [c('#C9B28A'), c(P.stoneShade), c('#BFA880')];
    stones.forEach(([x, z, s, r, road], i) => {
      this.cobbles.setMatrixAt(i, m.compose(new THREE.Vector3(x, 0.02, z), q.setFromEuler(e.set(0, r * 3, 0)), new THREE.Vector3(s, 1, s * (0.85 + r * 0.3))));
      this.cobbles.setColorAt(i, (road ? roadCols : stoneCols)[Math.floor(r * 97) % (road ? 3 : 4)]);
    });
    this.cobbles.count = stones.length;
    this.cobbles.receiveShadow = true;
    this.scene.add(this.cobbles);
    const tuftGeo = mergeTuft();
    this.grass = new THREE.InstancedMesh(tuftGeo, veilify(new THREE.MeshStandardMaterial({ color: '#FFFFFF', roughness: 1, flatShading: true })), Math.max(1, tufts.length));
    const tuftCols = [c('#8FB35A'), c('#9DBF62'), c('#7FA650'), c('#A8C66E')];
    tufts.forEach(([x, z, s, r], i) => {
      this.grass.setMatrixAt(i, m.compose(new THREE.Vector3(x, 0, z), q.setFromEuler(e.set(0, r * 6, 0)), new THREE.Vector3(s, s, s)));
      this.grass.setColorAt(i, tuftCols[Math.floor(r * 4)]);
    });
    this.grass.count = tufts.length;
    this.grass.receiveShadow = true;
    this.scene.add(this.grass);
    this.blooms = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.05, 0), veilify(new THREE.MeshStandardMaterial({ color: '#FFFFFF', roughness: 0.8, flatShading: true })), Math.max(1, blooms.length));
    const bloomCols = [c('#FFF6E6'), c('#F4D66A'), c(P.lotus), c(P.lavender)];
    blooms.forEach(([x, z, r], i) => {
      this.blooms.setMatrixAt(i, m.compose(new THREE.Vector3(x, 0.12, z), q.identity(), new THREE.Vector3(1, 1, 1)));
      this.blooms.setColorAt(i, bloomCols[Math.floor(r * 4)]);
    });
    this.blooms.count = blooms.length;
    this.scene.add(this.blooms);
  }

  update(time, night) {
    this.waterUniforms.uWaterTime.value = time;
    this.shroomCaps.material.color.setScalar(0.8 + night * 0.9);
  }
}

function mergePine() {
  const parts = [
    new THREE.ConeGeometry(0.75, 1.1, 7).translate(0, 0.9, 0),
    new THREE.ConeGeometry(0.6, 0.95, 7).translate(0, 1.45, 0),
    new THREE.ConeGeometry(0.42, 0.8, 7).translate(0, 1.95, 0),
  ];
  return mergeSimple(parts);
}

function mergeTuft() {
  const parts = [];
  for (let k = 0; k < 4; k++) {
    const g = new THREE.ConeGeometry(0.035, 0.26, 3).translate(0, 0.13, 0);
    g.rotateZ((k - 1.5) * 0.25);
    g.rotateY(k * 1.3);
    g.translate(Math.cos(k * 1.7) * 0.05, 0, Math.sin(k * 1.7) * 0.05);
    parts.push(g);
  }
  return mergeSimple(parts);
}

function mergeSimple(parts) {
  const geos = parts.map(g => (g.index ? g.toNonIndexed() : g));
  let n = 0;
  for (const g of geos) n += g.attributes.position.count;
  const pos = new Float32Array(n * 3);
  let o = 0;
  for (const g of geos) { pos.set(g.attributes.position.array, o); o += g.attributes.position.array.length; }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.computeVertexNormals();
  return out;
}
