from core.identity.identity import Identity


def test_identity_exposes_three_layers():
    identity = Identity(
        adaptive_state={"confidence": 0.5},
        autobiographical_history=[{"event_type": "bootstrap"}],
    )

    profile = identity.get_profile()

    assert set(("core", "adaptive", "autobiographical", "metadata")) <= set(profile)
    assert profile["core"]["name"] == identity.NAME
    assert profile["adaptive"]["confidence"] == 0.5
    assert profile["autobiographical"][0]["event_type"] == "bootstrap"


def test_identity_adaptive_and_history_are_separate_from_core():
    identity = Identity()
    identity.update_adaptive(confidence=0.8)
    identity.record_autobiographical_event("validated_change", evidence={"ok": True})

    core = identity.get_core()
    profile = identity.get_profile()

    assert "confidence" not in core
    assert profile["adaptive"]["confidence"] == 0.8
    assert profile["autobiographical"][-1]["event_type"] == "validated_change"
