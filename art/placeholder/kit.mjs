// Kingsbloom placeholder art kit.
// Hand-made vector placeholders in the illustrated direction of docs/08_ART_DIRECTION.md:
// coloured line art (never pure black), 2-tone cel shading, top-left light, soft contact shadows.
// These never ship. The hired artist replaces every one of them.

export const P = {
  line: '#2E3327', lineWarm: '#5B4A36', lineLeaf: '#2F4A3A',
  grassL: '#D1D987', grassM: '#B6CE6F', grassS: '#98A067', grassD: '#698D66',
  leaf: '#6FA864', leafHi: '#A9CF6A', leafSh: '#3F7A5E',
  pine: '#3C6D62', pineSh: '#2C5248', pineHi: '#5E9384',
  water: '#95C6C6', waterL: '#B8DAD9', foam: '#E4F1EE', waterD: '#6FAAB0',
  wood: '#8E6D56', woodD: '#4B372B', woodL: '#B08A68',
  cream: '#F9EAC5', creamW: '#F6E5B9', sand: '#E2CB9D', stoneS: '#B8A689', stone: '#E6DAC0',
  rock: '#A9AEA6', rockL: '#CBD0C7', rockD: '#7E857F', rockLine: '#4E5550',
  terra: '#B85A40', terraS: '#8C5039', terraD: '#5E3827',
  gold: '#FFC94A', goldL: '#FFF3C4', goldD: '#D9A03A', goldLine: '#8A5A1E',
  mush: '#E0B462', mushSh: '#C4914A', mushHi: '#F3D48E', stem: '#F3E6CC',
  pink: '#F0A7B4', pinkD: '#D9788C', berry: '#C9483E', lav: '#9E8AC8',
  veil: '#6B4FD8', veilT: '#3FD6C6', veilSoil: '#8C8298', veilSoilD: '#65597A',
  skin: '#F6D6B8', skinSh: '#E3B08F', blush: '#F2A0A0',
  white: '#FFFDF6', ember: '#FF8A3D', emberD: '#D9542B', soil: '#9A6E4E', soilD: '#6E4C37',
};

const svg = (w, h, body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">${body}</svg>`;
const shadow = (cx, cy, rx, ry, o = 0.2) =>
  `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="#2E3327" opacity="${o}"/>`;
// A clean outlined blob from overlapping circles: outline layer first, fill layer on top.
const blob = (cs, fill, line, lw = 3) =>
  cs.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${line}" stroke="${line}" stroke-width="${lw * 2}"/>`).join('') +
  cs.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}"/>`).join('');
const clip = (id, cs) => `<clipPath id="${id}">${cs.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}"/>`).join('')}</clipPath>`;
const stroke = (c, w = 3) => `stroke="${c}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"`;
const eyes = (lx, rx, y, s = 1) =>
  [lx, rx].map(x => `<ellipse cx="${x}" cy="${y}" rx="${3.2 * s}" ry="${4.2 * s}" fill="#2E3327"/><circle cx="${x + 1 * s}" cy="${y - 1.5 * s}" r="${1.3 * s}" fill="#fff"/>`).join('');

// ---------- Terrain tiles (128 × 128) ----------
const scatter = (n, seed, fn) => {
  let s = seed;
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  return Array.from({ length: n }, () => fn(rnd() * 118 + 5, rnd() * 118 + 5, rnd())).join('');
};

const tile_grass = svg(128, 128,
  `<rect width="128" height="128" fill="${P.grassL}"/>` +
  scatter(7, 11, (x, y) => `<g fill="${P.grassM}"><circle cx="${x}" cy="${y}" r="5"/><circle cx="${x + 6}" cy="${y + 2}" r="5"/><circle cx="${x + 3}" cy="${y - 5}" r="5"/></g>`) +
  scatter(14, 23, (x, y) => `<path d="M${x} ${y} l2 -6 M${x + 3} ${y} l0 -7 M${x + 6} ${y} l-2 -6" ${stroke(P.grassS, 1.6)} fill="none"/>`) +
  scatter(4, 7, (x, y, r) => `<circle cx="${x}" cy="${y}" r="2.2" fill="${r > 0.5 ? P.white : '#F3E27A'}"/>`));

const tile_path = svg(128, 128,
  `<rect width="128" height="128" fill="${P.sand}"/>` +
  scatter(12, 5, (x, y, r) => `<ellipse cx="${x}" cy="${y}" rx="${3 + r * 4}" ry="${2 + r * 2}" fill="#CBB184" stroke="#A8906A" stroke-width="1.2"/>`) +
  scatter(20, 9, (x, y) => `<circle cx="${x}" cy="${y}" r="1.2" fill="#B89C70"/>`));

const tile_tilled = svg(128, 128,
  `<rect width="128" height="128" fill="${P.soil}"/>` +
  [16, 48, 80, 112].map(y => `<path d="M0 ${y} Q32 ${y - 5} 64 ${y} T128 ${y}" ${stroke('#7A553B', 7)} fill="none"/><path d="M0 ${y - 8} Q32 ${y - 13} 64 ${y - 8} T128 ${y - 8}" ${stroke('#B08560', 3)} fill="none" opacity=".7"/>`).join(''));

const tile_watered = svg(128, 128,
  `<rect width="128" height="128" fill="${P.soilD}"/>` +
  [16, 48, 80, 112].map(y => `<path d="M0 ${y} Q32 ${y - 5} 64 ${y} T128 ${y}" ${stroke('#553A2A', 7)} fill="none"/><path d="M0 ${y - 8} Q32 ${y - 13} 64 ${y - 8} T128 ${y - 8}" ${stroke('#8A6A55', 3)} fill="none" opacity=".7"/>`).join('') +
  scatter(8, 3, (x, y) => `<ellipse cx="${x}" cy="${y}" rx="3" ry="1.6" fill="#A8C8CC" opacity=".55"/>`));

const tile_water = svg(128, 128,
  `<rect width="128" height="128" fill="${P.water}"/>` +
  scatter(6, 13, (x, y, r) => `<path d="M${x - 14} ${y} q14 -${4 + r * 4} 28 0" ${stroke(P.foam, 3)} fill="none" opacity=".85"/>`) +
  scatter(5, 29, (x, y) => `<path d="M${x - 10} ${y} q10 3 20 0" ${stroke(P.waterD, 2.5)} fill="none" opacity=".6"/>`));

const tile_veil = svg(128, 128,
  `<rect width="128" height="128" fill="${P.veilSoil}"/>` +
  scatter(5, 17, (x, y) => `<path d="M${x} ${y + 14} c-6 -10 8 -14 2 -24 c-4 -6 6 -10 10 -4" ${stroke(P.veilSoilD, 3)} fill="none"/><path d="M${x + 2} ${y + 4} l-4 -3 M${x + 6} ${y - 6} l4 -3" ${stroke(P.veilSoilD, 2)}/>`) +
  scatter(9, 31, (x, y) => `<circle cx="${x}" cy="${y}" r="1.8" fill="#C9B8FF" opacity=".8"/>`));

// ---------- Nature props ----------
function roundTree(id, s = 1, trunkH = 46) {
  const lobes = [[40, 78, 26], [64, 58, 30], [90, 78, 26], [50, 100, 24], [80, 100, 24]];
  return svg(128, 160,
    shadow(64, 148, 42, 9) +
    `<path d="M50 150 C56 146 56 ${150 - trunkH + 20} 58 ${150 - trunkH} L70 ${150 - trunkH} C72 ${150 - trunkH + 20} 72 146 78 150 Z" fill="${P.wood}" ${stroke(P.woodD, 3)}/>` +
    `<path d="M66 ${152 - trunkH} L70 ${150 - trunkH} C72 ${150 - trunkH + 20} 72 146 78 150 L69 150 C69 136 68 120 66 ${152 - trunkH} Z" fill="${P.woodD}" opacity=".35"/>` +
    `<defs>${clip(id, lobes)}</defs>` +
    blob(lobes, P.leaf, P.lineLeaf) +
    `<g clip-path="url(#${id})"><circle cx="100" cy="98" r="22" fill="${P.leafSh}"/><circle cx="78" cy="118" r="20" fill="${P.leafSh}"/><circle cx="46" cy="118" r="16" fill="${P.leafSh}"/>` +
    `<ellipse cx="54" cy="48" rx="16" ry="11" fill="${P.leafHi}"/><ellipse cx="32" cy="70" rx="10" ry="8" fill="${P.leafHi}"/><ellipse cx="84" cy="66" rx="9" ry="7" fill="${P.leafHi}"/>` +
    `<circle cx="62" cy="82" r="3" fill="${P.leafHi}"/><circle cx="72" cy="90" r="2" fill="${P.leafHi}"/></g>`);
}

const prp_tree_round = roundTree('kb-tree');

const prp_tree_sapling = svg(128, 160,
  shadow(64, 148, 16, 4) +
  `<path d="M64 148 C64 136 63 126 64 114" ${stroke(P.woodD, 3)} fill="none"/>` +
  `<path d="M64 124 C54 118 50 108 56 104 C62 108 64 116 64 124 Z" fill="${P.leaf}" ${stroke(P.lineLeaf, 2.5)}/>` +
  `<path d="M64 116 C74 110 80 100 74 96 C68 100 64 108 64 116 Z" fill="${P.leafHi}" ${stroke(P.lineLeaf, 2.5)}/>`);

const prp_tree_young = svg(128, 160,
  shadow(64, 148, 26, 6) +
  `<path d="M58 150 C61 140 61 120 61 104 L67 104 C67 120 67 140 70 150 Z" fill="${P.wood}" ${stroke(P.woodD, 3)}/>` +
  `<defs>${clip('kb-young', [[52, 96, 18], [74, 90, 20], [64, 76, 18]])}</defs>` +
  blob([[52, 96, 18], [74, 90, 20], [64, 76, 18]], P.leaf, P.lineLeaf) +
  `<g clip-path="url(#kb-young)"><circle cx="82" cy="104" r="16" fill="${P.leafSh}"/><ellipse cx="58" cy="70" rx="10" ry="7" fill="${P.leafHi}"/></g>`);

const prp_pine = svg(128, 176,
  shadow(64, 164, 34, 8) +
  `<rect x="58" y="138" width="12" height="26" rx="3" fill="${P.wood}" ${stroke(P.woodD, 3)}/>` +
  [[64, 12, 30, 58], [64, 42, 40, 96], [64, 76, 50, 142]].map(([x, top, half, bot]) =>
    `<path d="M${x} ${top} L${x + half} ${bot} Q${x} ${bot + 10} ${x - half} ${bot} Z" fill="${P.pine}" ${stroke('#23392F', 3)}/>` +
    `<path d="M${x} ${top + 4} L${x + half - 4} ${bot - 2} Q${x + 10} ${bot + 4} ${x + 4} ${bot + 3} Z" fill="${P.pineSh}" opacity=".7"/>` +
    `<path d="M${x - 2} ${top + 10} L${x - half * 0.55} ${bot - 12}" ${stroke(P.pineHi, 3)} opacity=".8"/>`).join(''));

const prp_mushroom = svg(128, 128,
  shadow(64, 116, 40, 7) +
  // small mushroom behind
  `<path d="M94 112 C94 100 92 92 94 86 L102 86 C104 92 102 100 102 112 Z" fill="${P.stem}" ${stroke(P.lineWarm, 2.5)}/>` +
  `<path d="M82 88 C82 72 114 72 114 88 C106 92 90 92 82 88 Z" fill="${P.mushSh}" ${stroke(P.lineWarm, 2.5)}/>` +
  // big mushroom
  `<path d="M52 114 C50 96 52 80 56 66 L72 66 C76 80 78 96 76 114 Z" fill="${P.stem}" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M68 70 L72 66 C76 80 78 96 76 114 L70 114 C71 98 70 82 68 70 Z" fill="#D8C7A4" opacity=".7"/>` +
  `<path d="M20 70 C20 30 108 30 108 70 C92 78 36 78 20 70 Z" fill="${P.mush}" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M70 38 C92 42 104 54 106 68 C96 74 84 76 74 76 C80 64 80 50 70 38 Z" fill="${P.mushSh}" opacity=".7"/>` +
  `<ellipse cx="44" cy="46" rx="12" ry="6" fill="${P.mushHi}" opacity=".9"/>` +
  `<g fill="${P.white}" stroke="${P.lineWarm}" stroke-width="1.5"><circle cx="40" cy="58" r="5"/><circle cx="62" cy="44" r="6"/><circle cx="86" cy="58" r="5"/><circle cx="74" cy="64" r="3"/></g>`);

