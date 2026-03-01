# Dzeck AI — Project Summary

## Ringkasan Proyek
Dzeck AI adalah platform AI Agent berbasis web yang memungkinkan pengguna berinteraksi dengan agen AI cerdas. AI dapat menelusuri web, menjalankan perintah shell, mengelola file, melakukan pencarian, dan menampilkan aktivitas secara real-time melalui VNC viewer.

---

## Arsitektur Sistem

```
Pengguna (Browser)
     │
     ▼
Frontend (Vue 3) — port 5000
     │  /api/* di-proxy ke →
     ▼
Backend (FastAPI) — port 8000
     │
     ├─── MongoDB Atlas (cloud database)
     ├─── Redis Labs (cloud cache/queue)
     └─── Sandbox (FastAPI + Chrome + VNC) — port 8080
```

**Alur data:**
1. User kirim pesan via Frontend
2. Backend terima request, buat session, jalankan AI Agent (PlanActFlow)
3. Agent panggil tools (Shell, Browser, File, Search) via Sandbox API
4. Hasil di-stream real-time ke Frontend via SSE (Server-Sent Events)
5. State disimpan di MongoDB, cache/lock di Redis

---

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS, ShadcnUI |
| Backend | Python 3.11, FastAPI, Beanie ODM, uvicorn |
| Database | MongoDB Atlas (cloud) |
| Cache | Redis Labs (cloud, port 16364, no SSL) |
| AI/LLM | Pollinations AI (`https://text.pollinations.ai/v1`), model `openai`, GRATIS |
| Auth | JWT (access + refresh token), bcrypt password hash |
| Sandbox | Supervisord, Xvfb, Chromium, x11vnc, websockify, Playwright |
| VNC Viewer | noVNC (embedded di frontend) |
| Code Editor | Monaco Editor |
| i18n | vue-i18n (default: Bahasa Indonesia) |
| Runtime | NixOS (Replit), Node 20, Python 3.11 |

---

## Struktur File Penting

```
workspace/
├── backend/
│   ├── app/
│   │   ├── domain/            # Core logic: Agent, Flow, Prompts
│   │   │   ├── services/
│   │   │   │   ├── agents/    # base.py — tool calling logic
│   │   │   │   ├── flows/     # plan_act.py — PlanActFlow AI
│   │   │   │   └── prompts/   # system.py, planner.py, execution.py
│   │   ├── infrastructure/    # DB, Redis, LLM, Sandbox clients
│   │   │   ├── external/llm/  # openai_llm.py — LLM wrapper
│   │   │   └── storage/       # mongodb.py, redis.py
│   │   ├── application/       # AuthService, AgentService, FileService
│   │   └── interfaces/        # FastAPI routes & schemas
│   ├── requirements.txt
│   └── .env                   # Semua konfigurasi credential
│
├── frontend/
│   └── src/
│       ├── locales/           # id.ts (ID), en.ts (EN), zh.ts (ZH)
│       ├── pages/             # HomePage, ChatPage, LoginPage
│       ├── components/
│       │   ├── toolViews/     # Browser, Shell, File, Search views
│       │   └── icons/         # ManusLogoTextIcon (→ teks "Dzeck")
│       ├── composables/       # useI18n.ts — default locale: "id"
│       └── api/               # auth.ts, sessions.ts
│
├── sandbox/
│   ├── app/
│   │   └── services/          # shell.py, browser.py, file.py
│   ├── supervisord-replit.conf
│   └── requirements.txt
│
├── start.sh          # Production: start semua services (Frontend+Backend+Sandbox)
├── start_frontend.sh # Dev: jalankan Vite dev server
├── start_backend.sh  # Dev: jalankan uvicorn
├── start_sandbox.sh  # Dev: jalankan supervisord sandbox
├── build.sh          # Deployment build: pip install + npm run build
├── setup.sh          # Setup awal Replit: install semua deps
└── .replit           # Konfigurasi workflow & deployment Replit
```

---

## Konfigurasi Deployment (`backend/.env`)

```env
# LLM — Pollinations (GRATIS, tidak perlu API key asli)
API_KEY=pollinations
API_BASE=https://text.pollinations.ai/v1
MODEL_NAME=openai
TEMPERATURE=0.7
MAX_TOKENS=8000

# MongoDB Atlas
MONGODB_URI=mongodb+srv://galerizaki_db_user:...@cluster0.vmiek8b.mongodb.net/manus
MONGODB_DATABASE=manus

# Redis Labs (cloud, NO SSL)
REDIS_HOST=redis-16364.c279.us-central1-1.gce.cloud.redislabs.com
REDIS_PORT=16364
REDIS_PASSWORD=0W7ImuMIUrkUTF0wxYSkIWmc8MRjPrYX
REDIS_SSL=false

# Sandbox (local instance di Replit)
SANDBOX_ADDRESS=127.0.0.1

# Auth (mode local — tanpa email service)
AUTH_PROVIDER=local
LOCAL_AUTH_EMAIL=admin@example.com
LOCAL_AUTH_PASSWORD=admin123
JWT_SECRET_KEY=Namakamusiapa123
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## API Endpoints Utama

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/v1/auth/status` | Cek status auth |
| POST | `/api/v1/auth/login` | Login (email + password) |
| POST | `/api/v1/auth/register` | Registrasi akun baru |
| POST | `/api/v1/auth/refresh` | Refresh JWT token |
| PUT | `/api/v1/sessions` | Buat session baru |
| GET | `/api/v1/sessions` | List semua session user |
| POST | `/api/v1/sessions/{id}/chat` | Kirim pesan ke AI (SSE stream) |
| GET | `/api/v1/sessions/{id}/events` | Ambil history events |
| POST | `/api/v1/files/upload` | Upload file ke session |
| GET | `/api/v1/files/{session_id}` | List file dalam session |

