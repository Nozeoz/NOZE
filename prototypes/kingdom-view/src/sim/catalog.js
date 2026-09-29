// Everything the Kingdom View prototype knows about: goods, buildable objects, tasks,
// Chronicle pages, visitor kinds, names, and the lines people say.
// Numbers are placeholders tuned for a 20–30 minute prototype.

export const GOODS = {
  harvest: { name: 'Harvest', item: 'turnips', price: 4, color: '#9DBB5A' },
  grain: { name: 'Grain', item: 'bread', price: 4, color: '#D7B068' },
  catch: { name: 'Catch', item: 'fish', price: 6, color: '#7FB2C4' },
  stew: { name: 'Stew', item: 'stew', price: 12, color: '#C9703E' },
  tonic: { name: 'Tonic', item: 'tonics', price: 14, color: '#9E8AC8' },
};
export const MARKET_GOODS = ['harvest', 'grain', 'catch', 'stew'];

// Stall upgrades: price multiplier and seconds per customer (game seconds at 1× speed).
export const STALL_LEVELS = [
  null,
  { mult: 1, service: 3.0, cost: 0 },
  { mult: 1.3, service: 2.4, cost: 50 },
  { mult: 1.6, service: 1.8, cost: 120 },
];

export const CATEGORIES = [
  { id: 'paths', name: 'Paths & Lights' },
  { id: 'market', name: 'Market & Work' },
  { id: 'homes', name: 'Homes' },
  { id: 'decor', name: 'Decor' },
];

// w × d is the footprint before rotation (x by z). The front of an object faces +z at rot 0.
export const TYPES = {
  path: { name: 'Stone Path', cat: 'paths', w: 1, d: 1, cost: 2, surface: true, desc: 'Visitors only walk on roads and paths. Drag to paint.' },
  lamp: { name: 'Lantern Post', cat: 'paths', w: 1, d: 1, cost: 15, light: 3.6, appeal: [1, 2], reach: true, desc: 'Lights 3 tiles around it. Can stand beside any road, even outside the realm.' },
  string: { name: 'String Lights', cat: 'paths', w: 1, d: 3, cost: 24, walkable: true, lights: [[0, 0, 2.3], [0, 1, 2.3], [0, 2, 2.3]], appeal: [3, 2], reach: true, desc: 'A line of little lanterns. People can walk under them.' },
  stall: { name: 'Market Stall', cat: 'market', w: 2, d: 1, cost: 40, stall: true, front: true, light: 1.6, variants: 4, desc: 'Sells one kind of goods from the kingdom stores. Needs a path in front of the counter.' },
  field_turnip: { name: 'Turnip Field', cat: 'market', w: 3, d: 3, cost: 30, produce: { harvest: 1 }, worker: true, playerWalkable: true, desc: '+1 Harvest an hour while someone works it.' },
  fishery: { name: 'Fishing Hut', cat: 'market', w: 2, d: 2, cost: 50, produce: { catch: 1 }, worker: true, needs: 'water', light: 1.4, desc: '+1 Catch an hour. Must touch the pond.' },
  field_wheat: { name: 'Wheat Field', cat: 'market', w: 3, d: 3, cost: 35, produce: { grain: 1 }, worker: true, playerWalkable: true, unlock: 'first_settler', desc: '+1 Grain an hour while someone works it.' },
  cookhouse: { name: 'Cookhouse', cat: 'market', w: 3, d: 2, cost: 90, convert: { in: { harvest: 1, catch: 1 }, out: { stew: 1 } }, worker: true, light: 2, unlock: 'first_settler', desc: 'Turns 1 Harvest and 1 Catch into 1 Stew each hour.' },
  tent: { name: 'Tent', cat: 'homes', w: 2, d: 2, cost: 20, beds: 1, light: 1.1, desc: 'A bed for 1 settler.' },
  hut: { name: 'Hut', cat: 'homes', w: 2, d: 2, cost: 60, beds: 2, light: 1.5, variants: 3, desc: 'Beds for 2 settlers.' },
  flowers: { name: 'Flower Bed', cat: 'decor', w: 1, d: 1, cost: 5, appeal: [2, 2.5], variants: 4, desc: 'Appeal +2 nearby.' },
  tree: { name: 'Tree', cat: 'decor', w: 1, d: 1, cost: 8, appeal: [2, 3], variants: 3, desc: 'Appeal +2 nearby.' },
  bench: { name: 'Bench', cat: 'decor', w: 1, d: 1, cost: 12, appeal: [2, 2.5], rest: true, desc: 'Appeal +2. Visitors sit here after shopping.' },
  banner: { name: 'Banner', cat: 'decor', w: 1, d: 1, cost: 15, appeal: [3, 3], variants: 4, desc: 'Your colours. Appeal +3 nearby.' },
  hedge: { name: 'Hedge', cat: 'decor', w: 1, d: 1, cost: 3, appeal: [1, 1.5], desc: 'Appeal +1.' },
  crates: { name: 'Crates', cat: 'decor', w: 1, d: 1, cost: 4, appeal: [1, 1.5], desc: 'Appeal +1. Looks busy.' },
  well: { name: 'Well', cat: 'decor', w: 1, d: 1, cost: 30, appeal: [3, 2.5], unlock: 'first_settler', desc: 'Appeal +3 nearby.' },
  fountain: { name: 'Fountain', cat: 'decor', w: 2, d: 2, cost: 120, appeal: [8, 4.5], rest: true, unlock: 'appeal_55', desc: 'Appeal +8. Visitors love to linger here.' },
  // Fixed buildings from Chapter 1 (can't be moved or removed).
  beacon: { name: 'Heartflame Brazier', cat: 'fixed', w: 2, d: 2, fixed: true, light: 5.5, desc: 'The heart of the realm. You can only build inside its reach.' },
  throne: { name: 'The Ashen Throne', cat: 'fixed', w: 2, d: 2, fixed: true, appeal: [3, 4], desc: 'Where you woke. Broken, for now.' },
  lodge: { name: "Bram's Lodge", cat: 'fixed', w: 3, d: 3, fixed: true, light: 2, sworn: 'bram', desc: "Bram's workshop. Every building starts here." },
  herbalist: { name: "Linnea's Herbalist Hut", cat: 'fixed', w: 3, d: 2, fixed: true, light: 2, sworn: 'linnea', stall: true, goods: 'tonic', front: true, desc: 'Linnea brews Tonics and sells them herself.' },
};

