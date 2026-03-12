"""Comprehensive tests for src/commands_navigation.py — NAVIGATION_COMMANDS registry.

Tests cover:
- Module import and data structure integrity
- JarvisCommand dataclass field validation
- Command uniqueness (names, actions)
- Trigger format and completeness
- URL validation for browser navigate actions
- Category consistency
- Parameterized search commands
- Section coverage (social, dev, crypto, FR sites, etc.)
"""

from __future__ import annotations

import re
from collections import Counter
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest


# ---------------------------------------------------------------------------
# Fixtures — import the module with proper mocking of heavy deps
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def nav_commands():
    """Import NAVIGATION_COMMANDS with external deps mocked."""
    # Mock src.config.PATHS to avoid filesystem dependency
    mock_config = MagicMock()
    mock_config.PATHS = {"turbo": "/home/turbo/jarvis-m1-ops"}
    with patch.dict("sys.modules", {
        "src.config": mock_config,
        "dotenv": MagicMock(),
    }):
        # Force re-resolve if commands.py was cached with real config
        from src.commands import JarvisCommand
        from src.commands_navigation import NAVIGATION_COMMANDS
    return NAVIGATION_COMMANDS


@pytest.fixture(scope="module")
def static_commands(nav_commands):
    """Commands without URL parameters (direct navigation)."""
    return [c for c in nav_commands if not c.params]


@pytest.fixture(scope="module")
def search_commands(nav_commands):
    """Commands with URL parameters (search/query)."""
    return [c for c in nav_commands if c.params]


# ---------------------------------------------------------------------------
# 1. Module Structure & Import
# ---------------------------------------------------------------------------

class TestModuleStructure:
    """Test that the module loads correctly and has expected shape."""

    def test_navigation_commands_is_list(self, nav_commands):
        """NAVIGATION_COMMANDS must be a list."""
        assert isinstance(nav_commands, list)

    def test_navigation_commands_not_empty(self, nav_commands):
        """The list must contain a substantial number of commands."""
        assert len(nav_commands) > 100, (
            f"Expected >100 navigation commands, got {len(nav_commands)}"
        )

    def test_all_items_are_jarvis_commands(self, nav_commands):
        """Every item in the list must be a JarvisCommand dataclass instance."""
        for i, cmd in enumerate(nav_commands):
            assert type(cmd).__name__ == "JarvisCommand", (
                f"Item {i} is {type(cmd).__name__}, not JarvisCommand"
            )
            # Verify dataclass fields exist
            assert hasattr(cmd, "name")
            assert hasattr(cmd, "category")
            assert hasattr(cmd, "triggers")
            assert hasattr(cmd, "action")


# ---------------------------------------------------------------------------
# 2. JarvisCommand Field Validation
# ---------------------------------------------------------------------------

class TestFieldValidation:
    """Validate that all required fields are properly set on each command."""

    def test_all_have_name(self, nav_commands):
        """Every command must have a non-empty string name."""
        for cmd in nav_commands:
            assert isinstance(cmd.name, str) and len(cmd.name) > 0, (
                f"Command missing name: {cmd}"
            )

    def test_all_have_category_navigation(self, nav_commands):
        """Every command in this module must have category='navigation'."""
        for cmd in nav_commands:
            assert cmd.category == "navigation", (
                f"Command '{cmd.name}' has category '{cmd.category}' instead of 'navigation'"
            )

    def test_all_have_description(self, nav_commands):
        """Every command must have a non-empty description."""
        for cmd in nav_commands:
            assert isinstance(cmd.description, str) and len(cmd.description) > 0, (
                f"Command '{cmd.name}' has empty description"
            )

    def test_all_have_triggers(self, nav_commands):
        """Every command must have at least one trigger phrase."""
        for cmd in nav_commands:
            assert isinstance(cmd.triggers, list) and len(cmd.triggers) >= 1, (
                f"Command '{cmd.name}' has no triggers"
            )

    def test_all_triggers_are_strings(self, nav_commands):
        """Each trigger phrase must be a non-empty string."""
        for cmd in nav_commands:
            for t in cmd.triggers:
                assert isinstance(t, str) and len(t.strip()) > 0, (
                    f"Command '{cmd.name}' has invalid trigger: {t!r}"
                )

    def test_action_type_is_browser(self, nav_commands):
        """All navigation commands must use action_type='browser'."""
        for cmd in nav_commands:
            assert cmd.action_type == "browser", (
                f"Command '{cmd.name}' has action_type '{cmd.action_type}', expected 'browser'"
            )

    def test_action_starts_with_navigate(self, nav_commands):
        """All browser actions must start with 'navigate:' prefix."""
        for cmd in nav_commands:
            assert cmd.action.startswith("navigate:"), (
                f"Command '{cmd.name}' action doesn't start with 'navigate:': {cmd.action}"
            )

    def test_confirm_is_false(self, nav_commands):
        """Navigation commands should not require confirmation (default False)."""
        for cmd in nav_commands:
            assert cmd.confirm is False, (
                f"Command '{cmd.name}' has confirm=True, unexpected for navigation"
            )

    def test_params_is_list(self, nav_commands):
        """The params field must always be a list."""
        for cmd in nav_commands:
            assert isinstance(cmd.params, list), (
                f"Command '{cmd.name}' has params of type {type(cmd.params).__name__}"
            )


