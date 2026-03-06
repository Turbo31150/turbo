"""Tests for JARVIS configuration module."""

import pytest
from src.config import (
    JarvisConfig, LMStudioNode, OllamaNode, GeminiNode,
    prepare_lmstudio_input, build_lmstudio_payload, build_ollama_payload,
    JARVIS_VERSION,
)


class TestJarvisVersion:
    def test_version_format(self):
        parts = JARVIS_VERSION.split(".")
        assert len(parts) == 2
        assert all(p.isdigit() for p in parts)

    def test_version_is_10_6(self):
        assert JARVIS_VERSION == "10.6"


class TestLMStudioNode:
    def test_auth_headers_with_key(self):
        node = LMStudioNode("M1", "http://127.0.0.1:1234", "test", api_key="sk-test")
        assert node.auth_headers == {"Authorization": "Bearer sk-test"}

    def test_auth_headers_without_key(self):
        node = LMStudioNode("M1", "http://127.0.0.1:1234", "test")
        assert node.auth_headers == {}


class TestPrepareLMStudioInput:
    def test_nothink_prefix_for_m1_qwen(self):
        result = prepare_lmstudio_input("hello", "M1", "qwen/qwen3-8b")
        assert result.startswith("/nothink\n")
        assert "hello" in result

    def test_no_prefix_for_m2(self):
        result = prepare_lmstudio_input("hello", "M2", "deepseek-coder")
        assert result == "hello"

    def test_no_prefix_for_non_qwen(self):
        result = prepare_lmstudio_input("hello", "M3", "deepseek-r1-0528-qwen3-8b")
        assert result == "hello"


class TestBuildLMStudioPayload:
    def test_basic_payload(self):
        payload = build_lmstudio_payload("model-x", "test prompt")
        assert payload["model"] == "model-x"
        assert payload["input"] == "test prompt"
        assert payload["stream"] is False
        assert payload["store"] is False

    def test_custom_temperature(self):
        payload = build_lmstudio_payload("model-x", "test", temperature=0.7)
        assert payload["temperature"] == 0.7

    def test_extra_kwargs(self):
        payload = build_lmstudio_payload("model-x", "test", context_length=16384)
        assert payload["context_length"] == 16384


class TestBuildOllamaPayload:
    def test_basic_payload(self):
        messages = [{"role": "user", "content": "hello"}]
        payload = build_ollama_payload("qwen3:1.7b", messages)
        assert payload["model"] == "qwen3:1.7b"
        assert payload["stream"] is False
        assert payload["think"] is False

    def test_temperature(self):
        messages = [{"role": "user", "content": "test"}]
        payload = build_ollama_payload("model", messages, temperature=0.5)
        assert payload["options"]["temperature"] == 0.5


class TestJarvisConfig:
    def test_default_nodes(self):
        config = JarvisConfig()
        assert len(config.lm_nodes) == 3
        assert config.lm_nodes[0].name == "M1"
        assert config.lm_nodes[1].name == "M2"
        assert config.lm_nodes[2].name == "M3"

    def test_get_node(self):
        config = JarvisConfig()
        m1 = config.get_node("M1")
        assert m1 is not None
        assert m1.name == "M1"
        assert config.get_node("NONEXISTENT") is None

    def test_get_ollama_node(self):
        config = JarvisConfig()
        ol1 = config.get_ollama_node("OL1")
        assert ol1 is not None
        assert "11434" in ol1.url

    def test_route_returns_list(self):
        config = JarvisConfig()
        nodes = config.route("code_generation")
        assert isinstance(nodes, list)
        assert len(nodes) > 0

    def test_route_fallback(self):
        config = JarvisConfig()
        nodes = config.route("nonexistent_task")
        assert nodes == ["M1"]

    def test_weighted_route(self):
        config = JarvisConfig()
        nodes = config.weighted_route("code")
        assert isinstance(nodes, list)
        assert "M1" in nodes

    def test_weighted_route_thermal_exclusion(self):
        config = JarvisConfig()
        nodes = config.weighted_route("code", gpu_temps={"M1": 90, "M2": 50})
        # M1 should be excluded at 90C (>= 85C critical)
        assert nodes[0] != "M1"

    def test_update_latency(self):
        config = JarvisConfig()
        config.update_latency("M1", 500)
        assert config._latency_cache["M1"] == 500

    def test_get_timeout(self):
        config = JarvisConfig()
        assert config.get_timeout("fast") == config.fast_timeout
        assert config.get_timeout("health") == config.health_timeout

    def test_get_model_for_task(self):
        config = JarvisConfig()
        node, model = config.get_model_for_task("code_generation")
        assert node in ("M1", "M2", "M3", "OL1")
        assert isinstance(model, str)
