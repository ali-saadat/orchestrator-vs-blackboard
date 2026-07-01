# The Harness — the control scaffold, and why orchestrator/blackboard/hybrid are three of them

> **TL;DR.** A multi-agent system is `agents + a harness`. The *agents* are model + role + tools; the *harness* is the deterministic program that owns the control loop, context assembly, tool dispatch, error handling, and the termination gate. **Orchestrator, blackboard, and hybrid are three harness *topologies*** — three answers to *how the harness schedules model calls and where shared state lives*. This repo holds the agents constant and swaps the harness.

# The Agent Harness

## What a harness is

An **agent harness** (also called a **scaffold**) is the deterministic program wrapped around an LLM that turns a next-token predictor into an agent. The model by itself "answers one prompt and stops"; the harness is *"every piece of code, configuration, and execution logic that isn't the model itself"* — system prompts, tool definitions and dispatch, middleware, memory, and orchestration logic [1][4]. LangChain's Vivek Trivedy compresses this into a slogan worth internalizing:

> **Agent = Model + Harness. If you're not the model, you're the harness.** [3]

Concretely, the harness **owns the control loop**: it *"calls the model, handles its tool calls, decides when to stop"* [4]. Anthropic frames the same primitive minimally — agents are *"typically just LLMs using tools based on environmental feedback in a loop,"* requiring *"ground truth from the environment at each step (such as tool call results or code execution) to assess progress"* [5].

Anthropic separates two phases that are easy to conflate:

- **Scaffolding** is how the agent is assembled *before* the first prompt — system prompt, tool registry, initializer setup.
- **The harness** is *"everything that happens after: dispatching tools, compacting context, enforcing safety invariants, and persisting state across turns"* [1].

In their long-running-agents work, the Claude Agent SDK is described as *"a powerful, general-purpose agent harness"* that provides the core loop, sub-agent delegation, permissions, and context management such as compaction [1].

## Why the harness — not the model — drives capability

Most *observed* agent capability lives in the harness, not the weights. MongoDB's framing: the LLM *"sits at the center of a production agent system... important, but tiny relative to the infrastructure that makes it work"* — the LLM is *"the smallest part"* [2]. Addy Osmani's rule of thumb:

> **A decent model with a great harness beats a great model with a bad harness.** [7]

The evidence is benchmark-based, holding the **model fixed** and changing only the harness:

- **Terminal-Bench 2.0** — LangChain moved from the bottom to the top-5 (52.8% → 66.5%) by changing only the harness [2][7].
- **CORE-Bench** (Princeton) — the *same* model scored **42%** under one scaffold and **78%** under another [2].
- **Vercel** — cut tools by 80%, lifting task success from **80% → 100%** while halving tokens and dropping latency from 724s to 141s [2].
- **SWE-agent** — a purpose-built **Agent-Computer Interface (ACI)**, i.e. LM-centric commands and feedback formats for browsing, editing, and running code, was *the* difference-maker on SWE-bench, "far exceeding" non-interactive baselines [8][9].
- **Code execution with MCP** (Anthropic) — having the model *write code that calls tools* instead of emitting direct tool calls cut context by up to **98.7%** while scaling to far more tools [10].

The takeaway for agentic engineers: invest your marginal effort in harness design.

## Harness anatomy

The harness is the deterministic host that owns, per turn/step:

1. **Control loop** — call model → parse output → execute tool calls → feed results back → repeat [4][5].
2. **Context / memory assembly** — build each prompt from system prompt, history, retrieved docs, scratchpads/task lists, and long-term memory; compact/summarize when the window fills [1][2].
3. **Tool dispatch** — expose capabilities (bash, code execution, APIs, MCP), receive structured tool calls, route to the right function [2][4].
4. **Error handling / retries** — timeouts, retries, budget caps, max-step limits, destructive-action guards, verification loops [2][7].
5. **Termination gate** — decide when the agent is done, blocked, or must be stopped [4].
6. **State/persistence, security/governance, observability, evals** — the production concerns that surround the loop [2].

## Multi-agent systems are just harnesses in different topologies

A multi-agent system decomposes into **agents** (each = model + role + tools) plus a **harness** — the control scaffold that schedules model calls and holds shared state. The load-bearing insight is that the well-known coordination patterns are **harness topologies**: different answers to *how the harness sequences model calls and where shared state lives*.

### Orchestrator topology