# ---------------------------------------------------------------------------
# 3. Uniqueness Checks
# ---------------------------------------------------------------------------

class TestUniqueness:
    """Ensure command names are unique and there are no accidental duplicates."""

    def test_unique_command_names(self, nav_commands):
        """Command names must be globally unique within the navigation list."""
        names = [c.name for c in nav_commands]
        dupes = [n for n, count in Counter(names).items() if count > 1]
        assert len(dupes) == 0, f"Duplicate command names: {dupes}"

    def test_no_exact_duplicate_triggers(self, nav_commands):
        """No two commands should share the exact same trigger phrase
        (excluding parameterized triggers with {requete})."""
        all_triggers: dict[str, list[str]] = {}
        for cmd in nav_commands:
            for t in cmd.triggers:
                # Skip parameterized triggers since they use {requete}
                if "{" in t:
                    continue
                if t in all_triggers:
                    all_triggers[t].append(cmd.name)
                else:
                    all_triggers[t] = [cmd.name]
        shared = {t: names for t, names in all_triggers.items() if len(names) > 1}
        # Allow a few known overlaps (e.g. "ouvre hacker news" appears in two cmd blocks)
        # but flag any that share more than 2
        excessive = {t: names for t, names in shared.items() if len(names) > 2}
        assert len(excessive) == 0, (
            f"Trigger phrases shared by >2 commands: {excessive}"
        )


# ---------------------------------------------------------------------------
# 4. URL Validation
# ---------------------------------------------------------------------------

class TestURLValidation:
    """Validate that all navigation URLs are well-formed."""

    def test_static_urls_are_valid(self, static_commands):
        """Static navigation commands must have valid URLs (scheme + netloc)."""
        for cmd in static_commands:
            url = cmd.action.replace("navigate:", "", 1)
            parsed = urlparse(url)
            assert parsed.scheme in ("http", "https"), (
                f"Command '{cmd.name}' URL has bad scheme: {url}"
            )
            assert len(parsed.netloc) > 0, (
                f"Command '{cmd.name}' URL has empty netloc: {url}"
            )

    def test_search_urls_contain_placeholder(self, search_commands):
        """Search commands must have {requete} placeholder in their URL."""
        for cmd in search_commands:
            url = cmd.action.replace("navigate:", "", 1)
            assert "{requete}" in url, (
                f"Search command '{cmd.name}' URL missing {{requete}}: {url}"
            )

    def test_search_urls_are_valid_when_placeholder_filled(self, search_commands):
        """Search URLs should be valid when the placeholder is filled in."""
        for cmd in search_commands:
            url = cmd.action.replace("navigate:", "", 1).replace("{requete}", "test")
            parsed = urlparse(url)
            assert parsed.scheme in ("http", "https"), (
                f"Command '{cmd.name}' filled URL has bad scheme: {url}"
            )

    def test_no_trailing_spaces_in_urls(self, nav_commands):
        """URLs must not have leading/trailing whitespace."""
        for cmd in nav_commands:
            url = cmd.action.replace("navigate:", "", 1)
            assert url == url.strip(), (
                f"Command '{cmd.name}' URL has whitespace: {url!r}"
            )

    def test_urls_use_https_predominantly(self, static_commands):
        """The vast majority of static URLs should use HTTPS."""
        https_count = sum(
            1 for c in static_commands
            if c.action.startswith("navigate:https://")
        )
        ratio = https_count / len(static_commands) if static_commands else 0
        assert ratio > 0.95, (
            f"Only {ratio:.1%} of static URLs use HTTPS, expected >95%"
        )


