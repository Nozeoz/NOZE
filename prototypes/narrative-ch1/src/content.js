// Kingsbloom Chapter 1 prototype: game data.
// Numbers are prototype placeholders for tuning (docs/07 §3.7, docs/06). Item IDs follow docs/06 §1.

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const PHASES = ['Morning', 'Afternoon', 'Evening', 'Night'];
export const SEASON_LENGTH = 28;
export const SEASONS = ['Spring', 'Summer', 'Autumn', 'Winter'];

export const ITEMS = {
  mat_wood: { name: 'Wood', sell: 2 },
  min_stone: { name: 'Stone', sell: 2 },
  mat_fiber: { name: 'Fiber', sell: 3 },
  frg_healing_herb: { name: 'Healing Herb', sell: 15 },
  frg_forage: { name: 'Wild greens', sell: 10, ration: 1 },
  crop_turnip: { name: 'Turnip', sell: 36, ration: 1, crop: true },
  crop_carrot: { name: 'Carrot', sell: 55, ration: 1, crop: true },
  crop_potato: { name: 'Potato', sell: 85, ration: 2, crop: true },
  crop_dawnbell: { name: 'Dawnbell', sell: 90, crop: true, flower: true },
  seed_turnip: { name: 'Turnip seeds' },
  seed_carrot: { name: 'Carrot seeds' },
  seed_potato: { name: 'Potato seeds' },
  seed_dawnbell: { name: 'Dawnbell seeds' },
  min_copper_ore: { name: 'Copper Ore', sell: 20 },
  min_veilglass: { name: 'Veilglass', sell: 60 },
  sig_twine: { name: 'Twine Sigil' },
  sig_treat: { name: 'Creature Treat', sell: 15 },
  mat_exotic_spice: { name: 'Exotic Spice', sell: 45 },
  trk_crow_charm: { name: 'Crow-Feather Charm', sell: 60 },
  con_healing_salve: { name: 'Healing Salve' },
  food_roasted_turnip: { name: 'Roasted Turnip', energy: 15, ration: 1, dish: true, sell: 45 },
  food_foragers_skewer: { name: "Forager's Skewer", energy: 20, ration: 1, dish: true, sell: 30 },
  food_baked_potato: { name: 'Baked Potato', energy: 25, ration: 2, dish: true, sell: 100 },
  food_herb_tea: { name: 'Herb Tea', energy: 10, dish: true, sell: 30, warms: true },
  food_vegetable_stew: { name: 'Vegetable Stew', energy: 45, ration: 3, dish: true, sell: 190 },
  key_expedition_report: { name: 'Survey 7 report', key: true },
  key_regalia_signet: { name: 'The Signet', key: true },
  key_magpie_slingshot: { name: "Magpie's slingshot", key: true },
};

export const CROPS = {
  crop_turnip: { seed: 'seed_turnip', days: 4 },
  crop_carrot: { seed: 'seed_carrot', days: 5 },
  crop_potato: { seed: 'seed_potato', days: 6 },
  crop_dawnbell: { seed: 'seed_dawnbell', days: 7 },
};

// Cooking and crafting are free actions (they don't use up the time of day). `unlock` names the unlock that teaches it.
export const RECIPES = [
  { id: 'food_roasted_turnip', needs: { crop_turnip: 1 } },
  { id: 'food_foragers_skewer', needs: { frg_forage: 2 } },
  { id: 'food_baked_potato', needs: { crop_potato: 1 }, unlock: 'recipe:food_baked_potato' },
  { id: 'food_herb_tea', needs: { frg_healing_herb: 1, frg_forage: 1 }, unlock: 'recipe:food_herb_tea' },
  { id: 'food_vegetable_stew', needs: { crop_carrot: 1, crop_potato: 1, frg_forage: 1 }, unlock: 'recipe:food_vegetable_stew' },
  { id: 'sig_twine', needs: { mat_fiber: 3 }, unlock: 'recipe:sig_twine', craft: true },
  { id: 'sig_treat', needs: { crop_carrot: 1, frg_forage: 1 }, unlock: 'familiar:tending', craft: true },
];