const prp_rock = svg(128, 112,
  shadow(64, 100, 44, 8) +
  `<path d="M20 96 L26 58 L50 36 L84 38 L106 62 L110 96 Q64 106 20 96 Z" fill="${P.rock}" ${stroke(P.rockLine, 3)}/>` +
  `<path d="M26 58 L50 36 L84 38 L96 52 L70 60 L40 64 Z" fill="${P.rockL}"/>` +
  `<path d="M96 52 L106 62 L110 96 Q92 100 80 101 L84 70 Z" fill="${P.rockD}" opacity=".85"/>` +
  `<path d="M40 64 L70 60 L96 52" ${stroke(P.rockLine, 2)} fill="none" opacity=".6"/>` +
  `<path d="M30 60 C38 52 48 50 56 54 C50 58 40 60 30 60 Z" fill="${P.grassM}" ${stroke(P.lineLeaf, 1.5)}/>`);

const prp_stump = svg(128, 112,
  shadow(64, 100, 40, 8) +
  `<path d="M30 52 L30 88 Q64 104 98 88 L98 52 Z" fill="${P.wood}" ${stroke(P.woodD, 3)}/>` +
  `<path d="M22 94 Q30 86 34 76 M104 92 Q98 86 94 76" ${stroke(P.woodD, 5)} fill="none"/>` +
  `<path d="M80 56 L98 52 L98 88 Q90 94 80 96 Z" fill="${P.woodD}" opacity=".35"/>` +
  `<ellipse cx="64" cy="52" rx="34" ry="13" fill="#D9B98A" ${stroke(P.woodD, 3)}/>` +
  `<ellipse cx="64" cy="52" rx="22" ry="8" fill="none" ${stroke('#B08A68', 2)}/><ellipse cx="64" cy="52" rx="10" ry="4" fill="none" ${stroke('#B08A68', 2)}/>`);

const prp_fern = svg(128, 112,
  shadow(64, 102, 30, 6) +
  [[-58, 1], [-28, 1.1], [0, 1.2], [28, 1.1], [58, 1]].map(([ang, k]) =>
    `<g transform="rotate(${ang} 64 100)"><path d="M64 100 C62 76 64 52 64 ${40 / k}" ${stroke(P.lineLeaf, 4)} fill="none"/>` +
    Array.from({ length: 6 }, (_, i) => {
      const y = 92 - i * 9;
      return `<path d="M64 ${y} q-12 -4 -${14 - i} -10 q10 2 14 10 Z" fill="${i % 2 ? P.leaf : P.leafHi}" ${stroke(P.lineLeaf, 1.5)}/><path d="M64 ${y} q12 -4 ${14 - i} -10 q-10 2 -14 10 Z" fill="${P.leaf}" ${stroke(P.lineLeaf, 1.5)}/>`;
    }).join('') + `</g>`).join(''));

const prp_berry_bush = svg(128, 112,
  shadow(64, 102, 44, 8) +
  `<defs>${clip('kb-bush', [[40, 72, 26], [68, 60, 30], [92, 74, 24]])}</defs>` +
  blob([[40, 72, 26], [68, 60, 30], [92, 74, 24]], '#5E9A5C', P.lineLeaf) +
  `<g clip-path="url(#kb-bush)"><circle cx="96" cy="94" r="22" fill="${P.leafSh}"/><ellipse cx="56" cy="42" rx="14" ry="9" fill="${P.leafHi}" opacity=".8"/></g>` +
  [[40, 66], [52, 80], [70, 70], [84, 60], [92, 82], [30, 84], [64, 50]].map(([x, y]) =>
    `<circle cx="${x}" cy="${y}" r="4.5" fill="${P.berry}" stroke="#7A2A24" stroke-width="1.5"/><circle cx="${x - 1.5}" cy="${y - 1.5}" r="1.3" fill="#fff" opacity=".8"/>`).join(''));

const prp_lily = svg(128, 96,
  `<ellipse cx="60" cy="58" rx="44" ry="22" fill="#7DB26A" ${stroke(P.lineLeaf, 3)}/>` +
  `<path d="M60 58 L104 50 L102 62 Z" fill="${P.water}" stroke="none"/>` +
  `<path d="M60 58 L30 48 M60 58 L40 72 M60 58 L76 76" ${stroke('#5E9A5C', 2)}/>` +
  // lotus
  `<g transform="translate(58 44)">` +
  [-50, -25, 0, 25, 50].map(a => `<path d="M0 6 C-8 -8 -4 -22 0 -26 C4 -22 8 -8 0 6 Z" transform="rotate(${a})" fill="${P.pink}" ${stroke(P.pinkD, 2)}/>`).join('') +
  `<circle cx="0" cy="2" r="5" fill="#F7D56A" stroke="#C9A23A" stroke-width="1.5"/></g>`);

const prp_veil_crystal = svg(128, 128,
  `<defs><linearGradient id="kb-vc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C9B8FF"/><stop offset=".55" stop-color="${P.veil}"/><stop offset="1" stop-color="${P.veilT}"/></linearGradient>` +
  `<radialGradient id="kb-vglow"><stop offset="0" stop-color="${P.veilT}" stop-opacity=".45"/><stop offset="1" stop-color="${P.veilT}" stop-opacity="0"/></radialGradient></defs>` +
  `<circle cx="64" cy="76" r="54" fill="url(#kb-vglow)"/>` + shadow(64, 112, 34, 7) +
  [[64, 22, 14, 108], [42, 52, 10, 110], [86, 48, 11, 110], [30, 78, 7, 110], [98, 80, 7, 110]].map(([x, top, hw, bot]) =>
    `<path d="M${x} ${top} L${x + hw} ${top + hw * 1.6} L${x + hw * 0.8} ${bot} L${x - hw * 0.8} ${bot} L${x - hw} ${top + hw * 1.6} Z" fill="url(#kb-vc)" ${stroke('#3B2A7A', 2.5)}/>` +
    `<path d="M${x} ${top + 4} L${x - hw * 0.6} ${top + hw * 1.6} L${x - hw * 0.5} ${bot - 6}" ${stroke('#E8E0FF', 2)} fill="none" opacity=".8"/>`).join(''));

const prp_brazier = svg(128, 150,
  `<defs><radialGradient id="kb-bglow"><stop offset="0" stop-color="${P.gold}" stop-opacity=".55"/><stop offset="1" stop-color="${P.gold}" stop-opacity="0"/></radialGradient>` +
  `<linearGradient id="kb-flame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${P.goldL}"/><stop offset=".45" stop-color="${P.gold}"/><stop offset="1" stop-color="${P.ember}"/></linearGradient></defs>` +
  `<circle cx="64" cy="56" r="60" fill="url(#kb-bglow)"/>` + shadow(64, 140, 30, 6) +
  `<path d="M52 138 L56 96 L72 96 L76 138 Z" fill="${P.stone}" ${stroke(P.lineWarm, 3)}/><path d="M66 96 L72 96 L76 138 L69 138 Z" fill="${P.stoneS}" opacity=".7"/>` +
  `<path d="M28 78 L100 78 Q96 100 64 102 Q32 100 28 78 Z" fill="${P.stone}" ${stroke(P.lineWarm, 3)}/><path d="M28 78 L100 78" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M64 12 C76 30 92 44 86 62 C82 76 72 80 64 80 C56 80 44 76 42 62 C38 46 54 34 58 20 C62 30 60 38 64 42 C68 34 66 22 64 12 Z" fill="url(#kb-flame)" ${stroke(P.emberD, 2.5)}/>` +
  `<path d="M64 44 C70 52 74 60 70 68 C66 74 58 72 58 64 C58 56 62 52 64 44 Z" fill="${P.goldL}"/>` +
  `<path d="M54 84 L58 90 L64 84 L70 90 L74 84" ${stroke(P.goldD, 2.5)} fill="none"/>`);

