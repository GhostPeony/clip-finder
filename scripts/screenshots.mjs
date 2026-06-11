// Design-review screenshot harness.
// Boots the vite dev server twice (authenticated app shell via VITE_AUTH_MODE=none,
// then the public landing page) and captures every view at desktop + mobile widths.
//
// Usage: npm run screenshots          (one-time setup: npx playwright install chromium)
// Output: screenshots/{app,landing}/<view>-<width>.png

import { spawn } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const PORT = 3010;
const BASE_URL = `http://localhost:${PORT}`;
const OUT_DIR = path.resolve('screenshots');
const VIEWPORTS = [
  { name: '1440', width: 1440, height: 900 },
  { name: '390', width: 390, height: 844 },
];

function startServer(extraEnv) {
  const env = { ...process.env, ...extraEnv };
  if (extraEnv.VITE_AUTH_MODE === undefined) delete env.VITE_AUTH_MODE;
  const child = spawn('npx', ['vite', '--port', String(PORT), '--strictPort'], {
    env,
    shell: true,
    stdio: 'ignore',
  });
  return child;
}

async function waitForServer(timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(BASE_URL);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`vite did not become ready on ${BASE_URL}`);
}

function stopServer(child) {
  if (!child || child.killed) return;
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { shell: true, stdio: 'ignore' });
  } else {
    child.kill('SIGTERM');
  }
}

async function clickIfPresent(page, locator, label) {
  try {
    if ((await locator.count()) > 0 && (await locator.first().isVisible())) {
      await locator.first().click();
      await page.waitForTimeout(600);
      return true;
    }
  } catch {
    // fall through
  }
  console.warn(`  ! skipped "${label}" (element not found/visible)`);
  return false;
}

async function shoot(page, group, view, viewportName, fullPage) {
  const file = path.join(OUT_DIR, group, `${view}-${viewportName}.png`);
  await page.screenshot({ path: file, fullPage });
  console.log(`  ✓ ${group}/${view}-${viewportName}.png`);
}

async function captureApp(browser) {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      reducedMotion: 'reduce',
    });
    const page = await context.newPage();
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    await shoot(page, 'app', 'workbench', vp.name, true);

    const navTargets = [
      ['Library', 'library'],
      ['Jobs', 'jobs'],
      ['About', 'about'],
      ['Contact', 'contact'],
    ];
    for (const [name, view] of navTargets) {
      // On mobile the nav may live behind a menu button; try opening it first.
      const direct = page.getByRole('button', { name, exact: true });
      let clicked = false;
      if ((await direct.count()) > 0 && (await direct.first().isVisible())) {
        clicked = await clickIfPresent(page, direct, name);
      } else {
        const menu = page.getByRole('button', { name: /open menu/i });
        if (await clickIfPresent(page, menu, 'mobile menu')) {
          clicked = await clickIfPresent(
            page,
            page.getByRole('button', { name, exact: true }),
            name,
          );
        }
      }
      if (clicked) await shoot(page, 'app', view, vp.name, true);
    }

    // Settings modal (gear button)
    const settings = page.getByRole('button', { name: /settings/i });
    if (await clickIfPresent(page, settings, 'Settings')) {
      await shoot(page, 'app', 'settings-modal', vp.name, false);
    }

    await context.close();
  }
}

async function captureLanding(browser) {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      reducedMotion: 'reduce',
    });
    const page = await context.newPage();
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    await shoot(page, 'landing', 'landing-full', vp.name, true);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight * 0.45));
    await page.waitForTimeout(700);
    await shoot(page, 'landing', 'landing-mid', vp.name, false);
    await context.close();
  }
}

async function waitForPortFree(timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await fetch(BASE_URL);
    } catch {
      return; // connection refused -> port is free
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  console.warn('  ! port did not free up in time; continuing anyway');
}

async function runPass(name, env, capture, browser) {
  console.log(`\n— Pass: ${name}`);
  await waitForPortFree();
  const server = startServer(env);
  try {
    await waitForServer();
    await capture(browser);
  } finally {
    stopServer(server);
    await waitForPortFree();
  }
}

rmSync(OUT_DIR, { recursive: true, force: true });
mkdirSync(path.join(OUT_DIR, 'app'), { recursive: true });
mkdirSync(path.join(OUT_DIR, 'landing'), { recursive: true });

const browser = await chromium.launch();
try {
  await runPass(
    'authenticated app (VITE_AUTH_MODE=none)',
    { VITE_AUTH_MODE: 'none' },
    captureApp,
    browser,
  );
  await runPass(
    'landing page (supabase auth, signed out)',
    { VITE_AUTH_MODE: undefined },
    captureLanding,
    browser,
  );
} finally {
  await browser.close();
}
console.log(`\nDone. Screenshots in ${OUT_DIR}`);
