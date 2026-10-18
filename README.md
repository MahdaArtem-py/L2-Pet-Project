# Bank

Bank is a small banking service with API troubleshooting, trace ID tracking, structured logs, log levels, metrics, error reproduction, Sentry error tracking, and basic observability.

The project includes a FastAPI backend, a simple web client, and several banking scenarios:

- successful balance check
- successful card top-up
- insufficient funds error
- card not found error
- backend crash / payment gateway failure
- multi-step transaction tracing by one `traceId`
- configurable logging levels with `LOG_LEVEL`

## Tech Stack

- Python
- FastAPI
- Uvicorn
- HTML / JavaScript / TailwindCSS
- Docker Compose
- Prometheus
- Grafana
- Elasticsearch
- Kibana
- Vector
- Sentry

## Project Structure

```text
.
|-- main.py              # FastAPI backend
|-- index.html           # Simple web client for testing L2 scenarios
|-- Dockerfile           # Backend container image
|-- docker-compose.yml   # Backend and observability stack
|-- prometheus.yml       # Prometheus scrape config
|-- vector.toml          # Vector log pipeline config
|-- grafana/             # Grafana provisioning files
|-- .env.example         # Optional environment variables example
|-- logs/app.log         # Application log file created at runtime
`-- requirements.txt     # Python dependencies
```

## Features

### Backend API

The backend provides several endpoints for testing support cases:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/api/v1/cards/{card_number}/balance` | Get card balance |
| POST | `/api/v1/cards/addmoney` | Add money to a card |
| POST | `/api/v1/transfer/p2p` | Transfer money between cards with a multi-step trace chain |
| POST | `/api/v1/transfer/crash` | Simulate SWIFT gateway failure and send the exception to Sentry |
| GET | `/metrics` | Prometheus metrics endpoint |
| GET | `/sentry-debug` | Test Sentry error reporting |

## Test Cards

| Card Number | Balance | Currency | Purpose |
|---|---:|---|---|
| `4441111122223333` | 1500.00 | UAH | Receiver card |
| `5375414199998888` | 50.00 | UAH | Main test card |

## Quick Start with Docker

Requirements:

- Docker Desktop
- Git

Run the full project:

```bash
git clone <repo-url>
cd bank
docker compose up --build
```

Services:

| Service | URL |
|---|---|
| Bank API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| Kibana | http://localhost:5601 |
| Elasticsearch | http://localhost:9200 |

Grafana default credentials:

```text
Username: admin
Password: admin
```

Prometheus is preconfigured as the default Grafana data source.

Open the web client:

```text
index.html
```

The web client sends requests to:

```text
http://127.0.0.1:8000
```

Optional Sentry setup:

```bash
SENTRY_DSN=<your-sentry-dsn> docker compose up --build
```

## Local Python Run