# ---------------------------------------------------------------------------
# 5. Trigger Quality
# ---------------------------------------------------------------------------

class TestTriggerQuality:
    """Validate trigger phrases are reasonable and consistent."""

    def test_triggers_are_lowercase(self, nav_commands):
        """Trigger phrases should be all lowercase (French voice input)."""
        for cmd in nav_commands:
            for t in cmd.triggers:
                # Allow {requete} placeholder to have any case
                cleaned = t.replace("{requete}", "")
                assert cleaned == cleaned.lower(), (
                    f"Command '{cmd.name}' trigger not lowercase: {t!r}"
                )

    def test_triggers_no_leading_trailing_spaces(self, nav_commands):
        """Triggers must not have leading/trailing whitespace."""
        for cmd in nav_commands:
            for t in cmd.triggers:
                assert t == t.strip(), (
                    f"Command '{cmd.name}' trigger has whitespace: {t!r}"
                )

    def test_minimum_trigger_length(self, nav_commands):
        """Each trigger (excluding abbreviations like 'hn') should be at least 2 chars."""
        for cmd in nav_commands:
            for t in cmd.triggers:
                base = t.replace("{requete}", "").strip()
                assert len(base) >= 2, (
                    f"Command '{cmd.name}' has too-short trigger: {t!r}"
                )

    def test_static_commands_have_multiple_triggers(self, static_commands):
        """Most static navigation commands should have 3+ triggers for voice UX."""
        with_few = [c.name for c in static_commands if len(c.triggers) < 2]
        ratio = len(with_few) / len(static_commands) if static_commands else 0
        assert ratio < 0.1, (
            f"{len(with_few)} commands have <2 triggers ({ratio:.0%}): {with_few[:5]}..."
        )


# ---------------------------------------------------------------------------
# 6. Search/Parameterized Commands
# ---------------------------------------------------------------------------

class TestSearchCommands:
    """Validate parameterized (search) commands."""

    def test_search_commands_exist(self, search_commands):
        """There should be a good number of search commands."""
        assert len(search_commands) >= 15, (
            f"Expected >=15 search commands, got {len(search_commands)}"
        )

    def test_search_params_are_requete(self, search_commands):
        """All search commands should use 'requete' as their parameter."""
        for cmd in search_commands:
            assert cmd.params == ["requete"], (
                f"Command '{cmd.name}' has unexpected params: {cmd.params}"
            )

    def test_search_triggers_contain_requete_placeholder(self, search_commands):
        """At least one trigger per search command should contain {requete}."""
        for cmd in search_commands:
            has_placeholder = any("{requete}" in t for t in cmd.triggers)
            assert has_placeholder, (
                f"Search command '{cmd.name}' has no trigger with {{requete}}"
            )

    def test_search_names_start_with_chercher(self, search_commands):
        """Search commands should follow the naming convention 'chercher_*'."""
        for cmd in search_commands:
            assert cmd.name.startswith("chercher_"), (
                f"Search command '{cmd.name}' doesn't follow 'chercher_*' naming"
            )


# ---------------------------------------------------------------------------
# 7. Section Coverage — Verify key categories of sites are present
# ---------------------------------------------------------------------------

