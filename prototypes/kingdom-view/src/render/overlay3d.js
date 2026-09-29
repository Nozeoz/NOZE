// In-world helpers for building: the ghost of what you're placing, its footprint, a light-radius
// ring, the selection box, the edge of the realm, and marks where the road is still dark.
import * as THREE from 'three';
import { buildModel, modelKey } from './models.js';
import { HALF } from './veil.js';
import { objectMatrix } from './objects.js';
import { TYPES } from '../sim/catalog.js';
import { BEACON, idx } from '../sim/world.js';
import { LIT } from '../sim/game.js';

const OK = new THREE.Color('#FFD37A');
const BAD = new THREE.Color('#E0604A');

function circle(r, color, dashed = false) {
  const pts = [];
  for (let i = 0; i <= 96; i++) { const a = (i / 96) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r)); }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = dashed ? new THREE.LineDashedMaterial({ color, dashSize: 0.5, gapSize: 0.35, transparent: true, opacity: 0.85, depthWrite: false }) : new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9, depthWrite: false });
  const line = new THREE.Line(geo, mat);
  if (dashed) line.computeLineDistances();
  line.renderOrder = 20;
  return line;
}

export class Overlay3D {
  constructor(scene) {
    this.scene = scene;
    this.ghostKey = null;
    this.ghost = new THREE.Group();
    scene.add(this.ghost);
    this.ghostMat = new THREE.MeshStandardMaterial({ vertexColors: true, transparent: true, opacity: 0.62, depthWrite: false, emissive: new THREE.Color('#FFD37A'), emissiveIntensity: 0.25 });
    this.tiles = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.92, 0.92).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: '#FFFFFF', transparent: true, opacity: 0.55, depthWrite: false, fog: false }), 64);
    this.tiles.count = 0;
    this.tiles.renderOrder = 21;
    this.tiles.frustumCulled = false;
    scene.add(this.tiles);
    this.lightRing = circle(1, '#FFD37A');
    this.lightRing.visible = false;
    scene.add(this.lightRing);
    this.realm = circle(1, '#F6E5B9', true);
    this.realm.visible = false;
    scene.add(this.realm);
    this.select = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)), new THREE.LineBasicMaterial({ color: '#FFD37A', transparent: true, depthWrite: false }));
    this.select.visible = false;
    this.select.renderOrder = 22;
    scene.add(this.select);
    this.dark = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.5, 0.5).rotateX(-Math.PI / 2).rotateY(Math.PI / 4), new THREE.MeshBasicMaterial({ color: new THREE.Color('#8C6CFF').multiplyScalar(1.6), transparent: true, opacity: 0.8, depthWrite: false, fog: false }), 128);
    this.dark.count = 0;
    this.dark.renderOrder = 21;
    this.dark.frustumCulled = false;
    scene.add(this.dark);
    this.hover = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(0.96, 0.96).rotateX(-Math.PI / 2)), new THREE.LineBasicMaterial({ color: '#FFF3C4', transparent: true, opacity: 0.7, depthWrite: false }));
    this.hover.visible = false;
    this.hover.renderOrder = 22;
    scene.add(this.hover);
  }

  setGhost(game, type, variant, goods) {
    const key = type ? (type === 'stall' ? `stall:${variant}:${goods || 'harvest'}` : `${type}:${variant || 0}`) : null;
    if (key === this.ghostKey) return;
    this.ghostKey = key;
    this.ghost.clear();
    if (!key || type === 'path') return;
    const m = buildModel(key);
    const solid = m.s.build();
    if (solid) this.ghost.add(new THREE.Mesh(solid, this.ghostMat));
    const glow = m.g.build();
    if (glow) this.ghost.add(new THREE.Mesh(glow, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.7, depthWrite: false })));
  }

  // state: { mode, placing: {type, x, z, rot, ok, tiles}, selected, hoverTile, showDark }
  update(game, state, time) {
    const p = state.placing;
    this.ghost.visible = !!(p && p.type !== 'path' && p.x !== undefined);
    this.lightRing.visible = false;
    let n = 0;
    const m = new THREE.Matrix4();
    if (p && p.x !== undefined) {
      const def = TYPES[p.type];
      const { w, d } = game.size(p.type, p.rot);
      if (this.ghost.visible) {
        objectMatrix({ x: p.x, z: p.z, w, d, rot: p.rot }, 1, m);
        this.ghost.matrixAutoUpdate = false;
        this.ghost.matrix.copy(m);
        this.ghost.matrixWorldNeedsUpdate = true;
        this.ghostMat.opacity = p.ok ? 0.66 : 0.4;
        this.ghostMat.emissive.copy(p.ok ? OK : BAD);
      }
      const tiles = p.tiles || game.tiles(p.x, p.z, w, d);
      for (const [x, z] of tiles.slice(0, 64)) {
        m.makeTranslation(x + 0.5 - HALF, 0.07, z + 0.5 - HALF);
        this.tiles.setMatrixAt(n, m);
        this.tiles.setColorAt(n, p.ok ? OK : BAD);
        n++;
      }
      const r = def.light || (def.lights && def.lights[0][2]);
      if (r && this.ghost.visible) {
        this.lightRing.visible = true;
        this.lightRing.position.set(p.x + w / 2 - HALF, 0.08, p.z + d / 2 - HALF);
        this.lightRing.scale.setScalar(r * (1 - LIT));
      }
    }
    this.tiles.count = n;
    this.tiles.instanceMatrix.needsUpdate = true;
    if (this.tiles.instanceColor) this.tiles.instanceColor.needsUpdate = true;
    // The realm's edge, while building.
    this.realm.visible = state.mode === 'build';
    if (this.realm.visible) {
      this.realm.position.set(BEACON.x - HALF, 0.06, BEACON.z - HALF);
      this.realm.scale.setScalar(game.realmRadius());
      this.realm.material.opacity = 0.55 + 0.25 * Math.sin(time * 2);
    }
    // Where the road is still dark at night.
    let k = 0;
    if (state.showDark) {
      const L = game.staticLight();
      for (const [x, z] of game.route()) {
        if (L[idx(x, z)] >= LIT || k >= 128) continue;
        m.compose(new THREE.Vector3(x + 0.5 - HALF, 0.09 + Math.sin(time * 3 + x + z) * 0.02, z + 0.5 - HALF), new THREE.Quaternion(), new THREE.Vector3(1, 1, 1));
        this.dark.setMatrixAt(k++, m);
      }
    }
    this.dark.count = k;
    this.dark.instanceMatrix.needsUpdate = true;
    // Selection box
    const o = state.selected ? game.objects.get(state.selected) : null;
    this.select.visible = !!o;
    if (o) {
      const h = { lamp: 1.9, string: 2.1, stall: 1.7, tree: 1.7, banner: 2.1, beacon: 2.4, lodge: 2.7, herbalist: 2.2, hut: 2.2, cookhouse: 2.3 }[o.type] || 1.2;
      this.select.position.set(o.x + o.w / 2 - HALF, h / 2, o.z + o.d / 2 - HALF);
      this.select.scale.set(o.w + 0.08, h, o.d + 0.08);
      this.select.material.opacity = 0.65 + 0.3 * Math.sin(time * 4);
    }
    // Hovered tile
    const hv = state.hoverTile;
    this.hover.visible = !!hv && !p;
    if (hv) this.hover.position.set(hv[0] + 0.5 - HALF, 0.08, hv[1] + 0.5 - HALF);
  }
}

export { modelKey };
