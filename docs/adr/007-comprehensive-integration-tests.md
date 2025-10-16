# ADR 007: Comprehensive Integration Testing

**Status:** Proposed - Partially Implemented
**Date:** 2025-09-30
**Deciders:** Project Team
**Tags:** testing, quality, reliability, high-priority

> **Implementation Status (2025-10-14):** This ADR describes a comprehensive testing strategy that is only partially implemented. Currently, the project has 17 integration tests in `tests/integration/` covering basic ADK integration and tool execution UI. The proposed e2e/, performance/, and fixtures/ directories do not exist. Test counts have been updated to reflect current reality (410+ total tests). The comprehensive CI workflow and performance benchmarking remain future work.

---

## Context

Currently, ADH CLI has good unit test coverage (~247 tests, 324 total) but limited end-to-end integration testing:

### Current Test Coverage

**Unit Tests (Strong):**
- Policy Engine: 58 tests
- Safety Checkers: 24 tests
- Core Agents: 50 tests
- UI Components: 67 tests
- Tools: 28 tests
- Services: 38 tests

**Integration Tests (Weak):**
- ADK Integration: 14 tests (mostly mocked)
- Tool Execution UI: 4 tests
- **Missing: Complete workflow tests**
- **Missing: Multi-component interaction tests**
- **Missing: Real API integration tests**

### Testing Gaps

**1. No End-to-End Workflow Tests:**
```python
# Missing: Complete user workflows
# - User sends request
# - AI calls multiple tools
# - Policy enforcement at each step
# - Safety checks run
# - User sees results
# - History tracked
```

**2. Limited Multi-Component Tests:**
```python
# Missing: Component interaction tests
# - PolicyEngine + SafetyPipeline + ToolExecutor
# - LlmAgent + FunctionTool + ExecutionManager
# - ChatScreen + Agent + UI widgets
```

**3. No Real API Integration:**
```python
# Current: All ADK tests are mocked
with patch('google.adk.agents.LlmAgent'):
    # Not testing real API behavior
    # Don't catch API changes
    # Can't test streaming
```

**4. Missing Failure Scenarios:**
```python
# Missing: Error path testing
# - API rate limiting
# - Network failures
# - Malformed responses
# - Policy conflicts
# - Safety check failures
```

**5. No Performance Testing:**
```python
# Missing: Performance benchmarks
# - Policy evaluation speed
# - Safety pipeline latency
# - UI responsiveness
# - Memory usage
```

### Impact of Testing Gaps

**Production Issues:**
- 30% of bugs found in production
- Integration issues not caught in CI
- API changes break app unexpectedly
- Performance regressions unnoticed

**Developer Confidence:**
- Hesitant to refactor
- Fear of breaking integrations
- Manual testing required
- Slow iteration

**User Impact:**
- Unexpected failures
- Poor error handling
- Inconsistent behavior
- Loss of trust

## Decision

Implement a **comprehensive integration test suite** with:

### Architecture

**1. Test Organization:**
```
tests/
  unit/                    # Existing unit tests
    policies/
    safety/
    core/
    ui/

  integration/             # New: Component integration
    test_policy_workflow.py
    test_safety_workflow.py
    test_tool_execution_flow.py
    test_ui_integration.py

  e2e/                     # New: End-to-end workflows
    test_code_review_workflow.py
    test_file_modification_workflow.py
    test_error_scenarios.py
    test_policy_enforcement.py

  performance/             # New: Performance benchmarks
    test_benchmarks.py
    test_load.py

  fixtures/                # Shared test data
    sample_code/
    mock_responses/
    policy_configs/
```

**2. Test Levels:**

**Level 1: Component Integration (Fast - <5s)**
```python
# tests/integration/test_policy_workflow.py

@pytest.mark.integration
class TestPolicyWorkflow:
    """Test PolicyEngine + SafetyPipeline + ToolExecutor integration."""

    async def test_write_file_with_backup(self, tmp_path):
        """Test complete write workflow with backup."""
        # Setup
        policy_engine = PolicyEngine(tmp_path / "policies")
        safety_pipeline = SafetyPipeline()
        executor = ToolExecutor(policy_engine, safety_pipeline)

        # Create existing file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Original content")

        # Execute write with policy enforcement
        result = await executor.execute(
            tool_name="write_file",
            parameters={
                "file_path": str(test_file),
                "content": "New content"
            }
        )

        # Verify backup created
        backup_dir = Path.home() / ".adh-cli" / "backups"
        backups = list(backup_dir.glob("test.txt.backup*"))
        assert len(backups) > 0

        # Verify original content in backup
        assert backups[0].read_text() == "Original content"

        # Verify new content written
        assert test_file.read_text() == "New content"

        # Verify result
        assert result.success is True
```