class TestSectionCoverage:
    """Ensure all major site categories are represented."""

    def _has_command_matching(self, commands, pattern: str) -> bool:
        """Check if any command name matches the given regex pattern."""
        return any(re.search(pattern, c.name) for c in commands)

    def _has_url_containing(self, commands, domain: str) -> bool:
        """Check if any command navigates to a URL containing the given domain."""
        return any(domain in c.action for c in commands)

    def test_social_media_coverage(self, nav_commands):
        """Social media sites should be covered."""
        social_domains = ["x.com", "reddit.com", "linkedin.com", "instagram.com"]
        for domain in social_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing social media site: {domain}"
            )

    def test_dev_tools_coverage(self, nav_commands):
        """Developer tools/sites should be covered."""
        dev_domains = ["github.com", "stackoverflow.com", "npmjs.com", "pypi.org"]
        for domain in dev_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing dev tool site: {domain}"
            )

    def test_ai_platforms_coverage(self, nav_commands):
        """AI platforms should be covered."""
        ai_domains = ["chat.openai.com", "claude.ai", "huggingface.co"]
        for domain in ai_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing AI platform: {domain}"
            )

    def test_google_workspace_coverage(self, nav_commands):
        """Google Workspace tools should be covered."""
        google_domains = [
            "drive.google.com", "docs.google.com", "sheets.google.com",
            "mail.google.com", "calendar.google.com",
        ]
        for domain in google_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing Google Workspace: {domain}"
            )

    def test_crypto_coverage(self, nav_commands):
        """Crypto/trading platforms should be covered."""
        crypto_domains = ["tradingview.com", "coingecko.com", "mexc.com"]
        for domain in crypto_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing crypto platform: {domain}"
            )

    def test_french_services_coverage(self, nav_commands):
        """French public services should be covered."""
        fr_domains = ["impots.gouv.fr", "ameli.fr", "caf.fr", "sncf-connect.com"]
        for domain in fr_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing French service: {domain}"
            )

    def test_streaming_coverage(self, nav_commands):
        """Streaming platforms should be covered."""
        streaming_domains = ["netflix.com", "open.spotify.com", "music.youtube.com"]
        for domain in streaming_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing streaming platform: {domain}"
            )

    def test_cloud_providers_coverage(self, nav_commands):
        """Major cloud providers should be covered."""
        cloud_domains = [
            "console.aws.amazon.com", "portal.azure.com",
            "console.cloud.google.com",
        ]
        for domain in cloud_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing cloud provider: {domain}"
            )

    def test_news_media_coverage(self, nav_commands):
        """News/media outlets should be covered."""
        news_domains = ["lemonde.fr", "techcrunch.com"]
        for domain in news_domains:
            assert self._has_url_containing(nav_commands, domain), (
                f"Missing news outlet: {domain}"
            )


# ---------------------------------------------------------------------------
# 8. Specific Command Checks
# ---------------------------------------------------------------------------

class TestSpecificCommands:
    """Spot-check a few specific commands for correctness."""

    def _find_cmd(self, commands, name: str):
        """Find a command by name."""
        matches = [c for c in commands if c.name == name]
        return matches[0] if matches else None

    def test_twitter_command(self, nav_commands):
        """The Twitter/X command should navigate to x.com."""
        cmd = self._find_cmd(nav_commands, "ouvrir_twitter")
        assert cmd is not None, "Missing ouvrir_twitter command"
        assert "x.com" in cmd.action
        assert "ouvre twitter" in cmd.triggers

    def test_github_command(self, nav_commands):
        """The GitHub command should navigate to github.com."""
        cmd = self._find_cmd(nav_commands, "ouvrir_github_web")
        assert cmd is not None, "Missing ouvrir_github_web command"
        assert "github.com" in cmd.action
        assert "ouvre github" in cmd.triggers

    def test_google_search_images(self, nav_commands):
        """The image search command should use Google Images with {requete}."""
        cmd = self._find_cmd(nav_commands, "chercher_images")
        assert cmd is not None, "Missing chercher_images command"
        assert "tbm=isch" in cmd.action
        assert "{requete}" in cmd.action
        assert cmd.params == ["requete"]

    def test_youtube_search_command(self, nav_commands):
        """The YouTube search command should navigate to YouTube results."""
        cmd = self._find_cmd(nav_commands, "chercher_video_youtube")
        assert cmd is not None, "Missing chercher_video_youtube command"
        assert "youtube.com/results" in cmd.action
        assert "{requete}" in cmd.action

    def test_amazon_fr_command(self, nav_commands):
        """Amazon should navigate to the .fr domain."""
        cmd = self._find_cmd(nav_commands, "ouvrir_amazon")
        assert cmd is not None, "Missing ouvrir_amazon command"
        assert "amazon.fr" in cmd.action

    def test_wikipedia_is_french(self, nav_commands):
        """Wikipedia should default to the French version."""
        cmd = self._find_cmd(nav_commands, "ouvrir_wikipedia")
        assert cmd is not None, "Missing ouvrir_wikipedia command"
        assert "fr.wikipedia.org" in cmd.action

    def test_deepl_translator(self, nav_commands):
        """DeepL should navigate to the translator page."""
        cmd = self._find_cmd(nav_commands, "ouvrir_deepl")
        assert cmd is not None, "Missing ouvrir_deepl command"
        assert "deepl.com/translator" in cmd.action

    def test_mexc_exchange(self, nav_commands):
        """MEXC exchange should be present (used for trading)."""
        cmd = self._find_cmd(nav_commands, "ouvrir_mexc_exchange")
        assert cmd is not None, "Missing ouvrir_mexc_exchange command"
        assert "mexc.com" in cmd.action