Anthropic's **orchestrator-workers** pattern: *"a central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results,"* with subtasks *"determined by the orchestrator based on the specific input"* rather than predefined [5]. Here the harness operates at a higher altitude — an orchestrator *"manages agents as units, each running their own harness"* [4]. State flows *through* the orchestrator (assignments down, results up); the schedule is **explicit and hierarchical**.

### Blackboard topology

The classic **blackboard architecture** (Hearsay-II, 1970s speech recognition) has three parts: **knowledge sources** (specialist agents), the **blackboard** (shared memory all KSs read/write), and a **control shell / control unit** (the scheduler) [11]. The control shell *"inspects the blackboard, finds all knowledge sources whose preconditions are met, selects the highest-priority one, and runs it,"* triggering on blackboard events [11]. That control shell **is a harness** — the same anatomy (loop, dispatch, termination) recognized decades before LLMs. State is **global** (the blackboard); the schedule is **opportunistic / data-driven** (whoever's preconditions fire).

### Hybrid topology

Real systems mix the two: an orchestrator holds hierarchical control while a shared blackboard/event-bus carries cross-cutting state, or a blackboard's control shell delegates a matched knowledge source to an orchestrated sub-team. The point stands — whether you call it a control loop, an orchestrator, or a control shell, you are describing the **same harness responsibilities** (loop, context, dispatch, error handling, termination), differing only in **scheduling discipline** and **where shared state lives**.

*(The single-agent/multi-agent equivalence and the "topologies" framing are synthesis; each component definition above is sourced. See references.)*

## Harness anatomy
| Harness responsibility | What it does |
|---|---|
| **Control loop** | Drives the agentic cycle: call model → parse output → execute tool calls → feed results back → repeat until the termination gate fires [4][5]. |
| **Context / memory assembly** | Builds each prompt from system prompt, running history, retrieved documents, scratchpads/task lists, and long-term memory; compacts or summarizes when the window fills [1][2]. |
| **Tool dispatch** | Exposes capabilities (bash, code execution, APIs, MCP servers), receives structured tool calls from the model, and routes each to the correct function; may have the model emit code that calls tools to cut context [2][4][10]. |
| **Error handling / retries** | Enforces timeouts, retries, token/step budget caps, destructive-action guards, and verification loops so partial failures don't derail the run [2][7]. |
| **Termination gate** | Decides when the agent is done, blocked, or must be force-stopped (goal reached, no progress, budget exhausted) [4]. |
| **State / persistence** | Persists conversation, task, and memory state across turns and process restarts so long-running agents survive interruptions [1][2]. |
| **Security / governance** | Enforces permission prompts, sandboxing, and safety invariants before dispatching sensitive or destructive actions [1][2]. |
| **Observability / evals** | Emits spans, token/cost usage, and traces; supports offline evaluation of harness changes against fixed benchmarks [2]. |

## The control models, per harness responsibility
| Harness responsibility | Orchestrator | Blackboard | Hybrid |
|---|---|---|---|
| **Control loop** | Central planner LLM decomposes the task, delegates to workers, then synthesizes their results [5]. | Control shell fires eligible knowledge sources on blackboard events until a goal state is reached [11]. | Orchestrator drives high-level phases; a blackboard/event-bus fans work out to reactive KSs within a phase. |
| **Scheduling** | Explicit, hierarchical, top-down — the planner chooses who runs next [4][5]. | Opportunistic, data-driven — whichever KS's preconditions match, highest-priority first [11]. | Hierarchical envelope with data-driven scheduling inside; orchestrator arbitrates, blackboard triggers. |
| **Shared state** | Passed *through* the orchestrator: assignments down, results up; no global store required [5]. | Global blackboard read/written by all knowledge sources [11]. | Orchestrator-owned task state plus a shared blackboard for cross-cutting facts. |
| **Tool dispatch** | Each worker runs its own harness with its own tools; orchestrator manages agents as units [4]. | Each KS acts on blackboard contents using its own tools/actions [11]. | Workers dispatch their own tools; results and artifacts land on the shared blackboard. |
| **Termination** | Orchestrator judges the goal met and stops synthesizing [4][5]. | Control shell halts when the goal state is reached or no KS's preconditions fire [11]. | Orchestrator's stop-gate is authoritative; blackboard quiescence (no eligible KS) is a secondary signal. |
| **Best fit** | Well-decomposable tasks with a clear plan and a synthesis step. | Emergent/uncertain problems where partial results unlock further specialists. | Large systems needing a controllable spine plus reactive specialization. |

## How this repo makes the harness *real* (and visible)

The thesis above is not just prose here — it is the code's structure.

**One harness, three schedulers.** [`core/harness.py`](../src/ovb/core/harness.py) is
the `Harness` base class. It implements the harness responsibilities *once*:

- **control-loop step** — `invoke(source, trigger)`: assemble the view, call the
  model, apply the validated patch through the ownership reducer, record every
  token / write / cost.
- **termination gate** — `gate_passed()`: a deterministic check; the LLM never
  renders the verdict.

The three engines in [`engines/`](../src/ovb/engines/) subclass `Harness` and
implement **only `run()`** — i.e. only the *scheduling discipline*:

| Harness responsibility | Orchestrator (`orchestrator.py`) | Blackboard (`blackboard.py`) | Hybrid (`hybrid.py`) |
|---|---|---|---|
| **control loop** | fixed-order supervisor sweeps to a no-op fixpoint | event loop: a write re-triggers subscribed agents | bounded blackboard on the coupled core, then a linear tail |
| **scheduling** | top-down, hierarchical, order fixed | opportunistic, data-driven (subscription match) | coupled subset reactive, independent tail linear |
| **shared state** | isolated views handed out by the hub | one shared `PlanState` all agents read/write | one shared state; supervisor decomposes access |
| **termination** | a whole confirming no-op sweep (the "hub tax") | deterministic gate, checked after each write | gate after the core settles, then finish the tail |
| **cost signature** | ≈ roster × rounds (+ confirm sweep) | ≈ number of ripples | core ripples + |tail| |

Because `invoke` and the gate are shared, the ONLY thing that differs between the
runs is the scheduler — which is exactly why the comparison is fair and why the
numbers (orchestrator 12 calls, blackboard 7, hybrid 5, all reaching the identical
plan) are attributable to the control model and nothing else.

**See it move.** `ovb bench` writes `output/report.html` — press play to watch each
harness's control loop converge, with token/cost/write meters computed live from the
same WORM event stream. The event `kind`s (`agent_activated`, `gen_ai.client.call.*`,
`state_write`, `agent_retriggered`, `gate_checked`) are the harness's own vocabulary.

**Security is a harness property.** A subverted agent cannot write outside its owned
fields — the reducer (`core/state.py`) raises `OwnershipError`. On a shared board a
poisoned write would otherwise re-trigger many agents (injection blast-radius); the
harness's write-seam is where you contain it.


## Appendix A — Anthropic streaming usage (so token accounting is correct)
## Anthropic streaming usage semantics (Messages API, current 2025–2026)

**Source:** `platform.claude.com/docs/en/build-with-claude/streaming` [1].

**Event flow:** `message_start` (a `Message` with empty `content`) → content blocks (`content_block_start` / `_delta` / `_stop`) → one or more `message_delta` events → a final `message_stop` [1].

### 1. `message_start` — input-side usage is final here

`message.usage` reports the **final** `input_tokens` and, when caching is active, `cache_creation_input_tokens` and `cache_read_input_tokens`. The `output_tokens` field here is only a **partial placeholder** (typically 1–3, tokens generated so far), **not** the final output count.

Verified from the docs' SSE examples:
```json
// simple stream, at message_start:
"usage": {"input_tokens": 25, "output_tokens": 1}

// web-search example, at message_start:
"usage": {"input_tokens": 2679, "cache_creation_input_tokens": 0,
          "cache_read_input_tokens": 0, "output_tokens": 3}
```
So take input/cache buckets from `message_start`; ignore its `output_tokens`.

### 2. `message_delta` — output usage is CUMULATIVE, do NOT sum

The docs state explicitly in a warning box:

> The token counts shown in the `usage` field of the `message_delta` event are **cumulative** [1].

```json
// a message_delta:
"usage": {"output_tokens": 15}

// web-search example, final message_delta:
"usage": {"input_tokens": 10682, "cache_creation_input_tokens": 0,
          "cache_read_input_tokens": 0, "output_tokens": 510}
```

Because the value is cumulative, take the **last** `message_delta`'s `output_tokens` as the final output count — **do not sum the deltas**. With server tools (e.g. web search), `input_tokens` in the final `message_delta` can grow beyond the `message_start` value as fetched results count as input; again, **take the final value, don't sum** [1].

### 3. `message_stop` — no usage payload

```json
data: {"type": "message_stop"}
```
It only signals stream completion; it carries no usage of its own [1].

### 4. Authoritative final usage

Combine the **input/cache buckets from `message_start`** with the **cumulative `output_tokens` from the last `message_delta`**. SDK stream accumulators (Python/TS `.stream()`) fold these into one final `Message.usage` for you.

### 5. Cache usage fields (`cache_control` ephemeral)

- `input_tokens` — uncached tokens after the last cache breakpoint.
- `cache_creation_input_tokens` — tokens written to a new cache entry.
- `cache_read_input_tokens` — tokens served from cache.
- With mixed TTLs, a `cache_creation` object splits writes into `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens` [2].
- **Total input = `cache_read_input_tokens + cache_creation_input_tokens + input_tokens`** [2].
- `cache_control` type is `"ephemeral"`; default TTL is 5 minutes; 1-hour TTL is `{"type": "ephemeral", "ttl": "1h"}` [2].

### 6. Cost computation

```
cost =   input_tokens              * base_input/1e6
       + cache_creation_5m_tokens  * base_input*1.25/1e6
       + cache_creation_1h_tokens  * base_input*2.0/1e6
       + cache_read_input_tokens   * base_input*0.1/1e6
       + output_tokens             * base_output/1e6
```
Use the **final cumulative** `output_tokens` (last `message_delta`); split cache-creation into 5m vs 1h via the `cache_creation` object when both TTLs are present [2][3].

## Appendix B — Pricing (dated)
## Claude pricing — USD per million tokens (MTok)

**Source:** official Anthropic/Claude pricing page (`docs.claude.com` → `platform.claude.com/docs/en/about-claude/pricing`), **observed 2026-07-01** [3].

Cache columns follow the multipliers **5-minute write = 1.25× base input**, **1-hour write = 2× base input**, **cache read/hit = 0.1× base input** [2][3].

| Model | Base input | 5m cache write | 1h cache write | Cache read | Output |
|---|---|---|---|---|---|
| **Claude Opus 4.8** (latest Opus) | $5.00 | $6.25 | $10.00 | $0.50 | $25.00 |
| Claude Opus 4.5–4.7 | $5.00 | $6.25 | $10.00 | $0.50 | $25.00 |
| **Claude Sonnet 5** (intro, thru 2026-08-31) | $2.00 | $2.50 | $4.00 | $0.20 | $10.00 |
| Claude Sonnet 5 (from 2026-09-01) | $3.00 | $3.75 | $6.00 | $0.30 | $15.00 |
| Claude Sonnet 4.5 / 4.6 | $3.00 | $3.75 | $6.00 | $0.30 | $15.00 |
| **Claude Haiku 4.5** (latest Haiku) | $1.00 | $1.25 | $2.00 | $0.10 | $5.00 |

**Notes**
- Opus 4.1 and earlier are deprecated/retired at older $15/$75 rates.
- **Sonnet 5** carries an introductory **$2 in / $10 out** rate through **2026-08-31**, reverting to **$3 / $15** on **2026-09-01** [3].
- **Batch API** = 50% off both input and output (e.g. Opus 4.8 = $2.50 in / $12.50 out). Batch (×0.5) and data-residency (×1.1, `inference_geo="us"` on Opus 4.6+/Sonnet 4.6+) multipliers **stack** on the relevant buckets [3].
- Opus 4.7+ and Sonnet 5 use a newer tokenizer that emits ~30% more tokens for the same text — factor this into cost estimates [3].

## `pricing.py` (ready to paste)

```python
# Anthropic per-MTok pricing. Source: platform.claude.com/docs/en/about-claude/pricing
# Observed 2026-07-01. Prices in USD per 1,000,000 tokens.
PRICE_OBSERVED_DATE = "2026-07-01"

# Cache multipliers relative to base input price.
CACHE_WRITE_5M_MULT = 1.25
CACHE_WRITE_1H_MULT = 2.0
CACHE_READ_MULT = 0.1

# Optional stacking multipliers (apply to relevant buckets).
BATCH_MULT = 0.5            # Batch API, both directions
DATA_RESIDENCY_US_MULT = 1.1  # inference_geo="us" on Opus 4.6+/Sonnet 4.6+

# {model: (base_input_per_mtok, output_per_mtok)}
PRICING = {
    "claude-opus-4-8":   (5.0, 25.0),   # latest Opus
    "claude-opus-4-7":   (5.0, 25.0),
    "claude-opus-4-6":   (5.0, 25.0),
    "claude-opus-4-5":   (5.0, 25.0),
    "claude-sonnet-5":   (2.0, 10.0),   # intro rate thru 2026-08-31; 3.0/15.0 from 2026-09-01
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5":  (1.0, 5.0),    # latest Haiku
}


def cost_usd(model, *, input_tokens=0, cache_creation_5m_tokens=0,
             cache_creation_1h_tokens=0, cache_read_input_tokens=0,
             output_tokens=0, batch=False, data_residency_us=False):
    base_in, base_out = PRICING[model]
    mult = 1.0
    if batch:
        mult *= BATCH_MULT
    if data_residency_us:
        mult *= DATA_RESIDENCY_US_MULT
    cost = (
        input_tokens              * base_in                     +
        cache_creation_5m_tokens  * base_in * CACHE_WRITE_5M_MULT +
        cache_creation_1h_tokens  * base_in * CACHE_WRITE_1H_MULT +
        cache_read_input_tokens   * base_in * CACHE_READ_MULT     +
        output_tokens             * base_out
    ) / 1_000_000
    return cost * mult
```

**Worked example (from the docs):** 40,000 cache-read tokens on Opus 4.8 = 40,000 × $5 × 0.1 / 1e6 = **$0.02** [3].

## Appendix C — OpenTelemetry GenAI alignment (our event field names)
## OpenTelemetry GenAI semantic conventions (align our event contract)

**Status & source of truth:** every `gen_ai.*` group is at stability level **Development** (formerly "Experimental") through mid-2026 — expect breaking changes, do not treat names as frozen. In 2026 the GenAI area **moved out of `open-telemetry/semantic-conventions` into the dedicated repo `open-telemetry/semantic-conventions-genai`**; the old `opentelemetry.io/docs/specs/semconv/gen-ai/*` pages are now redirect stubs. Cite the new repo [1][6][7].

### Inference span (chat / generate_content / text_completion / embeddings)
- **Span kind:** `CLIENT` (or `INTERNAL` when the model runs in-process).
- **Span name:** `{gen_ai.operation.name} {gen_ai.request.model}`, e.g. `chat claude-opus-4-8`.

| Attribute | Level | Notes |
|---|---|---|
| `gen_ai.operation.name` | **Required** | `chat`, `generate_content`, `text_completion`, `embeddings`, `execute_tool`, `create_agent`, `invoke_agent`, `invoke_workflow`, `plan`, `retrieval`, memory ops |
| `gen_ai.provider.name` | **Required** | `anthropic`, `openai`, `aws.bedrock`, `gcp.gemini` — discriminator that **replaced** `gen_ai.system` |
| `gen_ai.request.model` | Cond. Req. | requested model id |
| `gen_ai.conversation.id` | Cond. Req. | session/thread id |
| `gen_ai.output.type` | Cond. Req. | `text` \| `json` \| `image` \| `speech` |
| `gen_ai.request.temperature` / `top_p` / `max_tokens` / `stop_sequences` | Recommended | |
| `gen_ai.response.id` / `gen_ai.response.model` | Recommended | |
| `gen_ai.response.finish_reasons` | Recommended | **string array**, e.g. `["stop"]`, `["tool_calls"]` |
| `error.type`, `server.address`, `server.port` | as applicable | |

### Token-usage attributes (Recommended, int)
- `gen_ai.usage.input_tokens` — **must include all input token types, including cached tokens**.
- `gen_ai.usage.output_tokens`
- `gen_ai.usage.cache_read.input_tokens`
- `gen_ai.usage.cache_creation.input_tokens`
- `gen_ai.usage.reasoning.output_tokens`

### Content (Opt-In, off by default)
`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions` — structured JSON (role + parts). MAY be a JSON string on spans, MUST be structured on log-events. This **replaced** the now-**deprecated** `gen_ai.prompt` / `gen_ai.completion` (removed in v1.38.0) [9].

### Agent spans
- `invoke_agent {gen_ai.agent.name}` / `create_agent {gen_ai.agent.name}`; kind `CLIENT` or `INTERNAL` (same-process).
- Attributes: `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.agent.id`, `gen_ai.agent.name`, `gen_ai.agent.description`.

### Tool spans
- `execute_tool {gen_ai.tool.name}`; kind `INTERNAL`.
- `gen_ai.operation.name = execute_tool` (Req.), `gen_ai.tool.name` (Req.).
- `gen_ai.tool.call.id`, `gen_ai.tool.type` (`function` \| `extension` \| `datastore`), `gen_ai.tool.description` (Rec.); `gen_ai.tool.call.arguments` / `gen_ai.tool.call.result` (Opt-In).

### Metrics (both Development)
- `gen_ai.client.token.usage` — **Histogram**, unit `{token}`, **split by `gen_ai.token.type`** (`input`/`output`); dimensioned by `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`.
- `gen_ai.client.operation.duration` — Histogram, unit `s`.

### Cost
The spec defines **no** standard cost metric and **no** stable `gen_ai.cost.*` attribute. Cost is a **derived value** (token counts × pricing) computed downstream; some vendors emit non-standard `gen_ai.usage.cost_usd`. **Keep `cost` as a computed field with no OTel target** [6][10].

### Rename map for our event contract (mechanical OTLP export)
| Our field | OTel target |
|---|---|
| `operation_name` | `gen_ai.operation.name` |
| `provider` | `gen_ai.provider.name` *(Required — store as first-class discriminator)* |
| `model` | `gen_ai.request.model` |
| `response_model` | `gen_ai.response.model` |
| `input_tokens` | `gen_ai.usage.input_tokens` |
| `output_tokens` | `gen_ai.usage.output_tokens` |
| `cached_tokens` | `gen_ai.usage.cache_read.input_tokens` |
| `cache_write_tokens` | `gen_ai.usage.cache_creation.input_tokens` |
| `reasoning_tokens` | `gen_ai.usage.reasoning.output_tokens` |
| `finish_reason(s)` | `gen_ai.response.finish_reasons` *(array)* |
| `session_id` | `gen_ai.conversation.id` |
| `agent_id` / `agent_name` | `gen_ai.agent.id` / `gen_ai.agent.name` |
| `tool_name` | `gen_ai.tool.name` |
| `tool_call_id` | `gen_ai.tool.call.id` |
| raw prompt/response | `gen_ai.input.messages` / `gen_ai.output.messages` (role/parts) |
| `cost` | *(none — derived)* |

## References
## References

1. Anthropic — *Effective harnesses for long-running agents.* https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
2. MongoDB — *The agent harness: why the LLM is the smallest part of your agent system.* https://www.mongodb.com/company/blog/technical/agent-harness-why-llm-is-smallest-part-of-your-agent-system
3. Anthropic / Claude — *Pricing* (observed 2026-07-01; `docs.claude.com` → `platform.claude.com/docs/en/about-claude/pricing`). https://platform.claude.com/docs/en/about-claude/pricing
4. Hugging Face — *Agent glossary* (control loop; "if you're not the model, you're the harness"; orchestrator manages agents as units). https://huggingface.co/blog/agent-glossary
5. Anthropic — *Building effective agents* (agents as LLMs using tools in a loop; orchestrator-workers pattern). https://www.anthropic.com/research/building-effective-agents
6. MindStudio — *What is harness engineering?* https://www.mindstudio.ai/blog/what-is-harness-engineering
7. Addy Osmani — *Agent harness engineering* ("a decent model with a great harness beats a great model with a bad harness"). https://addyosmani.com/blog/agent-harness-engineering/
8. SWE-agent — *arXiv:2405.15793* (Agent-Computer Interface / ACI). https://arxiv.org/abs/2405.15793
9. SWE-agent — *Background: the Agent-Computer Interface.* https://swe-agent.com/latest/background/
10. Anthropic — *Code execution with MCP* (context reduction up to 98.7%). https://www.anthropic.com/engineering/code-execution-with-mcp
11. EmergentMind — *Blackboard / event-bus architecture* (Hearsay-II: knowledge sources, blackboard, control shell). https://www.emergentmind.com/topics/blackboard-event-bus
12. OpenTelemetry — *semantic-conventions-genai* (2026 dedicated GenAI repo; source of truth). https://github.com/open-telemetry/semantic-conventions-genai
13. OpenTelemetry — *GenAI spans* (span names, requirement levels, token-usage attributes). https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md
14. OpenTelemetry — *GenAI agent spans* (invoke_agent / create_agent / execute_tool). https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-agent-spans.md
15. OpenTelemetry — *GenAI observability blog* (2026; Development stability, adoption, no standard cost metric). https://opentelemetry.io/blog/2026/genai-observability/
16. Anthropic — *Streaming* (message_start / message_delta cumulative usage / message_stop). https://platform.claude.com/docs/en/build-with-claude/streaming
17. Anthropic — *Prompt caching* (`cache_control` ephemeral, TTLs, cache usage fields, multipliers). https://platform.claude.com/docs/en/build-with-claude/prompt-caching