const prp_lumen_lamp = svg(96, 160,
  `<defs><radialGradient id="kb-lglow"><stop offset="0" stop-color="${P.gold}" stop-opacity=".5"/><stop offset="1" stop-color="${P.gold}" stop-opacity="0"/></radialGradient></defs>` +
  `<circle cx="48" cy="44" r="42" fill="url(#kb-lglow)"/>` + shadow(48, 150, 18, 4) +
  `<rect x="44" y="60" width="8" height="90" rx="2" fill="${P.wood}" ${stroke(P.woodD, 2.5)}/>` +
  `<path d="M34 30 L62 30 L60 62 L36 62 Z" fill="${P.goldL}" ${stroke(P.goldLine, 3)}/>` +
  `<path d="M40 36 L56 36 L55 56 L41 56 Z" fill="${P.gold}" opacity=".9"/>` +
  `<path d="M30 30 L48 16 L66 30 Z" fill="${P.terra}" ${stroke(P.terraD, 3)}/>` +
  `<circle cx="48" cy="12" r="3" fill="${P.goldD}"/>`);

// ---------- Crops (64 × 64) ----------
const mound = `<ellipse cx="32" cy="54" rx="22" ry="7" fill="${P.soil}" ${stroke('#6E4C37', 2)}/>`;
const leafPair = (x, y, s, c = P.leaf) =>
  `<path d="M${x} ${y} C${x - 9 * s} ${y - 4 * s} ${x - 12 * s} ${y - 14 * s} ${x - 4 * s} ${y - 16 * s} C${x - 2 * s} ${y - 10 * s} ${x} ${y - 6 * s} ${x} ${y} Z" fill="${c}" ${stroke(P.lineLeaf, 1.8)}/>` +
  `<path d="M${x} ${y} C${x + 9 * s} ${y - 4 * s} ${x + 12 * s} ${y - 14 * s} ${x + 4 * s} ${y - 16 * s} C${x + 2 * s} ${y - 10 * s} ${x} ${y - 6 * s} ${x} ${y} Z" fill="${P.leafHi}" ${stroke(P.lineLeaf, 1.8)}/>`;
const turnipBulb = (r, y) =>
  `<ellipse cx="32" cy="${y}" rx="${r}" ry="${r * 0.85}" fill="${P.white}" ${stroke('#7A6A8A', 2)}/>` +
  `<path d="M${32 - r} ${y - r * 0.2} Q32 ${y - r * 1.1} ${32 + r} ${y - r * 0.2} Q32 ${y - r * 0.5} ${32 - r} ${y - r * 0.2} Z" fill="#B48ACB"/>`;

const crop_turnip_1 = svg(64, 64, mound + `<circle cx="28" cy="50" r="1.6" fill="#5A3E2B"/><circle cx="36" cy="51" r="1.4" fill="#5A3E2B"/>`);
const crop_turnip_2 = svg(64, 64, mound + `<path d="M32 52 L32 44" ${stroke(P.lineLeaf, 2)}/>` + leafPair(32, 46, 0.6));
const crop_turnip_3 = svg(64, 64, mound + `<path d="M32 52 L32 40" ${stroke(P.lineLeaf, 2)}/>` + leafPair(32, 46, 0.9) + leafPair(32, 40, 0.7));
const crop_turnip_4 = svg(64, 64, mound + turnipBulb(8, 50) + leafPair(32, 44, 1.1) + leafPair(32, 38, 0.9));
const crop_turnip_5 = svg(64, 64, mound + turnipBulb(11, 48) + leafPair(32, 40, 1.2) + leafPair(32, 33, 1) +
  `<path d="M50 14 l2 5 l5 2 l-5 2 l-2 5 l-2 -5 l-5 -2 l5 -2 Z" fill="${P.gold}" stroke="${P.goldLine}" stroke-width="1"/>`);

const crop_dawnbell = svg(64, 64, mound +
  `<path d="M32 52 C32 40 30 30 32 18 M32 36 C38 32 42 28 44 22 M32 30 C26 26 22 22 20 16" ${stroke(P.lineLeaf, 2.2)} fill="none"/>` +
  [[32, 18], [44, 22], [20, 16]].map(([x, y]) =>
    `<path d="M${x - 6} ${y + 8} Q${x - 6} ${y - 4} ${x} ${y - 4} Q${x + 6} ${y - 4} ${x + 6} ${y + 8} Q${x + 3} ${y + 5} ${x} ${y + 8} Q${x - 3} ${y + 5} ${x - 6} ${y + 8} Z" fill="#F6E3A1" ${stroke('#C98F5E', 1.8)}/>` +
    `<path d="M${x - 6} ${y + 8} Q${x - 3} ${y + 5} ${x} ${y + 8} Q${x + 3} ${y + 5} ${x + 6} ${y + 8}" ${stroke(P.pinkD, 2)} fill="none"/>`).join('') +
  leafPair(32, 48, 0.8));

const crop_mandrake = svg(64, 64, mound +
  `<path d="M22 48 Q32 62 42 48 Q40 40 32 40 Q24 40 22 48 Z" fill="#E7C9A0" ${stroke(P.lineWarm, 2)}/>` +
  `<circle cx="28.5" cy="46" r="1.8" fill="#2E3327"/><circle cx="35.5" cy="46" r="1.8" fill="#2E3327"/><path d="M30 50 q2 2 4 0" ${stroke('#2E3327', 1.5)} fill="none"/>` +
  leafPair(32, 40, 1.1, '#5E9A5C') + leafPair(32, 33, 0.8, '#5E9A5C'));

// ---------- Creatures (128 × 128) ----------
const cre_mossbun = svg(128, 128,
  shadow(64, 116, 32, 7) +
  // ears: cream with pink insides and moss caps
  `<path d="M44 64 C34 46 34 24 44 20 C54 18 58 40 56 62 Z" fill="#F3EEDC" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M45 28 C41 38 43 50 49 60 C52 48 51 36 45 28 Z" fill="#F2C4C4"/>` +
  `<path d="M36 34 C36 20 54 14 56 30 C50 28 42 30 36 34 Z" fill="#8FBF5E" ${stroke('#4E6B3A', 2.5)}/>` +
  `<path d="M72 62 C72 40 78 20 88 22 C98 26 92 48 82 66 Z" fill="#F3EEDC" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M86 30 C80 40 78 50 78 60 C84 50 88 40 86 30 Z" fill="#F2C4C4"/>` +
  `<path d="M78 28 C82 16 98 18 96 32 C90 28 84 28 78 28 Z" fill="#8FBF5E" ${stroke('#4E6B3A', 2.5)}/>` +
  // round body
  `<path d="M24 94 C20 52 108 52 104 94 C102 118 26 118 24 94 Z" fill="#F3EEDC" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M88 64 C102 74 106 96 98 108 C92 111 84 112 76 112 C90 100 94 80 88 64 Z" fill="#E2D8BC" opacity=".8"/>` +
  // moss tuft on the head and a patch on the back
  `<path d="M48 60 C52 48 76 48 80 60 C70 55 58 55 48 60 Z" fill="#8FBF5E" ${stroke('#4E6B3A', 2)}/>` +
  `<path d="M92 80 C100 82 102 92 98 98 C94 94 92 88 92 80 Z" fill="#8FBF5E" ${stroke('#4E6B3A', 2)}/>` +
  // feet
  `<ellipse cx="46" cy="112" rx="10" ry="5" fill="#EAE2CB" ${stroke(P.lineWarm, 2.5)}/><ellipse cx="80" cy="112" rx="10" ry="5" fill="#EAE2CB" ${stroke(P.lineWarm, 2.5)}/>` +
  eyes(52, 76, 82, 1.1) +
  `<path d="M61 91 L64 94 L67 91 Z" fill="${P.pinkD}"/><path d="M58 97 q6 5 12 0" ${stroke(P.lineWarm, 2)} fill="none"/>` +
  `<ellipse cx="42" cy="92" rx="6" ry="3.5" fill="${P.blush}" opacity=".6"/><ellipse cx="86" cy="92" rx="6" ry="3.5" fill="${P.blush}" opacity=".6"/>`);