// Buildings you order from Bram. Beds house settlers; Sworn live in their own buildings.
export const BUILDINGS = {
  tent: { name: 'Tent', cost: { mat_wood: 10, mat_fiber: 5 }, days: 0, beds: 1, repeat: true,
    desc: 'Sleeps one settler. Goes up at once.', needs: g => g.flag('ch1_campfire') },
  longhouse: { name: 'Longhouse', cost: { mat_wood: 80, min_stone: 50, gold: 150 }, days: 2, beds: 2,
    desc: 'Throne tier 1: your home, the Founding, and Court Day. Sleeps two settlers.', needs: g => g.flag('ch1_longhouse_planned') },
  hut: { name: 'Hut', cost: { mat_wood: 40, min_stone: 20 }, days: 1, beds: 2, repeat: true,
    desc: 'Sleeps two settlers.', needs: g => g.flag('ch1_founded') },
  commons: { name: 'Commons Field', cost: { mat_wood: 20, min_stone: 10 }, days: 1, repeat: true,
    desc: 'Three settlers can farm it for the Granary: +2 rations each a day instead of +1.', needs: g => g.flag('ch1_founded') },
  kitchen: { name: 'Kitchen', cost: { mat_wood: 40, min_stone: 30, gold: 60 }, days: 1,
    desc: "Marigold's kitchen. Hot meals raise Joy.", needs: g => g.flag('npc_marigold_met') },
  beacon_tower: { name: 'Beacon Tower', cost: { min_stone: 60, mat_wood: 30, min_copper_ore: 8, min_veilglass: 5 }, days: 2,
    desc: 'Beacon tier 2: the Realm grows to 18 tiles. Needs Tamsin for the metalwork. Required for Village.',
    needs: g => g.flag('ch1_founded') && g.flag('npc_tamsin_recruited') },
  waybeacon: { name: 'Waybeacon', cost: { min_stone: 20, min_veilglass: 3, min_copper_ore: 2 }, days: 1,
    desc: 'A beacon at the Veil Wall. Opens the road north.', needs: g => g.flag('ch1_bridge_restored') },
};

// Buildings that come free with a Sworn (they live and work there).
export const SWORN_BUILDINGS = {
  lodge: 'npc_bram_recruited', clinic: 'npc_linnea_recruited', scout_post: 'npc_rook_recruited',
  smithy: 'npc_tamsin_recruited', den: 'npc_juniper_recruited',
};

export const PROJECTS = {
  granary: {
    name: 'The Old Granary', unlock: 'project:granary', done: 'mq110_stairs',
    reward: 'Granary T1: your stores hold 200 rations, and something lies beneath it…',
    bundles: [
      { id: 'harvest', name: 'Spring Harvest', needs: { crop_any: 6 } },
      { id: 'timber', name: 'Timber & Stone', needs: { mat_wood: 40, min_stone: 30 } },
      { id: 'basket', name: "Forager's Basket", needs: { frg_forage: 8, frg_healing_herb: 3 } },
    ],
  },
  bridge: {
    name: 'The Old Bridge', unlock: 'project:bridge', done: 'mq117_bridge_done',
    reward: 'The road north, up to the Veil Wall.',
    bundles: [
      { id: 'timber', name: 'Timber', needs: { mat_wood: 50 } },
      { id: 'stone', name: 'Stone', needs: { min_stone: 40 } },
      { id: 'iron', name: 'Metal fittings', needs: { min_copper_ore: 5 } },
    ],
  },
};

// Mira's caravan: Tuesdays and Fridays, morning and afternoon.
export const SHOP = [
  { id: 'seed_turnip', price: 20 },
  { id: 'seed_carrot', price: 30 },
  { id: 'seed_potato', price: 50 },
  { id: 'seed_dawnbell', price: 40 },
  { id: 'crop_carrot', price: 40 },
  { id: 'sig_treat', price: 30 },
  { id: 'mat_exotic_spice', price: 90 },
  { id: 'trk_crow_charm', price: 120, needs: 'npc_rook_met' },
  { id: 'pack_rations', name: 'Dried rations ×5 (straight to your stores)', price: 45, needs: 'ch1_founded' },
];

