// The 3D view: renderer, diorama camera, post effects (bloom and tilt-shift), and every layer
// of the scene. `frame()` draws one frame from the simulation state.
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { Terrain } from './terrain.js';
import { Veil, veilUniforms, HALF } from './veil.js';
import { Lighting } from './lighting.js';
import { ObjectRenderer } from './objects.js';
import { AgentRenderer } from './agents.js';
import { Effects } from './fx.js';
import { Overlay3D } from './overlay3d.js';

export const QUALITY = {
  high: { label: 'High', pixelRatio: 2, shadows: true, shadowSize: 2048, bloom: true, tilt: true, msaa: 4, pool: 8 },
  medium: { label: 'Medium', pixelRatio: 1.25, shadows: true, shadowSize: 1024, bloom: true, tilt: true, msaa: 0, pool: 6 },
  low: { label: 'Low', pixelRatio: 1, shadows: false, shadowSize: 512, bloom: false, tilt: false, msaa: 0, pool: 3 },
};

const TiltShift = {
  uniforms: { tDiffuse: { value: null }, uDir: { value: new THREE.Vector2(1, 0) }, uFocus: { value: 0.5 }, uBand: { value: 0.17 }, uAmount: { value: 2.2 } },
  vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D tDiffuse; uniform vec2 uDir; uniform float uFocus; uniform float uBand; uniform float uAmount; varying vec2 vUv;
    void main() {
      float b = smoothstep(uBand, uBand + 0.3, abs(vUv.y - uFocus)) * uAmount;
      vec4 sum = vec4(0.0); float ws = 0.0;
      for (int i = -4; i <= 4; i++) { float w = exp(-float(i * i) / 8.0); sum += texture2D(tDiffuse, vUv + uDir * float(i) * b) * w; ws += w; }
      gl_FragColor = sum / ws;
    }`,
};

const Grade = {
  uniforms: { tDiffuse: { value: null }, uVignette: { value: 0.32 }, uNight: { value: 0 } },
  vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uVignette; uniform float uNight; varying vec2 vUv;
    void main() {
      vec4 c = texture2D(tDiffuse, vUv);
      vec2 d = vUv - 0.5; d.x *= 1.25;
      float v = smoothstep(0.85, 0.25, length(d));
      c.rgb *= mix(1.0 - uVignette, 1.0, v);
      c.rgb = mix(c.rgb, c.rgb * vec3(0.93, 0.96, 1.08), uNight * 0.35);
      gl_FragColor = c;
    }`,
};

export class CameraRig {
  constructor(camera) {
    this.camera = camera;
    this.target = new THREE.Vector3(0, 0, -2);
    this.goal = this.target.clone();
    this.yaw = 0.42;
    this.goalYaw = this.yaw;
    this.pitch = 0.92;
    this.dist = 30;
    this.goalDist = this.dist;
    this.min = 9;
    this.max = 62;
  }
  pan(dx, dz) {
    const c = Math.cos(this.yaw);
    const s = Math.sin(this.yaw);
    this.goal.x += dx * c + dz * s;
    this.goal.z += -dx * s + dz * c;
    this.clamp();
  }
  clamp() {
    this.goal.x = Math.max(-HALF - 2, Math.min(HALF + 2, this.goal.x));
    this.goal.z = Math.max(-HALF - 2, Math.min(HALF + 4, this.goal.z));
  }
  zoom(f) { this.goalDist = Math.max(this.min, Math.min(this.max, this.goalDist * f)); }
  rotate(d) { this.goalYaw += d; }
  follow(x, z) { this.goal.set(x, 0, z); }
  update(dt) {
    const k = 1 - Math.exp(-dt * 7);
    this.target.lerp(this.goal, k);
    this.yaw += (this.goalYaw - this.yaw) * k;
    this.dist += (this.goalDist - this.dist) * k;
    const cp = Math.cos(this.pitch);
    this.camera.position.set(
      this.target.x + Math.sin(this.yaw) * cp * this.dist,
      this.target.y + Math.sin(this.pitch) * this.dist,
      this.target.z + Math.cos(this.yaw) * cp * this.dist,
    );
    this.camera.lookAt(this.target);
  }
}

