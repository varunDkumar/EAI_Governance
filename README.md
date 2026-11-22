# Agent Trust Fabric — Academic Intelligence Edition

A local-first desktop app (Tauri + React + Python) that lets governed AI agents answer
questions over the IIMA academic repository in `moodle-bak/`, with persistent memory,
an interactive knowledge graph, and a backend-enforced governance/audit trail.

See [`~/.claude/plans/jaunty-gathering-pixel.md`](~/.claude/plans/jaunty-gathering-pixel.md) for the full build plan and phase breakdown.

## Prerequisites

- **Rust** (for Tauri) — already present on this machine.
- **Node 20** — managed via `nvm` (installed under `~/.nvm`, not the system Node). The system
  `node` on PATH is v14 and too old for this project; all scripts here explicitly `nvm use 20`.
- **Python 3.13** with a venv at `backend/.venv`.
- An LLM provider key — the backend supports four, selected via `LLM_PROVIDER` in `.env`:
  - `groq` (recommended) — fast, generous free tier, OpenAI-compatible. Get a key at console.groq.com.
  - `gemini` — Google's free tier caps `gemini-3.8-flash` at **20 requests/day**, which is easy to
    exhaust during normal use; fine for light testing, not for a working session.
  - `ollama` — fully local/offline, no key needed, but slow on CPU-only hardware (several minutes
    per response with a full RAG context on this machine). Requires `ollama pull llama3.2:3b` first.
  - `openai` — works like any standard OpenAI-compatible key.
- (Optional) **Tesseract** for OCR on scanned PDFs — not installed in this environment; PDFs with
  no extractable text are indexed with empty text rather than failing the import.

## First-time setup

```bash
# Frontend
cd app && npm install

# Backend
cd ../backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create `EYP_Demo/.env` (repo root, gitignored):
```
LLM_PROVIDER=groq
GROQ_API_KEY=your-key-here
```

## Installed app

**Agent Trust Fabric.app** is installed in `/Applications` — launch it like any other Mac app.
The Python backend is bundled inside as a self-contained PyInstaller sidecar (no system Python
needed); it auto-starts when the app opens and shuts down cleanly when it closes. This build is
tied to this specific checkout on this machine (it points at this folder's `backend/data`,
`moodle-bak`, and `.env` by absolute path) — it is not something you could hand to another Mac.

To rebuild after backend changes, see the "Rebuilding the packaged app" section below.

## Running in development

```bash
./scripts/dev.sh
```

This starts the FastAPI backend on `127.0.0.1:8756` and the Tauri dev shell (native window +
hot-reloading React frontend) together, without touching the installed app.

## Rebuilding the packaged app

After backend changes, rebuild the sidecar and the app:

```bash
cd backend
.venv/bin/pyinstaller --name atf-backend --onefile --noconfirm \
  --collect-all chromadb --collect-all fastembed --collect-all onnxruntime \
  --collect-all tokenizers --collect-all pymupdf --collect-all google.genai \
  --hidden-import=uvicorn.logging --hidden-import=uvicorn.loops.auto \
  --hidden-import=uvicorn.protocols.http.auto --hidden-import=uvicorn.protocols.http.h11_impl \
  --hidden-import=uvicorn.protocols.websockets.auto --hidden-import=uvicorn.lifespan.on \
  main.py
cp dist/atf-backend ../app/src-tauri/binaries/atf-backend-x86_64-apple-darwin
```

```bash
cd ../app
npm run tauri build
cp -R "src-tauri/target/release/bundle/macos/Agent Trust Fabric.app" /Applications/
```

## Project layout

```
app/              Tauri + React + TypeScript + Tailwind frontend
backend/
  api/            FastAPI routers (repository, agents, chat, memory, approvals, audit, graph, overview)
  db/             SQLAlchemy models, session (WAL-mode SQLite), seed data
  governance/     Policy engine (ALLOW/DENY/REQUIRE_APPROVAL) + hash-chained audit log
  memory/         Memory proposal, governance-gated approval, retrieval
  graph/          Knowledge graph construction (concept/framework/case extraction, relationship linking)
  ingest/         Document parsing, chunking, embeddings (fastembed/ONNX), Chroma vector store
  llm/            Vendor-neutral LLMProvider interface + gemini/groq/openai/ollama implementations
moodle-bak/        Source academic repository (read-only import source; Term 1-5 / Course / Session)
scripts/dev.sh    Runs backend + Tauri dev shell together
```

## Status

All phases of the build plan (A–H) are complete: foundation, knowledge repository ingest pipeline,
governed multi-agent chat, memory engine with cross-session/cross-restart continuity, approval
workflow + hash-chained audit log, knowledge graph, real (non-mocked) dashboards, and native macOS
packaging. Verified end-to-end against the real, full 5-term corpus (1,210/1,220 files indexed,
live LLM calls) both in dev mode and as the installed `/Applications` app launched standalone.

### Known limitations

- Embeddings run locally via ONNX (`fastembed`), not `sentence-transformers`/PyTorch — this Mac is
  Intel and PyTorch publishes no wheels for Intel macOS on Python 3.13.
- Legacy binary `.doc`/`.ppt` files are not parsed (only `.docx`/`.pptx`); they're recorded with a
  clear error status rather than silently skipped.
- A single document is capped at 400 indexed chunks — an extreme outlier (300+ page PDF) could
  otherwise exhaust memory on constrained hardware; oversized documents get a bounded prefix
  indexed with a note, not full-document failure.
- No native OS folder picker for import; the UI offers each `moodle-bak` term plus "entire
  repository" rather than an arbitrary filesystem path.