const cre_puddlepup = svg(128, 128,
  shadow(60, 116, 34, 7) +
  // bubble tail
  `<circle cx="104" cy="70" r="11" fill="${P.waterL}" ${stroke('#3F7F95', 2.5)} opacity=".9"/><circle cx="114" cy="54" r="7" fill="${P.waterL}" ${stroke('#3F7F95', 2)} opacity=".9"/><circle cx="118" cy="42" r="4" fill="${P.waterL}" ${stroke('#3F7F95', 1.5)}/>` +
  `<circle cx="101" cy="67" r="3" fill="#fff" opacity=".8"/>` +
  // body
  `<path d="M22 96 C18 56 98 56 96 96 C94 116 24 116 22 96 Z" fill="#8CCBE0" ${stroke('#3F7F95', 3)}/>` +
  `<path d="M80 70 C94 80 94 102 84 110 C78 111 72 111 66 110 C80 100 82 84 80 70 Z" fill="#6FB3CC" opacity=".8"/>` +
  // floppy ears
  `<path d="M28 70 C14 72 12 92 22 98 C28 92 30 82 34 76 Z" fill="#5FA3C0" ${stroke('#3F7F95', 3)}/>` +
  `<path d="M90 70 C104 72 106 92 96 98 C90 92 88 82 84 76 Z" fill="#5FA3C0" ${stroke('#3F7F95', 3)}/>` +
  // droplet on head
  `<path d="M58 44 C54 52 54 58 58 60 C62 58 62 52 58 44 Z" fill="${P.waterL}" ${stroke('#3F7F95', 2)}/>` +
  eyes(47, 71, 84, 1.15) +
  `<ellipse cx="59" cy="94" rx="4" ry="3" fill="#2E3327"/><path d="M54 99 q5 5 10 0" ${stroke('#2E3327', 2)} fill="none"/>` +
  `<ellipse cx="38" cy="94" rx="6" ry="3.5" fill="${P.blush}" opacity=".5"/><ellipse cx="80" cy="94" rx="6" ry="3.5" fill="${P.blush}" opacity=".5"/>`);

const cre_emberkit = svg(128, 128,
  `<defs><linearGradient id="kb-ek" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${P.goldL}"/><stop offset=".5" stop-color="${P.gold}"/><stop offset="1" stop-color="${P.ember}"/></linearGradient></defs>` +
  shadow(60, 116, 34, 7) +
  // ember tail
  `<path d="M88 100 C112 98 120 72 108 56 C106 68 98 72 94 66 C100 80 92 90 84 92 Z" fill="url(#kb-ek)" ${stroke(P.emberD, 2.5)}/>` +
  // body
  `<path d="M26 98 C22 62 94 62 92 98 C90 116 28 116 26 98 Z" fill="#F09A4A" ${stroke('#8A4A1E', 3)}/>` +
  `<path d="M44 88 C44 76 72 76 72 88 C72 106 44 106 44 88 Z" fill="#FFF1DC"/>` +
  // ears
  `<path d="M34 72 L30 42 L52 62 Z" fill="#F09A4A" ${stroke('#8A4A1E', 3)}/><path d="M33 64 L31 46 L44 58 Z" fill="#5B3A2A"/>` +
  `<path d="M82 72 L88 42 L66 62 Z" fill="#F09A4A" ${stroke('#8A4A1E', 3)}/><path d="M83 64 L87 46 L74 58 Z" fill="#5B3A2A"/>` +
  eyes(47, 71, 82, 1.05) +
  `<path d="M56 91 L59 94 L62 91 Z" fill="#2E3327"/><path d="M54 97 q5 4 10 0" ${stroke('#2E3327', 2)} fill="none"/>` +
  `<ellipse cx="38" cy="92" rx="5" ry="3" fill="${P.blush}" opacity=".6"/><ellipse cx="80" cy="92" rx="5" ry="3" fill="${P.blush}" opacity=".6"/>`);

const cre_glimmoth = svg(128, 128,
  `<defs><radialGradient id="kb-gm"><stop offset="0" stop-color="${P.gold}" stop-opacity=".55"/><stop offset="1" stop-color="${P.gold}" stop-opacity="0"/></radialGradient></defs>` +
  `<circle cx="64" cy="62" r="60" fill="url(#kb-gm)"/>` +
  `<path d="M62 60 C40 26 10 30 16 56 C20 72 44 72 62 64 Z" fill="#FFE08A" ${stroke(P.goldLine, 3)}/>` +
  `<path d="M66 60 C88 26 118 30 112 56 C108 72 84 72 66 64 Z" fill="#FFE08A" ${stroke(P.goldLine, 3)}/>` +
  `<path d="M62 66 C44 70 28 84 36 96 C44 104 58 90 62 72 Z" fill="${P.gold}" ${stroke(P.goldLine, 3)}/>` +
  `<path d="M66 66 C84 70 100 84 92 96 C84 104 70 90 66 72 Z" fill="${P.gold}" ${stroke(P.goldLine, 3)}/>` +
  `<circle cx="34" cy="50" r="6" fill="${P.goldL}"/><circle cx="94" cy="50" r="6" fill="${P.goldL}"/>` +
  `<ellipse cx="64" cy="70" rx="10" ry="20" fill="#FFF6E2" ${stroke(P.goldLine, 3)}/>` +
  `<path d="M60 52 C54 40 50 36 46 36 M68 52 C74 40 78 36 82 36" ${stroke(P.goldLine, 2.5)} fill="none"/>` +
  eyes(59.5, 68.5, 64, 0.8));

const amb_wispling = svg(128, 128,
  `<defs><radialGradient id="kb-wg"><stop offset="0" stop-color="#EAF7F7" stop-opacity=".9"/><stop offset="1" stop-color="#EAF7F7" stop-opacity="0"/></radialGradient></defs>` +
  `<circle cx="64" cy="74" r="48" fill="url(#kb-wg)"/>` + shadow(64, 112, 20, 4, 0.14) +
  `<path d="M54 64 C48 42 50 30 56 30 C62 30 62 46 60 64 Z" fill="${P.white}" ${stroke('#9FB3B4', 2.5)}/>` +
  `<path d="M68 64 C68 44 72 32 78 34 C84 38 78 52 72 66 Z" fill="${P.white}" ${stroke('#9FB3B4', 2.5)}/>` +
  `<path d="M40 94 C36 66 92 66 88 94 C86 110 42 110 40 94 Z" fill="${P.white}" ${stroke('#9FB3B4', 2.5)}/>` +
  `<circle cx="56" cy="86" r="2.6" fill="#2E3327"/><circle cx="72" cy="86" r="2.6" fill="#2E3327"/>` +
  `<ellipse cx="50" cy="93" rx="4" ry="2.2" fill="${P.blush}" opacity=".55"/><ellipse cx="78" cy="93" rx="4" ry="2.2" fill="${P.blush}" opacity=".55"/>` +
  // tiny flower it carries
  `<path d="M88 98 L96 82" ${stroke(P.lineLeaf, 2)}/><g transform="translate(97 79)">${[0, 72, 144, 216, 288].map(a => `<ellipse cx="0" cy="-4" rx="2.6" ry="4" transform="rotate(${a})" fill="${P.pink}"/>`).join('')}<circle r="2" fill="#F7D56A"/></g>`);

const cre_jellop = svg(128, 128,
  shadow(64, 112, 36, 7) +
  `<path d="M26 104 C18 70 44 38 64 38 C84 38 110 70 102 104 C90 112 38 112 26 104 Z" fill="#7FD1B9" ${stroke('#2F7F6E', 3)}/>` +
  `<path d="M84 50 C98 64 104 88 100 104 C92 108 82 110 74 110 C90 92 92 68 84 50 Z" fill="#5FBFA5" opacity=".75"/>` +
  `<ellipse cx="46" cy="58" rx="9" ry="6" fill="#fff" opacity=".7" transform="rotate(-30 46 58)"/>` +
  eyes(52, 76, 80, 1.1) + `<path d="M58 92 q6 6 12 0" ${stroke('#2E3327', 2)} fill="none"/>`);

// ---------- Characters ----------
export const FLICKER = svg(64, 72,
  `<defs><linearGradient id="kb-fl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${P.goldL}"/><stop offset=".5" stop-color="${P.gold}"/><stop offset="1" stop-color="${P.ember}"/></linearGradient>` +
  `<radialGradient id="kb-flg"><stop offset="0" stop-color="${P.gold}" stop-opacity=".5"/><stop offset="1" stop-color="${P.gold}" stop-opacity="0"/></radialGradient></defs>` +
  `<circle cx="32" cy="42" r="30" fill="url(#kb-flg)"/>` +
  `<path d="M32 14 C44 26 52 36 50 48 C48 60 40 66 32 66 C24 66 16 60 14 48 C12 36 20 26 32 14 Z" fill="url(#kb-fl)" ${stroke('#C0602A', 2.5)}/>` +
  `<ellipse cx="32" cy="50" rx="11" ry="10" fill="${P.goldL}" opacity=".85"/>` +
  `<ellipse cx="26" cy="46" rx="3.2" ry="4.6" fill="#3A2A1E"/><ellipse cx="38" cy="46" rx="3.2" ry="4.6" fill="#3A2A1E"/><circle cx="27" cy="44.2" r="1.3" fill="#fff"/><circle cx="39" cy="44.2" r="1.3" fill="#fff"/>` +
  `<path d="M29 54 q3 3 6 0" stroke="#3A2A1E" stroke-width="1.8" fill="none" stroke-linecap="round"/>` +
  `<g transform="rotate(-12 32 12)"><path d="M22 16 L22 6 L27 11 L32 3 L37 11 L42 6 L42 16 Z" fill="${P.gold}" ${stroke(P.goldLine, 2)}/><circle cx="32" cy="10" r="1.8" fill="${P.berry}"/></g>`);