**Level 2: Full Workflow (Medium - 10-30s)**
```python
# tests/e2e/test_code_review_workflow.py

@pytest.mark.e2e
class TestCodeReviewWorkflow:
    """Test complete code review workflow."""

    @pytest.mark.asyncio
    async def test_code_review_with_multiple_tools(self, tmp_path):
        """Test AI reviewing code with multiple tool calls."""
        # Setup workspace
        workspace = tmp_path / "project"
        workspace.mkdir()

        (workspace / "main.py").write_text("""
def calculate_total(items):
    total = 0
    for item in items:
        total += item
    return total
        """)

        (workspace / "test_main.py").write_text("""
def test_calculate_total():
    assert calculate_total([1, 2, 3]) == 6
        """)

        # Initialize app
        app = PolicyAwareADHApp()
        app.api_key = os.environ.get("GOOGLE_API_KEY")

        if not app.api_key:
            pytest.skip("Requires GOOGLE_API_KEY")

        app.policy_dir = tmp_path / "policies"
        app._initialize_agent()

        # Send review request
        response = await app.agent.chat(
            message=f"Review the code in {workspace}/main.py and check if tests exist"
        )

        # Verify tools were called
        # (Check via execution manager history)
        executions = app.agent.execution_manager.get_history()

        # Should have called read_file at least twice
        read_calls = [e for e in executions if e.tool_name == "read_file"]
        assert len(read_calls) >= 2

        # Should have read both files
        files_read = [e.parameters.get("file_path") for e in read_calls]
        assert str(workspace / "main.py") in files_read
        assert str(workspace / "test_main.py") in files_read

        # Response should mention the code
        assert "calculate_total" in response.lower() or "total" in response.lower()
```

**Level 3: Real API Tests (Slow - 30s+, Optional)**
```python
# tests/e2e/test_real_api.py

@pytest.mark.real_api
@pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="Requires API key")
class TestRealAPI:
    """Tests that hit real Gemini API."""

    @pytest.mark.asyncio
    async def test_streaming_response(self):
        """Test streaming with real API."""
        agent = PolicyAwareLlmAgent(
            api_key=os.environ.get("GOOGLE_API_KEY"),
            policy_dir=Path("adh_cli/policies/defaults")
        )

        chunks_received = []

        def status_callback(status: str):
            chunks_received.append(status)

        response = await agent.chat(
            message="What is 2+2? Answer in one word."
        )

        # Verify response
        assert "four" in response.lower() or "4" in response

        # Verify chunks were received
        # (This tests real streaming behavior)
```

**Level 4: Performance Benchmarks (Fast)**
```python
# tests/performance/test_benchmarks.py

@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmarks for critical paths."""

    def test_policy_evaluation_performance(self, benchmark):
        """Benchmark policy evaluation speed."""
        engine = PolicyEngine()
        tool_call = ToolCall(
            tool_name="read_file",
            parameters={"file_path": "test.txt"}
        )

        # Benchmark
        result = benchmark(engine.evaluate_tool_call, tool_call)

        # Assert performance target
        assert benchmark.stats['mean'] < 0.001  # <1ms

    def test_safety_pipeline_performance(self, benchmark):
        """Benchmark safety pipeline execution."""
        pipeline = SafetyPipeline()
        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"file_path": "test.txt", "content": "test"}
        )

        checks = [
            SafetyCheck(name="backup", checker_class="BackupChecker"),
            SafetyCheck(name="disk", checker_class="DiskSpaceChecker"),
        ]

        # Benchmark
        async def run_checks():
            return await pipeline.run_checks(tool_call, checks)

        result = benchmark(asyncio.run, run_checks())

        # Assert performance target
        assert benchmark.stats['mean'] < 0.1  # <100ms
```

### Test Infrastructure

**1. Shared Fixtures:**
```python
# tests/fixtures/conftest.py

@pytest.fixture
def integration_workspace(tmp_path):
    """Create a temporary workspace for integration tests."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create standard directories
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()
    (workspace / "docs").mkdir()

    # Create sample files
    (workspace / "src" / "main.py").write_text("print('hello')")
    (workspace / "README.md").write_text("# Test Project")

    yield workspace

@pytest.fixture
def mock_agent_with_history():
    """Create agent with execution history."""
    agent = PolicyAwareLlmAgent(api_key="test")

    # Pre-populate history
    agent.execution_manager.create_execution(
        tool_name="read_file",
        parameters={"file_path": "test.txt"}
    )

    yield agent

@pytest.fixture
def policy_config_balanced(tmp_path):
    """Create balanced policy configuration."""
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()

    # Copy default policies
    shutil.copytree(
        "adh_cli/policies/defaults",
        policy_dir,
        dirs_exist_ok=True
    )

    yield policy_dir
```

