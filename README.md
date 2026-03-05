# Agentic Warehouse Intelligence Platform

## Overview

The **Agentic Warehouse Intelligence Platform** is a full-stack analytics system for robotic warehouse operations. It combines a discrete-event simulation engine with deterministic statistical analysis and LLM-powered agentic reasoning to produce actionable operational insights — all accessible through a production-style RESTful API.

The platform generates realistic warehouse event data — task arrivals following Poisson processes, robot state-machine transitions, stochastic failures, battery drain cycles, conveyor delays, and zone overloads — then runs five independent deterministic analyzers to compute hard operational metrics, and finally passes those metrics to five specialized AI agents that interpret the numbers and produce human-readable strategic recommendations.

The core architectural principle is **"Rules decide → LLM explains."** Every metric, threshold, and flag is computed by deterministic code with no randomness beyond the seeded simulation. The LLM layer never makes decisions — it solely receives pre-computed analysis and produces natural-language interpretations, diagnoses, and recommendations.

---

## Architecture

The system follows a strict four-layer pipeline where each layer's output feeds the next:

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  SIMULATE   │ ──► │    ANALYZE       │ ──► │     REASON       │ ──► │    REPORT     │
│  Phase 1    │     │    Phase 2       │     │    Phase 3       │     │   Phase 4     │
│             │     │                  │     │                  │     │              │
│  Discrete-  │     │  5 Deterministic │     │  5 LLM-Powered   │     │  FastAPI +   │
│  event sim  │     │  analyzers       │     │  agents          │     │  unified CLI │
└─────────────┘     └─────────────────┘     └──────────────────┘     └──────────────┘
      │                      │                       │                       │
  JSON logs            JSON report            JSON intel report        REST endpoints
  (data/)              (outputs/)             (outputs/)               (port 8000)
