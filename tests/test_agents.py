"""Tests for NPC agents."""
import pytest

from src.agents.base import NPCAgent, NPCResponse
from src.agents.browning import BrowningNPC
from src.initial_state import build_initial_state


class TestNPCAgentBase:
    """Test NPCAgent base class behavior."""

    def test_detect_mood_angry(self):
        agent = BrowningNPC()
        assert agent._detect_mood("该死，我们太慢了") == "angry"

    def test_detect_mood_urgent(self):
        agent = BrowningNPC()
        assert agent._detect_mood("立即起飞，马上") == "urgent"

    def test_detect_mood_neutral(self):
        agent = BrowningNPC()
        assert agent._detect_mood("一切正常") == "neutral"

    def test_detect_urgency_critical(self):
        agent = BrowningNPC()
        assert agent._detect_urgency("立即起飞") == "critical"

    def test_detect_urgency_normal(self):
        agent = BrowningNPC()
        assert agent._detect_urgency("收到") == "normal"


class TestBrowningNPC:
    """Test Browning-specific behavior."""

    def test_build_system_prompt_includes_state(self):
        state = build_initial_state()
        browning = BrowningNPC()
        prompt = browning.build_system_prompt(state)

        assert "Miles R. Browning" in prompt
        assert "04:00" in prompt
        assert "Task Force 16" in prompt
        assert "USS Enterprise" in prompt
        assert "果断" in prompt or "暴躁" in prompt or "Miles R. Browning" in prompt

    def test_build_system_prompt_no_enemy(self):
        state = build_initial_state()
        browning = BrowningNPC()
        prompt = browning.build_system_prompt(state)

        assert "No CONFIRMED enemy contacts" in prompt or "Known enemy" in prompt

    def test_system_prompt_excludes_hidden_data(self):
        state = build_initial_state()
        browning = BrowningNPC()
        prompt = browning.build_system_prompt(state)

        assert "Kido Butai" not in prompt
        assert "Akagi" not in prompt
        assert "30.0N" not in prompt