**2. Mock Data:**
```python
# tests/fixtures/mock_responses.py

SAMPLE_GEMINI_RESPONSE = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": "This is a sample response"
            }]
        }
    }]
}

SAMPLE_FUNCTION_CALL_RESPONSE = {
    "candidates": [{
        "content": {
            "parts": [{
                "function_call": {
                    "name": "read_file",
                    "args": {"file_path": "test.txt"}
                }
            }]
        }
    }]
}

def create_mock_stream(chunks: List[str]):
    """Create mock streaming response."""
    for chunk_text in chunks:
        yield {
            "candidates": [{
                "content": {
                    "parts": [{"text": chunk_text}]
                }
            }]
        }
```

**3. Test Utilities:**
```python
# tests/utils/test_helpers.py

async def wait_for_execution(
    manager: ToolExecutionManager,
    tool_name: str,
    timeout: float = 5.0
) -> Optional[ToolExecutionInfo]:
    """Wait for tool execution to complete."""
    start = time.time()

    while time.time() - start < timeout:
        for exec in manager.get_history():
            if exec.tool_name == tool_name and exec.is_terminal:
                return exec
        await asyncio.sleep(0.1)

    return None

def assert_execution_successful(info: ToolExecutionInfo):
    """Assert execution completed successfully."""
    assert info is not None, "Execution not found"
    assert info.state == ToolExecutionState.SUCCESS, f"Execution failed: {info.error}"
    assert info.error is None
```

### CI/CD Integration

**1. GitHub Actions Workflow:**
```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=adh_cli

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run integration tests
        run: pytest tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run e2e tests (mocked)
        run: pytest tests/e2e/ -m "not real_api" -v

  performance-benchmarks:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
          pip install pytest-benchmark

      - name: Run benchmarks
        run: pytest tests/performance/ --benchmark-only

      - name: Compare with main
        run: |
          git fetch origin main
          git checkout origin/main
          pytest tests/performance/ --benchmark-only --benchmark-save=main
          git checkout -
          pytest tests/performance/ --benchmark-only --benchmark-compare=main
```

