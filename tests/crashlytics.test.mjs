import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { build } from 'esbuild';

const bridgeBundle = await build({
  entryPoints: ['client/crashlytics.js'], bundle: true, write: false,
  format: 'iife', platform: 'browser',
  plugins: [{ name: 'native-test-boundary', setup(builder) {
    builder.onResolve({ filter: /^@capacitor\/core$|^@capacitor-firebase\/crashlytics$/ }, args => ({ path: args.path, namespace: 'test-native' }));
    builder.onLoad({ filter: /.*/, namespace: 'test-native' }, args => ({
      contents: args.path === '@capacitor/core'
        ? 'export const Capacitor = window.testCapacitor;'
        : 'export const FirebaseCrashlytics = window.testSdk;',
    }));
  } }],
});

function elements() {
  const nodes = new Map();
  return { readyState: 'complete', getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, { hidden: true, disabled: true, textContent: '', addEventListener() {} });
    return nodes.get(id);
  } };
}

async function boot(platform) {
  const calls = [];
  const sdk = Object.fromEntries(['setCustomKey', 'log', 'recordException', 'crash'].map(method => [method, async options => calls.push({ method, options })]));
  sdk.didCrashOnPreviousExecution = async () => ({ crashed: false });
  const window = {
    testCapacitor: { getPlatform: () => platform, isPluginAvailable: () => platform === 'android' },
    testSdk: sdk, addEventListener() {},
  };
  const document = elements();
  const context = vm.createContext({ window, document, console: { warn() {} }, setTimeout, clearTimeout });
  vm.runInContext(bridgeBundle.outputFiles[0].text, context);
  await window.BankCrashlytics.ready;
  return { calls, sdk, window, document, context };
}

test('web client never calls native Crashlytics and keeps the test panel hidden', async () => {
  const app = await boot('web');
  assert.equal(await app.window.BankCrashlytics.testNonFatal(), false);
  assert.equal(app.document.getElementById('crashlyticsPanel').hidden, true);
  assert.equal(app.calls.length, 0);
});

test('Android reports JS stack frames and per-event trace context without card numbers', async () => {
  const app = await boot('android');
  assert.equal(app.document.getElementById('crashlyticsPanel').hidden, false);
  const recorded = await vm.runInContext(`window.BankCrashlytics.recordError(new Error('Test 5375414199998888'), {
    trace_id: 'web-trace-test', endpoint: '/cards/5375414199998888/balance', payload: 'private'
  })`, app.context);
  assert.equal(recorded, true);
  const report = app.calls.find(call => call.method === 'recordException').options;
  assert.match(report.message, /\[redacted\]/);
  assert.ok(report.stacktrace.length > 0);
  assert.equal(report.keysAndValues.find(key => key.key === 'trace_id').value, 'web-trace-test');
  assert.ok(!JSON.stringify(report).includes('5375414199998888'));
  assert.ok(!report.keysAndValues.some(key => key.key === 'payload'));
  app.sdk.recordException = async () => { throw new Error('SDK unavailable'); };
  assert.equal(await app.window.BankCrashlytics.testNonFatal(), false);
});

const html = await readFile('index.html', 'utf8');
const bankingScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
for (const status of [400, 404, 500]) {
  test(`banking HTTP ${status} reports only unexpected server errors`, async () => {
    const reports = [];
    const document = elements();
    const context = vm.createContext({ document, window: { BankCrashlytics: {
      noteRequest() {}, recordError(error, context) { reports.push({ error, context }); },
    } }, fetch: async () => ({ status, text: async () => '<html>Gateway error</html>', headers: { get: () => null } }) });
    vm.runInContext(bankingScript, context);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(reports.length, status === 500 ? 1 : 0);
    if (status === 500) {
      assert.equal(reports[0].context.endpoint, '/api/v1/cards/:card/balance');
      assert.match(reports[0].context.trace_id, /^web-trace-/);
      assert.equal(reports[0].context.http_status, 500);
    }
    assert.match(document.getElementById('outputLog').innerText, new RegExp(`"http_status": ${status}`));
  });
}