// Shared chibi generator: ~2.7 heads tall, front view.
function chibi(o) {
  const L = o.line || P.lineWarm;
  const head = `<circle cx="48" cy="46" r="26" fill="${P.skin}" ${stroke(L, 3)}/>` +
    `<path d="M28 58 Q48 74 68 58 Q62 70 48 72 Q34 70 28 58 Z" fill="${P.skinSh}" opacity=".45"/>`;
  const face = eyes(39, 57, 51) +
    `<path d="M${36} 42 q3 -2 6 0 M${54} 42 q3 -2 6 0" ${stroke(L, 1.8)} fill="none" opacity="${o.beard ? 0 : 0.9}"/>` +
    (o.beard ? '' : `<path d="M45 60 q3 2.5 6 0" ${stroke(L, 2)} fill="none"/>`) +
    `<ellipse cx="34" cy="58" rx="4" ry="2.4" fill="${P.blush}" opacity=".55"/><ellipse cx="62" cy="58" rx="4" ry="2.4" fill="${P.blush}" opacity=".55"/>` +
    (o.freckles ? `<g fill="#C77A55"><circle cx="36" cy="55" r="1"/><circle cx="39" cy="56.5" r="1"/><circle cx="57" cy="56.5" r="1"/><circle cx="60" cy="55" r="1"/></g>` : '');
  const legs = `<rect x="35" y="116" width="10" height="24" rx="4" fill="${o.boots}" ${stroke(L, 3)}/><rect x="51" y="116" width="10" height="24" rx="4" fill="${o.boots}" ${stroke(L, 3)}/>`;
  const w = o.stocky ? 6 : 0;
  const body = `<path d="M${30 - w} 80 Q48 72 ${66 + w} 80 L${74 + w} 122 Q48 130 ${22 - w} 122 Z" fill="${o.outfit}" ${stroke(L, 3)}/>` +
    `<path d="M${58 + w} 78 Q${64 + w} 80 ${66 + w} 80 L${74 + w} 122 Q${66 + w} 126 ${58 + w} 127 Z" fill="#000" opacity=".12"/>` +
    (o.trim ? `<path d="M48 76 L48 127" ${stroke(o.trim, 3)}/><path d="M${24 - w} 118 Q48 126 ${72 + w} 118" ${stroke(o.trim, 3)} fill="none"/>` : '') +
    (o.apron ? `<path d="M36 90 L60 90 L62 124 Q48 128 34 124 Z" fill="${o.apron}" ${stroke(L, 2.5)}/>` : '') +
    (o.belt ? `<path d="M${27 - w} 100 Q48 106 ${69 + w} 100" ${stroke(o.belt, 5)} fill="none"/>` : '') +
    (o.patch ? `<rect x="58" y="104" width="9" height="9" rx="1" fill="${P.wood}" ${stroke(L, 1.5)} transform="rotate(8 62 108)"/>` : '');
  const arms = `<path d="M${29 - w} 86 Q${19 - w} 100 ${23 - w} 112" ${stroke(L, 13)} fill="none"/><path d="M${29 - w} 86 Q${19 - w} 100 ${23 - w} 112" ${stroke(o.sleeve || o.outfit, 8)} fill="none"/>` +
    `<path d="M${67 + w} 86 Q${77 + w} 100 ${73 + w} 112" ${stroke(L, 13)} fill="none"/><path d="M${67 + w} 86 Q${77 + w} 100 ${73 + w} 112" ${stroke(o.sleeve || o.outfit, 8)} fill="none"/>` +
    `<circle cx="${23 - w}" cy="114" r="5" fill="${o.gloves || P.skin}" ${stroke(L, 2.5)}/><circle cx="${73 + w}" cy="114" r="5" fill="${o.gloves || P.skin}" ${stroke(L, 2.5)}/>`;
  return svg(96, 150, shadow(48, 142, 26, 5) + (o.back || '') + legs + body + arms + head + face + (o.hair || '') + (o.front || ''));
}

const HAIR = {
  sovereign: `<path d="M22 50 C18 20 78 12 76 48 C70 36 62 32 56 34 C54 40 46 42 40 36 C34 38 28 44 22 50 Z" fill="#4A3426" ${stroke('#2E1F16', 3)}/><path d="M60 30 C66 24 72 26 74 32" ${stroke('#6A4C38', 2.5)} fill="none"/>`,
  bram: `<path d="M22 44 C24 18 72 18 74 44 C60 38 36 38 22 44 Z" fill="${P.skin}"/><path d="M21 42 Q48 30 75 42 L75 48 Q48 38 21 48 Z" fill="#5E7F52" ${stroke('#33462C', 2.5)}/><path d="M74 44 l10 -2 l-4 8 Z" fill="#5E7F52" ${stroke('#33462C', 2)}/>` +
    `<path d="M26 56 Q30 78 48 82 Q66 78 70 56 Q62 64 48 64 Q34 64 26 56 Z" fill="#C9C4BA" ${stroke('#7C766C', 2.5)}/><path d="M40 62 q8 4 16 0" ${stroke('#7C766C', 2)} fill="none"/>`,
  linnea: `<path d="M20 52 C16 16 80 14 76 52 C70 40 60 34 48 34 C36 34 26 40 20 52 Z" fill="#E6D2A2" ${stroke('#9A7F4E', 3)}/><path d="M48 22 C44 30 42 36 40 40" ${stroke('#C9B07A', 2)} fill="none"/>`,
  linneaBack: `<path d="M22 50 C20 76 26 96 30 104 L66 104 C70 96 76 76 74 50 Z" fill="#DCC690" ${stroke('#9A7F4E', 3)}/>`,
  linneaFront: `<g>${[0, 1, 2, 3].map(i => `<ellipse cx="${72 - i}" cy="${78 + i * 9}" rx="6" ry="5.5" fill="#E6D2A2" ${stroke('#9A7F4E', 2)}/>`).join('')}<circle cx="30" cy="34" r="3.5" fill="${P.white}" stroke="${P.pinkD}" stroke-width="1.5"/><circle cx="36" cy="28" r="2.8" fill="${P.pink}"/></g>`,
  rook: `<path d="M20 52 L22 30 L30 36 L32 18 L42 30 L48 14 L54 30 L64 18 L66 34 L76 28 L76 52 C70 40 60 34 48 34 C36 34 26 40 20 52 Z" fill="#23232B" ${stroke('#101014', 3)}/><path d="M50 16 L54 30 L50 34" ${stroke('#E8E6E0', 3)} fill="none"/>`,
  rookBack: `<path d="M18 84 Q48 64 78 84 L86 126 Q48 136 10 126 Z" fill="#2A2A33" ${stroke('#101014', 3)}/><path d="M22 88 L14 124 Q20 126 26 126 Z M74 88 L82 124 Q76 126 70 126 Z" fill="#A33A3A"/>`,
  rookFront: `<path d="M34 76 l-6 10 l8 -4 Z M62 76 l6 10 l-8 -4 Z M48 74 l-3 10 l6 0 Z" fill="#23232B" ${stroke('#101014', 1.5)}/><path d="M36 60 l8 -3" ${stroke('#B98A7A', 1.6)}/>`,
  tamsin: `<path d="M20 52 C16 18 80 16 76 52 C72 42 64 36 58 38 C56 42 50 42 46 38 C38 38 26 42 20 52 Z" fill="#B55B34" ${stroke('#6E3218', 3)}/>`,
  tamsinBack: `<path d="M72 36 C92 38 94 62 82 70 C84 58 80 46 72 44 Z" fill="#B55B34" ${stroke('#6E3218', 3)}/>`,
};

const PROPS = {
  hammer: `<g transform="rotate(-20 78 112)"><rect x="75" y="94" width="5" height="34" rx="2" fill="${P.wood}" ${stroke(P.woodD, 2)}/><rect x="68" y="88" width="20" height="10" rx="2" fill="#9AA0A6" ${stroke('#4E5550', 2.5)}/></g>`,
  daggers: `<path d="M18 112 L10 96 L14 94 L22 110 Z" fill="#C9CED3" ${stroke('#4E5550', 2)}/><path d="M78 112 L86 96 L82 94 L74 110 Z" fill="#C9CED3" ${stroke('#4E5550', 2)}/>`,
  satchel: `<path d="M30 80 L66 110" ${stroke('#6B4A33', 4)}/><rect x="60" y="104" width="16" height="14" rx="3" fill="${P.wood}" ${stroke(P.woodD, 2.5)}/><path d="M64 108 l3 -4 l3 4" ${stroke(P.leaf, 2)} fill="none"/>`,
  sword: `<g transform="rotate(25 76 110)"><rect x="74" y="80" width="5" height="34" rx="1.5" fill="#A89F8A" ${stroke(P.woodD, 2)}/><rect x="70" y="112" width="13" height="4" rx="1.5" fill="${P.wood}" ${stroke(P.woodD, 1.5)}/></g>`,
};

const chr_sovereign = chibi({ hair: HAIR.sovereign, outfit: '#56608A', sleeve: '#56608A', trim: P.goldD, belt: '#6B4A33', boots: '#4B372B', patch: true, front: PROPS.sword });
const chr_bram = chibi({ hair: HAIR.bram, beard: true, stocky: true, outfit: '#5E7F52', apron: P.wood, boots: '#4B372B', front: PROPS.hammer });
const chr_linnea = chibi({ back: HAIR.linneaBack, hair: HAIR.linnea, front: HAIR.linneaFront + PROPS.satchel, outfit: '#EFE6CF', sleeve: '#9CB38A', boots: '#7A5A40' });
const chr_rook = chibi({ back: HAIR.rookBack, hair: HAIR.rook, front: HAIR.rookFront + PROPS.daggers, outfit: '#3A3A44', boots: '#23232B', belt: '#A33A3A' });
const chr_tamsin = chibi({ back: HAIR.tamsinBack, hair: HAIR.tamsin, freckles: true, outfit: '#4A4A50', apron: '#E07A3A', gloves: '#6B4A33', boots: '#3A3A40', front: PROPS.hammer });

