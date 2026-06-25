import { spawnSync } from 'node:child_process';

process.env.VITE_API_URL ||= 'https://api.memexai.xyz';

const projectName = process.env.CLOUDFLARE_PAGES_PROJECT || 'memexai';
const branch = process.env.CLOUDFLARE_PAGES_BRANCH || 'main';
const npx = 'npx';

function run(command, args) {
  const result = spawnSync(command, args, {
    env: process.env,
    shell: process.platform === 'win32',
    stdio: 'inherit',
  });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

run(npx, ['vite', 'build']);
run(npx, [
  'wrangler',
  'pages',
  'deploy',
  'dist',
  '--project-name',
  projectName,
  '--branch',
  branch,
  '--commit-dirty=true',
]);
