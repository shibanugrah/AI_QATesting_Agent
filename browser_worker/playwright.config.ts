import {defineConfig} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import type {WorkerRequest} from './protocol';
const request:WorkerRequest = JSON.parse(fs.readFileSync(process.env.QA_WORKER_REQUEST!, 'utf8'));
export default defineConfig({
  testDir: __dirname,
  testMatch: 'journey.spec.ts',
  workers: 1,
  retries: 0,
  timeout: request.timeout_ms,
  globalTimeout: request.timeout_ms * request.journey.profiles.length + 15000,
  reporter: [['./reporter.ts']],
  outputDir: path.join(request.output_dir, 'playwright'),
  use: {browserName:'chromium', headless:true, serviceWorkers:'block', acceptDownloads:false,
    trace:'off', screenshot:'off', video:'off', ignoreHTTPSErrors:false,
    launchOptions:{args:['--disable-background-networking','--disable-quic','--force-webrtc-ip-handling-policy=disable_non_proxied_udp']}},
});