// ---------- Buildings ----------
const bld_throne_t0 = svg(200, 180,
  shadow(100, 168, 86, 10) +
  `<path d="M22 164 L30 146 L170 146 L178 164 Z" fill="${P.stone}" ${stroke(P.lineWarm, 3)}/><path d="M38 146 L44 132 L156 132 L162 146 Z" fill="#EFE5CE" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M150 146 L156 132 L162 146 Z" fill="${P.stoneS}" opacity=".6"/>` +
  // broken pillar
  `<path d="M16 146 L16 92 L22 86 L28 94 L34 88 L34 146 Z" fill="#E6DAC0" ${stroke(P.lineWarm, 3)}/><path d="M28 94 L34 88 L34 146 L28 146 Z" fill="${P.stoneS}" opacity=".6"/>` +
  // throne back
  `<path d="M66 132 L64 56 Q100 22 136 56 L134 132 Z" fill="#D8CFB9" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M100 32 Q124 40 136 56 L134 132 L116 132 L118 60 Q112 44 100 32 Z" fill="#B4AA93" opacity=".6"/>` +
  `<path d="M86 54 L96 70 L90 84 L100 100" ${stroke('#8E846E', 2.5)} fill="none"/>` +
  // sun sigil on the backrest
  `<circle cx="100" cy="58" r="10" fill="none" ${stroke(P.goldD, 2.5)} opacity=".8"/>${[0, 45, 90, 135, 180, 225, 270, 315].map(a => `<path d="M100 44 L100 40" transform="rotate(${a} 100 58)" ${stroke(P.goldD, 2)} opacity=".8"/>`).join('')}` +
  // seat and arms
  `<path d="M58 104 L142 104 L140 132 L60 132 Z" fill="#E6DCC6" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M52 92 L68 92 L68 132 L54 132 Z" fill="#D8CFB9" ${stroke(P.lineWarm, 3)}/><path d="M132 92 L148 92 L146 132 L132 132 Z" fill="#C2B8A1" ${stroke(P.lineWarm, 3)}/>` +
  // moss and vines
  `<path d="M60 58 C70 50 78 52 84 60 C74 60 66 62 60 58 Z" fill="${P.grassM}" ${stroke(P.lineLeaf, 2)}/>` +
  `<path d="M140 70 C130 84 138 96 128 110" ${stroke('#5E9A5C', 3)} fill="none"/>${[[136, 78], [133, 92], [130, 104]].map(([x, y]) => `<ellipse cx="${x}" cy="${y}" rx="5" ry="3" fill="${P.leaf}" ${stroke(P.lineLeaf, 1.5)} transform="rotate(-30 ${x} ${y})"/>`).join('')}` +
  `<path d="M40 146 C48 138 60 140 64 146 Z" fill="${P.grassM}" ${stroke(P.lineLeaf, 2)}/>` +
  // a faint ember on the seat
  `<circle cx="100" cy="116" r="8" fill="${P.gold}" opacity=".35"/><circle cx="100" cy="116" r="3" fill="${P.goldL}"/>`);

const bld_tent = svg(160, 130,
  shadow(80, 120, 64, 8) +
  `<path d="M16 116 L80 22 L144 116 Z" fill="#EADFC4" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M80 22 L144 116 L104 116 Z" fill="#D2C5A6"/>` +
  `<path d="M40 82 L120 82" ${stroke(P.terra, 6)} opacity=".9"/><path d="M52 64 L108 64" ${stroke(P.terra, 5)} opacity=".9"/>` +
  `<path d="M16 116 L80 22 L144 116 Z" fill="none" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M68 116 L80 70 L92 116 Z" fill="#5B4A36" ${stroke(P.lineWarm, 2.5)}/>` +
  `<path d="M80 22 L80 12" ${stroke(P.woodD, 4)}/><path d="M10 120 L20 104 M150 120 L140 104" ${stroke(P.woodD, 3)}/>`);

const bld_hut = svg(170, 160,
  shadow(85, 150, 66, 9) +
  `<path d="M34 146 L34 94 L136 94 L136 146 Z" fill="#C9A57A" ${stroke(P.woodD, 3)}/>` +
  [104, 116, 128, 140].map(y => `<path d="M34 ${y} L136 ${y}" ${stroke('#A07E5A', 2)}/>`).join('') +
  `<path d="M112 94 L136 94 L136 146 L112 146 Z" fill="${P.woodD}" opacity=".25"/>` +
  `<path d="M72 146 L72 114 Q85 104 98 114 L98 146 Z" fill="#5B4A36" ${stroke(P.woodD, 3)}/>` +
  `<path d="M16 100 L85 26 L154 100 Q85 110 16 100 Z" fill="#D9B96A" ${stroke('#8A6A2E', 3)}/>` +
  `<path d="M85 26 L154 100 Q124 106 104 107 Z" fill="#B8964E" opacity=".75"/>` +
  [[40, 90], [58, 72], [76, 56], [98, 60], [116, 78], [132, 92]].map(([x, y]) => `<path d="M${x} ${y} l6 12" ${stroke('#A8843E', 2)}/>`).join(''));

const bld_longhouse = svg(260, 210,
  shadow(130, 196, 112, 12) +
  // facade
  `<path d="M40 110 L220 110 L220 188 L40 188 Z" fill="${P.creamW}" ${stroke(P.lineWarm, 3)}/>` +
  [124, 138, 152, 166, 180].map((y, i) => `<path d="M40 ${y} L220 ${y}" ${stroke('#DCCBA4', 1.5)}/>` +
    Array.from({ length: 6 }, (_, k) => `<path d="M${52 + k * 30 + (i % 2) * 15} ${y - 14} L${52 + k * 30 + (i % 2) * 15} ${y}" ${stroke('#DCCBA4', 1.5)}/>`).join('')).join('') +
  `<path d="M180 110 L220 110 L220 188 L180 188 Z" fill="${P.stoneS}" opacity=".35"/>` +
  `<rect x="40" y="108" width="180" height="6" fill="${P.wood}" ${stroke(P.woodD, 2)}/><rect x="38" y="110" width="6" height="78" fill="${P.wood}" ${stroke(P.woodD, 2)}/><rect x="216" y="110" width="6" height="78" fill="${P.wood}" ${stroke(P.woodD, 2)}/>` +
  // door
  `<path d="M114 188 L114 146 Q130 130 146 146 L146 188 Z" fill="${P.terra}" ${stroke(P.terraD, 3)}/><path d="M122 144 L122 188 M130 138 L130 188 M138 144 L138 188" ${stroke(P.terraS, 2)}/><circle cx="140" cy="168" r="2.5" fill="${P.goldD}"/>` +
  // windows with shutters
  [[62, 132], [170, 132]].map(([x, y]) => `<rect x="${x}" y="${y}" width="24" height="24" rx="2" fill="#35545A" ${stroke(P.lineWarm, 2.5)}/><path d="M${x + 12} ${y} L${x + 12} ${y + 24} M${x} ${y + 12} L${x + 24} ${y + 12}" ${stroke(P.wood, 2)}/>` +
    `<rect x="${x - 12}" y="${y - 1}" width="11" height="26" rx="1.5" fill="${P.terra}" ${stroke(P.terraD, 2)}/><rect x="${x + 25}" y="${y - 1}" width="11" height="26" rx="1.5" fill="${P.terra}" ${stroke(P.terraD, 2)}/>` +
    `<rect x="${x - 4}" y="${y + 27}" width="32" height="9" rx="2" fill="${P.wood}" ${stroke(P.woodD, 2)}/><circle cx="${x + 4}" cy="${y + 26}" r="3" fill="${P.pink}"/><circle cx="${x + 12}" cy="${y + 25}" r="3" fill="${P.white}"/><circle cx="${x + 20}" cy="${y + 26}" r="3" fill="${P.pink}"/>`).join('') +
  // roof
  `<path d="M22 114 L70 38 L190 38 L238 114 Z" fill="${P.terra}" ${stroke(P.terraD, 3)}/>` +
  `<path d="M150 38 L190 38 L238 114 L186 114 Z" fill="${P.terraS}" opacity=".75"/>` +
  [56, 74, 92].map((y, i) => `<path d="M${60 - i * 11} ${y} L${200 + i * 11} ${y}" ${stroke('#9A4A34', 2.5)} opacity=".8"/>`).join('') +
  `<path d="M70 38 L190 38" ${stroke(P.terraD, 5)}/>` +
  // chimney + smoke
  `<rect x="168" y="22" width="18" height="34" fill="${P.stone}" ${stroke(P.lineWarm, 3)}/>` +
  `<circle cx="182" cy="12" r="7" fill="#EDEDE4" opacity=".75"/><circle cx="192" cy="4" r="5" fill="#EDEDE4" opacity=".6"/>` +
  // banner
  `<path d="M28 188 L28 118" ${stroke(P.woodD, 3)}/><path d="M28 120 L52 124 L46 134 L52 144 L28 140 Z" fill="#3E5A8A" ${stroke('#23324F', 2)}/><circle cx="38" cy="131" r="4" fill="${P.gold}"/>`);

const bld_beacon_t2 = svg(150, 250,
  `<defs><radialGradient id="kb-bt"><stop offset="0" stop-color="${P.gold}" stop-opacity=".55"/><stop offset="1" stop-color="${P.gold}" stop-opacity="0"/></radialGradient>` +
  `<linearGradient id="kb-btf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${P.goldL}"/><stop offset=".5" stop-color="${P.gold}"/><stop offset="1" stop-color="${P.ember}"/></linearGradient></defs>` +
  `<circle cx="75" cy="44" r="70" fill="url(#kb-bt)"/>` +
  [0, 30, 60, 120, 150, 180].map(a => `<path d="M75 44 L75 -10" transform="rotate(${a - 90} 75 44)" ${stroke(P.gold, 2)} opacity=".35"/>`).join('') +
  shadow(75, 240, 46, 8) +
  `<path d="M44 238 L50 92 L100 92 L106 238 Z" fill="${P.creamW}" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M86 92 L100 92 L106 238 L90 238 Z" fill="${P.stoneS}" opacity=".45"/>` +
  [120, 150, 180, 210].map(y => `<path d="M${48 + (238 - y) * 0.04} ${y} L${102 - (238 - y) * 0.04} ${y}" ${stroke('#DCCBA4', 2)}/>`).join('') +
  `<path d="M66 172 L66 150 Q75 142 84 150 L84 172 Z" fill="#35545A" ${stroke(P.lineWarm, 2.5)}/>` +
  `<path d="M70 238 L70 208 Q75 202 80 208 L80 238 Z" fill="${P.terra}" ${stroke(P.terraD, 2.5)}/>` +
  `<path d="M36 92 L114 92 Q110 72 75 70 Q40 72 36 92 Z" fill="${P.stone}" ${stroke(P.lineWarm, 3)}/>` +
  `<path d="M75 8 C88 24 100 36 94 54 C90 66 82 70 75 70 C68 70 58 66 56 54 C52 40 66 30 70 18 C73 26 72 32 75 36 C78 30 77 18 75 8 Z" fill="url(#kb-btf)" ${stroke(P.emberD, 2.5)}/>` +
  `<path d="M75 38 C81 46 84 54 80 60 C76 65 70 63 70 56 C70 50 73 46 75 38 Z" fill="${P.goldL}"/>`);

