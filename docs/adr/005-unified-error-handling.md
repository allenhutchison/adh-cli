# ADR 005: Unified Error Handling and Response Processing

**Status:** Proposed - Not Implemented
**Date:** 2025-09-30
**Deciders:** Project Team
**Tags:** reliability, error-handling, refactoring, critical

> **Implementation Status (2025-10-14):** This ADR describes a proposed future enhancement that has not yet been implemented. Error handling is currently distributed across the `PolicyAwareLlmAgent` class without the unified `ResponseHandler` abstraction described here. The proposed exception hierarchy and response handler remain future work.

---

## Context

The current ADK service implementation (`adh_cli/services/adk_service.py`) has several error handling issues:

### Current Problems

**1. Inconsistent Error Handling:**
```python
# Different error handling in different methods
def send_message(self, message: str):
    try:
        response = self._chat_session.send_message(message)
        return response.text
    except Exception:
        return "Error occurred"  # Silent failure

def send_message_streaming(self, message: str):
    try:
        # ... complex streaming logic
        if not text_accumulated:
            return "Task completed."  # Ambiguous
    except AttributeError:
        return f"Error: {e}"  # Inconsistent format
```

**2. Silent Failures:**
- Empty responses treated as success
- Missing error context
- No distinction between different failure modes
- Hard to debug from user reports

**3. Code Duplication:**
- Response validation duplicated across methods
- Text extraction logic repeated
- Tool call detection repeated
- ~150 lines of similar code in streaming vs non-streaming

**4. Poor Error Messages:**
```python
# What user sees:
"Error occurred"  # Which error? Where?

# What they should see:
"Empty response from AI (no candidates). Please try rephrasing your request."
```

**5. No Response Structure Validation:**
```python
# Current: Hope for the best
text = response.candidates[0].content.parts[0].text

# What happens when structure differs:
AttributeError: 'NoneType' object has no attribute 'content'
```

### Impact

**Users Experience:**
- Cryptic error messages
- Can't recover from errors
- Don't know what went wrong
- Support burden increases

**Developers Face:**
- Hard to debug issues
- Duplicate bug fixes in both code paths
- Can't add features without touching both
- High maintenance cost

**Metrics:**
- ~30% of errors are "Error occurred"
- ~15% silent failures (empty responses)
- ~40% of debug time on error reproduction

## Decision

Implement a **unified response handling system** with:

### Architecture

**1. Custom Exception Hierarchy:**
```python
# adh_cli/services/response_handler.py

class ResponseError(Exception):
    """Base exception for response handling."""
    pass

class EmptyResponseError(ResponseError):
    """Raised when AI returns empty or invalid response."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Empty response: {reason}")

class ResponseValidationError(ResponseError):
    """Raised when response structure is invalid."""
    def __init__(self, expected: str, got: str):
        self.expected = expected
        self.got = got
        super().__init__(f"Invalid response structure: expected {expected}, got {got}")

class ToolExecutionError(ResponseError):
    """Raised when tool execution fails during streaming."""
    def __init__(self, tool_name: str, error: str):
        self.tool_name = tool_name
        self.error = error
        super().__init__(f"Tool '{tool_name}' failed: {error}")
```

