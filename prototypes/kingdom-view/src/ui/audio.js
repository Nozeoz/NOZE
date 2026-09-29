// Sound, all generated in the browser: little effects, night crickets, the Heartflame's crackle,
// and a slow plucked-string tune ("the Bard's playlist"). Starts only after the player asks for it.
export class Audio {
  constructor() {
    this.ctx = null;
    this.on = false;
    this.musicOn = true;
    this.track = 0;
    this.tracks = ['Lanterns over Dawnmere', 'The Old Road at Dusk', 'Heartflame Lullaby'];
  }

  start() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return false;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.7;
      this.master.connect(this.ctx.destination);
      this.reverb = this.ctx.createConvolver();
      this.reverb.buffer = this.impulse(2.4);
      const wet = this.ctx.createGain();
      wet.gain.value = 0.28;
      this.reverb.connect(wet).connect(this.master);
      this.musicBus = this.ctx.createGain();
      this.musicBus.gain.value = 0.32;
      this.musicBus.connect(this.master);
      this.musicBus.connect(this.reverb);
      this.ambBus = this.ctx.createGain();
      this.ambBus.gain.value = 0;
      this.ambBus.connect(this.master);
      this.noise = this.noiseBuffer();
      this.startAmbience();
      this.nextNote = this.ctx.currentTime + 0.3;
      this.step = 0;
    }
    this.ctx.resume();
    this.on = true;
    return true;
  }

  stop() { this.on = false; if (this.ctx) this.ctx.suspend(); }
  toggle() { return this.on ? (this.stop(), false) : this.start(); }

  impulse(sec) {
    const rate = this.ctx.sampleRate;
    const buf = this.ctx.createBuffer(2, rate * sec, rate);
    for (let c = 0; c < 2; c++) {
      const d = buf.getChannelData(c);
      for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 2.6);
    }
    return buf;
  }

  noiseBuffer() {
    const buf = this.ctx.createBuffer(1, this.ctx.sampleRate * 2, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  // Wind and the Heartflame's crackle under everything; crickets join at night.
  startAmbience() {
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    const lp = this.ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 420;
    const g = this.ctx.createGain();
    g.gain.value = 0.05;
    src.connect(lp).connect(g).connect(this.master);
    src.start();
    this.wind = g;
  }

  // A plucked string (Karplus–Strong).
  pluck(freq, when, vol = 0.5, bus = this.musicBus) {
    const ctx = this.ctx;
    const len = Math.round(ctx.sampleRate / freq);
    const dur = 2.6;
    const buf = ctx.createBuffer(1, Math.round(ctx.sampleRate * dur), ctx.sampleRate);
    const d = buf.getChannelData(0);
    const ring = new Float32Array(len);
    for (let i = 0; i < len; i++) ring[i] = Math.random() * 2 - 1;
    let p = 0;
    for (let i = 0; i < d.length; i++) {
      const next = (p + 1) % len;
      const v = 0.497 * (ring[p] + ring[next]);
      d[i] = ring[p];
      ring[p] = v;
      p = next;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const g = ctx.createGain();
    g.gain.setValueAtTime(vol, when);
    g.gain.exponentialRampToValueAtTime(0.001, when + dur);
    src.connect(g).connect(bus);
    src.start(when);
  }

  tone(freq, when, dur, vol = 0.2, type = 'sine') {
    const o = this.ctx.createOscillator();
    o.type = type;
    o.frequency.value = freq;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0, when);
    g.gain.linearRampToValueAtTime(vol, when + 0.01);
    g.gain.exponentialRampToValueAtTime(0.001, when + dur);
    o.connect(g).connect(this.master);
    o.start(when);
    o.stop(when + dur + 0.05);
  }

  sfx(name) {
    if (!this.on || !this.ctx) return;
    const t = this.ctx.currentTime;
    if (name === 'coin') { this.tone(1318, t, 0.12, 0.08, 'triangle'); this.tone(1760, t + 0.07, 0.2, 0.07, 'triangle'); }
    else if (name === 'tip') { this.tone(1568, t, 0.1, 0.09, 'triangle'); this.tone(2093, t + 0.06, 0.22, 0.08, 'triangle'); }
    else if (name === 'place') {
      const src = this.ctx.createBufferSource();
      src.buffer = this.noise;
      const f = this.ctx.createBiquadFilter();
      f.type = 'lowpass';
      f.frequency.value = 320;
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0.35, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
      src.connect(f).connect(g).connect(this.master);
      src.start(t, Math.random(), 0.2);
      this.tone(196, t, 0.16, 0.12, 'sine');
    } else if (name === 'click') this.tone(880, t, 0.05, 0.04, 'triangle');
    else if (name === 'bell') { [523, 659, 784].forEach((f, i) => this.pluck(f, t + i * 0.12, 0.35, this.master)); }
    else if (name === 'task') { [587, 740, 880, 1175].forEach((f, i) => this.tone(f, t + i * 0.09, 0.4, 0.06, 'triangle')); }
    else if (name === 'error') this.tone(180, t, 0.18, 0.08, 'square');
  }

  // Called every frame: schedules music notes and fades ambience with the night.
  update(night, near) {
    if (!this.on || !this.ctx) return;
    const t = this.ctx.currentTime;
    this.wind.gain.value = 0.03 + night * 0.03;
    if (night > 0.5 && Math.random() < 0.04) {
      const f = 4200 + Math.random() * 900;
      for (let i = 0; i < 3; i++) this.tone(f, t + i * 0.05, 0.03, 0.012 * night, 'sine');
    }
    if (near > 0 && Math.random() < 0.05 * near) {
      const src = this.ctx.createBufferSource();
      src.buffer = this.noise;
      const f = this.ctx.createBiquadFilter();
      f.type = 'highpass';
      f.frequency.value = 2500;
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0.05 * near, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.05);
      src.connect(f).connect(g).connect(this.master);
      src.start(t, Math.random() * 1.5, 0.06);
    }
    if (!this.musicOn) return;
    // D dorian, four chords, a slow melody over gentle arpeggios.
    const beat = 0.62;
    const roots = [[146.83, 220, 293.66], [130.81, 196, 261.63], [174.61, 261.63, 349.23], [164.81, 246.94, 329.63]];
    const scale = [293.66, 329.63, 349.23, 392, 440, 493.88, 523.25, 587.33];
    while (this.nextNote < t + 0.5) {
      const bar = Math.floor(this.step / 8) % 4;
      const i = this.step % 8;
      const chord = roots[(bar + this.track) % 4];
      if (i % 2 === 0) this.pluck(chord[(i / 2) % 3] * (i === 4 ? 2 : 1), this.nextNote, 0.32);
      if (i === 1 || i === 5 || (i === 6 && Math.random() < 0.5)) this.pluck(scale[Math.floor(Math.random() * scale.length)] * (Math.random() < 0.2 ? 2 : 1), this.nextNote + beat * 0.5, 0.22);
      this.nextNote += beat;
      this.step++;
      if (this.step % 64 === 0) this.track = (this.track + 1) % this.tracks.length;
    }
  }

  nowPlaying() { return this.tracks[this.track]; }
}