// ---------- Icons (64 × 64) ----------
const ico_turnip = svg(64, 64,
  leafPair(32, 26, 1.1) + `<ellipse cx="32" cy="40" rx="15" ry="13" fill="${P.white}" ${stroke('#7A6A8A', 2.5)}/>` +
  `<path d="M17 36 Q32 18 47 36 Q32 30 17 36 Z" fill="#B48ACB"/><path d="M32 53 L32 60" ${stroke('#7A6A8A', 2)}/><ellipse cx="26" cy="40" rx="3" ry="4" fill="#fff"/>`);
const ico_copper_ore = svg(64, 64,
  `<path d="M8 50 L12 24 L30 12 L52 16 L58 38 L50 54 Q30 60 8 50 Z" fill="${P.rock}" ${stroke(P.rockLine, 2.5)}/>` +
  `<path d="M12 24 L30 12 L52 16 L44 26 L24 30 Z" fill="${P.rockL}"/>` +
  `<path d="M20 36 L28 32 L36 40 L46 34" ${stroke('#D9793A', 4)} fill="none"/><circle cx="34" cy="46" r="4" fill="#E08A48" ${stroke('#9A4A1E', 1.5)}/><circle cx="18" cy="44" r="3" fill="#E08A48" ${stroke('#9A4A1E', 1.5)}/>`);
const ico_veilglass = svg(64, 64,
  `<defs><linearGradient id="kb-ivg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#D8CCFF"/><stop offset=".6" stop-color="${P.veil}"/><stop offset="1" stop-color="${P.veilT}"/></linearGradient></defs>` +
  `<path d="M32 4 L46 20 L40 58 L24 58 L18 20 Z" fill="url(#kb-ivg)" ${stroke('#3B2A7A', 2.5)}/><path d="M32 8 L24 22 L27 52" ${stroke('#F0EBFF', 2)} fill="none" opacity=".85"/>` +
  `<path d="M50 30 l2 4 l4 2 l-4 2 l-2 4 l-2 -4 l-4 -2 l4 -2 Z" fill="${P.veilT}"/>`);
const ico_twine_sigil = svg(64, 64,
  `<circle cx="32" cy="32" r="22" fill="#E8D8B0" ${stroke('#8A6A3E', 3)}/><circle cx="32" cy="32" r="15" fill="none" ${stroke('#B8964E', 3)} stroke-dasharray="4 3"/>` +
  `<path d="M32 20 L40 36 L24 36 Z" fill="none" ${stroke(P.veil, 2.5)}/><circle cx="32" cy="31" r="3" fill="${P.veilT}"/>` +
  `<path d="M46 50 C52 56 56 58 60 58" ${stroke('#8A6A3E', 2.5)} fill="none"/>`);