// People. `art` points at a placeholder-kit portrait (art/placeholder); the rest get a monogram.
export const NPCS = {
  flicker: { name: 'Flicker', color: '#E8A21F', art: 'chr_flicker' },
  you: { name: 'You', color: '#56608A', art: 'chr_sovereign' },
  bram: { name: 'Bram', full: 'Bram Holloway', color: '#5E7F52', art: 'chr_bram', sworn: true, role: 'Carpenter',
    building: "Carpenter's Lodge", purpose: 'Builds everything. Helping him speeds up construction.',
    loved: ['food_vegetable_stew'], liked: ['mat_wood', 'food_roasted_turnip', 'food_baked_potato', 'food_foragers_skewer'], disliked: ['crop_dawnbell'], birthday: ['Autumn', 2] },
  linnea: { name: 'Linnea', full: 'Linnea Marsh', color: '#7FA06C', art: 'chr_linnea', sworn: true, romance: true, role: 'Healer',
    building: 'Herbalist Hut', purpose: 'Catches you after a knockout and turns herbs into salves.',
    loved: ['crop_dawnbell'], liked: ['frg_healing_herb', 'frg_forage', 'food_herb_tea'], disliked: ['min_copper_ore'], birthday: ['Spring', 5] },
  rook: { name: 'Rook', full: 'Rook', color: '#A33A3A', art: 'chr_rook', sworn: true, romance: true, role: 'Scout',
    building: "Scout's Post", purpose: 'Scouts floors and bounties: +1 floor per dive, and coin when you help.',
    loved: ['trk_crow_charm'], liked: ['frg_forage', 'food_roasted_turnip', 'food_foragers_skewer', 'food_baked_potato', 'food_vegetable_stew'], disliked: [], birthday: ['Summer', 3] },
  tamsin: { name: 'Tamsin', full: 'Tamsin Hale', color: '#D9672B', art: 'chr_tamsin', sworn: true, romance: true, role: 'Blacksmith',
    building: 'Smithy', purpose: 'Forges your blade and the metalwork for bigger buildings.',
    loved: [], liked: ['min_copper_ore', 'min_veilglass'], disliked: [], birthday: ['Autumn', 6] },
  juniper: { name: 'Juniper', full: 'Juniper Thistle', color: '#2FA79A', sworn: true, role: 'Beast Warden',
    building: 'Den', purpose: 'Cares for your familiars; the herd forages greens for the stores.',
    loved: ['sig_treat'], liked: ['crop_carrot', 'frg_forage'], disliked: [], birthday: ['Spring', 10] },
  marigold: { name: 'Marigold', full: 'Marigold Fenn', color: '#D98A1E', sworn: true, role: 'Cook',
    building: 'Kitchen', purpose: 'Hot meals: more Joy, more settlers, fuller stores.',
    loved: ['mat_exotic_spice'], liked: ['crop_turnip', 'crop_carrot', 'crop_potato', 'frg_forage'], disliked: ['min_copper_ore', 'min_stone'], birthday: ['Summer', 25] },
  mira: { name: 'Mira', full: 'Mira Caravel', color: '#C98B2C', role: 'Merchant', purpose: 'Buys what you grow, sells seeds and rare things. Tuesdays and Fridays.',
    loved: ['mat_exotic_spice'], liked: ['min_veilglass', 'trk_crow_charm'], disliked: ['mat_wood', 'min_stone'], birthday: ['Autumn', 11] },
  hob: { name: 'Hob', full: 'Hob Furrow', color: '#8E6D56', role: 'Settler · Farmer', purpose: 'Your first settler. Farms the Commons.',
    loved: [], liked: ['crop_turnip', 'crop_carrot', 'crop_potato'], disliked: [], birthday: null },
  pip: { name: 'Pip', color: '#D98A1E' },
  magpie: { name: 'Magpie', color: '#4A4A55' },
  jackdaw: { name: 'Jackdaw', color: '#4A4A55' },
  finch: { name: 'Finch', color: '#4A4A55' },
};

export const SWORN_ORDER = ['bram', 'linnea', 'rook', 'tamsin', 'juniper', 'marigold'];

// Generated settlers (docs/04 §6): Dawnmere-style names, backgrounds, and VS traits.
export const SETTLER_NAMES = ['Ada Quill', 'Tobias Reed', 'Nell Ashby', 'Wren Hartley', 'Silas Moor', 'Elsie Barrow', 'Ned Fallow',
  'Maud Tanner', 'Perrin Vale', 'Hester Brook', 'Joss Weller', 'Tilly Cobb', 'Rufus Penn', 'Clem Harrow', 'Bea Lark', 'Osric Lowe',
  'Mabel Dunn', 'Kit Sorrel', 'Agnes Pike', 'Walter Gale'];
