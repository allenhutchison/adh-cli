# ADR 018: Initialization Agent and Environment Probing Workflow

**Status:** Proposed - Not Implemented
**Date:** 2025-10-05
**Deciders:** ADH CLI Core Team
**Tags:** architecture, agents, onboarding, documentation, developer-experience

> **Implementation Status (2025-10-14):** This ADR describes a proposed initialization workflow that has not yet been implemented. `AGENTS.md` exists and was manually created, but there is no `AGENTS.local.md`, no initialization agent, no `InitScreen` in the TUI, no `initialization_service.py`, and no `probe_registry.py`. The TUI-driven initialization workflow and environment probing system remain future work.

---

## Context

Adopting ADH CLI in a new workspace still requires manual discovery of project conventions and local environment capabilities. The orchestrator and multi-agent plans defined in ADR-010 and ADR-016 assume that agents already understand repository layout, available tools, and execution constraints. In practice, assistants frequently waste early interactions crawling directories, rediscovering configuration patterns, and probing the shell for installed tooling. This leads to:

- Repetitive cost and latency as each session relearns the workspace.
- Inconsistent `AGENTS.md` authoring quality, delaying tool awareness envisioned by ADR-014's tool spec registry.
- Limited ability to adapt prompts or tool availability based on host machine capabilities (e.g., GitHub CLI, ripgrep, `uv`, internet access).

Existing documentation expects humans to hand-curate contextual files before leveraging advanced flows, yet the TUI has no guided initialization to help users produce these artifacts. Additionally, agents lack a persistent, machine-scoped record describing installed utilities or network reachability, making it difficult to gracefully degrade when dependencies are missing.

Forces shaping this decision include:

- **Consistency:** We need a standard way to generate `AGENTS.md` so downstream agents can rely on its structure without ad hoc human edits.
- **Automation:** Initial discovery should be automated to reduce onboarding friction for each repository or machine.
- **Privacy & Safety:** Machine-specific diagnostics should stay local (not committed) while still being accessible to the orchestrator.
- **Extensibility:** Sub-agents and tools must be able to declare custom probes without modifying core logic, aligning with ADR-016's specialization goals and ADR-014's registry concepts.
- **User Experience:** The Textual TUI should provide a guided, repeatable "init" flow similar to other CLIs that scaffold config (e.g., `npm init`).

## Decision

Introduce a TUI-driven initialization workflow powered by a specialized Initialization Agent that documents project structure and machine capabilities via two complementary artifacts:

1. **`AGENTS.md` (project-scoped, committed):** Generated or refreshed by the agent to capture repository topology, key technologies, configuration files, testing commands, and relevant policies. The format extends ADR-010's markdown-driven agent context standards so orchestrator sessions start with comprehensive knowledge of the workspace.
2. **`AGENTS.local.md` (machine-scoped, ignored):** A sibling file excluded via `.gitignore` that stores environment probes—available CLIs (e.g., `gh`, `rg`, `uv`), virtualization containers, network reachability, and other capability checks requested by registered sub-agents or tools.

### Workflow Overview

```
┌──────────────┐      ┌────────────────────┐      ┌─────────────────────┐
│ User selects │────▶│ Initialization TUI │────▶│ Initialization Agent │
│  "Init" CTA  │      │  (wizard screens)  │      │  (specialist model) │
└──────────────┘      └────────────────────┘      └─────────────┬───────┘
                                                                 │
                        ┌────────────────────────────────────────┴────────────────────┐
                        │                                                            │
          ┌──────────────▼─────────────┐                              ┌───────────────▼──────────────┐
          │ Project Analysis Subtasks │                              │ Environment Probe Subtasks   │
          │ - Directory walk summary  │                              │ - Tool detection (gh, rg)    │
          │ - Stack identification    │                              │ - Python/uv/venv detection   │
          │ - Test & build commands   │                              │ - Network & auth checks      │
          │ - Policy/ADR references   │                              │ - OS / shell metadata        │
          └──────────────┬─────────────┘                              └───────────────┬──────────────┘
                           │                                                         │
          ┌───────────────▼──────────────┐                            ┌──────────────▼────────────────┐
          │ Write/Update `AGENTS.md`     │                            │ Write/Update `AGENTS.local.md`│
          └──────────────────────────────┘                            └───────────────────────────────┘
```

### Key Components

