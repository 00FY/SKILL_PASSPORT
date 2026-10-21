import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8')
  .replaceAll('import.meta.env', '__env');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function loadApi(env = {}, fetch = async () => new Response('{}')) {
  const links = [];
  const context = vm.createContext({
    exports: {}, __env: env, fetch, Headers,
    setTimeout: callback => { callback(); return 0; },
    URL: { createObjectURL: () => 'blob:report', revokeObjectURL: () => {} },
    document: {
      createElement: () => { const link = { click() {}, remove() {} }; links.push(link); return link; },
      body: { appendChild() {} },
    },
  });
  new vm.Script(compiled).runInContext(context);
  return { api: context.exports, links };
}

test('local development keeps using the Vite API proxy', async () => {
  const calls = [];
  const { api } = loadApi({}, async url => { calls.push(url); return new Response('{}'); });
  await api.postJson('/api/jobs/analyze', { repo_urls: [] });
  assert.deepEqual(calls, ['/api/jobs/analyze']);
});

test('hosted JSON requests and PDF downloads use the same backend origin', async () => {
  const calls = [];
  const { api, links } = loadApi({ VITE_API_BASE_URL: 'https://api.example.com///' }, async (url, init) => {
    calls.push({ url, method: init?.method });
    return new Response('{}');
  });
  await api.postJson('/api/jobs/analyze', { repo_urls: [] });
  await api.request('/api/jobs/example');
  await api.downloadPassportPdf({ candidate_name: 'Test Candidate' });
  assert.deepEqual(calls, [
    { url: 'https://api.example.com/api/jobs/analyze', method: 'POST' },
    { url: 'https://api.example.com/api/jobs/example', method: undefined },
    { url: 'https://api.example.com/api/report/pdf', method: 'POST' },
  ]);
  assert.equal(links[0].download, 'skill-passport-test-candidate.pdf');
});

test('hosted connection failures give a useful message without localhost instructions', async () => {
  const { api } = loadApi({ VITE_API_BASE_URL: 'https://api.example.com' }, async () => {
    throw new TypeError('Network failed');
  });
  await assert.rejects(api.request('/api/health'), /analysis server.*starting up/);
  await assert.rejects(api.downloadPassportPdf({ candidate_name: 'Test' }), /analysis server.*starting up/);
});
