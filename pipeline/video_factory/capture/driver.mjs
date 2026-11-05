// vf capture's driver: the app's built demo, served on 127.0.0.1, driven by the pinned Playwright and Chromium on a
// fake clock, frame by frame. Nothing here is meant to read the real time: the clock is installed and paused before
// the page loads (the demo's scenario starts at that instant), then only `clock.runFor` moves it. Motion's WAAPI animations
// would run in real time, so Element.prototype.animate is removed and Motion falls back to requestAnimationFrame,
// which the fake clock drives; CSS animations and transitions (spinners, pulses) run on the real document timeline,
// so each is paused when first seen, after any step of the clock, and set from the fake clock from then on.
//
//   node driver.mjs <job.json>
//
// The job (written by vf capture): the plan, the paths of Playwright, Chromium, the demo and the output folder, and
// the app's start (localStorage, ready selector, font). Output: frames/f_000001.png, ... and track.json.
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { extname, join, resolve, sep } from 'node:path';

const job = JSON.parse(await readFile(process.argv[2], 'utf8'));
const plan = job.plan;
const require = createRequire(join(job.playwright, 'package.json'));
const { chromium, devices } = require(job.playwright);

// The instant the demo starts at, on the fake clock: any fixed date gives the same pictures.
const CLOCK_ORIGIN = Date.parse('2026-10-28T17:00:00Z');
const START_DELAY_MS = 1000;
const ZOOM_SETTLE_MS = 1500;
// The step of the fake clock, in milliseconds. Playwright yields to the real event loop between two timers, where
// React's MessageChannel tasks may or may not run first: with one millisecond, no step holds two timers apart from
// equal ones, so every render lands at the same fake instant. Coarser steps were measured to drift Motion's clock.
const STEP_MS = 1;
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
  '.webmanifest': 'application/manifest+json',
};

function serve(root) {
  const base = resolve(root);
  const server = createServer(async (request, response) => {
    const path = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
    let file = resolve(join(base, path));
    if (file !== base && !file.startsWith(base + sep)) return response.writeHead(403).end();
    try {
      if ((await stat(file)).isDirectory()) file = join(file, 'index.html');
      await stat(file);
    } catch {
      return response.writeHead(404).end();
    }
    response.writeHead(200, { 'content-type': TYPES[extname(file)] ?? 'application/octet-stream' });
    createReadStream(file).pipe(response);
  });
  return new Promise((done) => server.listen(0, '127.0.0.1', () => done(server)));
}

function contextOptions() {
  const common = {
    colorScheme: 'dark',
    reducedMotion: 'no-preference',
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    deviceScaleFactor: plan.scale,
    viewport: { width: plan.window.width, height: plan.window.height },
  };
  if (plan.device !== 'iphone') return common;
  const phone = devices['iPhone 13'];
  return { ...common, userAgent: phone.userAgent, isMobile: true, hasTouch: true };
}

const server = await serve(job.demo);
const url = `http://127.0.0.1:${server.address().port}/${plan.view}`;
const browser = await chromium.launch({
  executablePath: job.chromium,
  // Software rendering, no font hinting, sRGB: the same pixels from one run to the next.
  args: ['--disable-gpu', '--font-render-hinting=none', '--force-color-profile=srgb', '--hide-scrollbars'],
});
const context = await browser.newContext(contextOptions());
await context.addInitScript((storage) => {
  for (const [key, value] of Object.entries(storage)) localStorage.setItem(key, value);
  delete Element.prototype.animate;
  // CSS animations and transitions run on the real document timeline: each one is paused as soon as it is seen, as
  // starting at that fake instant, and set from the fake clock from then on. The driver calls this after every step
  // of the clock, so even a short animation is caught before it could end in real time.
  window.__vfPin = () => {
    const now = Date.now();
    for (const animation of document.getAnimations()) {
      if (animation.timeline && !(animation.timeline instanceof DocumentTimeline)) continue;
      if (animation.__vfStart === undefined) {
        animation.__vfStart = now;
        animation.pause();
      }
      animation.currentTime = now - animation.__vfStart;
    }
  };
}, job.storage);
const page = await context.newPage();
await page.clock.install({ time: CLOCK_ORIGIN });
await page.clock.pauseAt(CLOCK_ORIGIN + START_DELAY_MS);
await page.goto(url);
await page.locator(job.ready).first().waitFor();
if (job.font) await page.evaluate(async (font) => { await document.fonts.load(font); await document.fonts.ready; }, job.font);

// Scenario time, in milliseconds since the demo started: only runFor moves it, by small steps. React schedules its
// renders with a MessageChannel, which the fake clock does not drive: after each step the page's pending messages are
// let through, so a render always lands between the same two fake frames, whatever the machine's speed.
let elapsed = 0;
async function settle() {
  await page.evaluate(
    () =>
      new Promise((done) => {
        const first = new MessageChannel();
        first.port1.onmessage = () => {
          const second = new MessageChannel();
          second.port1.onmessage = () => {
            window.__vfPin();
            done();
          };
          second.port2.postMessage(0);
        };
        first.port2.postMessage(0);
      }),
  );
}
async function runTo(ms) {
  while (elapsed < ms) {
    const next = Math.min(ms, elapsed + STEP_MS);
    await page.clock.runFor(next - elapsed);
    elapsed = next;
    await settle();
  }
}

async function scaleOf(selector) {
  return page.evaluate((s) => {
    const element = document.querySelector(s);
    return element && element.offsetWidth ? element.getBoundingClientRect().width / element.offsetWidth : 1;
  }, selector);
}