export const BEACON_TIERS = [
  null,
  { name: 'Heartflame Brazier', light: 5.5, cost: 0 },
  { name: 'Heartflame Beacon', light: 8, cost: 250 },
];

export const VISITOR_KINDS = {
  traveler: { name: 'Traveler', weight: 3, settles: true, wants: { harvest: 3, grain: 2, catch: 2, stew: 2, tonic: 1 } },
  merchant: { name: 'Merchant', weight: 2, settles: true, wants: { harvest: 1, grain: 2, catch: 3, stew: 2, tonic: 2 } },
  farmer: { name: 'Farmhand', weight: 2, settles: true, wants: { harvest: 2, grain: 3, catch: 1, stew: 3, tonic: 1 } },
  monk: { name: 'Lantern Monk', weight: 1, settles: true, lantern: 1.6, wants: { harvest: 2, grain: 3, catch: 1, stew: 2, tonic: 3 } },
  mossbun: { name: 'Mossbun', weight: 1, creature: true, wants: { harvest: 5, grain: 1 } },
  puddlepup: { name: 'Puddlepup', weight: 1, creature: true, wants: { catch: 5, harvest: 1 } },
  emberkit: { name: 'Emberkit', weight: 0.7, creature: true, lantern: 1.2, wants: { stew: 3, catch: 2 } },
};

export const NAMES = [
  'Wren', 'Tobin', 'Maeve', 'Corin', 'Ilse', 'Pell', 'Rosalind', 'Bastian', 'Nell', 'Oswin', 'Edda', 'Finch', 'Hollis', 'Mabry',
  'Orla', 'Percival', 'Quill', 'Rue', 'Sabine', 'Teodor', 'Una', 'Vesper', 'Willa', 'Brannoc', 'Cress', 'Dunstan', 'Elowen',
  'Fenwick', 'Greer', 'Hesper', 'Isolde', 'Jory', 'Lark', 'Merrin', 'Nessa', 'Odo', 'Posy', 'Sorrel', 'Tansy', 'Ulric', 'Wynn',
];

export const SWORN = {
  bram: { name: 'Bram', role: 'Builder', color: '#8E6D56' },
  linnea: { name: 'Linnea', role: 'Herbalist', color: '#729F8B' },
};

export const LINES = {
  arrive_lit: ['Lanterns all the way up. Someone cares.', "The road's lit! We must be close.", 'Warm lights ahead.'],
  dark: ['So dark… is this the way?', 'I can barely see the road.', 'The mist is thick tonight.'],
  turn_back: ["Too dark. I'll try another night.", "No lights… I'm turning back.", 'Not through that mist. Not tonight.'],
  buy: {
    harvest: ['Fresh turnips!', 'Crunchy and sweet.'],
    grain: ['Still-warm bread!', 'Smells like home.'],
    catch: ['Fish from your own pond?', 'Grilled trout, please!'],
    stew: ['Hot stew on a misty night…', 'Seconds, please!'],
    tonic: ['A tonic from Linnea? Perfect.', 'Linnea knows her herbs.'],
  },
  served: ["Served by the Sovereign? I'll tell everyone!", "The Sovereign's own hands!"],
  none: {
    harvest: 'Nobody sells turnips?', grain: 'No bread anywhere?', catch: 'No fish tonight?', stew: 'I hoped for something warm…', tonic: 'No tonics?',
  },
  sold_out: ['Sold out already?', 'Empty crates… next time.'],
  stroll_high: ['The flowers smell lovely.', 'What a pretty little market.', 'I could stay here.', 'Listen to that fire crackle.'],
  stroll_mid: ['Nice and quiet.', 'Cozy spot.'],
  stroll_low: ["It's a bit bare, isn't it?", 'Could use some flowers.'],
  settle: ['Is there room for one more?', "I'd like to stay, if you'll have me."],
  creature: { mossbun: ['Mip!', '*happy thump*'], puddlepup: ['Arf!', '*splash*'], emberkit: ['Mrrp.', '*warm purr*'] },
};