```

### Data Flow

1. **Phase 1** creates a `WarehouseSimulator(config)`, calls `.run()` to produce a list of `LogEntry` objects, calls `.get_summary()` for aggregate stats, and saves everything as JSON to `data/`.
2. **Phase 2** loads the latest JSON log from `data/`, runs all five analyzers, assembles a `WarehouseAnalysisReport`, and saves it to `outputs/`.
3. **Phase 3** loads the latest analysis report from `outputs/`, instantiates all five agents, calls `.run(report)` on each, and saves the intelligence report to `outputs/`.
4. **Phase 4** exposes all of this as REST endpoints and provides a unified CLI entry point.

---

## System Modules

### Phase 1 — Simulation Engine

The simulation engine models a 6-zone warehouse with 10 autonomous robots operating over a configurable time period (default: 4 hours / 14,400 seconds). The entire simulation is deterministic given a random seed (default: 42).

#### Core Components

| Module | Class | Description |
|--------|-------|-------------|
| `simulation/warehouse.py` | `WarehouseSimulator` | Main simulation loop — advances in 1-second discrete time steps |
| `simulation/robot.py` | `Robot` | State-machine entity: `idle → traveling → picking → idle`, with diversions to `charging` and `failed` |
| `simulation/zone.py` | `Zone` | Named zone with a priority min-heap task queue (ordered by priority then arrival time) |
| `simulation/task_generator.py` | `TaskGenerator` | Poisson-process task arrivals per zone per second (λ = zone rate / 60) |
| `simulation/dispatcher.py` | `Dispatcher` | Nearest-zone-first assignment: checks robot's current zone, then falls back to busiest zone |
| `simulation/failure_injector.py` | `FailureInjector` | Injects robot failures, conveyor delays, and zone overloads |
| `config/warehouse_config.py` | `WarehouseConfig` | Central dataclass holding every tunable parameter |

#### Simulation Tick Cycle

Each 1-second tick follows this sequence:

1. **Generate tasks** — Poisson draw per zone, priorities sampled from weighted distribution (P1: 20%, P2: 50%, P3: 30%)
2. **Dispatch idle robots** — Nearest-zone-first with priority-queue ordering
3. **Tick all robots** — Advance timers, detect state transitions (travel_done, pick_done, charge_done, recover)
4. **Check failures** — Per-robot failure roll after task completion (3% base, 10.5% for robots 8/9/10)
5. **Conveyor delays** — 10% chance of 5–20s extra delay on pick
6. **Zone overloads** — Exponential inter-arrival (~30 min), doubles a random zone's rate for 5 min
7. **Battery management** — Drain per task/travel, charge when below 15%
8. **Log events** — Every state transition emits a `LogEntry`

#### Zone Configuration

| Zone | Arrival Rate (tasks/min) | Notes |
|------|-------------------------|-------|
| A1 | 2.0 | Normal zone |
| A2 | 1.8 | Normal zone |
| A3 | 4.0 | **Intentional congestion zone** |
| B1 | 1.5 | Low-volume zone |
| B2 | 2.2 | Normal zone |
| B3 | 1.9 | Normal zone |

#### Robot Configuration

| Parameter | Value |
|-----------|-------|
| Fleet size | 10 robots |
| Home zones | 2 per zone (A1: 1,2 · A2: 3,4 · A3: 5,6 · B2: 7,8 · B3: 9,10) |
| Base failure rate | 3% per task cycle |
| High-failure robots | 8, 9, 10 (3.5× multiplier → 10.5%) |
| Battery capacity | 100 units |
| Low-battery threshold | 15 units |
| Drain per task | 0.5 units |
| Drain per travel | 0.1 units |
| Charge time | 60–120 seconds |
| Failure downtime | 120–300 seconds |
| Travel time (cross-zone) | 8–40 seconds |
| Pick duration | Normal(μ=18s, σ=5s), floor-clamped at 6s |

#### Event Types

The simulation emits 10 distinct event types:

| Event | Trigger |
|-------|---------|
| `task_queued` | New task arrives via Poisson process |
| `task_completed` | Robot finishes picking |
| `robot_failed` | Post-task failure roll succeeds |
| `robot_recovered` | Failure downtime expires |
| `robot_charging` | Battery drops below threshold |
| `robot_charged` | Charging complete (battery → 100%) |
| `robot_idle` | Periodic idle-state logging (every 60s) |
| `conveyor_delay` | Random 5–20s delay on pick (10% chance) |
| `zone_overload_start` | Zone arrival rate doubles |
| `zone_overload_end` | Zone rate restored to base |

---

### Phase 2 — Deterministic Analysis Layer

Five independent analyzers process the raw simulation logs to produce hard metrics. No LLM involvement — every number is computed deterministically.

#### Throughput Analyzer (`analysis/throughput_analyzer.py`)

- Total tasks completed across the simulation
- Hourly throughput breakdown (tasks per hour)
- Per-zone throughput and zone-level hourly breakdown
- Linear regression trend detection (`increasing`, `decreasing`, or `stable`)
- Highest and lowest performing zones with their throughput rates

#### Queue Growth Detector (`analysis/queue_analyzer.py`)

- Average queue length per zone (computed from `queue_length` fields in log events)
- Peak queue length per zone
- Queue growth rate per zone (slope of queue length over time)
- Congested zone identification (zones with positive growth rate)
- Congestion event count
- Highest average and highest peak queue zones

#### Robot Utilization Analyzer (`analysis/utilization_analyzer.py`)

- Per-robot time breakdown: active, failed, charging, idle (in seconds and percentages)
- Per-robot utilization rate and idle rate
- Task count per robot
- Fleet average utilization percentage
- Underutilized robots (>40% idle)
- Overworked robots (>85% active)

#### Downtime & Reliability Metrics (`analysis/downtime_analyzer.py`)

- Per-robot failure count, total downtime, and downtime percentage
- Mean Time Between Failures (MTBF) per robot (in minutes)
- Per-robot reliability score (0–100)
- Fleet-wide failure rate (failures per robot-hour)
- Failure clustering detection
- Least and most reliable robots

#### Cost Impact Estimator (`analysis/cost_estimator.py`)

- Dollar-value estimates for four cost categories:
  - **Idle cost** — robots sitting unused
  - **Delay cost** — conveyor delays impacting throughput
  - **Failure cost** — downtime from robot failures
  - **Queue cost** — tasks waiting in queue
- Total inefficiency cost with percentage breakdown
- Takes utilization and downtime reports as inputs for cross-referencing

#### Output Schema

All analyzers produce typed dataclass reports that compose into a `WarehouseAnalysisReport`:

```
WarehouseAnalysisReport
├── ThroughputReport
├── QueueReport
├── UtilizationReport (contains per-robot RobotMetrics)
├── DowntimeReport (contains per-robot RobotDowntime)
└── CostReport
```

---

### Phase 3 — Agentic Reasoning Layer

Five LLM-powered agents receive the Phase 2 analysis report and produce strategic insights. Each agent extends `BaseAgent`, which implements the `run()` → `_build_prompt()` → `call_llm()` → `_parse_response()` pipeline.

#### Agent Architecture

```
BaseAgent (base_agent.py)
│
├── name, description, system_prompt  ← set by each subclass
│
├── run(analysis_report)              ← public entry point
│   ├── _build_prompt(report)         ← subclass extracts relevant metrics
│   ├── call_llm(system, user)        ← sends to Anthropic Claude API
│   └── _parse_response(text)         ← extracts recommendations, builds AgentOutput
│
└── AgentOutput                       ← structured output dataclass
    ├── agent_name
    ├── timestamp
    ├── summary (full LLM text)
    ├── recommendations (extracted list)
    ├── confidence
    └── raw_input_preview