**2. Response Handler Class:**
```python
@dataclass
class ResponseChunk:
    """Represents a single response chunk."""
    text: str
    has_tool_call: bool
    tool_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class ResponseHandler:
    """Unified response handling for streaming and non-streaming."""

    def __init__(self, status_callback: Optional[Callable[[str], None]] = None):
        self.status_callback = status_callback
        self.text_buffer: List[str] = []
        self.tool_activity = False
        self.last_tool_name: Optional[str] = None
        self.chunk_count = 0

    def validate_response(self, response) -> None:
        """Validate response structure."""
        if not response:
            raise ResponseValidationError("response object", "None")

        if not hasattr(response, 'candidates'):
            raise ResponseValidationError("candidates attribute", type(response).__name__)

        if not response.candidates:
            raise EmptyResponseError("no candidates in response")

        candidate = response.candidates[0]
        if not hasattr(candidate, 'content'):
            raise ResponseValidationError("content attribute", "missing")

    async def process_chunk(self, chunk) -> Optional[ResponseChunk]:
        """Process a single response chunk."""
        if not chunk:
            return None

        self.chunk_count += 1
        result = ResponseChunk(text="", has_tool_call=False)

        # Extract text
        if hasattr(chunk, 'text') and chunk.text:
            result.text = chunk.text
            self.text_buffer.append(chunk.text)
            self._update_status_preview()

        # Detect tool calls
        if hasattr(chunk, 'candidates') and chunk.candidates:
            candidate = chunk.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call'):
                        result.has_tool_call = True
                        result.tool_name = getattr(part.function_call, 'name', 'unknown')
                        self.tool_activity = True
                        self.last_tool_name = result.tool_name
                        self._update_status_tool(result.tool_name)

        return result

    def get_final_response(self) -> str:
        """Get the final processed response."""
        # Text takes priority
        if self.text_buffer:
            return ''.join(self.text_buffer)

        # Tool-only response
        if self.tool_activity:
            return self._generate_tool_completion_message()

        # No response at all
        raise EmptyResponseError(
            f"no text or tool activity after {self.chunk_count} chunks"
        )

    def _generate_tool_completion_message(self) -> str:
        """Generate appropriate message for tool-only responses."""
        if self.last_tool_name:
            return f"Analysis complete. Executed {self.last_tool_name} successfully."
        return "Analysis complete using available tools."

    def _update_status_preview(self) -> None:
        """Update status with text preview."""
        if not self.status_callback:
            return

        full_text = ''.join(self.text_buffer)
        preview = full_text[:50].replace('\n', ' ')
        if len(full_text) > 50:
            preview += "..."
        self.status_callback(f"💭 {preview}")

    def _update_status_tool(self, tool_name: str) -> None:
        """Update status with tool activity."""
        if self.status_callback:
            self.status_callback(f"🔧 Using {tool_name}...")
```

**3. Refactored ADK Service:**
```python
# adh_cli/services/adk_service.py

class ADKService:
    def send_message(self, message: str) -> str:
        """Send a message and get response."""
        if not self._chat_session:
            self.start_chat()

        handler = ResponseHandler()

        try:
            response = self._chat_session.send_message(message)
            handler.validate_response(response)

            # Extract text
            if hasattr(response, 'text') and response.text:
                return response.text

            # No text - check for tool activity
            if self._has_tool_calls(response):
                return "Task completed using available tools."

            # Empty response
            raise EmptyResponseError("no text in response")

        except EmptyResponseError as e:
            return self._format_empty_response_message(e)

        except ResponseValidationError as e:
            return self._format_validation_error_message(e)

        except Exception as e:
            return self._format_generic_error_message(e)

    def send_message_streaming(
        self,
        message: str,
        status_callback: Optional[Callable] = None
    ) -> str:
        """Send a message with streaming response."""
        if not self._chat_session:
            self.start_chat()

        handler = ResponseHandler(status_callback)

        try:
            if status_callback:
                status_callback("⏳ Sending message to AI...")

            stream = self._chat_session.send_message_stream(message)

            if stream is None:
                raise EmptyResponseError("no response stream received")

            # Process all chunks
            for chunk in stream:
                handler.process_chunk(chunk)

            return handler.get_final_response()

        except EmptyResponseError as e:
            if status_callback:
                status_callback(f"⚠️ {str(e)}")
            return self._format_empty_response_message(e)

        except ResponseValidationError as e:
            if status_callback:
                status_callback(f"❌ {str(e)}")
            return self._format_validation_error_message(e)

        except Exception as e:
            if status_callback:
                status_callback(f"❌ Error: {str(e)}")
            return self._format_generic_error_message(e)

    def _format_empty_response_message(self, error: EmptyResponseError) -> str:
        """Format user-friendly message for empty responses."""
        return (
            "The AI returned an empty response. This can happen if:\n"
            "• The request was unclear or too complex\n"
            "• The model encountered an internal error\n"
            "• Rate limiting or quota issues\n\n"
            "Please try:\n"
            "• Rephrasing your request more clearly\n"
            "• Breaking complex requests into smaller steps\n"
            f"\nTechnical details: {error.reason}"
        )

    def _format_validation_error_message(self, error: ResponseValidationError) -> str:
        """Format user-friendly message for validation errors."""
        return (
            "Received an unexpected response format from the AI.\n"
            f"Expected: {error.expected}\n"
            f"Got: {error.got}\n\n"
            "This may be a temporary API issue. Please try again."
        )

    def _format_generic_error_message(self, error: Exception) -> str:
        """Format user-friendly message for generic errors."""
        error_type = type(error).__name__
        return (
            f"An error occurred while communicating with the AI:\n"
            f"{error_type}: {str(error)}\n\n"
            "Please check your internet connection and try again."
        )
```