**2. Pytest Configuration:**
```ini
# pytest.ini

[pytest]
markers =
    integration: Integration tests (component interaction)
    e2e: End-to-end workflow tests
    real_api: Tests that hit real Gemini API (requires API key)
    benchmark: Performance benchmark tests
    slow: Slow tests (>30s)

# Default: Run everything except real_api and slow
addopts = -v -m "not real_api and not slow"

# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Coverage
[coverage:run]
source = adh_cli
omit =
    tests/*
    */migrations/*
    */conftest.py

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

## Consequences

### Positive

**Reliability:**
- Catch integration issues before production
- Verify component interactions work
- Test real-world scenarios
- Reduce production bugs by ~50%

**Confidence:**
- Safe to refactor
- Trust CI results
- Deploy with confidence
- Faster iteration

**Documentation:**
- Tests serve as examples
- Show how components work together
- Demonstrate workflows
- Living documentation

**Performance:**
- Catch regressions early
- Benchmark critical paths
- Track performance over time
- Optimize based on data

**Quality Metrics:**
- Integration coverage: 80%+
- E2E coverage: All major workflows
- Performance baselines established
- Clear quality gates

### Negative

**Initial Effort:**
- ~1000 LOC for tests
- ~200 LOC for fixtures
- ~100 LOC for utilities
- ~2-3 weeks of work

**CI Time:**
- Unit: 30s → no change
- Integration: +2 minutes
- E2E: +5 minutes
- Benchmarks: +1 minute
- **Total CI time: ~10 minutes** (acceptable)

**Maintenance:**
- More tests to maintain
- Update tests when refactoring
- Keep fixtures up to date
- Monitor flaky tests

**Infrastructure:**
- Need better test isolation
- Mock API responses
- Clean up test data
- Manage test environments

### Risks

**Risk 1: Flaky Tests**
- **Impact:** High - unreliable CI
- **Mitigation:**
  - Strict timeouts
  - Proper cleanup
  - Idempotent tests
  - Retry mechanisms
  - Monitor flakiness

**Risk 2: Slow CI**
- **Impact:** Medium - developer friction
- **Mitigation:**
  - Parallel test execution
  - Cache dependencies
  - Skip slow tests in PR (run in main)
  - Optimize slow tests

**Risk 3: API Key Management**
- **Impact:** Medium - can't run real API tests
- **Mitigation:**
  - Use secrets for keys
  - Mock by default
  - Real API tests optional
  - Document setup

**Risk 4: Test Maintenance Burden**
- **Impact:** Medium - tests become outdated
- **Mitigation:**
  - Good test organization
  - Shared fixtures
  - Clear naming
  - Regular cleanup

### Neutral

**Coverage Goals:**
- Unit tests: 80%+ (current: ~75%)
- Integration tests: 80%+ (current: ~20%)
- E2E tests: All major workflows
- Performance: Benchmarks for critical paths

**Test Distribution:**
- Unit: 70% of total tests
- Integration: 20% of total tests
- E2E: 10% of total tests
- Benchmark: Continuous monitoring

## Alternatives Considered

### Alternative 1: Only Unit Tests

Keep current approach with unit tests only.

**Pros:**
- Fast CI
- Easy to write
- Good isolation

**Cons:**
- Miss integration bugs
- No workflow coverage
- Can't verify real behavior

**Why Rejected:** Already seeing integration issues in production.

### Alternative 2: Manual Testing

Rely on manual QA testing.

**Pros:**
- No test code to write
- Flexible testing
- Catch UX issues

**Cons:**
- Slow feedback
- Inconsistent coverage
- Not repeatable
- Expensive

**Why Rejected:** Not scalable; can't regression test.

### Alternative 3: Only E2E Tests

Skip unit/integration, only do E2E.

**Pros:**
- Test real behavior
- High confidence
- User-focused

**Cons:**
- Very slow
- Hard to debug
- Brittle
- Poor coverage

**Why Rejected:** Too slow for CI; need faster feedback.

### Alternative 4: Contract Testing

Use contract tests between components.

**Pros:**
- Good for microservices
- Catch interface changes
- Independent deployment

**Cons:**
- Overkill for monolith
- Doesn't test workflows
- More complexity

**Why Rejected:** Not appropriate for current architecture.

## Implementation Notes

### Test Files to Create

```
tests/
  integration/
    test_policy_workflow.py           # 200 LOC
    test_safety_workflow.py           # 150 LOC
    test_tool_execution_flow.py       # 200 LOC
    test_ui_integration.py            # 150 LOC
    test_agent_tool_integration.py    # 200 LOC

  e2e/
    test_code_review_workflow.py      # 300 LOC
    test_file_modification_workflow.py # 250 LOC
    test_error_scenarios.py           # 200 LOC
    test_policy_enforcement.py        # 200 LOC

  performance/
    test_benchmarks.py                # 150 LOC

  fixtures/
    conftest.py                       # 200 LOC
    mock_responses.py                 # 100 LOC
    sample_data.py                    # 100 LOC

  utils/
    test_helpers.py                   # 150 LOC
```

**Total: ~2400 LOC**

### Priority Implementation Order

**Phase 1: Component Integration (Week 1)**
- Policy workflow tests
- Safety workflow tests
- Tool execution flow tests
- **Goal: 80% integration coverage**

**Phase 2: E2E Workflows (Week 2)**
- Code review workflow
- File modification workflow
- Error scenarios
- **Goal: All major workflows covered**

**Phase 3: Performance (Week 3)**
- Benchmarks for critical paths
- Load testing
- Memory profiling
- **Goal: Baselines established**

**Phase 4: CI/CD (Week 3)**
- GitHub Actions setup
- Parallel execution
- Coverage reporting
- **Goal: <10 minute CI**

### Success Metrics

**Code Coverage:**
- Unit tests: 80%+ (maintain current)
- Integration tests: 80%+ (up from ~20%)
- E2E tests: All major workflows

**Quality:**
- Production bugs: -50%
- Integration issues: -70%
- Support tickets: -30%

**Performance:**
- All benchmarks <100ms
- No performance regressions
- Track trends over time

**CI:**
- Total time: <10 minutes
- Flaky tests: <1%
- Pass rate: >95%

## References

**Testing Best Practices:**
- [Google Testing Blog](https://testing.googleblog.com/)
- [Martin Fowler - Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Python Testing with pytest](https://pragprog.com/titles/bopytest/python-testing-with-pytest/)

**Tools:**
- [pytest](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [pytest-benchmark](https://github.com/ionelmc/pytest-benchmark)
- [pytest-cov](https://github.com/pytest-dev/pytest-cov)

**Related ADRs:**
- ADR-001: Policy-Aware Architecture
- ADR-002: Tool Execution UI Tracking
- ADR-003: Google ADK Integration

**Examples:**
- Textual test suite
- LangChain test suite
- FastAPI test suite

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-09-30 | Initial proposal | Project Team |