```

#### The Five Agents

| Agent | Focus | Input Sections |
|-------|-------|----------------|
| **Performance Summary Agent** | Executive overview of warehouse health | Throughput, utilization, cost |
| **Bottleneck Diagnosis Agent** | Root-cause analysis of congestion | Queue, throughput per zone, congested zones |
| **Resource Allocation Agent** | Robot rebalancing recommendations | Utilization, underutilized/overworked robots, per-zone throughput |
| **Risk Forecast Agent** | Predictive risk assessment | Downtime, failure rates, reliability scores, MTBF |
| **Optimization Strategy Agent** | Cost-benefit ranked improvements | Full report (all sections) |

#### LLM Client (`tools/llm_client.py`)

- Thin wrapper around the Anthropic Claude Messages API
- Model: `claude-sonnet-4-20250514` (configurable)
- Max tokens: 1,500 per response
- Retry logic: 2 attempts with 3-second delay
- Graceful degradation: returns fallback string on failure
- API key loaded from `.env` via `python-dotenv`

---

### Phase 4 — API Layer & CLI

#### FastAPI Application (`api/app.py`)

- CORS middleware (allow all origins for development)
- Request-logging middleware (logs method, path, response time in ms)
- All route modules included via `APIRouter`

#### API Endpoints

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/health` | Health check | — |
| `POST` | `/warehouse/simulate` | Run Phase 1 simulation | Optional JSON body: `num_robots`, `sim_duration_seconds`, `random_seed`, `base_failure_rate`, `conveyor_delay_probability` |
| `GET` | `/warehouse/analysis` | Run Phase 2 analysis | Optional query: `?log_file=filename` |
| `GET` | `/warehouse/optimization` | Run optimization agents (Performance Summary + Resource Allocation + Optimization Strategy) | Optional query: `?analysis_file=filename` |
| `GET` | `/warehouse/risk` | Run risk agents (Bottleneck Diagnosis + Risk Forecast) | Optional query: `?analysis_file=filename` |
| `GET` | `/warehouse/config` | View default config | — |
| `POST` | `/warehouse/config` | Preview merged config (non-persisting) | JSON body with partial overrides |
| `POST` | `/warehouse/full-pipeline` | Run complete Phase 1→2→3 pipeline | — |

#### Unified CLI (`main.py`)

| Mode | What It Runs |
|------|-------------|
| `simulate` | Phase 1 only |
| `analyze` | Phase 1 → Phase 2 |
| `agents` | Phase 1 → Phase 2 → Phase 3 |
| `api` | Start FastAPI server on port 8000 |
| `full` | Complete pipeline (default) |

---

## How To Run

### Prerequisites

- Python 3.10+
- Anthropic API key (required for Phase 3 agents)

### Setup

```bash
git clone https://github.com/Yassin-Youssef/Agentic-Warehouse-Intelligence-Platform.git
cd Agentic-Warehouse-Intelligence-Platform
pip install -r requirements.txt
cp .env.example .env
# Add your Anthropic API key to .env
```

### Run Modes

```bash
# Simulation only (Phase 1) — no API key needed
python main.py --mode simulate

# Simulate + Analyze (Phase 1 + 2) — no API key needed
python main.py --mode analyze

# Full pipeline (Phase 1 + 2 + 3) — requires API key
python main.py --mode agents

# Start REST API server on port 8000
python main.py --mode api

# Complete pipeline (default if no --mode given)
python main.py --mode full
```

### API Usage

