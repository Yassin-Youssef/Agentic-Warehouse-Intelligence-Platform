# Agentic Warehouse Intelligence Platform

A full-stack analytics system for robotic warehouse operations — combining discrete-event simulation, deterministic analysis, LLM-powered reasoning, and a production-style REST API.

> **Core principle: "Rules decide → LLM explains."**  
> Every metric is computed by deterministic code. The LLM layer never makes decisions — it only interprets pre-computed analysis and produces natural-language recommendations.

---

## Architecture

```
SIMULATE (Phase 1) → ANALYZE (Phase 2) → REASON (Phase 3) → REPORT (Phase 4)
   Discrete-event       5 Deterministic      5 LLM-Powered       FastAPI +
   simulation           analyzers            agents               unified CLI
       ↓                     ↓                    ↓                    ↓
   JSON logs            JSON report         Intelligence         REST endpoints
   (data/)              (outputs/)          report (outputs/)    (port 8000)
```

---

## Phase 1 — Simulation Engine

Generates realistic warehouse event data using a discrete-event simulation with a 6-zone warehouse, 10 autonomous robots, and configurable time period (default: 4 hours). Fully reproducible via seeded RNG (default seed: 42).

### How It Works

Each 1-second tick runs this cycle:

1. **Generate tasks** — Poisson arrivals per zone, with weighted priorities (P1: 20%, P2: 50%, P3: 30%)
2. **Dispatch idle robots** — Nearest-zone-first with priority-queue ordering
3. **Tick all robots** — Advance state-machine timers (`idle → traveling → picking → idle`, with diversions to `charging` and `failed`)
4. **Inject failures** — Post-task failure rolls (3% base, 10.5% for robots 8–10), conveyor delays (10% chance), zone overloads (~30 min intervals)
5. **Manage batteries** — Drain per task/travel, auto-charge below 15%
6. **Log events** — Every state transition emits a `LogEntry`

### Key Configuration

- **6 zones** — Zone A3 is intentionally congested (4.0 tasks/min vs 1.5–2.2 for others)
- **10 robots** — 2 per zone, with robots 8–10 having 3.5× failure rate
- **10 event types** — `task_queued`, `task_completed`, `robot_failed`, `robot_recovered`, `robot_charging`, `robot_charged`, `robot_idle`, `conveyor_delay`, `zone_overload_start`, `zone_overload_end`

### Modules

| Module | Purpose |
|--------|---------|
| `simulation/warehouse.py` | Main simulation loop (1-second discrete time steps) |
| `simulation/robot.py` | Robot state machine with 5 states |
| `simulation/zone.py` | Zone with priority min-heap task queue |
| `simulation/task_generator.py` | Poisson-process task arrivals |
| `simulation/dispatcher.py` | Nearest-zone-first assignment strategy |
| `simulation/failure_injector.py` | Failures, conveyor delays, zone overloads |
| `config/warehouse_config.py` | Central configuration dataclass |

---

## Phase 2 — Deterministic Analysis

Five independent analyzers process raw simulation logs to produce hard metrics. No LLM involvement — everything is computed deterministically.

| Analyzer | What It Computes |
|----------|-----------------|
| **Throughput** (`throughput_analyzer.py`) | Total/hourly/per-zone throughput, trend detection via linear regression |
| **Queue Growth** (`queue_analyzer.py`) | Average/peak queue lengths, growth rates, congested zone identification |
| **Robot Utilization** (`utilization_analyzer.py`) | Per-robot time breakdown (active/failed/charging/idle), fleet utilization averages |
| **Downtime & Reliability** (`downtime_analyzer.py`) | MTBF, failure counts, reliability scores (0–100), failure clustering |
| **Cost Impact** (`cost_estimator.py`) | Dollar-value estimates for idle, delay, failure, and queue costs |

All analyzers produce typed dataclass reports that compose into a `WarehouseAnalysisReport`.

---

## Phase 3 — Agentic Reasoning

Five LLM-powered agents receive the Phase 2 report and produce strategic insights. Each extends `BaseAgent` with a `run()` → `_build_prompt()` → `call_llm()` → `_parse_response()` pipeline.

