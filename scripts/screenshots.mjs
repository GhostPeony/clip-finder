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
  { name: '320', width: 320, height: 844 },
  { name: '390', width: 390, height: 844 },
];

const busyDashboardFixtures = {
  usage: {
    plan: 'pro',
    planKey: 'pro',
    billingStatus: 'active',
    searchesUsedToday: 92,
    searchesUsedThisMonth: 1827,
    searchLimit: 5000,
    searchPeriod: 'month',
    indexesUsedThisMonth: 21,
    indexLimit: 80,
    indexedVideosUsed: 143,
    indexedVideoLimit: 300,
    indexedSecondsUsed: 288000,
    indexedSecondsLimit: 720000,
    maxImportVideos: 50,
    maxSearchResults: 10,
    hasOwnKey: false,
    hasServerKey: true,
    allowUserKeys: true,
    apiKeyMode: 'hybrid',
  },
  library: {
    totalVideos: 143,
    totalClips: 9842,
    channels: [
      {
        name: 'Extremely Long Client Research Channel Name That Should Truncate Cleanly',
        videoCount: 88,
        videos: [],
      },
      { name: 'AI Agent Harness Reliability Talks and Workshops', videoCount: 31, videos: [] },
      { name: 'Founder Calls, Pricing, GTM, and Product Strategy', videoCount: 24, videos: [] },
    ],
  },
  jobs: {
    jobs: [
      {
        id: 'job-1',
        status: 'running',
        source_type: 'video',
        source_url:
          'https://www.youtube.com/watch?v=veryLongVideoIdentifierWithManyParams&list=PL_long_playlist_context&index=41&t=1234s',
        indexed_video_count: 2,
        skipped_video_count: 0,
        failed_video_count: 0,
        last_message: 'Generating source report and timestamped topics from transcript evidence...',
      },
      {
        id: 'job-2',
        status: 'failed',
        source_type: 'playlist',
        source_url:
          'https://www.youtube.com/playlist?list=PL_an_unreasonably_long_capture_playlist_id_for_mobile_testing',
        indexed_video_count: 0,
        skipped_video_count: 2,
        failed_video_count: 1,
        error: 'Transcript unavailable for one video',
        last_message: 'Transcript unavailable for one video',
      },
    ],
  },
  captureSources: {
    captureSources: [
      {
        id: 'source-1',
        source_type: 'playlist',
        source_url: 'https://www.youtube.com/playlist?list=PL_long_capture_source_url',
        external_id: 'PL_long',
        title: 'Memexai Inbox With A Long Playlist Title For Saved Research Videos',
        status: 'active',
        visibility: 'private',
        last_synced_at: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
        recentItems: [{}, {}, {}, {}, {}],
      },
      {
        id: 'source-2',
        source_type: 'playlist',
        source_url: 'https://www.youtube.com/playlist?list=PL_other',
        external_id: 'PL_other',
        title: 'Client discovery calls',
        status: 'paused',
        visibility: 'private',
        recentItems: [],
      },
    ],
  },
  youtubeStatus: {
    connected: true,
    needsReconnect: false,
    youtubeReadonlyGranted: true,
    hasRefreshToken: true,
    scopes: ['https://www.googleapis.com/auth/youtube.readonly'],
    expiresAt: null,
    connectedAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    lastError: null,
  },
};

const emptyLibraryGraph = {
  version: 'memexai-library-source-graph-v1',
  limit: 50,
  accessModel: {
    scope: 'current_user_grants',
    visibilityGrants: ['user_videos', 'user_channels'],
    sourceTruth: 'read_only',
    provenanceFields: ['accessScope', 'accessSource', 'accessReason'],
  },
  videos: [],
  componentCounts: {
    videos: 0,
    channels: 0,
    sourceLabels: 0,
    sourceConcepts: 0,
    sourceEdges: 0,
    knowledgeArtifacts: 0,
    transcriptChunksSampled: 0,
    agentNotes: 0,
    personalConcepts: 0,
    reviewFlags: 0,
  },
  graph: { nodes: [], edges: [], selectedNodeId: null },
  reviewFlags: [],
  edgeCaseHandling: [],
  guidance: '',
};

function mockApiResponse(pathname, searchParams) {
  if (pathname.endsWith('/config')) {
    return {
      storage: 'supabase',
      authMode: 'none',
      hasServerKey: true,
      apiKeyMode: 'hybrid',
      allowUserKeys: true,
    };
  }
  if (pathname.endsWith('/library/graph')) return emptyLibraryGraph;
  if (pathname.endsWith('/library/components/search')) {
    return {
      query: searchParams.get('q') || '',
      retrievalMode: 'component_keyword',
      results: [],
      componentTypes: [],
      accessModel: {
        scope: 'current_user_grants',
        embeddingUsed: false,
        llmAnswerUsed: false,
      },
      retrievalBudget: {
        embeddingCalls: 0,
        llmCalls: 0,
        maxResults: 20,
        searchedVideos: 0,
        returnedResults: 0,
      },
      guidance: '',
    };
  }
  if (pathname.endsWith('/library')) return busyDashboardFixtures.library;
  if (pathname.endsWith('/usage')) return busyDashboardFixtures.usage;
  if (pathname.endsWith('/billing/status')) {
    return {
      planKey: 'pro',
      billingStatus: 'active',
      currentPeriodStart: null,
      currentPeriodEnd: null,
      cancelAtPeriodEnd: false,
      entitlements: null,
      usage: null,
      hasStripeCustomer: true,
    };
  }
  if (pathname.endsWith('/ingestion-jobs')) return busyDashboardFixtures.jobs;
  if (pathname.endsWith('/capture/sources')) return busyDashboardFixtures.captureSources;
  if (pathname.endsWith('/youtube/oauth/status')) return busyDashboardFixtures.youtubeStatus;
  if (pathname.endsWith('/mcp/tokens')) return { tokens: [] };
  if (pathname.endsWith('/mcp/setup-bundle')) return {};
  return {};
}

async function installAppApiMocks(page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockApiResponse(url.pathname, url.searchParams)),
    });
  });
}

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
    await installAppApiMocks(page);
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
    { VITE_AUTH_MODE: 'supabase' },
    captureLanding,
    browser,
  );
} finally {
  await browser.close();
}
console.log(`\nDone. Screenshots in ${OUT_DIR}`);
