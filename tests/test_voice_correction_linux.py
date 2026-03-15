from __future__ import annotations


def test_linux_corrections_loaded():
    """Les corrections Linux STT sont chargees."""
    from src.voice_correction import PHONETIC_GROUPS
    # Check that Linux command groups exist
    linux_terms = ["systemctl", "journalctl", "nvidia", "docker", "pytest", "ollama"]
    found = 0
    for group in PHONETIC_GROUPS:
        canonical = group[0] if isinstance(group, (list, tuple)) else ""
        if canonical.lower() in linux_terms:
            found += 1
    assert found >= 4, f"Seulement {found} termes Linux trouves dans PHONETIC_GROUPS"


def test_voice_correction_basic():
    """correct_voice_text corrige les commandes Linux."""
    try:
        from src.voice_correction import correct_voice_text
        # Test basique — la fonction ne devrait pas crasher
        result = correct_voice_text("verifie la sante du systeme")
        assert isinstance(result, str)
        assert len(result) > 0
    except ImportError:
        import pytest
        pytest.skip("voice_correction not available")
