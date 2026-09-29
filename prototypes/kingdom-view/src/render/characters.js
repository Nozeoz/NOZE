// Chibi placeholder figures: visitors, Veilkin creatures, the Sworn, settlers, and the Sovereign.
// About one tile tall, facing +z. Each kind comes in a few colour variants.
import { Kit } from './kit.js';
import { P } from './palette.js';

const EYE = '#2A1E18';
const BLUSH = '#F2A0A0';
const SHOE = '#3A2E26';

function humanoid(m, { robe, robe2 = robe, skin = P.skin, hair = P.hair, long = false }) {
  for (const x of [-0.07, 0.07]) m.s.box(0.08, 0.08, 0.13, SHOE, { x, z: 0.02 });
  m.s.cyl(0.16, 0.24, 0.42, 8, robe, { y: 0.05 });
  m.s.cyl(0.175, 0.175, 0.05, 8, robe2, { y: 0.3 });
  for (const sx of [-1, 1]) {
    m.s.sphere(0.068, robe, { x: sx * 0.2, y: 0.33, z: 0.02, sy: 1.6 }, 6, 5);
    m.s.sphere(0.045, skin, { x: sx * 0.215, y: 0.21, z: 0.05 }, 6, 5);
  }
  m.s.sphere(0.215, skin, { y: 0.66 }, 12, 10);
  for (const sx of [-1, 1]) {
    m.s.sphere(0.03, EYE, { x: sx * 0.078, y: 0.665, z: 0.195, sz: 0.45 }, 6, 5);
    m.s.sphere(0.032, BLUSH, { x: sx * 0.125, y: 0.61, z: 0.175, sz: 0.3 }, 6, 4);
  }
  if (hair) {
    m.s.cap(0.23, hair, { y: 0.67, z: -0.02, rx: -0.45 }, 0.56);
    if (long) m.s.cyl(0.17, 0.2, 0.36, 10, hair, { y: 0.36, z: -0.08 });
  }
}

const VARIANTS = {
  traveler: [{ robe: '#5E7A55', hood: '#4B6346' }, { robe: '#7A5E45', hood: '#664C36' }, { robe: '#4F6275', hood: '#3F5063' }],
  merchant: [{ robe: '#8C4A3A', hat: '#3A2E2A' }, { robe: '#3F5A7A', hat: '#2E2A3A' }],
  farmer: [{ robe: '#B89A5A' }, { robe: '#7F9A5A' }],
  monk: [{ robe: '#E8DCC0' }],
  villager: [{ robe: '#A06A4A', apron: '#E9DFC8' }, { robe: '#5E7A8A', apron: '#E3D8BC' }, { robe: '#8A6A9A', apron: '#EDE3CD' }, { robe: '#6A8A5A', apron: '#E3D8BC' }],
  mossbun: [{}], puddlepup: [{}], emberkit: [{}], sovereign: [{}], bram: [{}], linnea: [{}], hob: [{}],
};
export const variantCount = kind => (VARIANTS[kind] || [{}]).length;

const HAIRS = [P.hair, '#2E2420', '#B0703A', '#D9C08A'];