Use this only if you want to run the backend without Docker.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:LOG_LEVEL="INFO"
python main.py
```

## Docker Services

`docker compose up --build` starts:

| Service | URL |
|---|---|
| Bank API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| Kibana | http://localhost:5601 |
| Elasticsearch | http://localhost:9200 |

## Banking Scenarios

### Scenario 1: Balance Check

Expected result:

```text
HTTP 200 OK
```

Steps:

1. Open the web client.
2. Click "Update balance".
3. Check the response body.
4. Copy the `TraceID`.
5. Find the same trace ID in application logs.

Useful places to check:

- browser response panel
- `logs/app.log`
- Kibana logs
- FastAPI `/metrics`

### Scenario 2: Insufficient Funds

Expected result:

```text
HTTP 400 Bad Request
```

Steps:

1. Click "Transfer 1000 UAH".
2. Check the returned error.
3. Copy the `TraceID`.
4. Search logs by trace ID.
5. Confirm that the failure reason is insufficient balance.

Possible support conclusion:

```text
The transfer failed because the sender balance is lower than the requested transfer amount.
```

Trace chain example:

```text
p2p_transfer_received
sender_card_validation_started
sender_card_validation_passed
receiver_card_validation_started
receiver_card_validation_passed
balance_check_started
insufficient_funds
p2p_transfer_failed
```

### Scenario 3: Card Not Found

Expected result:

```text
HTTP 404 Not Found
```

Steps:

1. Click "Transfer to fake card".
2. Check the response.
3. Find the trace ID in logs.
4. Confirm that the receiver card does not exist in the test database.

Possible support conclusion:

```text
The transfer failed because the receiver card number was not found.
```

### Scenario 4: Backend Crash

Expected result:

```text
HTTP 500 Internal Server Error
```

Steps:

1. Click "SWIFT payment crash".
2. Check the response body.
3. Copy the `TraceID`.
4. Search logs by trace ID.
5. Check Sentry for the captured exception.
6. Check metrics in Prometheus/Grafana.

Possible support conclusion:

```text
The payment failed because the backend payment gateway simulation crashed.
The incident can be tracked by TraceID.
```

Trace chain example:

```text
swift_transfer_received
card_validation_passed
balance_check_passed
fraud_check_passed
gateway_request_started
gateway_timeout
swift_transfer_failed
```

This simulates a real support investigation flow:

```text
Frontend
-> Bank API
-> Card Validation
-> Balance Service
-> Fraud Check
-> External SWIFT Gateway
-> Error handling / Sentry
```

## Logging

The application writes structured JSON logs to:

```text
logs/app.log
```

Example log fields:

| Field | Description |
|---|---|
| `asctime` | Log timestamp |
| `levelname` | Log level |
| `message` | Event message |
| `traceId` | Request trace ID |
| `service` | Service name |
| `event_type` | Machine-readable event name |
| `step` | Step number inside a simulated transaction flow |
| `status` | HTTP or business status code |
| `reason` | Failure reason |
| `error_type` | Python exception type or error category |
| `method` | HTTP method |
| `url` | Request path |
| `card_last4` | Last 4 digits of card number |
| `from_card_last4` | Last 4 digits of sender card |
| `to_card_last4` | Last 4 digits of receiver card |
| `amount` | Transfer amount |
| `current_balance` | Sender balance before transfer |

Example log:

```json
{
  "asctime": "2026-10-10 12:18:33,881",
  "levelname": "ERROR",
  "message": "External SWIFT gateway timeout",
  "traceId": "web-trace-eyp5tgbp",
  "service": "swift-gateway",
  "event_type": "gateway_timeout",
  "step": "6",
  "status": null,
  "error_type": "AttributeError"
}
```

### Log Levels

The application supports configurable log levels using the `LOG_LEVEL` environment variable.

Examples:

```powershell
$env:LOG_LEVEL="DEBUG"
python main.py
```

```powershell
$env:LOG_LEVEL="INFO"
python main.py
```

```powershell
$env:LOG_LEVEL="WARNING"
python main.py
```

Recommended modes:

| Mode | LOG_LEVEL | Purpose |
|---|---|---|
| Deep troubleshooting | `DEBUG` | Shows payload details and internal processing context |
| L2 investigation | `INFO` | Shows the full transaction flow by `traceId` |
| Production-like mode | `WARNING` | Shows only warnings and errors |
| Failure-only mode | `ERROR` | Shows only system failures |

Log level examples:

| Event | Level |
|---|---|
| Request received | `INFO` |
| Card validation passed | `INFO` |
| Balance check passed | `INFO` |
| Debug payload/context | `DEBUG` |
| Card not found | `WARNING` |
| Insufficient funds | `WARNING` |
| SWIFT gateway timeout | `ERROR` |
| Transfer failed with 500 | `ERROR` |

## Trace Investigation

Each API request receives a `traceId`.

For transfer scenarios, the same `traceId` is written into every log event in the simulated processing chain. This allows the full operation to be reconstructed from one `traceId`.

Example Kibana search:

```text
traceId: "web-trace-eyp5tgbp"
```

Useful Kibana filters:

```text
levelname: "ERROR"
service: "swift-gateway"
event_type: "gateway_timeout"
status: 500
```

Recommended investigation table columns:

```text
asctime | traceId | levelname | service | event_type | step | status | reason | error_type
```

## Dashboards

In Kibana:

- Requests by Endpoint
- Logs by Level
- Errors by Service
- Status Distribution

In Grafana:

- HTTP Status Codes
- Total Requests
- Requests by Endpoint
- Requests per Minute
- 5xx Server Errors

## Android client (initial setup)

The existing `index.html` is the shared source for the browser and Capacitor Android
client. Build scripts bundle Tailwind CSS locally and copy the page into `dist/`.
The FastAPI backend continues running on the computer or a separate server.

Requirements: Node.js 22+, Android Studio with JDK 25, Android SDK, and an AVD
created in Android Studio's Device Manager. Open `android/` in Android Studio and
let Gradle sync before the first run. Select the AVD and run the `app` configuration.

```powershell
npm ci
npm run android:sync
npm run android:open
```

Start just the local backend if the full observability stack is unnecessary:

```powershell
docker compose up --build bank-api
```

The Android build defaults to `http://10.0.2.2:8000`, the emulator's route to the
computer's localhost. The browser build (`npm run build`) defaults to
`http://127.0.0.1:8000`. The original `index.html` still works as before.
To use another backend, set `BANK_API_URL` before building or syncing:

```powershell
$env:BANK_API_URL = 'https://your-bank-api.example.com'
npm run android:sync
Remove-Item Env:BANK_API_URL
```

Local emulator development permits HTTP in the debug Android manifest and mixed
content in the Capacitor config. Before any release, use an HTTPS API and disable
`android.allowMixedContent`. No release distribution is configured at this stage.
After editing the web source, run `npm run android:sync` before running Android again.

Firebase Crashlytics is integrated through `@capacitor-firebase/crashlytics`.
The Android app uses package ID `com.mahdaartem.bankl2` and its Firebase client
configuration in `android/app/google-services.json`. This is Android configuration,
not a Firebase service-account credential. Native Gradle builds apply both the
Google Services and Crashlytics plugins. Google Analytics is optional and is not
included in this integration.

The Android client includes a Crashlytics panel with a handled JavaScript error
and a deliberate native crash. The native crash closes the app; reopen Bank L2
to let the SDK upload reports. Run the app without an attached debugger when
testing crashes. Check the Android app in Firebase Console > Crashlytics after
several minutes. A local "recorded" status means the SDK accepted the event, not
that the Firebase dashboard has already received it.

Unexpected API HTTP 5xx and network failures are recorded as non-fatal client
errors, with per-event `trace_id`, sanitized endpoint, method, and HTTP status
where available. Expected HTTP 400/404 business responses are not crash reports.
Unhandled JavaScript exceptions and rejected promises are also recorded. Request
bodies and full card numbers are not added to telemetry. The same trace ID can be
looked up in the existing backend logs. Server-side SWIFT exceptions remain in
Sentry; an HTTP 500 alone does not crash Android.

The Crashlytics panel stays hidden in an ordinary browser. For a browser build,
run `npm run build`; native reporting calls become no-ops. `npm test` covers this
boundary, JavaScript stack/trace metadata, reporting failures, and HTTP error
classification.

Local verification on 2026-10-18: debug APK built with Java 25 / Gradle 9.1.0
and ran on the Android API 37 emulator. The SDK recorded a handled JS error,
HTTP 500 with trace ID, and the intentional native crash. After restart,
DataTransport received HTTP 200 from the Crashlytics reports endpoint. Firebase
Console dashboard visibility must be checked in the project's account.

Dependency audit at bootstrap: npm reports 10 advisories in development tooling
(Tailwind 3 dependency chain and the Capacitor CLI iOS/xcode dependency chain).
`npm audit --omit=dev` checks the shipped npm runtime dependencies separately.
Resolve or reassess these before adopting this bootstrap for release builds.

### Java 25 and Gradle

The Android wrapper is pinned to Gradle 9.1.0, the first Gradle release with
Java 25 runtime support. The Android Gradle Plugin stays on 8.13.0 to match
Capacitor 8.5.3. Java source and bytecode targets remain 21 as required by the
Capacitor modules; the compiler comes from JDK 25, so no separate JDK 21 is needed.

In Android Studio, open the `android/` directory and select its bundled JDK 25
in Settings > Build, Execution, Deployment > Build Tools > Gradle > Gradle JDK.
On this workstation its path is `W:\AndroidStudio\jbr`.

For a terminal build, set `JAVA_HOME` for the current session (adjust the Studio
path on other computers), then run from the repository root:

```powershell
$env:JAVA_HOME = 'W:\AndroidStudio\jbr'
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
npm run android:sync
Push-Location android
try {
    .\gradlew.bat --version
    .\gradlew.bat assembleDebug
} finally {
    Pop-Location
}
```

The first build needs internet access to download Gradle, Google/Maven dependencies,
and Android SDK Platform 36 if it is not installed. An API 37 emulator can run this
app, but its system image does not replace the compile SDK Platform 36.
If Gradle download reports a connection timeout, check network/proxy settings and
retry Android Studio's Sync Project with Gradle Files. This failure happens before
compilation and does not establish whether the full Android build succeeds.