```bash
# Start the API server
python main.py --mode api

# Health check
curl http://localhost:8000/health
# → {"status": "healthy", "version": "1.0.0"}

# Run full pipeline (one-click)
curl -X POST http://localhost:8000/warehouse/full-pipeline

# Run simulation with custom config
curl -X POST http://localhost:8000/warehouse/simulate \
  -H "Content-Type: application/json" \
  -d '{"num_robots": 12, "sim_duration_seconds": 7200}'

# Run analysis on latest simulation log
curl http://localhost:8000/warehouse/analysis

# Run analysis on a specific log file
curl "http://localhost:8000/warehouse/analysis?log_file=warehouse_logs_20260226_120000.json"

# Get optimization recommendations
curl http://localhost:8000/warehouse/optimization

# Get risk assessment
curl http://localhost:8000/warehouse/risk

# View default config
curl http://localhost:8000/warehouse/config

# Preview a modified config (non-persisting)
curl -X POST http://localhost:8000/warehouse/config \
  -H "Content-Type: application/json" \
  -d '{"num_robots": 15, "base_failure_rate": 0.02}'
```

### Interactive API Docs

When the API server is running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Example Output

### Simulation Summary (Phase 1)

```
================================================================
  SIMULATION SUMMARY
================================================================
  Duration            : 14,400 s  (4.0 hours)
  Total events        : 12,847
  Tasks generated     : 3,912
  Tasks completed     : 847
  Completion rate     : 21.6%
  Tasks still queued  : 3,065
  Robot failures      : 42
  Charging events     : 68
  Conveyor delays     : 89
  Zone overloads      : 8
```

### Intelligence Report (Phase 3)

```
━━━ PERFORMANCE SUMMARY ━━━
The warehouse processed 847 tasks over a 4-hour window with an average
throughput of 211.8 tasks/hour. Zone A3 exhibited the highest congestion
with an average queue depth of 12.4 items, indicating a capacity mismatch.
Fleet utilization averaged 67.3%, with robots 8, 9, and 10 experiencing
significantly higher downtime due to elevated failure rates.

━━━ BOTTLENECK DIAGNOSIS ━━━
Primary bottleneck identified in Zone A3 (arrival rate 4.0 tasks/min vs
fleet capacity of ~2.1 tasks/min in that zone). Queue growth rate of +0.8
items/hour confirms sustained congestion. Secondary bottleneck: robots
8-10 spending 18% of time in failed state, reducing effective fleet capacity.

━━━ OPTIMIZATION STRATEGIES ━━━
1. Redistribute 2 robots from Zone B1 to Zone A3 — estimated +15% throughput
2. Implement predictive maintenance on Robots 8, 9, 10 — reduce downtime by 40%
3. Adjust conveyor scheduling during peak hours — reduce delay cost by $45/shift
```

---

## Schemas & Data Models

### Log Schema (`schemas/log_schema.py`)

| Class | Purpose |
|-------|---------|
| `EventType` | Enum of all 10 simulation event types |
| `RobotStatus` | Enum: `idle`, `traveling`, `picking`, `charging`, `failed` |
| `Task` | Dataclass: `task_id`, `zone`, `arrival_timestamp`, `priority` |
| `LogEntry` | Dataclass: one row of the event log with all fields |
| `SimulationSummary` | Aggregate stats: totals, per-zone, per-robot |

### Analysis Schema (`schemas/analysis_schema.py`)

| Class | Purpose |
|-------|---------|
| `ThroughputReport` | Throughput metrics and trends |
| `QueueReport` | Queue health and congestion detection |
| `RobotMetrics` | Per-robot utilization breakdown |
| `UtilizationReport` | Fleet-wide utilization analysis |
| `RobotDowntime` | Per-robot downtime and reliability |
| `DowntimeReport` | Fleet-wide reliability analysis |
| `CostReport` | Dollar-value cost breakdown |
| `WarehouseAnalysisReport` | Top-level container for all analysis |

### Agent Schema (`schemas/agent_schema.py`)

| Class | Purpose |
|-------|---------|
| `AgentOutput` | Structured output: `agent_name`, `summary`, `recommendations`, `confidence`, `timestamp` |