const ico_herb = svg(64, 64,
  `<path d="M32 60 C30 44 32 28 34 10" ${stroke(P.lineLeaf, 3)} fill="none"/>` +
  [[30, 46, -1], [32, 34, 1], [33, 24, -1]].map(([x, y, d]) => `<path d="M${x} ${y} C${x + 16 * d} ${y - 2} ${x + 18 * d} ${y - 12} ${x + 6 * d} ${y - 14} C${x + 4 * d} ${y - 8} ${x} ${y - 6} ${x} ${y} Z" fill="${P.leaf}" ${stroke(P.lineLeaf, 2)}/>`).join('') +
  [[36, 10], [30, 8], [33, 4]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3" fill="${P.white}" stroke="#9FB3B4" stroke-width="1.2"/>`).join(''));
const ico_stew = svg(64, 64,
  `<path d="M8 30 L56 30 Q54 54 32 56 Q10 54 8 30 Z" fill="${P.terra}" ${stroke(P.terraD, 2.5)}/><path d="M40 32 L56 30 Q54 54 36 56 Q46 46 40 32 Z" fill="${P.terraS}" opacity=".6"/>` +
  `<ellipse cx="32" cy="30" rx="24" ry="6" fill="#C9763E" ${stroke(P.terraD, 2.5)}/>` +
  `<circle cx="24" cy="29" r="3" fill="#F09A4A"/><circle cx="34" cy="31" r="3" fill="#EFE3C8"/><circle cx="40" cy="28" r="2.5" fill="#7DB26A"/>` +
  `<path d="M22 20 q-4 -6 0 -10 M32 18 q-4 -6 0 -12 M42 20 q-4 -6 0 -10" ${stroke('#D9D4C8', 2.5)} fill="none" opacity=".8"/>`);
const ico_hoe = svg(64, 64,
  `<path d="M12 56 L46 16" ${stroke(P.woodD, 8)}/><path d="M12 56 L46 16" ${stroke(P.wood, 4)}/>` +
  `<path d="M40 10 L58 16 L54 26 L42 20 Z" fill="#9AA0A6" ${stroke('#4E5550', 2.5)}/><path d="M44 12 L56 16" ${stroke('#D5DADF', 2)}/>`);
const ico_gold = svg(64, 64,
  `<circle cx="32" cy="34" r="20" fill="${P.gold}" ${stroke(P.goldLine, 3)}/><circle cx="32" cy="34" r="14" fill="none" ${stroke(P.goldD, 2)}/>` +
  `<path d="M24 30 L28 36 L32 28 L36 36 L40 30 L39 40 L25 40 Z" fill="${P.goldD}"/><ellipse cx="25" cy="25" rx="5" ry="3" fill="${P.goldL}" opacity=".8"/>`);
const ico_signet = svg(64, 64,
  `<ellipse cx="32" cy="38" rx="18" ry="16" fill="none" ${stroke(P.goldLine, 8)}/><ellipse cx="32" cy="38" rx="18" ry="16" fill="none" ${stroke(P.gold, 4)}/>` +
  `<circle cx="32" cy="20" r="11" fill="${P.gold}" ${stroke(P.goldLine, 2.5)}/><circle cx="32" cy="20" r="4" fill="${P.goldL}"/>` +
  [0, 45, 90, 135, 180, 225, 270, 315].map(a => `<path d="M32 11 L32 13" transform="rotate(${a} 32 20)" ${stroke(P.goldLine, 1.5)}/>`).join(''));

export const KINGSBLOOM = (size = 64, id = 'kb-kbl') => svg(size, size,
  `<g transform="scale(${size / 64})"><defs><radialGradient id="${id}" cx=".5" cy=".75" r=".75"><stop offset="0" stop-color="${P.pink}"/><stop offset=".55" stop-color="#FFF7E0"/><stop offset="1" stop-color="#FFFDF6"/></radialGradient></defs>` +
  `<path d="M32 62 C32 52 31 46 32 38" ${stroke(P.lineLeaf, 3)} fill="none"/>` +
  `<path d="M32 54 C22 52 18 46 18 40 C26 40 30 46 32 54 Z" fill="${P.leaf}" ${stroke(P.lineLeaf, 2)}/>` +
  [-72, -36, 0, 36, 72].map(a => `<path d="M32 30 C22 22 22 8 32 4 C42 8 42 22 32 30 Z" transform="rotate(${a} 32 30)" fill="url(#${id})" ${stroke('#C9963A', 2)}/>`).join('') +
  `<path d="M26 30 L26 24 L29 27 L32 22 L35 27 L38 24 L38 30 Z" fill="${P.gold}" ${stroke(P.goldLine, 1.5)}/><circle cx="32" cy="30" r="3" fill="${P.goldD}"/></g>`);

const ELEMENTS = {
  terra: ['#7E8F4A', `<rect x="12" y="12" width="40" height="40" rx="6"/>`],
  aqua: ['#3F8FC0', `<circle cx="32" cy="32" r="21"/>`],
  ignis: ['#E0613A', `<path d="M32 9 L55 52 L9 52 Z"/>`],
  zephyr: ['#4FB89A', `<path d="M32 8 L56 32 L32 56 L8 32 Z"/>`],
  lumen: ['#E3A92A', `<path d="M32 7 L38.5 24 L56 24.5 L42 35.5 L47 53 L32 43 L17 53 L22 35.5 L8 24.5 L25.5 24 Z"/>`],
  umbra: ['#5B4FA8', `<path d="M53.6 33.9 A21.6 21.6 0 1 1 30.1 10.4 A16.8 16.8 0 0 0 53.6 33.9 Z"/>`],
  veil: ['#7A5CE0', `<circle cx="32" cy="32" r="21"/><path d="M20 20 L44 44 M44 20 L20 44" stroke="#fff" stroke-width="5" stroke-linecap="round"/>`],
};
const elementIcon = k => svg(64, 64, `<g fill="${ELEMENTS[k][0]}" stroke="#2E3327" stroke-width="2.5" stroke-linejoin="round">${ELEMENTS[k][1]}</g>`);

// ---------- Logo (256 × 256) ----------
export const LOGO = svg(256, 256,
  `<defs><linearGradient id="kb-lg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE08A"/><stop offset=".6" stop-color="${P.gold}"/><stop offset="1" stop-color="${P.goldD}"/></linearGradient>` +
  `<radialGradient id="kb-lglow"><stop offset="0" stop-color="${P.gold}" stop-opacity=".35"/><stop offset="1" stop-color="${P.gold}" stop-opacity="0"/></radialGradient>` +
  `<radialGradient id="kb-lbud" cx=".5" cy=".8" r=".8"><stop offset="0" stop-color="${P.pink}"/><stop offset=".6" stop-color="#FFF7E0"/><stop offset="1" stop-color="#FFFDF6"/></radialGradient></defs>` +
  `<circle cx="128" cy="140" r="116" fill="url(#kb-lglow)"/>` +
  // left half of the crown
  `<g transform="rotate(-7 118 200)"><path d="M40 204 L34 120 L66 152 L90 100 L112 148 L120 132 L114 170 L122 186 L116 204 Z" fill="url(#kb-lg)" ${stroke(P.goldLine, 5)}/>` +
  `<path d="M42 196 L114 196" ${stroke(P.goldLine, 4)}/><circle cx="34" cy="116" r="8" fill="${P.berry}" ${stroke(P.goldLine, 3)}/><circle cx="90" cy="96" r="9" fill="#3F8FC0" ${stroke(P.goldLine, 3)}/><circle cx="72" cy="178" r="7" fill="${P.berry}" ${stroke(P.goldLine, 3)}/></g>` +
  // right half of the crown
  `<g transform="rotate(7 138 200)"><path d="M216 204 L222 120 L190 152 L166 100 L144 148 L136 132 L142 170 L134 186 L140 204 Z" fill="url(#kb-lg)" ${stroke(P.goldLine, 5)}/>` +
  `<path d="M214 196 L142 196" ${stroke(P.goldLine, 4)}/><circle cx="222" cy="116" r="8" fill="${P.berry}" ${stroke(P.goldLine, 3)}/><circle cx="166" cy="96" r="9" fill="#3F8FC0" ${stroke(P.goldLine, 3)}/><circle cx="184" cy="178" r="7" fill="${P.berry}" ${stroke(P.goldLine, 3)}/></g>` +
  // sprout through the crack
  `<path d="M128 214 C126 180 124 150 130 104 C132 88 128 76 128 64" ${stroke(P.lineLeaf, 6)} fill="none"/><path d="M128 214 C126 180 124 150 130 104 C132 88 128 76 128 64" ${stroke('#6FA864', 3)} fill="none"/>` +
  `<path d="M128 150 C106 146 94 128 96 112 C114 114 126 128 128 150 Z" fill="${P.leaf}" ${stroke(P.lineLeaf, 4)}/><path d="M112 124 C118 132 124 140 128 150" ${stroke(P.leafHi, 2.5)} fill="none"/>` +
  `<path d="M130 126 C150 120 160 102 156 88 C140 92 130 106 130 126 Z" fill="${P.leafHi}" ${stroke(P.lineLeaf, 4)}/>` +
  // the Kingsbloom bud
  `<path d="M128 70 C110 60 112 30 128 18 C144 30 146 60 128 70 Z" fill="url(#kb-lbud)" ${stroke('#C9963A', 4)}/>` +
  `<path d="M128 70 C120 60 120 40 128 26" ${stroke('#E9B8C0', 3)} fill="none"/>` +
  `<path d="M116 66 C120 74 136 74 140 66 C134 70 122 70 116 66 Z" fill="${P.leaf}" ${stroke(P.lineLeaf, 3)}/>`);

// ---------- Registry ----------
const A = (id, label, cat, ms, markup, note = '') => ({ id, label, cat, ms, svg: markup, note });

export const ASSETS = [
  A('logo_kingsbloom', 'Kingsbloom logo', 'brand', 'VS', LOGO, 'Broken crown, a sprout through the crack, a Kingsbloom bud on top'),
  A('chr_sovereign', 'The Sovereign', 'character', 'VS', chr_sovereign, 'Tattered royal coat; no crown'),
  A('chr_flicker', 'Flicker', 'character', 'VS', FLICKER, 'The last spark of the Heartflame'),
  A('chr_bram', 'Bram', 'character', 'VS', chr_bram, 'Carpenter · signature: hammer, bandana'),
  A('chr_linnea', 'Linnea', 'character', 'VS', chr_linnea, 'Healer · signature: braid with flowers, satchel'),
  A('chr_rook', 'Rook', 'character', 'VS', chr_rook, 'Scout · signature: white streak, crow cloak'),
  A('chr_tamsin', 'Tamsin', 'character', 'VS', chr_tamsin, 'Smith · signature: ponytail, orange apron'),
  A('cre_mossbun', 'Mossbun', 'creature', 'VS', cre_mossbun, 'Terra · Offering (Carrot) · Tending'),
  A('cre_puddlepup', 'Puddlepup', 'creature', 'VS', cre_puddlepup, 'Aqua · Subdue · Watering'),
  A('cre_emberkit', 'Emberkit', 'creature', 'VS', cre_emberkit, 'Ignis · Subdue · Kindling'),
  A('cre_glimmoth', 'Glimmoth', 'creature', 'VS', cre_glimmoth, 'Lumen · Offering at night · Lighting'),
  A('cre_jellop', 'Jellop', 'creature', 'VS', cre_jellop, 'Aqua · Subdue · Hauling'),
  A('amb_wispling', 'Wispling', 'creature', 'VS', amb_wispling, 'Ambient · numbers mirror kingdom happiness'),
  A('tile_grass', 'Meadow grass', 'terrain', 'VS', tile_grass, '64 px tile at 1080p'),
  A('tile_path', 'Dirt path', 'terrain', 'VS', tile_path),
  A('tile_tilled', 'Tilled soil', 'terrain', 'VS', tile_tilled),
  A('tile_watered', 'Watered soil', 'terrain', 'VS', tile_watered),
  A('tile_water', 'River water', 'terrain', 'VS', tile_water, 'Animated by shader in-game'),
  A('tile_veil', 'Veil-choked soil', 'terrain', 'VS', tile_veil, 'Purified when the Realm covers it'),
  A('prp_tree_sapling', 'Oak: sapling', 'prop', 'VS', prp_tree_sapling),
  A('prp_tree_young', 'Oak: young', 'prop', 'VS', prp_tree_young),
  A('prp_tree_round', 'Oak: mature', 'prop', 'VS', prp_tree_round),
  A('prp_pine', 'Pine', 'prop', 'VS', prp_pine),
  A('prp_mushroom_giant', 'Giant mushrooms', 'prop', 'EA', prp_mushroom, 'Whisperwood forest-floor set'),
  A('prp_rock', 'Mossy rock', 'prop', 'VS', prp_rock),
  A('prp_stump', 'Stump', 'prop', 'VS', prp_stump),
  A('prp_fern', 'Fern', 'prop', 'VS', prp_fern),
  A('prp_berry_bush', 'Berry bush', 'prop', 'VS', prp_berry_bush),
  A('prp_lily_lotus', 'Lily pad & lotus', 'prop', 'VS', prp_lily),
  A('prp_veil_crystal', 'Veilglass node', 'prop', 'VS', prp_veil_crystal, 'Grows outside the light'),
  A('prp_brazier', 'Heartflame Brazier', 'prop', 'VS', prp_brazier, 'Beacon tier 1'),
  A('prp_lumen_lamp', 'Lumen Lamp', 'prop', 'VS', prp_lumen_lamp),
  A('crop_turnip_1', 'Turnip · planted', 'crop', 'VS', crop_turnip_1),
  A('crop_turnip_2', 'Turnip · sprout', 'crop', 'VS', crop_turnip_2),
  A('crop_turnip_3', 'Turnip · young', 'crop', 'VS', crop_turnip_3),
  A('crop_turnip_4', 'Turnip · mature', 'crop', 'VS', crop_turnip_4),
  A('crop_turnip_5', 'Turnip · ready', 'crop', 'VS', crop_turnip_5),
  A('crop_dawnbell', 'Dawnbell', 'crop', 'VS', crop_dawnbell, 'Fantasy flower; attracts Glimmoth'),
  A('crop_mandrake', 'Mandrake Root', 'crop', 'VS', crop_mandrake, '5% chance to be a Mandragling'),
  A('bld_throne_t0', 'The Ashen Throne', 'building', 'VS', bld_throne_t0, 'Throne tier 0: where you wake'),
  A('bld_tent', 'Tent', 'building', 'VS', bld_tent),
  A('bld_hut', 'Hut', 'building', 'VS', bld_hut),
  A('bld_longhouse', 'Longhouse', 'building', 'VS', bld_longhouse, 'Throne tier 1: the Founding'),
  A('bld_beacon_t2', 'Beacon Tower', 'building', 'VS', bld_beacon_t2, 'Beacon tier 2: radius 18 tiles'),
  A('ico_turnip', 'Turnip', 'icon', 'VS', ico_turnip),
  A('ico_copper_ore', 'Copper Ore', 'icon', 'VS', ico_copper_ore),
  A('ico_veilglass', 'Veilglass', 'icon', 'VS', ico_veilglass),
  A('ico_twine_sigil', 'Twine Sigil', 'icon', 'VS', ico_twine_sigil),
  A('ico_healing_herb', 'Healing Herb', 'icon', 'VS', ico_herb),
  A('ico_vegetable_stew', 'Vegetable Stew', 'icon', 'VS', ico_stew),
  A('ico_hoe', 'Hoe', 'icon', 'VS', ico_hoe),
  A('ico_gold', 'Gold', 'icon', 'VS', ico_gold),
  A('ico_signet', 'The Signet', 'icon', 'VS', ico_signet, 'Regalia #1'),
  A('ico_kingsbloom', 'Kingsbloom', 'icon', '1.0', KINGSBLOOM(64, 'kb-kbl-icon'), 'The title flower'),
  ...Object.keys(ELEMENTS).map(k => A(`ico_el_${k}`, k[0].toUpperCase() + k.slice(1), 'element', 'VS', elementIcon(k))),
];
