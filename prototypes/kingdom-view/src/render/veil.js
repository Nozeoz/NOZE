// The Veil: a living mist that fills every unlit place at night (docs/08 §8).
// A small texture holds the light level of every tile. Lit materials read it to fade toward a
// desaturated violet-teal in the dark, and two drifting mist layers hug the ground.
import * as THREE from 'three';
import { W, H, T, idx } from '../sim/world.js';
import { VISITOR_KINDS } from '../sim/catalog.js';
import { P } from './palette.js';

export const MARGIN = 10;
export const TEX = W + MARGIN * 2; // 64 texels, one per tile, with a margin of forest all round
export const HALF = 22; // world x = tile x − 22

export const veilUniforms = {
  uVeilTex: { value: null },
  uVeilOrigin: { value: new THREE.Vector2(-HALF - MARGIN, -HALF - MARGIN) },
  uVeilSize: { value: TEX },
  uNight: { value: 0 },
  uTime: { value: 0 },
  uVeilA: { value: new THREE.Color(P.veilA) },
  uVeilB: { value: new THREE.Color(P.veilB) },
};

const PARS = `
uniform sampler2D uVeilTex;
uniform vec2 uVeilOrigin;
uniform float uVeilSize;
uniform float uNight;
uniform float uTime;
uniform vec3 uVeilA;
uniform vec3 uVeilB;
varying vec3 vVeilPos;
`;

const FRAG = `
#include <fog_fragment>
{
  vec4 vt = texture2D(uVeilTex, (vVeilPos.xz - uVeilOrigin) / uVeilSize);
  float dark = uNight * (1.0 - smoothstep(0.12, 0.55, vt.r));
  dark = max(dark, uNight * vt.g * 0.92);
  float lum = dot(gl_FragColor.rgb, vec3(0.299, 0.587, 0.114));
  vec3 desat = mix(gl_FragColor.rgb, vec3(lum), 0.55 * dark);
  float n = sin(vVeilPos.x * 0.35 + uTime * 0.15) * sin(vVeilPos.z * 0.29 - uTime * 0.11);
  vec3 veil = mix(uVeilA, uVeilB, 0.5 + 0.5 * n);
  gl_FragColor.rgb = mix(desat, desat * 0.42 + veil * 0.05, dark * 0.88);
}
`;

// Makes a lit material fade into the Veil where there is no light at night.
export function veilify(material) {
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, veilUniforms);
    shader.vertexShader = shader.vertexShader
      .replace('#include <fog_pars_vertex>', `#include <fog_pars_vertex>\nvarying vec3 vVeilPos;`)
      .replace('#include <fog_vertex>', `#include <fog_vertex>
#ifdef USE_INSTANCING
  vVeilPos = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).xyz;
#else
  vVeilPos = (modelMatrix * vec4(transformed, 1.0)).xyz;
#endif`);
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <fog_pars_fragment>', `#include <fog_pars_fragment>\n${PARS}`)
      .replace('#include <fog_fragment>', FRAG);
  };
  material.customProgramCacheKey = () => 'veil';
  return material;
}

export class Veil {
  constructor(scene) {
    this.data = new Uint8Array(TEX * TEX * 4);
    this.tex = new THREE.DataTexture(this.data, TEX, TEX, THREE.RGBAFormat);
    this.tex.magFilter = THREE.LinearFilter;
    this.tex.minFilter = THREE.LinearFilter;
    this.tex.wrapS = this.tex.wrapT = THREE.ClampToEdgeWrapping;
    this.tex.needsUpdate = true;
    veilUniforms.uVeilTex.value = this.tex;
    for (let i = 0; i < TEX * TEX; i++) { this.data[i * 4 + 1] = 255; this.data[i * 4 + 3] = 255; }
    this.layers = [0, 1].map(layer => {
      const mat = new THREE.ShaderMaterial({
        uniforms: { ...veilUniforms, uLayer: { value: layer } },
        vertexShader: `varying vec3 vPos; void main() { vec4 wp = modelMatrix * vec4(position, 1.0); vPos = wp.xyz; gl_Position = projectionMatrix * viewMatrix * wp; }`,
        fragmentShader: MIST,
        transparent: true,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(TEX, TEX, 1, 1).rotateX(-Math.PI / 2), mat);
      mesh.position.y = layer ? 1.0 : 0.32;
      mesh.renderOrder = 10 + layer;
      mesh.frustumCulled = false;
      scene.add(mesh);
      return mesh;
    });
    this.timer = 0;
  }

  // Light from buildings (static) plus the Sovereign's Flicker and lantern-carrying visitors.
  update(game, dt, force = false) {
    this.timer -= dt;
    if (this.timer > 0 && !force) return;
    this.timer = 0.12;
    const L = game.staticLight();
    const dyn = [[game.player.x, game.player.z, 2.4]];
    for (const v of game.visitors) { const r = VISITOR_KINDS[v.kind].lantern; if (r) dyn.push([v.x, v.z, r]); }
    const d = this.data;
    for (let j = 0; j < TEX; j++) {
      for (let i = 0; i < TEX; i++) {
        const x = i - MARGIN;
        const z = j - MARGIN;
        const k = (j * TEX + i) * 4;
        if (x < 0 || z < 0 || x >= W || z >= H) { d[k] = 0; d[k + 1] = 255; continue; }
        let l = L[idx(x, z)];
        for (const [sx, sz, r] of dyn) {
          const f = 1 - Math.hypot(x + 0.5 - sx, z + 0.5 - sz) / r;
          if (f > l) l = f;
        }
        d[k] = Math.round(Math.max(0, Math.min(1, l)) * 255);
        d[k + 1] = game.terrain[idx(x, z)] === T.FOREST ? 255 : 0;
      }
    }
    this.tex.needsUpdate = true;
  }
}

const MIST = `
uniform sampler2D uVeilTex;
uniform vec2 uVeilOrigin;
uniform float uVeilSize;
uniform float uNight;
uniform float uTime;
uniform vec3 uVeilA;
uniform vec3 uVeilB;
uniform float uLayer;
varying vec3 vPos;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0; float a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }
void main() {
  vec4 vt = texture2D(uVeilTex, (vPos.xz - uVeilOrigin) / uVeilSize);
  float dens = max(1.0 - smoothstep(0.06, 0.5, vt.r), vt.g * 0.9);
  vec2 q = vPos.xz * (0.17 + uLayer * 0.08) + vec2(uTime * 0.05, -uTime * 0.035) * (1.0 + uLayer);
  float n = fbm(q + fbm(q * 0.6 + uTime * 0.03));
  float a = uNight * dens * smoothstep(0.3, 0.8, n) * (0.62 - uLayer * 0.24);
  float edge = smoothstep(0.08, 0.22, vt.r) * (1.0 - smoothstep(0.22, 0.42, vt.r)) * (1.0 - vt.g);
  vec3 col = mix(uVeilA, uVeilB, n) * 0.42 + vec3(0.015, 0.015, 0.04);
  col += vec3(1.0, 0.78, 0.4) * edge * 0.12;
  a += uNight * edge * 0.05 * smoothstep(0.35, 0.7, n);
  gl_FragColor = vec4(col, a);
}
`;
