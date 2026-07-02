import { spawnSync } from 'node:child_process';

// Deploys the API worker + container with a fresh container instance id so the
// new image actually serves traffic (Cloudflare containers pin instances by id;
// reusing an id can keep routing to the old container). Operationalizes lesson 53.
//
// Override the id with API_INSTANCE_ID=... when a specific value is needed.

const healthUrl = process.env.API_HEALTH_URL || 'https://api.memexai.xyz/_worker/health';

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    env: process.env,
    shell: process.platform === 'win32',
    stdio: options.capture ? ['ignore', 'pipe', 'inherit'] : 'inherit',
    encoding: 'utf8',
  });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
  return result.stdout ? result.stdout.trim() : '';
}

function computeInstanceId() {
  const override = process.env.API_INSTANCE_ID?.trim();
  if (override) return override;

  const sha = run('git', ['rev-parse', '--short', 'HEAD'], { capture: true });
  const now = new Date();
  const date = [
    now.getUTCFullYear(),
    String(now.getUTCMonth() + 1).padStart(2, '0'),
    String(now.getUTCDate()).padStart(2, '0'),
  ].join('');
  return `production-${date}-${sha}`;
}

const instanceId = computeInstanceId();
console.log(`Deploying memexai-api with API_INSTANCE_ID=${instanceId}`);

run('npx', [
  'wrangler',
  'deploy',
  '--config',
  'wrangler.api.toml',
  '--containers-rollout=immediate',
  '--var',
  `API_INSTANCE_ID:${instanceId}`,
]);

console.log(`Deployed. Container instance id: ${instanceId}`);

// Non-fatal health check: confirm the worker reports the new instance id.
try {
  const response = await fetch(healthUrl);
  const body = await response.json();
  if (body?.containerInstance === instanceId) {
    console.log(`Health check OK: ${healthUrl} reports ${body.containerInstance}`);
  } else {
    console.warn(
      `Health check WARNING: ${healthUrl} reports ${String(
        body?.containerInstance,
      )} (expected ${instanceId}). Propagation can lag; re-check in a minute.`,
    );
  }
} catch (error) {
  console.warn(`Health check skipped (${error?.message || error}). Verify ${healthUrl} manually.`);
}