| Agent | Focus | Input |
|-------|-------|-------|
| **Performance Summary** | Executive warehouse health overview | Throughput, utilization, cost |
| **Bottleneck Diagnosis** | Root-cause congestion analysis | Queue data, per-zone throughput |
| **Resource Allocation** | Robot rebalancing recommendations | Utilization, per-zone throughput |
| **Risk Forecast** | Predictive risk assessment | Downtime, MTBF, reliability scores |
| **Optimization Strategy** | Cost-benefit ranked improvements | Full report (all sections) |

**LLM Client** — Thin wrapper around Anthropic Claude API (`claude-sonnet-4-20250514`). Includes retry logic (2 attempts) and graceful fallback on failure. API key loaded from `.env`.

---

## Phase 4 — API Layer & CLI

### REST API (FastAPI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/warehouse/simulate` | Run simulation (optional config overrides) |
| `GET` | `/warehouse/analysis` | Run analysis (optional `?log_file=`) |
| `GET` | `/warehouse/optimization` | Run optimization agents |
| `GET` | `/warehouse/risk` | Run risk agents |
| `GET` | `/warehouse/config` | View default config |
| `POST` | `/warehouse/config` | Preview merged config |
| `POST` | `/warehouse/full-pipeline` | Run complete Phase 1→2→3 pipeline |

### CLI (`main.py`)

| Mode | What It Runs |
|------|-------------|
| `simulate` | Phase 1 only |
| `analyze` | Phase 1 → Phase 2 |
| `agents` | Phase 1 → Phase 2 → Phase 3 |
| `api` | Start FastAPI server (port 8000) |
| `full` | Complete pipeline (default) |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Anthropic API key (only required for Phase 3)

### Setup

```bash
git clone https://github.com/Yassin-Youssef/Agentic-Warehouse-Intelligence-Platform.git
cd Agentic-Warehouse-Intelligence-Platform
pip install -r requirements.txt
cp .env.example .env
# Add your Anthropic API key to .env
```

### Quick Start

```bash
# Simulation only (no API key needed)
python main.py --mode simulate

# Simulate + Analyze (no API key needed)
python main.py --mode analyze

# Full pipeline with LLM agents (requires API key)
python main.py --mode agents

# Start REST API server
python main.py --mode api

# Then visit http://localhost:8000/docs for interactive Swagger UI
```

### Example API Calls

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/warehouse/simulate
curl http://localhost:8000/warehouse/analysis
curl -X POST http://localhost:8000/warehouse/full-pipeline
```

---

## Example Output

**Simulation Summary (Phase 1):**
```
Duration: 14,400s (4.0 hours) · Tasks generated: 3,912 · Completed: 847 (21.6%)
Robot failures: 42 · Charging events: 68 · Conveyor delays: 89 · Zone overloads: 8
```

**Intelligence Report (Phase 3):**
```
━━━ BOTTLENECK DIAGNOSIS ━━━
Primary bottleneck in Zone A3 (arrival rate 4.0 tasks/min vs fleet capacity ~2.1).
Queue growth rate of +0.8 items/hour confirms sustained congestion.

━━━ TOP RECOMMENDATIONS ━━━
1. Redistribute 2 robots from Zone B1 to A3 → estimated +15% throughput
2. Predictive maintenance on Robots 8-10 → reduce downtime by 40%
3. Adjust conveyor scheduling during peak hours → reduce delay cost by $45/shift
```

---

## Project Structure

```
Agentic_warehouse/
├── simulation/          # Phase 1 — Discrete-event simulator
├── analysis/            # Phase 2 — Deterministic analyzers
├── agents/              # Phase 3 — LLM-powered agents
├── api/                 # Phase 4 — FastAPI application
│   └── routes/          #   Route handlers
├── tools/               # Shared utilities (log loader, LLM client)
├── schemas/             # Data models (log, analysis, agent)
├── config/              # Configuration dataclasses
├── data/                # Generated simulation logs (JSON)
├── outputs/             # Analysis & intelligence reports
├── main.py              # Unified CLI entry point
├── requirements.txt     # Python dependencies
└── .env.example         # Environment variable template
```

---

## Tech Stack

| Technology | Role |
|------------|------|
| Python 3.10+ | Core language |
| FastAPI + Uvicorn | Async REST API |
| NumPy | Numerical computation, seeded RNG |
| Anthropic Claude API | LLM reasoning (Phase 3) |
| python-dotenv | Environment management |

---

## Author

**Yassin Baher Youssef**  
Robotics & Intelligent Systems Student  
Constructor University Bremen