---

## Sistem Autentikasi

- **JWT-based**: Access token (60 menit) + Refresh token (7 hari)
- **Mode `local`**: Admin credentials dari `.env` (tidak perlu email service)
- **Mode `password`**: User bisa daftar sendiri via `/auth/register`
- **Password hash**: PBKDF2-SHA256 (via passlib)
- **Isolasi data**: Setiap user hanya bisa lihat session miliknya sendiri (filtered by `user_id`)

**Login default:**
- Email: `admin@example.com`
- Password: `admin123`

---

## AI Agent Logic

```
User Message
    │
    ▼
PlannerAgent (system.py + planner.py)
    │  → Buat daftar langkah (Plan)
    │  → Jika percakapan biasa: langsung jawab (steps=[])
    ▼
ExecutionAgent (execution.py)
    │  → Jalankan setiap step dengan tools:
    │     - shell_exec, file_read, file_write
    │     - browser_navigate, browser_click, browser_type
    │     - web_search
    │  → Setiap tool result di-stream ke Frontend
    ▼
Summarizer → Jawaban akhir
```

**LLM:** Pollinations AI (GPT-4o compatible, free, no rate limit fee)
**Identity:** AI bernama "Dzeck", bukan "Manus"

---

## Bahasa / Internasionalisasi (i18n)

- **Default:** Bahasa Indonesia (`id`)
- **Tersedia:** Indonesia (`id`), Inggris (`en`), Mandarin (`zh`)
- **Storage key:** `dzeck-locale` (localStorage)
- **Fallback:** Jika browser pakai Mandarin → `zh`, Inggris → `en`, selainnya → `id`
- **File:** `frontend/src/locales/id.ts` (100+ teks terjemahan)

---

## Deployment ke Replit

**Config di `.replit`:**
```toml
[deployment]
deploymentTarget = "vm"
build = ["bash", "build.sh"]
run   = ["bash", "start.sh"]
```

**URL:**
- Development: `*.replit.dev` (preview di IDE)
- Production: `*.replit.app` (setelah klik Publish)

**Proses publish:**
1. `build.sh` dijalankan: install Python deps + install Node deps + `npm run build`
2. `start.sh` dijalankan: start Frontend (vite preview) + Backend (uvicorn) + Sandbox (supervisord)
3. Frontend serve dari `frontend/dist/` (production build)
4. CORS: `allow_origins=["*"]` — semua domain diizinkan

---

## Sandbox (Komputer Virtual AI)

- **Services yang berjalan:** Xvfb (display virtual), Chromium, x11vnc, websockify, FastAPI agent
- **Port:** 8080 (API sandbox internal)
- **VNC viewer:** Embedded di frontend via noVNC — user bisa lihat browser AI secara real-time
- **Working directory:** `/home/runner`
- **Limitasi Replit:** Sandbox adalah single shared instance (bukan Docker per-session). Cocok untuk single-user atau low-concurrency.

---

## Bug Fix History (Kumulatif)

1. Vite `allowedHosts: true` — fix "Blocked request" di domain Replit
2. noVNC CJS module error — fix blank page (hapus dari `optimizeDeps.exclude`)
3. Agent NullPointerError — `(message or '')[:50]` fix
4. Sandbox port conflict — `pkill -f "uvicorn.*8080"` di startup
5. Sandbox null data — null check untuk `shell_result.data` dan `file_read_result.data`
6. Sandbox wrong home dir — fallback `/home/runner` → `/`
7. AI prompt home dir — ubah `/home/ubuntu` → `/home/runner`
8. Tool name corruption — regex sanitize nama tool dari Pollinations API
9. `response_format` + `tools` conflict — suppress `json_object` saat tools digunakan
10. Unknown tool name — graceful error handling, AI bisa recovery
11. Rate limit (429) — wait 30 detik sebelum retry
12. Planner conversational — pesan biasa tidak buat steps, langsung jawab
13. Deployment config — ubah dari `cloudrun` ke `vm` target
14. pip `--user` flag — fix "Permission denied" di Nix store saat deploy
15. Production frontend — `vite preview` dari `dist/` di `start.sh`
16. Root `pyproject.toml` — hapus agar tidak konflik dengan Replit auto-detect
17. Startup stability — backend health-check, sandbox wait 60s
18. Deps sync — tambah `supervisor` dan `websockify` ke `sandbox/requirements.txt`
19. **TypeScript error** — `getBrowserLocale` tidak digunakan → fix dengan panggil di fallback
20. **start.sh port** — explicit `--port ${FRONTEND_PORT}` ke vite preview/dev

---

## Branding

| Sebelum | Sesudah |
|---|---|
| Manus | Dzeck |
| AI Manus | Dzeck AI |
| Login to Manus | Masuk ke Dzeck |
| `manus-locale` (localStorage) | `dzeck-locale` |
| Avatar fallback 'M' | Avatar fallback 'D' |
| GitHub login button | Dihapus |
| Bahasa default: Inggris | Bahasa default: Indonesia |
