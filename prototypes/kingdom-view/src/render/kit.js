// A tiny low-poly modelling kit: stack primitives with colours, then merge them into one
// vertex-coloured geometry (one draw call per model). Units are tiles; y is up; models face +z.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

const tmpColor = new THREE.Color();

export class Kit {
  constructor() { this.parts = []; }

  add(geo, color, { x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1, intensity = 1 } = {}) {
    const g = geo.index ? geo.toNonIndexed() : geo;
    const m = new THREE.Matrix4().compose(
      new THREE.Vector3(x, y, z),
      new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz, 'YXZ')),
      new THREE.Vector3(sx, sy, sz),
    );
    g.applyMatrix4(m);
    for (const name of Object.keys(g.attributes)) if (name !== 'position' && name !== 'normal') g.deleteAttribute(name);
    tmpColor.set(color);
    const n = g.attributes.position.count;
    const col = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { col[i * 3] = tmpColor.r * intensity; col[i * 3 + 1] = tmpColor.g * intensity; col[i * 3 + 2] = tmpColor.b * intensity; }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    this.parts.push(g);
    return this;
  }

  // Box sitting on y (its bottom at y).
  box(w, h, d, color, o = {}) { return this.add(new THREE.BoxGeometry(w, h, d), color, { ...o, y: (o.y || 0) + h / 2 }); }
  // Cylinder sitting on y.
  cyl(rt, rb, h, seg, color, o = {}) { return this.add(new THREE.CylinderGeometry(rt, rb, h, seg), color, { ...o, y: (o.y || 0) + h / 2 }); }
  cone(r, h, seg, color, o = {}) { return this.add(new THREE.ConeGeometry(r, h, seg), color, { ...o, y: (o.y || 0) + h / 2 }); }
  sphere(r, color, o = {}, ws = 10, hs = 8) { return this.add(new THREE.SphereGeometry(r, ws, hs), color, o); }
  ico(r, color, o = {}, detail = 0) { return this.add(new THREE.IcosahedronGeometry(r, detail), color, o); }
  torus(r, t, color, o = {}, rs = 6, ts = 12) { return this.add(new THREE.TorusGeometry(r, t, rs, ts), color, o); }
  // The top part of a sphere (hair, hoods, caps). `cover` is the fraction of the sphere, from the top.
  cap(r, color, o = {}, cover = 0.55, ws = 12, hs = 8) { return this.add(new THREE.SphereGeometry(r, ws, hs, 0, Math.PI * 2, 0, Math.PI * cover), color, o); }

  // A gable roof: ridge along x, width w (x), depth d (z), height h, sitting on y.
  roof(w, d, h, color, o = {}) {
    const hw = w / 2;
    const hd = d / 2;
    const shape = new THREE.Shape();
    shape.moveTo(-hd, 0);
    shape.lineTo(hd, 0);
    shape.lineTo(0, h);
    shape.closePath();
    const geo = new THREE.ExtrudeGeometry(shape, { depth: w, bevelEnabled: false });
    geo.translate(0, 0, -hw);
    geo.rotateY(Math.PI / 2);
    return this.add(geo, color, o);
  }

  // A pyramid roof (four slopes).
  hip(w, d, h, color, o = {}) {
    const geo = new THREE.ConeGeometry(Math.SQRT1_2, 1, 4, 1);
    geo.rotateY(Math.PI / 4);
    return this.add(geo, color, { ...o, y: (o.y || 0) + h / 2, sx: w, sy: h, sz: d });
  }

  // A thin rope or pole from a to b.
  beam(a, b, r, color, seg = 5) {
    const va = new THREE.Vector3(...a);
    const vb = new THREE.Vector3(...b);
    const len = va.distanceTo(vb);
    const geo = new THREE.CylinderGeometry(r, r, len, seg);
    geo.translate(0, len / 2, 0);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), vb.clone().sub(va).normalize());
    geo.applyQuaternion(q);
    geo.translate(va.x, va.y, va.z);
    return this.add(geo, color);
  }

  build() {
    if (!this.parts.length) return null;
    const merged = mergeGeometries(this.parts, false);
    merged.computeBoundingSphere();
    merged.computeBoundingBox();
    return merged;
  }
}

// Deterministic pseudo-random numbers for decorating models.
export function hashRand(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
