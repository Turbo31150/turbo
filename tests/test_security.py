"""Tests for JARVIS security module."""

import pytest
from src.security import (
    sanitize_input, sanitize_mcp_args,
    RateLimiter, CredentialVault,
    calculate_security_score,
    generate_api_token, hash_token,
)


class TestSanitizeInput:
    def test_empty_input(self):
        result = sanitize_input("")
        assert result.is_safe
        assert result.clean == ""

    def test_generic_safe_input(self):
        result = sanitize_input("hello world")
        assert result.is_safe

    def test_command_injection_semicolon(self):
        result = sanitize_input("test; rm -rf /", context="command")
        assert not result.is_safe
        assert "cmd_injection" in result.threats[0]

    def test_command_injection_pipe(self):
        result = sanitize_input("test | cat /etc/passwd", context="command")
        assert not result.is_safe

    def test_command_injection_backtick(self):
        result = sanitize_input("test `whoami`", context="command")
        assert not result.is_safe

    def test_sql_injection_union(self):
        result = sanitize_input("1 UNION SELECT * FROM users", context="sql")
        assert not result.is_safe
        assert any("sql_injection" in t for t in result.threats)

    def test_sql_injection_drop(self):
        result = sanitize_input("1; DROP TABLE users", context="sql")
        assert not result.is_safe

    def test_path_traversal(self):
        result = sanitize_input("../../etc/passwd", context="path")
        assert not result.is_safe
        assert any("path_traversal" in t for t in result.threats)

    def test_prompt_truncation(self):
        long_text = "x" * 60000
        result = sanitize_input(long_text, context="prompt")
        assert len(result.clean) <= 50000

    def test_null_byte_removal(self):
        result = sanitize_input("test\x00injection")
        assert "\x00" not in result.clean

    def test_safe_path(self):
        result = sanitize_input("/home/turbo/jarvis-m1-ops/src/config.py", context="path")
        assert result.is_safe


class TestSanitizeMCPArgs:
    def test_powershell_sanitization(self):
        args = {"command": "Get-Process; Remove-Item C:\\"}
        result = sanitize_mcp_args("powershell_run", args)
        assert ";" not in result["command"]

    def test_lm_query_as_prompt(self):
        args = {"prompt": "Write a Python function"}
        result = sanitize_mcp_args("lm_query", args)
        assert result["prompt"] == "Write a Python function"

    def test_non_string_passthrough(self):
        args = {"limit": 10, "flag": True}
        result = sanitize_mcp_args("some_tool", args)
        assert result["limit"] == 10
        assert result["flag"] is True


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=5)
        for _ in range(5):
            assert limiter.allow("test") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)
        assert limiter.allow("test") is True
        assert limiter.allow("test") is True
        assert limiter.allow("test") is False

    def test_different_keys_independent(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)
        assert limiter.allow("key1") is True
        assert limiter.allow("key2") is True
        assert limiter.allow("key1") is False

    def test_retry_after(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)
        limiter.allow("test")
        limiter.allow("test")
        retry = limiter.get_retry_after("test")
        assert retry >= 0


class TestCredentialVault:
    def test_encrypt_decrypt(self):
        vault = CredentialVault()
        encrypted = vault.encrypt("my_secret_key")
        assert encrypted != "my_secret_key"
        decrypted = vault.decrypt(encrypted)
        assert decrypted == "my_secret_key"

    def test_store_retrieve(self):
        vault = CredentialVault()
        vault.store("API_KEY", "sk-12345")
        result = vault.retrieve("API_KEY")
        assert result == "sk-12345"

    def test_retrieve_missing(self):
        vault = CredentialVault()
        assert vault.retrieve("NONEXISTENT") is None


class TestTokenGeneration:
    def test_generate_token_length(self):
        token = generate_api_token(32)
        assert len(token) > 20  # URL-safe base64 encoding

    def test_tokens_unique(self):
        t1 = generate_api_token()
        t2 = generate_api_token()
        assert t1 != t2

    def test_hash_token(self):
        token = "my_secret_token"
        h = hash_token(token)
        assert len(h) == 64  # SHA-256 hex
        assert hash_token(token) == h  # Deterministic


class TestSecurityScore:
    def test_returns_dict(self):
        score = calculate_security_score()
        assert "score" in score
        assert "grade" in score
        assert "details" in score

    def test_score_range(self):
        score = calculate_security_score()
        assert 0 <= score["score"] <= 100

    def test_grade_valid(self):
        score = calculate_security_score()
        assert score["grade"] in ("A", "B", "C", "D", "F")