- **Initialization Agent Definition:** A new markdown-defined agent (`adh_cli/agents/initializer/agent.md`) leveraging ADR-010's loading pattern, optimized for summarizing repositories and synthesizing structured markdown sections.
- **Probe Registry:** Extend the tool registry from ADR-014 so sub-agents/tools can register capability probes with metadata (`name`, `command`, `success_criteria`, `redact_output`). Initialization Agent orchestrates these probes when building `AGENTS.local.md`.
- **TUI Wizard:** Add an `InitScreen` within the Textual app offering steps (overview → project scan confirmation → environment probes → preview → apply). This aligns with ADR-011's command palette integration for discoverability.
- **File Management Service:** Implement a service responsible for diffing existing `AGENTS.md`/`AGENTS.local.md`, prompting for confirmation, and ensuring `.gitignore` includes the local file.
- **Persistence Hooks:** When the orchestrator starts (per ADR-016), load both files: committed project context to inform planning, and local capabilities to adjust tool availability or degrade gracefully.

### Integration Points

- Reuse directory introspection utilities already used by tests/tool specs where possible.
- Ensure environment probes run via the existing shell tool with explicit safeguards (timeouts, redacted env vars).
- Provide extensibility hooks so future agents (e.g., security auditor) can append additional project/environment sections without modifying core workflow.

## Consequences

### Positive
- **Faster Onboarding:** Agents start with curated context, reducing redundant discovery loops.
- **Better Tooling Awareness:** Sub-agents can tailor behavior to confirmed capabilities, avoiding failing tool calls.
- **Documentation Quality:** Projects gain consistent, high-quality `AGENTS.md` aligned with ADR standards, improving collaboration.
- **Extensible Probing:** Tool authors can self-register probes, supporting evolving ecosystem requirements.

### Negative
- **Initial Complexity:** Building the wizard, agent, and registry extensions adds upfront work compared to ad hoc instructions.
- **Runtime Overhead:** Initialization scans may take time on large repositories; must communicate progress and allow cancellation.
- **Maintenance Load:** `AGENTS.md` may drift if projects restructure without rerunning init, requiring change-detection prompts.

### Risks
- **Outdated Information:** If users ignore rerun prompts, agents may rely on stale context. *Mitigation:* add heuristics (git diff triggers) to suggest refresh.
- **Privacy Concerns:** Environment probes might surface sensitive paths. *Mitigation:* strict redaction defaults, local-only storage, user confirmation before writing.
- **Tool Execution Failures:** Probes could hang or fail on unsupported shells. *Mitigation:* enforce timeouts, graceful error capture, mark uncertain capabilities explicitly.

### Neutral
- **File Footprint Increase:** Repository gains another committed markdown file and a local companion; storage impact minimal.
- **User Workflow Change:** Users must complete an initialization step but can skip or rerun as needed.

## Alternatives Considered

### Alternative 1: Manual Documentation Guidelines
Provide a checklist in docs for humans to populate `AGENTS.md` and manually note environment tools.
- **Rejected because** it preserves current inconsistency, burdens users, and doesn't support automated tool capability detection.

### Alternative 2: Lightweight CLI Script
Create a non-agent shell script that dumps directory trees and tool versions.
- **Rejected because** it ignores ADR-016's multi-agent architecture, can't leverage agent reasoning for summaries, and lacks extensibility for sub-agent-specific probes.

## Implementation Notes

- **Key Modules:**
  - `adh_cli/agents/initializer/agent.md` (new agent definition)
  - `adh_cli/services/initialization_service.py` (coordinates scans and writes)
  - `adh_cli/screens/init_screen.py` (Textual UI wizard)
  - `adh_cli/tools/probe_registry.py` (probe declarations and execution)
  - Updates to orchestrator startup to load new artifacts.
- **Configuration:** Add `.gitignore` entry for `AGENTS.local.md`; expose CLI flag `adh-cli init` mirroring TUI workflow for automation.
- **Migration Steps:**
  1. Implement agent definition and probe registry API.
  2. Build environment probe library for core tools (git, gh, rg, uv, python, network reachability).
  3. Develop TUI wizard with previews and confirmation dialogs.
  4. Integrate orchestrator bootstrapping to read generated files.
  5. Document workflow in `docs/TOOLS.md` and onboarding materials.
- **Testing Approach:**
  - Unit tests for probe execution/serialization.
  - Snapshot tests for generated markdown sections.
  - TUI integration tests (Textual `pilot`) verifying wizard flow.
  - End-to-end scenario: run init in sample repo and assert orchestrator loads context without extra probing.

## References

- Related ADRs: ADR-010 (Markdown-Driven Agent Definition), ADR-011 (Command Palette Integration), ADR-014 (Tool Spec Registry), ADR-016 (Multi-Agent Orchestration)
- GitHub CLI Manual: https://cli.github.com/manual/
- ripgrep User Guide: https://github.com/BurntSushi/ripgrep#user-guide
- UV Python Packaging Tool: https://github.com/astral-sh/uv
- Textual Application Wizard Patterns: https://textual.textualize.io/guide/patterns/

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-05 | Initial proposal | ADH CLI Core Team |