---

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Deterministic core logic** | No LLM in the analysis path — all metrics are rule-based |
| **"Rules decide → LLM explains"** | Agents interpret pre-computed metrics, never compute them |
| **Reproducible simulations** | Seeded NumPy RNG (`numpy.random.Generator`) for identical runs |
| **Modular architecture** | Each layer is an independent package with its own schemas |
| **Clean separation of concerns** | Simulation, analysis, reasoning, and API are fully decoupled |
| **Production-style API** | FastAPI with middleware, CORS, structured error handling |
| **Graceful degradation** | LLM client retries and returns fallback on failure |

---

## Engineering Concepts Demonstrated

- **Queueing theory** — Poisson arrivals, priority min-heaps, queue growth rate analysis
- **Discrete-event simulation** — 1-second tick-based with state machines
- **Statistical analysis** — Linear regression for trend detection, MTBF calculation
- **Multi-agent LLM architecture** — BaseAgent pattern with prompt engineering
- **Cost-performance tradeoff modeling** — Dollar-value estimates for operational inefficiencies
- **RESTful API design** — Resource-oriented routes, proper HTTP methods, query parameters
- **State-machine design** — Robot entity with 5 states and deterministic transitions

---

## Tech Stack

| Technology | Role |
|------------|------|
| **Python 3.10+** | Core language |
| **FastAPI** | Async REST API framework |
| **Uvicorn** | ASGI server |
| **NumPy** | Numerical computation, Poisson/normal distributions, seeded RNG |
| **Anthropic Claude API** | LLM reasoning for Phase 3 agents |
| **python-dotenv** | Environment variable management |
| **requests** | HTTP client for LLM API calls |

---

## Repository Structure

```
Agentic_warehouse/
│
├── simulation/                    # Phase 1 — Discrete-event simulator
│   ├── warehouse.py               #   Main simulation loop (291 lines)
│   ├── robot.py                   #   Robot state machine (151 lines)
│   ├── zone.py                    #   Zone with priority queue (67 lines)
│   ├── task_generator.py          #   Poisson task arrivals (60 lines)
│   ├── dispatcher.py              #   Nearest-zone-first dispatch (102 lines)
│   └── failure_injector.py        #   Failures, delays, overloads (112 lines)
│
├── analysis/                      # Phase 2 — Deterministic analyzers
│   ├── throughput_analyzer.py     #   Throughput and trend detection
│   ├── queue_analyzer.py          #   Queue health and congestion
│   ├── utilization_analyzer.py    #   Robot utilization breakdown
│   ├── downtime_analyzer.py       #   MTBF and reliability scoring
│   └── cost_estimator.py          #   Dollar-value cost estimates
│
├── agents/                        # Phase 3 — LLM-powered agents
│   ├── base_agent.py              #   Abstract base with run/parse pipeline
│   ├── performance_summary_agent.py
│   ├── bottleneck_diagnosis_agent.py
│   ├── resource_allocation_agent.py
│   ├── risk_forecast_agent.py
│   └── optimization_strategy_agent.py
│
├── api/                           # Phase 4 — FastAPI application
│   ├── app.py                     #   App factory, middleware, health check
│   └── routes/
│       ├── simulate.py            #   POST /warehouse/simulate
│       ├── analysis.py            #   GET  /warehouse/analysis
│       ├── optimization.py        #   GET  /warehouse/optimization
│       ├── risk.py                #   GET  /warehouse/risk
│       ├── config.py              #   GET + POST /warehouse/config
│       └── pipeline.py            #   POST /warehouse/full-pipeline
│
├── tools/                         # Shared utilities
│   ├── log_loader.py              #   JSON log loading and filtering
│   └── llm_client.py              #   Anthropic Claude API wrapper
│
├── schemas/                       # Data models
│   ├── log_schema.py              #   EventType, RobotStatus, Task, LogEntry
│   ├── analysis_schema.py         #   All analysis report dataclasses
│   └── agent_schema.py            #   AgentOutput dataclass
│
├── config/                        # Configuration
│   ├── warehouse_config.py        #   WarehouseConfig dataclass (all parameters)
│   └── agent_config.py            #   Agent-specific configuration
│
├── data/                          # Generated simulation logs (JSON)
├── outputs/                       # Analysis reports & intelligence reports
│
├── main.py                        # Unified CLI entry point
├── main_phase1.py                 # Standalone Phase 1 runner
├── main_phase2.py                 # Standalone Phase 2 runner
├── main_phase3.py                 # Standalone Phase 3 runner
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template
└── README.md                      # This file
```

---

## Author

**Yassin Baher Youssef**
Robotics & Intelligent Systems Student
Constructor University Bremen