export class View {
  constructor(container, game, qualityName = 'high') {
    this.container = container;
    this.game = game;
    this.qualityName = qualityName;
    this.q = QUALITY[qualityName];
    this.renderer = new THREE.WebGLRenderer({ antialias: !this.q.bloom && !this.q.tilt, powerPreference: 'high-performance', preserveDrawingBuffer: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.q.pixelRatio));
    this.renderer.shadowMap.enabled = this.q.shadows;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    container.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(30, 1, 0.5, 260);
    this.rig = new CameraRig(this.camera);
    this.veil = new Veil(this.scene);
    this.lighting = new Lighting(this.scene, { shadows: this.q.shadows, shadowSize: this.q.shadowSize, pool: this.q.pool });
    this.terrain = new Terrain(this.scene, game, { shadows: this.q.shadows });
    this.objects = new ObjectRenderer(this.scene, { shadows: this.q.shadows });
    this.agents = new AgentRenderer(this.scene, { shadows: this.q.shadows });
    this.fx = new Effects(this.scene, game);
    this.overlay = new Overlay3D(this.scene);
    this.buildComposer();
    this.raycaster = new THREE.Raycaster();
    this.ground = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    this.time = 0;
    this.resize();
    this.veil.update(game, 0, true);
  }

  buildComposer() {
    const size = this.renderer.getSize(new THREE.Vector2());
    const target = new THREE.WebGLRenderTarget(Math.max(1, size.x), Math.max(1, size.y), { type: THREE.HalfFloatType, samples: this.q.msaa });
    this.composer = new EffectComposer(this.renderer, target);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.8, 0.5, 1.0);
    this.bloom.enabled = this.q.bloom;
    this.composer.addPass(this.bloom);
    this.tiltH = new ShaderPass(TiltShift);
    this.tiltV = new ShaderPass(TiltShift);
    this.tiltH.enabled = this.tiltV.enabled = this.q.tilt;
    this.composer.addPass(this.tiltH);
    this.composer.addPass(this.tiltV);
    this.grade = new ShaderPass(Grade);
    this.composer.addPass(this.grade);
    this.composer.addPass(new OutputPass());
  }

  resize() {
    const w = Math.max(1, this.container.clientWidth);
    const h = Math.max(1, this.container.clientHeight);
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = '100%';
    this.renderer.domElement.style.height = '100%';
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.composer.setSize(w, h);
    const pr = this.renderer.getPixelRatio();
    this.bloom.resolution.set(w * pr / 2, h * pr / 2);
    this.tiltH.uniforms.uDir.value.set(1 / (w * pr), 0);
    this.tiltV.uniforms.uDir.value.set(0, 1 / (h * pr));
    const px = (h * pr) / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)));
    this.objects.smoke.mat.uniforms.uScale.value = px;
    this.fx.setScale(px);
    this.width = w;
    this.height = h;
  }

  // Screen point → tile under it (and the world point on the ground).
  pick(clientX, clientY) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(ndc, this.camera);
    const hit = new THREE.Vector3();
    if (!this.raycaster.ray.intersectPlane(this.ground, hit)) return null;
    return { x: hit.x, z: hit.z, tx: Math.floor(hit.x + HALF), tz: Math.floor(hit.z + HALF) };
  }

  project(x, y, z) {
    const v = new THREE.Vector3(x, y, z).project(this.camera);
    return { x: (v.x * 0.5 + 0.5) * this.width, y: (-v.y * 0.5 + 0.5) * this.height, behind: v.z > 1 };
  }

  frame(game, dt, uiState) {
    this.time += dt;
    const time = this.time;
    const night = game.nightFactor();
    veilUniforms.uNight.value = night;
    veilUniforms.uTime.value = time;
    this.rig.update(dt);
    this.veil.update(game, dt);
    this.terrain.sync();
    this.terrain.update(time, night);
    this.objects.sync(game, time);
    this.objects.update(dt, time, night, 0.45 + night * 0.75);
    this.agents.update(game, dt, time, night);
    this.fx.update(game, dt, time, night);
    this.overlay.update(game, uiState, time);
    this.lighting.update({
      minute: game.minute, night, target: this.rig.target, lights: this.objects.lights, lightsVersion: this.objects.lightsVersion, dt,
      flicker: this.agents.flicker,
    });
    this.grade.uniforms.uNight.value = night;
    this.bloom.strength = 0.3 + night * 0.5;
    this.composer.render(dt);
  }
}