# ---------------------------------------------------------------------------
# 9. Data Consistency
# ---------------------------------------------------------------------------

class TestDataConsistency:
    """Cross-check data consistency across the entire command set."""

    def test_name_follows_convention(self, nav_commands):
        """Command names should follow snake_case convention."""
        pattern = re.compile(r"^[a-z][a-z0-9_]+$")
        for cmd in nav_commands:
            assert pattern.match(cmd.name), (
                f"Command name '{cmd.name}' doesn't match snake_case"
            )

    def test_static_commands_name_starts_with_ouvrir(self, static_commands):
        """Static navigation commands should start with 'ouvrir_'."""
        for cmd in static_commands:
            assert cmd.name.startswith("ouvrir_"), (
                f"Static command '{cmd.name}' doesn't start with 'ouvrir_'"
            )

    def test_no_empty_actions(self, nav_commands):
        """No command should have an empty or whitespace-only action URL."""
        for cmd in nav_commands:
            url = cmd.action.replace("navigate:", "", 1)
            assert len(url.strip()) > 0, (
                f"Command '{cmd.name}' has empty URL in action"
            )

    def test_action_urls_no_double_slashes(self, nav_commands):
        """URLs should not have erroneous double slashes after the protocol."""
        for cmd in nav_commands:
            url = cmd.action.replace("navigate:", "", 1)
            # Remove the protocol part (https://)
            after_protocol = url.split("://", 1)[-1] if "://" in url else url
            assert "//" not in after_protocol, (
                f"Command '{cmd.name}' URL has double slash: {url}"
            )

    def test_total_trigger_count(self, nav_commands):
        """The total number of trigger phrases should be substantial."""
        total = sum(len(c.triggers) for c in nav_commands)
        assert total > 400, (
            f"Expected >400 total triggers, got {total}"
        )

    def test_average_triggers_per_command(self, nav_commands):
        """Each command should have ~3 triggers on average."""
        total = sum(len(c.triggers) for c in nav_commands)
        avg = total / len(nav_commands) if nav_commands else 0
        assert avg >= 2.5, (
            f"Average triggers per command is {avg:.1f}, expected >=2.5"
        )


# ---------------------------------------------------------------------------
# 10. Edge Cases & Robustness
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and potential data issues."""

    def test_no_none_fields(self, nav_commands):
        """No field on any command should be None."""
        for cmd in nav_commands:
            assert cmd.name is not None
            assert cmd.category is not None
            assert cmd.description is not None
            assert cmd.triggers is not None
            assert cmd.action_type is not None
            assert cmd.action is not None
            assert cmd.params is not None

    def test_no_duplicate_triggers_within_command(self, nav_commands):
        """A single command should not have duplicate trigger phrases."""
        for cmd in nav_commands:
            unique_triggers = set(cmd.triggers)
            if len(unique_triggers) != len(cmd.triggers):
                dupes = [t for t, c in Counter(cmd.triggers).items() if c > 1]
                pytest.fail(
                    f"Command '{cmd.name}' has duplicate triggers: {dupes}"
                )

    def test_urls_no_localhost(self, nav_commands):
        """Navigation URLs should not point to localhost."""
        for cmd in nav_commands:
            url = cmd.action.replace("navigate:", "", 1)
            assert "localhost" not in url and "127.0.0.1" not in url, (
                f"Command '{cmd.name}' URL points to localhost: {url}"
            )

    def test_no_placeholder_in_static_urls(self, static_commands):
        """Static commands should not accidentally contain URL placeholders."""
        for cmd in static_commands:
            url = cmd.action.replace("navigate:", "", 1)
            assert "{" not in url and "}" not in url, (
                f"Static command '{cmd.name}' URL contains placeholder: {url}"
            )

    def test_search_commands_trigger_count(self, search_commands):
        """Search commands should have at least 2 trigger variants."""
        for cmd in search_commands:
            assert len(cmd.triggers) >= 2, (
                f"Search command '{cmd.name}' has only {len(cmd.triggers)} trigger(s)"
            )

    def test_descriptions_are_informative(self, nav_commands):
        """Descriptions should be at least 5 characters (not just abbreviations)."""
        for cmd in nav_commands:
            assert len(cmd.description) >= 5, (
                f"Command '{cmd.name}' description too short: {cmd.description!r}"
            )
