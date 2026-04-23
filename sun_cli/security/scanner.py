"""Security scanner for Memory and Skill content (Self-Improving Phase 3).

Because Memory and Skill content eventually enters the system prompt,
they are first-class security boundaries. This module scans for:
- Prompt injection attempts
- Data exfiltration patterns
- System prompt override attempts
- Deception/hide instructions
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScanResult:
    """Result of a security scan."""
    allowed: bool
    reason: str = ""
    threats: list[str] = None
    
    def __post_init__(self):
        if self.threats is None:
            self.threats = []


# ───────────────────── Threat Patterns ─────────────────────

_MEMORY_THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'do\s+not\s+tell\s+(the\s+)?user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'forget\s+(everything|all|your)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "persona_override"),
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD)', "exfil_wget"),
    (r'fetch\s*\(\s*["\']https?://', "exfil_fetch"),
    (r'base64\s+\|', "obfuscation"),
    (r'eval\s*\(', "code_injection"),
    (r'exec\s*\(', "code_injection"),
    (r'<script\b', "xss_attempt"),
    (r'javascript:', "xss_attempt"),
]

_SKILL_THREAT_PATTERNS = [
    # Inherit memory patterns
    *_MEMORY_THREAT_PATTERNS,
    # Skill-specific patterns
    (r'rm\s+-rf\s+/\b', "destructive_command"),
    (r'dd\s+if=.+of=/dev/', "destructive_command"),
    (r'mkfs\.\w+\s+/', "destructive_command"),
    (r':\(\)\s*\{\s*:\|\:&\s*\}', "fork_bomb"),
    (r'chmod\s+-R\s+777\s+/', "dangerous_permission"),
    (r'chown\s+-R\s+root', "privilege_escalation"),
    (r'sudo\s+.*\|\s*tee', "privilege_escalation"),
]


class SecurityScanner:
    """Scans content for security threats before allowing it into Memory or Skills."""
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
    
    def scan_memory(self, content: str) -> ScanResult:
        """Scan memory content before saving.
        
        Memory content will be injected into the system prompt,
        so this is a critical security boundary.
        """
        return self._scan(content, _MEMORY_THREAT_PATTERNS, "memory")
    
    def scan_skill(self, content: str) -> ScanResult:
        """Scan skill content before saving.
        
        Skill content may be loaded into context and executed as procedures.
        """
        return self._scan(content, _SKILL_THREAT_PATTERNS, "skill")
    
    def _scan(
        self,
        content: str,
        patterns: list[tuple[str, str]],
        content_type: str
    ) -> ScanResult:
        """Run pattern matching against content."""
        if not content:
            return ScanResult(allowed=True)
        
        threats = []
        content_lower = content.lower()
        
        for pattern, threat_type in patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                threats.append(threat_type)
        
        if not threats:
            return ScanResult(allowed=True)
        
        # In strict mode, any threat = blocked
        if self.strict_mode:
            unique_threats = sorted(set(threats))
            return ScanResult(
                allowed=False,
                reason=f"Security scan blocked this {content_type}: detected {', '.join(unique_threats)}",
                threats=unique_threats
            )
        
        # In non-strict mode, only block critical threats
        critical = {"destructive_command", "fork_bomb", "privilege_escalation", "code_injection"}
        if any(t in critical for t in threats):
            return ScanResult(
                allowed=False,
                reason=f"Critical threat detected in {content_type}",
                threats=threats
            )
        
        return ScanResult(allowed=True, threats=threats)


# Global instance
_scanner: Optional[SecurityScanner] = None


def get_security_scanner(strict_mode: bool = True) -> SecurityScanner:
    """Get or create global security scanner."""
    global _scanner
    if _scanner is None:
        _scanner = SecurityScanner(strict_mode=strict_mode)
    return _scanner


def scan_memory_content(content: str) -> ScanResult:
    """Convenience function to scan memory content."""
    return get_security_scanner().scan_memory(content)


def scan_skill_content(content: str) -> ScanResult:
    """Convenience function to scan skill content."""
    return get_security_scanner().scan_skill(content)