export function buildCharacter(kind, variant = 0) {
  const m = { s: new Kit(), g: new Kit() };
  const v = (VARIANTS[kind] || [{}])[variant % variantCount(kind)];
  switch (kind) {
    case 'traveler':
      humanoid(m, { robe: v.robe, hair: null, skin: [P.skin, P.skin2, P.skin3][variant % 3] });
      m.s.cap(0.25, v.hood, { y: 0.67, z: -0.03, rx: -0.3 }, 0.62);
      m.s.cone(0.26, 0.5, 8, v.hood, { y: 0.1, z: -0.08, rx: -0.12 });
      m.s.cyl(0.018, 0.018, 1.05, 5, P.woodDark, { x: 0.27, z: 0.08 });
      break;
    case 'merchant':
      humanoid(m, { robe: v.robe, robe2: P.gold, hair: HAIRS[variant + 1] });
      m.s.cyl(0.34, 0.34, 0.025, 12, v.hat, { y: 0.8 });
      m.s.cyl(0.16, 0.18, 0.14, 10, v.hat, { y: 0.8 });
      m.s.cone(0.02, 0.26, 4, P.berry, { x: 0.12, y: 0.86, z: -0.06, rz: -0.6 });
      m.s.box(0.3, 0.34, 0.16, '#8A6A4A', { y: 0.2, z: -0.26 });
      m.s.box(0.32, 0.06, 0.18, '#6A4E36', { y: 0.52, z: -0.26 });
      break;
    case 'farmer':
      humanoid(m, { robe: v.robe, robe2: '#6A4E36', hair: HAIRS[variant] });
      m.s.cyl(0.33, 0.33, 0.025, 12, P.thatch, { y: 0.8 });
      m.s.cone(0.18, 0.16, 10, P.thatch, { y: 0.8 });
      m.s.box(0.3, 0.26, 0.02, '#E3D8BC', { y: 0.1, z: 0.2 });
      break;
    case 'monk':
      humanoid(m, { robe: v.robe, robe2: P.gold, hair: null, skin: P.skin2 });
      m.s.cap(0.25, '#D9C9A6', { y: 0.67, z: -0.04, rx: -0.2 }, 0.6);
      m.s.cyl(0.012, 0.012, 0.22, 4, P.iron, { x: 0.2, y: 0.24, z: 0.2 });
      m.s.hip(0.13, 0.13, 0.06, P.iron, { x: 0.2, y: 0.24, z: 0.2 });
      m.g.box(0.1, 0.13, 0.1, P.heartflame, { x: 0.2, y: 0.1, z: 0.2, intensity: 3 });
      break;
    case 'villager':
      humanoid(m, { robe: v.robe, robe2: '#5A4636', hair: HAIRS[variant % 4] });
      m.s.box(0.3, 0.3, 0.02, v.apron, { y: 0.08, z: 0.2 });
      break;
    case 'hob':
      humanoid(m, { robe: '#5E6E8A', robe2: '#4A3A2E', hair: '#C9C2B2', skin: P.skin2 });
      m.s.cyl(0.35, 0.35, 0.025, 12, P.thatch, { y: 0.82 });
      m.s.cone(0.18, 0.16, 10, P.thatch, { y: 0.82 });
      m.s.sphere(0.1, '#E8E2D2', { y: 0.55, z: 0.17, sy: 0.7 }, 8, 6);
      break;
    case 'bram':
      humanoid(m, { robe: '#6B4E3A', robe2: '#3A2A20', hair: '#7A4A2A', skin: P.skin2 });
      m.s.sphere(0.16, '#7A4A2A', { y: 0.53, z: 0.12, sy: 0.8 }, 8, 6);
      m.s.box(0.32, 0.36, 0.02, '#8A6A4A', { y: 0.06, z: 0.21 });
      m.s.box(0.05, 0.26, 0.05, P.woodDark, { x: 0.25, y: 0.12, z: 0.1 });
      m.s.box(0.14, 0.07, 0.07, P.iron, { x: 0.25, y: 0.36, z: 0.1 });
      break;
    case 'linnea':
      humanoid(m, { robe: '#6F9B6A', robe2: '#E9DFC8', hair: '#C0703A', long: true });
      m.s.ico(0.05, P.lotus, { x: 0.15, y: 0.8, z: 0.06 });
      m.s.box(0.3, 0.28, 0.02, '#EFE6D2', { y: 0.08, z: 0.2 });
      break;
    case 'sovereign':
      humanoid(m, { robe: '#8E2F3A', robe2: P.gold, hair: '#E9E1D0', skin: P.skin });
      m.s.cone(0.3, 0.62, 9, '#6E1F2A', { y: 0.02, z: -0.1, rx: -0.1 });
      m.s.cyl(0.2, 0.2, 0.05, 10, '#F3E7CE', { y: 0.46 });
      m.s.torus(0.12, 0.022, P.gold, { y: 0.87, rx: Math.PI / 2 }, 5, 12);
      for (let i = 0; i < 5; i++) {
        const a = (i / 5) * Math.PI * 2;
        m.s.cone(0.03, 0.09, 4, P.gold, { x: Math.cos(a) * 0.12, y: 0.87, z: Math.sin(a) * 0.12 });
      }
      break;
    case 'mossbun':
      m.s.sphere(0.25, '#8DB266', { y: 0.25, sy: 0.9 }, 12, 9);
      m.s.sphere(0.16, '#C9DE9A', { y: 0.2, z: 0.12, sy: 0.9 }, 10, 8);
      for (const sx of [-1, 1]) {
        m.s.sphere(0.06, '#7FA35A', { x: sx * 0.1, y: 0.56, z: -0.02, sy: 2.6, rz: sx * 0.25 }, 6, 5);
        m.s.sphere(0.028, EYE, { x: sx * 0.09, y: 0.3, z: 0.22, sz: 0.5 }, 6, 5);
        m.s.sphere(0.03, BLUSH, { x: sx * 0.15, y: 0.25, z: 0.2, sz: 0.3 }, 6, 4);
      }
      m.s.sphere(0.07, '#F6F2E4', { y: 0.2, z: -0.25 }, 6, 5);
      m.s.cone(0.05, 0.14, 5, '#5E9A4A', { y: 0.46, z: 0.04 });
      break;
    case 'puddlepup':
      m.s.sphere(0.2, '#7FB2C4', { y: 0.22, sz: 1.3 }, 12, 9);
      for (const [x, z] of [[-0.1, 0.14], [0.1, 0.14], [-0.1, -0.14], [0.1, -0.14]]) m.s.cyl(0.04, 0.045, 0.12, 6, '#6A9CAE', { x, z });
      m.s.sphere(0.17, '#8CC0D0', { y: 0.42, z: 0.2 }, 12, 9);
      for (const sx of [-1, 1]) {
        m.s.sphere(0.07, '#5E8FA2', { x: sx * 0.16, y: 0.4, z: 0.16, sx: 0.5, sy: 1.5 }, 6, 5);
        m.s.sphere(0.024, EYE, { x: sx * 0.065, y: 0.45, z: 0.35, sz: 0.5 }, 6, 5);
      }
      m.s.sphere(0.03, '#2E2A2A', { y: 0.4, z: 0.37 }, 6, 5);
      m.s.cone(0.04, 0.16, 5, '#8CC0D0', { y: 0.28, z: -0.26, rx: -0.9 });
      break;
    case 'emberkit':
      m.s.sphere(0.19, '#E2854A', { y: 0.2, sz: 1.2 }, 12, 9);
      m.s.sphere(0.16, '#EE9A5C', { y: 0.4, z: 0.14 }, 12, 9);
      for (const sx of [-1, 1]) {
        m.s.cone(0.06, 0.13, 4, '#D06F38', { x: sx * 0.09, y: 0.52, z: 0.12 });
        m.s.sphere(0.024, EYE, { x: sx * 0.06, y: 0.43, z: 0.29, sz: 0.5 }, 6, 5);
      }
      m.s.sphere(0.06, '#F6E6D2', { y: 0.36, z: 0.27, sy: 0.7 }, 6, 5);
      m.g.cone(0.07, 0.3, 6, P.ember, { y: 0.2, z: -0.26, rx: -0.6, intensity: 3 });
      m.g.ico(0.05, P.heartflame, { y: 0.44, z: -0.36, intensity: 4 });
      break;
    default:
      humanoid(m, { robe: '#888888' });
  }
  return { solid: m.s.build(), glow: m.g.build() };
}

// How tall each kind stands, for placing speech bubbles.
export const HEAD = { mossbun: 0.75, puddlepup: 0.7, emberkit: 0.7 };
