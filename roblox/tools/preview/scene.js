import * as THREE from 'three';
const params = new URLSearchParams(location.search);
const view = params.get('view') || 'plot';
const night = params.get('night') === '1';
const data = window.DATA;
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(1);
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = night ? 0.9 : 1.05;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const sky = night ? 0x2a2450 : 0xcfe0ea;
scene.background = new THREE.Color(sky);
scene.fog = view === 'overview' ? null : new THREE.Fog(sky, 380, 1100);
scene.add(new THREE.HemisphereLight(night ? 0x6c62b0 : 0xfff4e0, night ? 0x1c1830 : 0x6a7f5a, night ? 0.5 : 1.15));
const sun = new THREE.DirectionalLight(night ? 0x9aa0ff : 0xfff0d8, night ? 0.35 : 1.7);
sun.position.set(160, 260, 120);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
const sc = sun.shadow.camera;
sc.left = -420; sc.right = 420; sc.top = 420; sc.bottom = -420; sc.near = 10; sc.far = 900;
scene.add(sun);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(2600, 2600), new THREE.MeshStandardMaterial({ color: night ? 0x3d4a45 : 0x7fa85a, roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.02;
ground.receiveShadow = view !== 'overview';
scene.add(ground);

// Roblox WedgePart: full height at +Z, sloping down to -Z.
function wedgeGeo() {
  const A = (x) => [x, -0.5, -0.5], B = (x) => [x, -0.5, 0.5], C = (x) => [x, 0.5, 0.5];
  const tri = (a, b, c) => [...a, ...b, ...c];
  const quad = (a, b, c, d) => [...tri(a, b, c), ...tri(a, c, d)];
  const L = -0.5, R = 0.5;
  const v = [
    ...tri(A(L), C(L), B(L)),
    ...tri(A(R), B(R), C(R)),
    ...quad(A(L), B(L), B(R), A(R)),
    ...quad(B(L), C(L), C(R), B(R)),
    ...quad(A(L), A(R), C(R), C(L)),
  ];
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
  g.computeVertexNormals();
  return g;
}
const WEDGE = wedgeGeo();
const BOX = new THREE.BoxGeometry(1, 1, 1);
const SPHERE = new THREE.SphereGeometry(0.5, 18, 12);
const CYL = new THREE.CylinderGeometry(0.5, 0.5, 1, 18); CYL.rotateZ(Math.PI / 2);
const mats = new Map();
function material(c, m, t) {
  const key = c.join(',') + m + t;
  if (mats.has(key)) return mats.get(key);
  const color = new THREE.Color(`rgb(${c[0]},${c[1]},${c[2]})`);
  const neon = m === 'Neon';
  const mat = new THREE.MeshStandardMaterial({
    color, roughness: m === 'Metal' || m === 'Glass' ? 0.35 : 0.85, metalness: m === 'Metal' ? 0.5 : 0,
    emissive: neon ? color : new THREE.Color(0), emissiveIntensity: neon ? (night ? 2.2 : 0.9) : 0,
    transparent: t > 0 || m === 'ForceField' || m === 'Glass', opacity: m === 'ForceField' ? 0.35 : (m === 'Glass' ? Math.min(1 - t, 0.75) : 1 - t),
    side: THREE.DoubleSide,
  });
  mats.set(key, mat);
  return mat;
}
let lights = 0;
for (const p of data.parts) {
  let geo, sx = p.z[0], sy = p.z[1], sz = p.z[2];
  if (p.s === 'W') geo = WEDGE;
  else if (p.s === 'S') { geo = SPHERE; const d = Math.min(sx, sy, sz); sx = sy = sz = d; }
  else if (p.s === 'Y') { geo = CYL; const d = Math.min(sy, sz); sy = sz = d; }
  else if (p.s === 'E') geo = SPHERE;
  else geo = BOX;
  const mesh = new THREE.Mesh(geo, material(p.c, p.m, p.t));
  const f = p.f;
  const m4 = new THREE.Matrix4().set(f[3], f[4], f[5], f[0], f[6], f[7], f[8], f[1], f[9], f[10], f[11], f[2], 0, 0, 0, 1);
  m4.multiply(new THREE.Matrix4().makeScale(sx, sy, sz));
  mesh.matrixAutoUpdate = false;
  mesh.matrix.copy(m4);
  mesh.castShadow = p.t < 0.5 && p.m !== 'Neon';
  mesh.receiveShadow = true;
  scene.add(mesh);
  if (night && p.l && lights < 60) {
    lights++;
    const l = new THREE.PointLight(new THREE.Color(`rgb(${p.l[2][0]},${p.l[2][1]},${p.l[2][2]})`), p.l[1] * 30, p.l[0] * 1.2, 1.6);
    l.position.set(f[0], f[1], f[2]);
    scene.add(l);
  }
}
// ponds (terrain water) as flat quads
function plotCF(i) {
  const row = Math.floor((i - 1) / 3), col = (i - 1) % 3;
  return row === 0 ? { x: -292 + col * 204, z: -216, rot: 0 } : { x: -112 + col * 204, z: 216, rot: Math.PI };
}
function toWorld(i, lx, lz) {
  const c = plotCF(i);
  const s = c.rot ? -1 : 1;
  return new THREE.Vector3(c.x + s * lx * 6, 0, c.z + s * lz * 6);
}
for (let i = 1; i <= 6; i++) {
  const w = new THREE.Mesh(new THREE.PlaneGeometry(24, 24), new THREE.MeshStandardMaterial({ color: 0x5fa8bd, roughness: 0.2, metalness: 0.1 }));
  const c = toWorld(i, 10, 8);
  w.position.set(c.x, 0.05, c.z);
  w.rotation.x = -Math.PI / 2;
  scene.add(w);
}
// the avenue
const ave = new THREE.Mesh(new THREE.PlaneGeometry(620, 48), new THREE.MeshStandardMaterial({ color: night ? 0x5a5550 : 0xa69884, roughness: 1 }));
ave.rotation.x = -Math.PI / 2; ave.position.set(2, 0.01, 0); ave.receiveShadow = true; scene.add(ave);

const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 1, 3000);
const plot = data.plot || 2;
const heart = toWorld(plot, 15, 13);
const toAve = plotCF(plot).rot ? -1 : 1;
const views = {
  overview: [[2, 430, 330], [2, 0, -10]],
  plot: [[heart.x, 120, heart.z + toAve * 150], [heart.x, 0, heart.z + toAve * 22]],
  close: [[heart.x + 55, 48, heart.z + toAve * 75], [heart.x, 2, heart.z + toAve * 22]],
  road: [[heart.x - 30, 30, heart.z + toAve * 200], [heart.x, 2, heart.z + toAve * 60]],
  hub: [[70, 60, 90], [2, 0, 0]],
  cat1: [[-150, 38, 470], [-150, 5, 420]],
  cat2: [[-60, 38, 470], [-60, 5, 420]],
  cat3: [[30, 38, 470], [30, 5, 420]],
  cat4: [[120, 38, 470], [120, 5, 420]],
  cat5: [[210, 38, 470], [210, 5, 420]],
  hearts: [[-170, 34, 505], [-170, 8, 460]],
  actors: [[-160, 12, 515], [-160, 2, 490]],
  actors2: [[-110, 12, 515], [-110, 2, 490]],
};
const v = views[view] || views.plot;
camera.position.set(...v[0]);
camera.lookAt(new THREE.Vector3(...v[1]));
renderer.render(scene, camera);
document.title = 'done ' + data.parts.length;
