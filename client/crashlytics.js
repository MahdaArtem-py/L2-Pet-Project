import { Capacitor } from '@capacitor/core';
import { FirebaseCrashlytics } from '@capacitor-firebase/crashlytics';
import StackTrace from 'stacktrace-js';

const native = Capacitor.getPlatform() === 'android'
  && Capacitor.isPluginAvailable('FirebaseCrashlytics');
const redact = value => String(value).replace(/\b\d{12,19}\b/g, '[redacted]').slice(0, 1024);
const contextKeys = new Set(['trace_id', 'endpoint', 'method', 'http_status', 'scenario']);
const keysFor = context => Object.entries(context)
  .filter(([key]) => contextKeys.has(key))
  .map(([key, value]) => ({ key, value: redact(value), type: 'string' }));
const showStatus = message => {
  const status = document.getElementById('crashlyticsStatus');
  if (status) status.textContent = message;
};

async function initialize() {
  if (!native) return false;
  document.getElementById('crashlyticsPanel').hidden = false;
  try {
    await FirebaseCrashlytics.setCustomKey({ key: 'client', value: 'bank-l2-android', type: 'string' });
    await FirebaseCrashlytics.log({ message: 'Bank L2 Android session started' });
    const { crashed } = await FirebaseCrashlytics.didCrashOnPreviousExecution();
    showStatus(crashed
      ? 'Попередній запуск завершився крашем. SDK надішле звіт за наявності інтернету.'
      : 'Crashlytics готовий до тестування.');
    document.getElementById('nonFatalButton').disabled = false;
    document.getElementById('nativeCrashButton').disabled = false;
    return true;
  } catch (error) {
    showStatus('Не вдалося ініціалізувати Crashlytics. Перевірте Android Logcat.');
    console.warn('Crashlytics initialization failed', error);
    return false;
  }
}

const ready = new Promise(resolve => {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => resolve(initialize()), { once: true });
  } else {
    resolve(initialize());
  }
});

async function recordError(error, context = {}) {
  if (!await ready) return false;
  try {
    let stacktrace = [];
    if (error instanceof Error) {
      try { stacktrace = await StackTrace.fromError(error, { offline: true }); }
      catch { /* The native SDK can still record an exception without JS frames. */ }
    }
    await FirebaseCrashlytics.recordException({
      message: redact(error instanceof Error ? error.message : 'Unhandled JavaScript rejection'),
      stacktrace,
      keysAndValues: keysFor(context),
    });
    return true;
  } catch (sdkError) {
    // Reporting must never break the banking request or cause recursive reports.
    console.warn('Crashlytics could not record an error', sdkError);
    return false;
  }
}

async function noteRequest(context) {
  if (!await ready) return;
  try {
    await Promise.all(keysFor(context).map(key => FirebaseCrashlytics.setCustomKey(key)));
    await FirebaseCrashlytics.log({ message: `${context.method} ${redact(context.endpoint)} trace_id=${context.trace_id}` });
  } catch (error) {
    console.warn('Crashlytics could not record request context', error);
  }
}

async function testNonFatal() {
  const recorded = await recordError(new Error('Bank L2 non-fatal test'), { scenario: 'manual_nonfatal' });
  showStatus(recorded
    ? 'Тестову помилку записано. Вона з’явиться у Firebase після надсилання звіту SDK.'
    : 'Не вдалося записати тестову помилку. Перевірте Android Logcat.');
  return recorded;
}

async function testCrash() {
  if (!await ready) return;
  await FirebaseCrashlytics.setCustomKey({ key: 'scenario', value: 'manual_native_crash', type: 'string' });
  await FirebaseCrashlytics.log({ message: 'Forcing Bank L2 native test crash' });
  await FirebaseCrashlytics.crash({ message: 'Bank L2 native test crash' });
}

window.BankCrashlytics = { recordError, noteRequest, testNonFatal, testCrash, ready };
window.addEventListener('error', event => {
  void recordError(event.error || new Error('Unhandled JavaScript error'), { scenario: 'javascript_error' });
});
window.addEventListener('unhandledrejection', event => {
  void recordError(event.reason, { scenario: 'unhandled_rejection' });
});
ready.then(enabled => {
  if (!enabled) return;
  document.getElementById('nonFatalButton').addEventListener('click', () => void testNonFatal());
  document.getElementById('nativeCrashButton').addEventListener('click', () => {
    void testCrash().catch(error => {
      showStatus('Не вдалося виконати тест Android-крашу.');
      console.warn('Crashlytics test crash failed', error);
    });
  });
});