// The app's own zoom: Ctrl and the wheel, around a point. Chrome divides a synthetic wheel delta by the device scale
// factor, hence the multiplication; the app turns 300 px of wheel into a factor e.
async function zoom(action) {
  const measure = action.measure ?? '[data-box]';
  const before = await scaleOf(measure);
  await page.mouse.move(action.x, action.y);
  await page.keyboard.down('Control');
  await page.mouse.wheel(0, -300 * Math.log(action.scale / before) * plan.scale);
  await page.keyboard.up('Control');
  await page.mouse.move(plan.window.width - 1, plan.window.height - 1);
  await runTo(elapsed + ZOOM_SETTLE_MS);
  return { from: before, to: await scaleOf(measure) };
}

async function act(action) {
  if (action.do === 'zoom') return zoom(action);
  const target = page.locator(action.selector).first();
  if (action.do === 'tap') await target.tap();
  else await target.click();
  return null;
}

// What the camera needs, read in the page: each tracked element (box, opacity, group, flags), the stage, the texts.
function read({ track, stage, texts }) {
  window.__vfPin();
  const round = (value) => Math.round(value * 100) / 100;
  const rect = (element) => {
    const box = element.getBoundingClientRect();
    return [box.x, box.y, box.width, box.height].map(round);
  };
  const opacity = (element) => {
    let value = 1;
    for (let node = element; node; node = node.parentElement) value *= Number(getComputedStyle(node).opacity);
    return round(value);
  };
  const out = { track: {}, texts: [] };
  for (const [name, spec] of Object.entries(track)) {
    out.track[name] = [...document.querySelectorAll(spec.selector)].map((element) => {
      const found = { rect: rect(element), opacity: opacity(element), group: null, flags: [] };
      if (spec.group) found.group = element.closest(`[${spec.group}]`)?.getAttribute(spec.group) ?? null;
      found.flags = (spec.flags ?? []).filter((flag) => element.hasAttribute(flag));
      return found;
    });
  }
  const area = stage ? document.querySelector(stage) : document.documentElement;
  const bounds = area ? area.getBoundingClientRect() : null;
  if (texts && bounds) {
    const walker = document.createTreeWalker(area, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent.trim()) continue;
      const parent = node.parentElement;
      const style = getComputedStyle(parent);
      if (style.visibility === 'hidden' || style.display === 'none' || opacity(parent) < 0.05) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const box = range.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      if (box.right < bounds.left || box.left > bounds.right || box.bottom < bounds.top || box.top > bounds.bottom) continue;
      // The size as drawn: the font size times the scale of every transform above it (the app's zoom).
      const scale = parent.offsetWidth ? parent.getBoundingClientRect().width / parent.offsetWidth : 1;
      out.texts.push([box.x, box.y, box.width, box.height, parseFloat(style.fontSize) * scale].map(round));
    }
  }
  return out;
}

const stageBox = async () =>
  page.evaluate((selector) => {
    const element = selector ? document.querySelector(selector) : document.documentElement;
    if (!element) return null;
    const box = element.getBoundingClientRect();
    let background = 'rgba(0, 0, 0, 0)';
    for (let node = element; node && /rgba\(.*, 0\)|transparent/.test(background); node = node.parentElement)
      background = getComputedStyle(node).backgroundColor;
    if (/rgba\(.*, 0\)|transparent/.test(background)) background = getComputedStyle(document.body).backgroundColor;
    return { rect: [box.x, box.y, box.width, box.height], background };
  }, plan.stage ?? null);

const start = Math.round(plan.scenario.start * 1000);
const end = Math.round(plan.scenario.end * 1000);
const pending = [...plan.actions];
const done = [];
while (pending.length && Math.round(pending[0].at * 1000) <= start) {
  const action = pending.shift();
  await runTo(Math.round(action.at * 1000));
  done.push({ ...action, result: await act(action), ran_at: elapsed / 1000 });
}
if (elapsed > start) throw new Error(`gestes trop tardifs : la plage commence à ${start} ms, l'horloge est à ${elapsed} ms`);
await runTo(start);

await mkdir(join(job.out, 'frames'), { recursive: true });
const textSets = [];
const textIndex = new Map();
const frames = [];
const count = Math.round(((end - start) * plan.fps) / 1000);
for (let index = 0; index < count; index += 1) {
  const target = start + Math.round((index * 1000) / plan.fps);
  while (pending.length && Math.round(pending[0].at * 1000) <= target) {
    const action = pending.shift();
    await runTo(Math.round(action.at * 1000));
    done.push({ ...action, result: await act(action), ran_at: elapsed / 1000 });
  }
  await runTo(target);
  const data = await page.evaluate(read, { track: plan.track, stage: plan.stage ?? null, texts: plan.texts });
  const key = JSON.stringify(data.texts);
  if (!textIndex.has(key)) {
    textIndex.set(key, textSets.length);
    textSets.push(data.texts);
  }
  const name = `f_${String(index + 1).padStart(6, '0')}.png`;
  await page.screenshot({ path: join(job.out, 'frames', name), type: 'png' });
  frames.push({ index, t: target / 1000, track: data.track, texts: textIndex.get(key) });
  if (index % plan.fps === 0) console.log(`image ${index + 1}/${count}, scénario ${(target / 1000).toFixed(2)} s`);
}

const track = {
  plan: plan.name,
  fps: plan.fps,
  scale: plan.scale,
  window: plan.window,
  scenario: plan.scenario,
  stage: await stageBox(),
  actions: done,
  frames,
  text_sets: textSets,
};
await writeFile(join(job.out, 'track.json'), JSON.stringify(track));
await browser.close();
server.close();