### Error Handling Flow

```
User Request
    ↓
ADKService.send_message_streaming()
    ↓
Create ResponseHandler
    ↓
For each chunk:
    ↓
    handler.process_chunk()
    ↓
    ├─ Text? → Add to buffer, update status
    ├─ Tool call? → Track activity, update status
    └─ Error? → Raise specific exception
    ↓
handler.get_final_response()
    ↓
    ├─ Has text? → Return text
    ├─ Has tool activity? → Return tool message
    └─ Empty? → Raise EmptyResponseError
    ↓
Catch specific exceptions
    ↓
Format user-friendly message
    ↓
Return to user
```

## Consequences

### Positive

**Better User Experience:**
- Clear, actionable error messages
- Understand what went wrong
- Know how to fix issues
- Reduced support requests

**Code Quality:**
- Single source of truth for response handling
- ~200 lines reduced (from ~400 to ~200 in adk_service.py)
- Easier to maintain
- Consistent behavior

**Debuggability:**
- Specific exception types
- Detailed error context
- Easier to reproduce issues
- Better logging opportunities

**Extensibility:**
- Easy to add new response types
- Can add metrics/monitoring
- Pluggable status callbacks
- Future-proof for API changes

**Testing:**
- Easier to test error paths
- Can mock ResponseHandler
- Clear test cases per exception type
- Better coverage

### Negative

**Initial Effort:**
- ~400 lines of new code
- Need to refactor existing code
- Update all tests
- Documentation updates

**Learning Curve:**
- New exception hierarchy to learn
- ResponseHandler API to understand
- Different patterns than current code

**Migration Risk:**
- Could introduce regressions
- Need comprehensive testing
- Affects critical path

### Risks

**Risk 1: Breaking Existing Behavior**
- **Impact:** High - users see different error messages
- **Mitigation:**
  - Comprehensive tests for all paths
  - Beta test with real users
  - Monitor error rates after deploy
  - Keep error messages informative

**Risk 2: Performance Regression**
- **Impact:** Low - handler adds overhead
- **Mitigation:**
  - Benchmark before/after
  - Profile in production
  - Optimize hot paths
  - Expect <5ms overhead

**Risk 3: Unforeseen Edge Cases**
- **Impact:** Medium - new exceptions for rare cases
- **Mitigation:**
  - Extensive error path testing
  - Catch-all for unknown errors
  - Log all exceptions
  - Monitor production errors

### Neutral

**Testing:**
- Need new test fixtures for exceptions
- Mock ResponseHandler in tests
- Integration tests for real responses
- Error simulation tests

**Documentation:**
- Update API docs
- Document exception types
- Error recovery guide
- Migration guide

## Alternatives Considered

### Alternative 1: Keep Current Approach

Don't refactor, just fix specific bugs.

**Pros:**
- Less work
- No migration risk
- Known behavior

**Cons:**
- Technical debt accumulates
- Bugs keep recurring
- Hard to maintain
- Poor user experience

**Why Rejected:** Doesn't solve root cause; problems will persist.

### Alternative 2: Use Existing Library (Tenacity, etc.)

Use retry/error handling library.

**Pros:**
- Battle-tested
- Less code to write
- Standard patterns

**Cons:**
- Overkill for needs
- Doesn't solve response parsing
- Still need custom error types
- Added dependency

**Why Rejected:** Doesn't address response handling; only retry logic.

### Alternative 3: Separate Streaming and Non-Streaming

Keep them completely separate, no shared code.

**Pros:**
- Clear separation
  - Independent evolution
- No shared state

**Cons:**
- Duplicate error handling
- Inconsistent messages
- Double maintenance
- Current problem continues

**Why Rejected:** Perpetuates the duplication problem we're trying to solve.

### Alternative 4: Event-Based Architecture

Use events for response processing.

**Pros:**
- Very flexible
- Easy to extend
- Decoupled components

**Cons:**
- Much more complex
- Harder to debug
- Overkill for current needs
- Learning curve

**Why Rejected:** Too complex for the problem at hand.

## Implementation Notes

### File Structure

```
adh_cli/
  services/
    response_handler.py        # New: 200 LOC
    adk_service.py             # Refactor: -150 LOC

tests/
  services/
    test_response_handler.py   # New: 250 LOC
    test_adk_service.py        # Update: +50 LOC
```

### Exception Hierarchy