// Tasks guide the prototype. Up to three are active at once, in this order.
export const TASKS = [
  { id: 'open_market', giver: 'flicker', title: 'Open the Lantern Market', text: 'When dusk falls, open the market and let the travelers in.', reward: 20, page: 'first_night' },
  { id: 'light_road', giver: 'bram', title: 'Light the Old Road', text: 'Travelers walk up the Old Road through the forest and turn back in the dark. Light most of it with Lantern Posts.', reward: 40, page: 'old_road' },
  { id: 'sell_fish', giver: 'hob', title: 'Fish from the pond', text: 'Build a Fishing Hut by the pond, then sell Catch at a stall.', reward: 30 },
  { id: 'build_hut', giver: 'bram', title: 'A roof for newcomers', text: 'Build a Hut. Visitors only stay if there is a free bed.', reward: 25 },
  { id: 'first_settler', giver: 'flicker', title: 'Someone stays', text: 'Make a visitor happy enough to settle in the realm.', reward: 30, page: 'those_who_stay' },
  { id: 'appeal_55', giver: 'linnea', title: 'Make it lovely', text: 'Raise the market’s Appeal to 55 with flowers, trees, benches and banners near the paths.', reward: 50, page: 'what_the_mist_takes' },
  { id: 'sell_stew', giver: 'hob', title: 'Stew for cold nights', text: 'Build a Cookhouse and sell 5 Stew in one night.', reward: 60 },
  { id: 'beacon_t2', giver: 'bram', title: 'Raise the Heartflame', text: 'Upgrade the Heartflame Brazier. More light, and a wider realm to build in.', reward: 0, page: 'heartflame' },
  { id: 'happy_12', giver: 'linnea', title: 'A night to remember', text: 'Send 12 happy visitors home in one night.', reward: 80 },
  { id: 'village', giver: 'flicker', title: 'Twelve under one banner', text: 'Reach 12 residents with the Heartflame raised, and the Hamlet becomes a Village.', reward: 0, page: 'village' },
];

export const PAGES = {
  ember: {
    title: 'The Ember and the Throne',
    text: 'You woke beside a broken stone throne with a flame for company. Flicker says you were a sovereign once, a thousand years ago, and that this clearing was a garden of the old kingdom. Now it is a ring of grass in a sea of trees, and every night the Veil rolls in from the forest. Light keeps it back. Light, and people who choose to stay.',
  },
  first_night: {
    title: 'The First Lantern Night',
    text: 'Markets were how Halcyon began, Flicker insists: a fire, a few stalls, strangers who came for bread and stayed for the company. The first night you opened the stalls, they came up the Old Road with the mist on their cloaks. Some bought turnips. One asked your name. You found you didn’t mind that nobody knew it yet.',
  },
  old_road: {
    title: 'The Old Road',
    text: 'The road through the forest is older than the trees. Bram found the old kerbstones under the moss while he set the posts. “Someone built this to be walked at night,” he said. Travelers from the Outer Realms say the Veil swallows roads whole. This one it gave back.',
  },
  those_who_stay: {
    title: 'Those Who Stay',
    text: 'A kingdom is not walls. It is the first person who walks out of the dark, eats at your fire, and asks if there is room. You said yes. Flicker cried a little, which for a flame mostly looks like sparks.',
  },
  what_the_mist_takes: {
    title: 'What the Mist Takes',
    text: 'Linnea says the Veil does not only hide things. It takes colour first, then warmth, then names. That is why she plants flowers where the lamplight falls. “People forget where they are,” she says, “but they remember a place that smelled of lavender.”',
  },
  heartflame: {
    title: 'Heartflame',
    text: 'The brazier drank the oil and the gold and then, all at once, it roared. The light rolled past the huts and the pond to the first trees, and for a moment you saw the clearing as it was: a courtyard of pale stone, a crown carved over a gate. Then it was grass again. But it was brighter grass.',
  },
  village: {
    title: 'Twelve Under One Banner',
    text: 'Twelve people now sleep under your banner. The Order of the Dawn Lantern keeps a prophecy: when the ember wakes, the Crown returns. You do not feel like a crown. You feel like someone who must fix the roof of the third hut before the rain. Flicker says that is exactly what a crown feels like. Somewhere under the throne hill, a seed is waiting.',
  },
};
export const PAGE_ORDER = ['ember', 'first_night', 'old_road', 'those_who_stay', 'what_the_mist_takes', 'heartflame', 'village'];
