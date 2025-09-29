"""Data and content safety checkers."""

import re
from pathlib import Path
from typing import List, Pattern

from ..base_checker import SafetyChecker, SafetyResult, SafetyStatus
from ...policies.policy_types import ToolCall, RiskLevel


class SensitiveDataChecker(SafetyChecker):
    """Detects sensitive data in files and parameters."""

    def __init__(self, config=None):
        super().__init__(config)
        self.patterns = self._compile_patterns()

    def _compile_patterns(self) -> List[Pattern]:
        """Compile regex patterns for sensitive data detection."""
        patterns = [
            # API Keys and Tokens
            r'(?i)(api[_\-\s]?key|api[_\-\s]?token|auth[_\-\s]?token|access[_\-\s]?token)[\s:=]+[\w\-]+',
            r'(?i)bearer\s+[\w\-\.]+',

            # AWS Keys
            r'AKIA[0-9A-Z]{16}',
            r'(?i)aws[_\-\s]?secret[_\-\s]?access[_\-\s]?key[\s:=]+[\w\-/+=]+',

            # SSH Keys
            r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
            r'ssh-rsa\s+[\w+/=]+',

            # Passwords
            r'(?i)password[\s:=]+["\']?[\w\-!@#$%^&*]+["\']?',
            r'(?i)pwd[\s:=]+["\']?[\w\-!@#$%^&*]+["\']?',

            # Credit Cards
            r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',

            # Social Security Numbers
            r'\b\d{3}-\d{2}-\d{4}\b',

            # Email addresses (for PII detection)
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ]

        return [re.compile(pattern) for pattern in patterns]

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Check for sensitive data in parameters and files."""
        findings = []

        # Check parameters
        param_str = str(tool_call.parameters)
        for pattern in self.patterns:
            if pattern.search(param_str):
                findings.append("Sensitive data detected in parameters")
                break

        # Check file content if reading/writing
        file_path = tool_call.get_parameter("path") or tool_call.get_parameter("file_path")
        if file_path and Path(file_path).exists():
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1024 * 100)  # Read first 100KB

                for pattern in self.patterns:
                    if pattern.search(content):
                        findings.append(f"Sensitive data detected in file: {file_path}")
                        break
            except Exception:
                pass  # Ignore read errors

        if findings:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.WARNING,
                message="Sensitive data detected",
                risk_level=RiskLevel.HIGH,
                details={"findings": findings},
                suggestions=[
                    "Review the data carefully",
                    "Consider redacting sensitive information",
                    "Ensure proper encryption if storing",
                ],
                can_override=True,
            )

        return SafetyResult(
            checker_name=self.name,
            status=SafetyStatus.PASSED,
            message="No sensitive data detected",
            risk_level=RiskLevel.NONE,
        )