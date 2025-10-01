# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for ADH CLI.

## What are ADRs?

Architecture Decision Records document important architectural decisions made during the development of this project. They help:

- **Preserve context**: Why decisions were made, not just what was decided
- **Onboard new contributors**: Understand the reasoning behind the architecture
- **Prevent revisiting**: Document alternatives considered and why they were rejected
- **Track evolution**: See how the architecture has changed over time

## Format

Each ADR follows a consistent template (see `000-template.md`):

1. **Title**: Short, descriptive title
2. **Status**: Proposed, Accepted, Deprecated, or Superseded
3. **Context**: Problem being solved, forces at play
4. **Decision**: What was decided and how it works
5. **Consequences**: Positive, negative, risks, and neutral impacts
6. **Alternatives Considered**: Other options and why they were rejected
7. **Implementation Notes**: Practical details for implementation
8. **References**: Links to code, docs, issues, etc.

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [000](000-template.md) | ADR Template | - | - |
| [001](001-policy-aware-architecture.md) | Policy-Aware Architecture for AI Agent Safety | Accepted | 2025-09-30 |
| [002](002-tool-execution-ui-tracking.md) | Tool Execution UI Tracking System | Accepted | 2025-09-30 |
| [003](003-google-adk-integration.md) | Google ADK Integration for Tool Orchestration | Accepted | 2025-09-30 |
| [004](004-secure-api-key-storage.md) | Secure API Key Storage with System Keychain | Proposed | 2025-09-30 |
| [005](005-unified-error-handling.md) | Unified Error Handling and Response Processing | Proposed | 2025-09-30 |
| [006](006-policy-configuration-ui.md) | Policy Configuration UI | Proposed | 2025-09-30 |
| [007](007-comprehensive-integration-tests.md) | Comprehensive Integration Testing | Proposed | 2025-09-30 |
| [008](008-centralized-model-configuration.md) | Centralized Model Configuration | Proposed | 2025-09-30 |

## When to Create an ADR

Create an ADR when making decisions about:

- **Architecture**: Core system design, layering, separation of concerns
- **Dependencies**: Adding new libraries or frameworks
- **Interfaces**: Public APIs, tool protocols, plugin systems
- **Data Models**: Core data structures that affect multiple components
- **Security**: Authentication, authorization, data protection
- **Performance**: Tradeoffs that impact system performance
- **User Experience**: Major UX patterns or workflows

## When NOT to Create an ADR

Don't create ADRs for:

- **Implementation details**: How a specific function works
- **Bug fixes**: Unless they require architectural changes
- **Refactoring**: Unless changing the architecture
- **Configuration**: Simple config changes
- **Trivial decisions**: Choices with no long-term impact

## How to Create an ADR

1. **Copy the template**:
   ```bash
   cp docs/adr/000-template.md docs/adr/XXX-your-title.md
   ```

2. **Number sequentially**: Use the next available number (004, 005, etc.)

3. **Fill in the sections**:
   - Start with Context (the problem)
   - Describe the Decision (the solution)
   - List Consequences (impacts)
   - Document Alternatives (what else was considered)

4. **Get review**: Have teammates review before marking as Accepted

5. **Update index**: Add entry to the table above

6. **Commit**: Include ADR in the same PR as the implementation

## ADR Lifecycle

### Proposed
- Under discussion
- Not yet implemented
- Subject to change

### Accepted
- Agreed upon by team
- Being implemented or already implemented
- Should not be changed without good reason

### Deprecated
- No longer recommended
- Better alternative exists
- Still in codebase for backward compatibility

### Superseded
- Replaced by another ADR
- No longer in use
- Link to superseding ADR

## Revising ADRs

Once Accepted, ADRs should generally not be changed. Instead:

1. **For corrections**: Add to Revision History section
2. **For major changes**: Create new ADR that supersedes the old one
3. **For deprecation**: Update status and add reason

## Examples from This Project

### Good ADR Examples

**ADR-001: Policy-Aware Architecture**
- Clear problem statement (AI safety)
- Detailed decision with diagrams
- Comprehensive alternatives section
- Honest about tradeoffs

**ADR-002: Tool Execution UI Tracking**
- Good context on user pain points
- Clear architectural layers
- Event-driven design explained
- Migration notes included

**ADR-003: Google ADK Integration**
- Compares manual vs. ADK approach
- Documents critical bug fixes
- Performance benchmarks
- Dual-mode strategy explained

### What Makes a Good ADR?

**Clear Context:**
```markdown
❌ "We needed a better UI"
✅ "Users couldn't see tool execution status, parameters were hidden,
    confirmations interrupted workflow, and history was lost"
```

**Specific Decision:**
```markdown
❌ "Use a manager pattern"
✅ "Implement three-layer architecture: Data (ToolExecutionInfo),
    Coordination (ToolExecutionManager), UI (ToolExecutionWidget)"
```

**Honest Tradeoffs:**
```markdown
❌ "This is the best approach"
✅ "This adds complexity (3 layers vs 1) but provides better separation
    of concerns and testability. Memory usage increases ~1-2KB per execution."
```

**Documented Alternatives:**
```markdown
❌ "We considered other options"
✅ "Alternative 1: Single class combining all concerns
    - Pros: Simpler, fewer files
    - Cons: Tight coupling, hard to test
    - Rejected because: Would make testing and maintenance harder long-term"
```

## References

- [ADR GitHub Organization](https://adr.github.io/)
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR Tools](https://github.com/npryce/adr-tools)

## Questions?

If you're unsure whether something needs an ADR:
- Ask yourself: "Will this decision affect future contributors?"
- If yes, write an ADR
- If no, just document in code comments

When in doubt, write it down. It's easier to have too much documentation than too little.