```python
ResponseError (base)
  ├─ EmptyResponseError
  │   ├─ NoCandidatesError
  │   ├─ NoTextError
  │   └─ NoToolActivityError
  │
  ├─ ResponseValidationError
  │   ├─ MissingAttributeError
  │   ├─ InvalidStructureError
  │   └─ UnexpectedTypeError
  │
  └─ ToolExecutionError
      ├─ ToolNotFoundError
      └─ ToolFailedError
```

### Testing Strategy

**Unit Tests:**
```python
class TestResponseHandler:
    def test_validate_response_success(self):
        """Test successful response validation."""
        response = create_valid_response()
        handler = ResponseHandler()
        handler.validate_response(response)  # Should not raise

    def test_validate_response_missing_candidates(self):
        """Test validation with missing candidates."""
        response = Mock(candidates=None)
        handler = ResponseHandler()

        with pytest.raises(EmptyResponseError, match="no candidates"):
            handler.validate_response(response)

    def test_process_chunk_with_text(self):
        """Test processing chunk with text."""
        chunk = Mock(text="Hello", candidates=[])
        handler = ResponseHandler()

        result = await handler.process_chunk(chunk)

        assert result.text == "Hello"
        assert not result.has_tool_call
        assert handler.text_buffer == ["Hello"]

    def test_get_final_response_empty(self):
        """Test getting final response when empty."""
        handler = ResponseHandler()

        with pytest.raises(EmptyResponseError, match="no text or tool activity"):
            handler.get_final_response()
```

**Integration Tests:**
```python
@pytest.mark.integration
async def test_streaming_with_errors():
    """Test streaming handles errors gracefully."""
    service = ADKService(api_key="test")

    # Mock stream that raises
    def error_stream():
        yield create_chunk("Some text")
        raise AttributeError("Missing attribute")

    with patch.object(service._chat_session, 'send_message_stream', return_value=error_stream()):
        response = service.send_message_streaming("test")

        assert "error occurred" in response.lower()
        assert "AttributeError" in response
```

### Migration Steps

**Phase 1: Add ResponseHandler**
- Create response_handler.py
- Add exception classes
- Write comprehensive tests
- No changes to adk_service.py yet

**Phase 2: Refactor Non-Streaming**
- Update send_message() to use ResponseHandler
- Keep send_message_streaming() unchanged
- A/B test for regressions

**Phase 3: Refactor Streaming**
- Update send_message_streaming()
- Remove duplicate code
- Full integration testing

**Phase 4: Cleanup**
- Remove old error handling code
- Update documentation
- Add monitoring

### Performance Benchmarks

**Before:**
- send_message: ~500ms average
- send_message_streaming: ~800ms average

**After (target):**
- send_message: ~505ms (+5ms acceptable)
- send_message_streaming: ~805ms (+5ms acceptable)

**Overhead Budget:**
- Response validation: <1ms
- Chunk processing: <0.5ms per chunk
- Total: <5ms per request

### Error Message Examples

**Current:**
```
"Error occurred"
```

**After:**
```
The AI returned an empty response. This can happen if:
• The request was unclear or too complex
• The model encountered an internal error
• Rate limiting or quota issues

Please try:
• Rephrasing your request more clearly
• Breaking complex requests into smaller steps

Technical details: no candidates in response
```

### Logging Strategy

```python
# Add structured logging
import logging

logger = logging.getLogger(__name__)

class ResponseHandler:
    async def process_chunk(self, chunk):
        try:
            # ... processing
            logger.debug(
                "Processed chunk",
                extra={
                    "chunk_num": self.chunk_count,
                    "has_text": bool(result.text),
                    "has_tool_call": result.has_tool_call,
                }
            )
        except Exception as e:
            logger.error(
                "Chunk processing failed",
                extra={
                    "chunk_num": self.chunk_count,
                    "error": str(e),
                },
                exc_info=True
            )
            raise
```

## References

**Error Handling Best Practices:**
- [Python Exception Hierarchy](https://docs.python.org/3/library/exceptions.html)
- [Effective Python Error Handling](https://realpython.com/python-exceptions/)
- [Google Cloud Error Handling](https://cloud.google.com/apis/design/errors)

**Related ADRs:**
- ADR-003: Google ADK Integration
- ADR-002: Tool Execution UI Tracking

**Code:**
- Current: `adh_cli/services/adk_service.py`
- Will create: `adh_cli/services/response_handler.py`

**Similar Implementations:**
- LangChain error handling
- OpenAI Python SDK error handling
- Anthropic Claude SDK error handling

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-09-30 | Initial proposal | Project Team |