export const BACKGROUNDS = ['farmhand', 'soldier', 'scribe', 'sailor', 'miner', 'Veil orphan', 'minstrel', 'cook', 'woodcutter', 'artisan', 'acolyte', 'merchant'];
export const TRAITS = [
  ['Hardworking', 'hardworking'], ['Lazy', 'a bit lazy, honestly'], ['Green Thumb', 'good with growing things'],
  ['Strong Back', 'strong in the back'], ['Night Owl', 'a night owl'], ['Early Bird', 'an early riser'],
  ['Beast Friend', 'good with animals'], ['Glutton', 'always hungry'], ['Cheerful', 'cheerful'],
  ['Gloomy', 'a bit gloomy'], ['Brave', 'brave'], ['Timid', 'timid'],
];

export const DECREES = {
  harvest_tithe: { name: 'Harvest Tithe', effect: '10% of harvests go to the Granary; crop sales −5%' },
  open_gates: { name: 'Open Gates', effect: 'Settler arrivals ×2; Safety −10' },
  night_curfew: { name: 'Night Curfew', effect: 'Night incidents −50%; Joy −5' },
  rationing: { name: 'Rationing', effect: 'Food eaten −25%; Joy −10' },
  festival_year: { name: 'Festival Year', effect: 'Festival Joy ×2' },
  mercy_edict: { name: 'Mercy Edict', effect: 'Spared enemies join faster; Safety −5' },
};

// Rank requirements (docs/07 §2).
export const RANKS = [
  { name: "Exile's Camp" },
  { name: 'Hamlet', residents: 3, sworn: 2 },
  { name: 'Village', residents: 12, sworn: 5 },
];

// When scenes play. The game checks this list at the start of every part of the day
// (and after every scene), and plays the first scene whose conditions hold.
// phase: when it can start · after: what the scene uses up ('phase' | 'night' | 'dawn'; default: nothing)
export const SCENES = [
  { knot: 'mq101_waking', when: g => !g.flag('ch1_woke') },
  { knot: 'mq101_campfire', when: g => g.flag('ch1_woke') && !g.flag('ch1_campfire') && g.item('mat_wood') >= 10 && g.item('min_stone') >= 5 },
  { knot: 'mq102_first_night', phase: 'Night', when: g => g.flag('ch1_woke') && !g.flag('ch1_survived_night1'), after: 'dawn' },
  { knot: 'mq103_old_fields', phase: 'Morning', when: g => g.flag('ch1_survived_night1') && !g.flag('ch1_first_crops') },
  { knot: 'fest_blossomfall', phase: 'Morning', when: g => g.season === 'Spring' && g.seasonDay === 13 && g.flag('ch1_founded'), after: 'night' },
  { knot: 'mq104_smoke', phase: 'Morning', when: g => g.flag('ch1_first_crops') && g.day >= 3 && !g.flag('ch1_smoke_seen') },
  { knot: 'mq105_intro', phase: 'Evening', when: g => g.flag('ch1_first_crops') && !g.flag('ch1_meadow_shown') },
  { knot: 'mq106_lost_healer', phase: 'Evening', when: g => g.flag('npc_bram_recruited') && g.day >= 5 && !g.flag('npc_linnea_recruited'), after: 'dawn' },
  { knot: 'mq107_plans', phase: 'Morning', when: g => g.flag('npc_linnea_recruited') && !g.flag('ch1_longhouse_planned') },
  { knot: 'mq107_hob', phase: 'Morning', when: g => g.flag('npc_linnea_recruited') && g.day >= 6 && !g.flag('npc_hob_arrived') },
  { knot: 'mq107_founding', phase: ['Morning', 'Afternoon', 'Evening'], when: g => g.built('longhouse') && g.flag('npc_hob_arrived') && !g.flag('ch1_founded') },
  { knot: 'mq110_granary', phase: 'Morning', when: g => g.flag('ch1_founded') && g.day > g.v('ch1_founded_day') && !g.flag('ch1_granary_shown') },
  { knot: 'mq108_crowfeather', phase: 'Night', when: g => g.flag('ch1_founded') && g.day > g.v('ch1_founded_day') && !g.flag('npc_rook_met') },
  { knot: 'mq109_trial_start', phase: 'Morning', when: g => g.v('npc_rook_trial') === 'active' && !g.played('mq109_trial_start') },
  { knot: 'mq109_join', phase: 'Morning', when: g => ['active', 'late'].includes(g.v('npc_rook_trial')) && g.stat('food') >= 28 },
  { knot: 'mq109_deadline', phase: 'Morning', when: g => g.v('npc_rook_trial') === 'active' && g.s.trialDays <= 0 },
  { knot: 'mq113_feast', phase: 'Evening', when: g => g.flag('ch1_signet') && (g.flag('npc_rook_recruited') || g.flag('deed_banished_rook')) && !g.flag('ch1_vs_complete'), after: 'night' },
  { knot: 'sq114_cart', phase: 'Evening', when: g => g.flag('ch1_vs_complete') && g.day > g.v('ch1_vs_day') && !g.flag('npc_marigold_met'), after: 'phase' },
  { knot: 'sq114_kitchen', when: g => g.built('kitchen') && !g.flag('npc_marigold_recruited') },
  { knot: 'mq116_court', phase: 'Morning', when: g => g.weekday === 'Sun' && g.flag('ch1_vs_complete') && !g.flag('court_held') && g.villageReady(), after: 'phase' },
  { knot: 'court_weekly', phase: 'Morning', repeat: true, when: g => g.weekday === 'Sun' && g.flag('court_held') && g.s.courtDay !== g.day },
  { knot: 'mq117_bridge', phase: 'Morning', when: g => g.flag('court_held') && !g.flag('ch1_bridge_shown') },
  { knot: 'mq117_waybeacon', when: g => g.built('waybeacon') && !g.flag('ch1_complete') },
];

