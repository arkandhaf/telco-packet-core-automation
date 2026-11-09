# ⚡ RELPOOL Core Automation Platform

> **Mobile Core Packet Core (MCPE) Automation Engine**  
> **Engineered & Developed by:** Arkan Dhaifulloh ([@arkandhaf](https://github.com/arkandhaf))  
> **Domain Context:** Group Core Planning & Engineering — Indosat Ooredoo Hutchison (IOH) © 2026

RELPOOL adalah platform otomasi provisioning dan tata kelola konfigurasi **Policy and Charging Enforcement Function (PCEF)** serta **Policy and Charging Rules Function (PCRF UPCC)** untuk node Core Network Huawei (Service-V).

> 🔒 **Confidentiality & Data Sanitization Notice:**  
> Seluruh alamat IP, nama node, Rating Group (`RG`), Service ID (`SID`), serta template CIQ di dalam repositori ini merupakan **data simulasi/dummy** untuk keperluan demonstrasi portofolio rekayasa perangkat lunak. File skrip produk internal perusahaan (`SCRIPT_*.txt` / `vSCRIPT_*.txt`), kredensial (`.env` / `secrets.toml`), dan riwayat audit lokal dikecualikan secara otomatis melalui `.gitignore`.

---

## 🏛️ Arsitektur Proyek (Clean Modular Architecture)

```text
IOH-core-automation/
│
├── .streamlit/               # Konfigurasi server & tema Streamlit
│   └── secrets.toml          # Local secrets & API base
│
├── configs/                  # Konfigurasi topologi jaringan & node core
│   └── nodes.yaml            # Daftar node cluster (GGSN-JKT, UPCC, DR-SUB)
│
├── docs/                     # Dokumentasi teknis & SOP Operasional
│   ├── ARCHITECTURE.md       # Diagram arsitektur & sequence flow sistem
│   ├── CIQ_SPECIFICATION.md  # Spesifikasi format CIQ untuk Product Manager/BU
│   └── OPERATIONAL_RUNBOOK.md# SOP NOC: Pre-check, eksekusi, & emergency rollback
│
├── data/                     # Penyimpanan data lokal & sample data
│   ├── samples/              # File template & contoh data CIQ (.csv / .xlsx)
│   │   └── TEMPLATE_CIQ_STANDARD.csv
│   └── audit/                # Database JSON riwayat deployment (audit trail)
│       └── audit_history.json
│
├── core/                     # Business Logic Engine Layer (Modular)
│   ├── models/               # Data contracts & Pydantic schema validation
│   ├── engines/              # Multi-vendor rule generators (Huawei Service-V)
│   ├── parsers/              # CIQ explicit alias mapper, batch processor, & packager
│   ├── transports/           # SSH Gateway (buffer draining) & Fernet Crypto
│   └── services/             # Thread-safe persistent audit logging service
│
├── ui/                       # Presentation Layer (Streamlit Modules)
│   ├── styles.py             # Cyberpunk NOC Dark Theme CSS & animations
│   ├── components/           # Header live bar, KPI bento grid, sidebar stats
│   └── views/                # Sub-views: Manual Form, Batch CIQ, Audit Trail
│
├── tests/                    # Automated Test Suite (CI/CD Ready)
│   ├── unit/                 # Unit tests (sanitization, engines, parsers, audit)
│   └── integration/          # Integration tests (SSH simulation & crypto cycle)
│
├── app.py                    # Lean Application Orchestrator (< 50 lines)
├── requirements.txt          # Production dependencies
└── .gitignore                # Security protection for secrets & env files
```

---

## 🚀 Quickstart Guide

### 1. Prasyarat Lingkungan
Pastikan Python 3.11+ telah terpasang.

### 2. Instalasi Dependensi
```bash
pip install -r requirements.txt
```

### 3. Jalankan Aplikasi Command Center
```bash
python -m streamlit run app.py
```
Aplikasi akan aktif pada URL default: `http://localhost:8501`.

---

## 🧪 Menjalankan Automated Test Suite
Untuk memverifikasi keutuhan fungsi sanitasi, rule engine, dan parser CIQ:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## 🛡️ Fitur Utama
1. **Validated inputs:** Shared Pydantic validation rejects invalid IDs, unsafe domains and ambiguous CIQ columns. Numeric Excel IDs are normalized without silently replacing invalid values.
2. **Reviewed rollback drafts:** Revamp preserves the old rule. Delta rollback requires a real pre-change snapshot and emits no executable commands without one.
3. **Batch processing:** CSV/XLSX validation, content-based upload invalidation, row risk reviews, combined scripts and ZIP archives.
4. **Auditable events:** Atomic appends, UUID event IDs, UTC timestamps, nested secret redaction and explicit persistence failures. The JSON store supports one application process.
5. **Anomaly-detection foundation:** Explainable rule checks and versioned feature export. No trained model is active.

Classic Streamlit keeps live execution blocked until device pre-checks, shared-object ownership checks and verified snapshot rollback are implemented. The new Astro command center exposes the existing environment-gated SSH gateway (see below). Simulation does not validate device syntax or impact. QoS, capping and speed settings are currently comments, not applied policies.

See [the reliability and machine-learning roadmap](docs/RELIABILITY_AND_ML_ROADMAP.md) for recommendations, migration notes and release criteria. Direct dependencies are pinned to the versions tested in this workspace. Copy `.env.example` to a local environment configuration and supply a native Fernet key if configuring credentials; existing passphrase-based credentials need migration.

## Astro + GSAP Command Center

The command center in `web/` uses Astro, Tailwind CSS and GSAP. `server.py`
serves the static build and calls the existing Python core directly through
FastAPI. The classic Streamlit application remains available.

### First-time setup

Use Python 3.11+ and Node.js 22.12+ (Node 24 LTS is also suitable).

```bash
python -m pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
```

### Run the complete command center

```bash
python server.py
```

Open **http://localhost:8000**. After building once, Python serves the complete
application; Node.js is only needed when changing or rebuilding the frontend.
The server resolves configuration and build paths relative to `server.py`.
The generated `web/dist/` directory is included and contains bundled fonts,
styles and JavaScript, so the GUI does not depend on a public font CDN.

The GUI includes validated manual presets, a backend-synchronized Service-V
hierarchy, MML and rollback downloads, SSH simulation and gated live execution,
CSV/XLSX/XLS batch ingestion, alias mapping, per-row inspection, combined script
and ZIP downloads, searchable audit history, filtered CSV export and payload
inspection. Invalid edits clear previous output; invalid replacement uploads
clear previous batch results.

### Frontend development

Keep `python server.py` running and start Astro in another terminal:

```bash
cd web
npm run dev
```

Open the local URL printed by Astro (normally http://localhost:4321). Its `/api`
proxy connects to FastAPI on port 8000. After changing frontend source, run
`npm run check` and `npm run build` in `web/` to refresh the Python-served GUI.

### Animation controls

The workspace toolbar reports the loaded GSAP version. **Motion: On** is the
default on every fresh visit: the bento entrance and packet flow start without
any click, including when an old Auto/Off value exists in browser storage.
**Replay** repeats the entrance. **Off** stops motion for the current page
session. Selecting **Auto** explicitly follows the Windows/browser reduced-motion
preference for that session. Reloading or reopening the page starts in On again;
the application does not change Windows settings.
Hidden tabs pause the perpetual packet animation. A missing JavaScript bundle
is reported as `FRONTEND NOT LOADED` with a visible error panel. Startup errors
show their message separately from the motion preference.

After rebuilding, restart `python server.py` if needed and use **Ctrl+F5** in
the browser. API, HTML and the self-contained client bundle disable caching.
The bundle is served as `text/javascript` and uses a deferred classic script;
GSAP and application code are compiled together for ES2020 browsers.
See [dashboard UI and startup details](docs/COMMAND_CENTER_UI.md).

### Manage deployment history

History is stored on disk as JSON; it is not a permanent in-memory cache.
The Astro audit table fetches **25 events per page** by default, supports
server-side filters/search, and can show 50 or 100 events per page. CSV export
includes every matching active event across pages. The footer and **Manage
history** panel show actual active and compressed archive sizes on disk.

**Manage history → Archive & reset active history** preserves all current
events in a `.json.gz` archive before clearing the active JSON file. Confirm
the checkbox before using it. Active WO counters start at zero afterward.
Archives remain on the server and are individually downloadable from that
panel, including their payloads, event IDs and timestamps. No automatic
rotation or permanent-delete operation is enabled. Compression can reduce
disk use; archiving does not remove records from the machine.

The server rejects an archive request if records changed since the panel was
opened. An archive write failure leaves the active records untouched. A reset
failure retains both the active records and any completed archive. Archive
files live in `archives/` beside the effective history JSON (also supporting
the legacy `data/audit_history.json` path). These generated archives are ignored
by Git. The single-process JSON store still reads active history to filter it;
pagination bounds the browser payload and rendered rows, not server-side JSON
parsing. For very large histories, use a transactional database migration.

### Execution and persistence

Simulation is the default. The live-mode controls respect the existing
`RELPOOL_ENABLE_LIVE=true` server environment gate. Configure
`GGSN_TESTBED_USER`, a Fernet-encrypted `GGSN_TESTBED_PASS`, `SECRET_KEY`,
the SSH port and trusted host keys as described in `.env.example` and the
operational runbook. Targets must come from `configs/nodes.yaml`, and live
scripts must match the validated CIQ compiler output. The GUI never stores SSH
credentials.

Live execution reports the core's actual outcome, including `FAILED`,
`PARTIAL_FAILED`, `UNKNOWN` and `SENT_UNVERIFIED`; receiving CLI prompts does
not establish service health. An audit attempt is persisted before SSH starts.
Rollback output remains a draft requiring ownership review, and a regular
update produces no executable rollback without a pre-change snapshot. QoS,
speed and capping remain descriptive comments in the current engine.

Audit events use the existing redacted JSON history store in `data/audit/`.
Run one application process against this store; do not run Streamlit and
FastAPI concurrently against the same history file. FastAPI serializes audit
updates from concurrent HTTP requests within its process. The server binds to
loopback and is intended for a local operator workstation; shared deployment
needs an authenticated gateway and a transactional audit store.

### API and verification

The API is documented at http://localhost:8000/docs. Routes are registered
before the static root mount:

| Route | Purpose |
| --- | --- |
| `GET /api/system-info` | Configured clusters, Jakarta-day counters and engine/gateway metadata |
| `POST /api/preview` | Validated hierarchy preview without creating an audit event |
| `POST /api/generate` | MML, rollback draft, hierarchy and persisted generation event |
| `POST /api/ssh/execute` | Real core SSH simulation or gated live push and outcome audit |
| `GET /api/batch/sample` | Download the standard CSV template |
| `POST /api/batch/process` | Multipart `file`, first 50 data rows, mappings, scripts and base64 ZIP |
| `GET /api/audit` | Full redacted deployment history |
| `GET /api/audit/page` | Paginated active history, filters, counts and storage metadata |
| `GET /api/audit/export` | CSV export of all matching active events |
| `POST /api/audit/archive` | Confirmed, revision-checked archive before resetting active history |
| `GET /api/audit/archives/{filename}` | Download a preserved compressed audit snapshot |

```bash
python -m unittest discover -s tests -p "test_*.py"
cd web
npm run check
npm run build
npm test
```

`tests/test_server_api.py` uses temporary audit files and real generation,
batch/archive and simulation functions. It also checks invalid input, secret
redaction, audit storage failure, concurrent requests and mocked live outcomes;
tests never open a real SSH connection.
