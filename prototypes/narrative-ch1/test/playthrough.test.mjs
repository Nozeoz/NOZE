// Plays Chapter 1 start to finish on both big branches and checks the story state it ends in.
// Run with: npm test   (compiles the Ink first)
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Story } from 'inkjs';
import { Game } from '../src/sim.js';
import { autoplay } from '../src/autoplay.js';
import { SCENES, HEART_EVENTS, NPCS, PROJECTS } from '../src/content.js';

const json = readFileSync(new URL('../build/story.json', import.meta.url), 'utf8');
const newGame = seed => new Game(new Story(json), { seed }).begin();
const milestones = g => Object.entries(g.s.milestones).map(([k, d]) => `${k}@${d}`).join(' ');

test('every knot the game can call exists in the Ink', () => {
  const story = new Story(json);
  const knots = [
    ...SCENES.map(s => s.knot), ...HEART_EVENTS.map(h => h.knot), ...Object.values(PROJECTS).map(p => p.done),
    'loc_windmill', 'loc_meadow', 'talk_flicker', 'arrival', 'theft_report', 'knockout_wake', 'heart_mira_2', 'tamsin_forge',
    ...['bram', 'linnea', 'rook', 'tamsin', 'mira', 'hob', 'juniper', 'marigold'].flatMap(n => [`talk_${n}`, `gift_${n}`]),
    ...['bram', 'linnea', 'rook', 'tamsin', 'hob', 'juniper', 'marigold'].map(n => `help_${n}`),
  ];
  const missing = knots.filter(k => !story.KnotContainerWithName(k));
  assert.deepEqual(missing, []);
  assert.ok(Object.keys(NPCS).length >= 10);
});

for (const path of ['spare', 'banish']) {
  for (const seed of [3, 11, 29]) {
    test(`Chapter 1 can be finished on the ${path} path (seed ${seed})`, () => {
      const g = newGame(seed);
      assert.equal(autoplay(g, { path }), 'ended');
      assert.ok(g.flag('ch1_complete'), 'chapter complete');
      assert.ok(g.flag('ch1_vs_complete'), 'vertical slice complete');
      assert.equal(g.v('kingdom_rank'), 2, 'Village rank');
      assert.ok(g.flag('ch1_signet'), 'the Signet');
      assert.ok(g.residents() >= 12, 'twelve residents');
      assert.ok(g.swornCount() >= 5, 'five Sworn');
      if (path === 'spare') {
        assert.ok(g.flag('npc_rook_recruited'));
        assert.ok(g.s.settlers.some(x => x.name === 'Magpie'));
        assert.equal(g.v('kingdom_reputation'), 'merciful');
      } else {
        assert.ok(g.flag('deed_banished_rook'));
        assert.ok(!g.flag('npc_rook_recruited'));
        assert.ok(g.flag('npc_juniper_recruited') && g.flag('npc_marigold_recruited'), 'both optional Sworn are needed without Rook');
        assert.equal(g.v('kingdom_reputation'), 'stern');
      }
      console.log(`  ${path}/${seed}: done on day ${g.s.day} · VS on day ${g.s.milestones.ch1_vs_complete} · ${milestones(g)} · stats ${JSON.stringify(g.s.stats)}`);
    });
  }
}

test('saving and loading mid-chapter keeps the story and the realm', () => {
  const g = newGame(5);
  autoplay(g, { path: 'spare', stopWhen: x => x.flag('ch1_founded') && x.mode === 'plan' });
  const saved = g.serialize();
  const h = new Game(new Story(json), { seed: 1 });
  h.load(saved);
  assert.equal(h.v('var_kingdom_name'), 'Brightwater');
  assert.equal(h.s.day, g.s.day);
  assert.equal(h.residents(), g.residents());
  assert.equal(autoplay(h, { path: 'spare' }), 'ended');
});

test('the quest log always has something to say while the chapter runs', () => {
  const g = newGame(9);
  let checked = 0;
  autoplay(g, {
    path: 'banish',
    stopWhen: x => {
      if (x.mode === 'plan' && x.s.phase === 0 && x.flag('ch1_campfire') && !x.flag('ch1_complete')) {
        const log = String(x.story.EvaluateFunction('quest_log', [], true).output).trim();
        assert.ok(log.length > 0, `empty quest log on day ${x.s.day}`);
        checked++;
      }
      return false;
    },
  });
  assert.ok(checked > 10);
});