// Heart events play at the start of an evening, one per evening (docs/14 §6).
export const HEART_EVENTS = [
  { npc: 'bram', hearts: 2, knot: 'heart_bram_2', flag: 'ev_bram_2' },
  { npc: 'linnea', hearts: 2, knot: 'heart_linnea_2', flag: 'ev_linnea_2' },
  { npc: 'rook', hearts: 2, knot: 'heart_rook_2', flag: 'ev_rook_2' },
  { npc: 'tamsin', hearts: 2, knot: 'heart_tamsin_2', flag: 'ev_tamsin_2' },
  { npc: 'juniper', hearts: 2, knot: 'heart_juniper_2', flag: 'ev_juniper_2' },
  { npc: 'marigold', hearts: 2, knot: 'heart_marigold_2', flag: 'ev_marigold_2' },
  { npc: 'bram', hearts: 4, knot: 'heart_bram_4', flag: 'ev_bram_4' },
  { npc: 'linnea', hearts: 4, knot: 'heart_linnea_4', flag: 'ev_linnea_4' },
  { npc: 'rook', hearts: 4, knot: 'heart_rook_4', flag: 'ev_rook_4' },
  { npc: 'tamsin', hearts: 4, knot: 'heart_tamsin_4', flag: 'ev_tamsin_4' },
];

// Toasts for flags that turn true during a scene.
export const FLAG_NEWS = {
  npc_bram_recruited: 'Bram joined as your Carpenter. The Carpenter\'s Lodge is open.',
  npc_linnea_recruited: 'Linnea joined as your Healer. Knockouts now end at her Herbalist Hut.',
  npc_hob_arrived: 'Hob Furrow moved in: your first settler.',
  ch1_founded: 'The Founding! Your realm is a Hamlet.',
  deed_spared_rook: 'You spared Rook. Reputation: Merciful (more arrivals, a little less Safety).',
  deed_banished_rook: 'You banished Rook. Reputation: Stern (more Safety, fewer arrivals, thefts until Chapter 2).',
  npc_rook_recruited: 'Rook joined as your Scout, with Magpie, Jackdaw and Finch as settlers.',
  world_cellars_open: 'The Sunken Cellars are open.',
  npc_tamsin_recruited: 'Tamsin joined as your Blacksmith. The Smithy is open.',
  ch1_signet: 'You recovered the Signet, the first of the Regalia.',
  ch1_vs_complete: 'End of the Vertical Slice. Chapter 1 continues.',
  npc_marigold_recruited: 'Marigold joined as your Cook, with Pip.',
  npc_juniper_recruited: 'Juniper joined as your Beast Warden.',
  court_held: 'Court is held. Your realm is a Village.',
  ch1_complete: 'Chapter 1 complete.',
};
