"""Tests for multi-NPC system.

Validates:
- NPC config parameters
- Info scope filtering (each NPC sees only permitted data)
- NPC isolation (independent conversation histories)
- Tool filtering per NPC
"""
import pytest

from src.npc_config import NPC_REGISTRY, NPCConfig
from src.agents.browning import BrowningNPC
from src.agents.murray import MurrayNPC
from src.agents.mitscher import MitscherNPC
from src.agents.radio_officer import RadioOfficerNPC
from src.agents.intel_officer import IntelOfficerNPC
from src.initial_state import build_initial_state


# ─────────────────────────────────────────────────────────────
# NPC Config Tests
# ─────────────────────────────────────────────────────────────

class TestNPCConfig:
    """Test NPC configuration registry."""

    def test_all_npcs_registered(self):
        expected = {"browning", "murray", "mitscher", "radio_officer", "intel_officer"}
        assert set(NPC_REGISTRY.keys()) == expected

    def test_npc_params_in_range(self):
        for npc_id, cfg in NPC_REGISTRY.items():
            assert 0 <= cfg.autonomy <= 10, f"{npc_id} autonomy out of range"
            assert 0 <= cfg.risk_tolerance <= 10, f"{npc_id} risk_tolerance out of range"
            assert 0 <= cfg.initiative <= 10, f"{npc_id} initiative out of range"
            assert 0 <= cfg.competence <= 10, f"{npc_id} competence out of range"

    def test_browning_high_autonomy(self):
        assert NPC_REGISTRY["browning"].autonomy == 8

    def test_radio_officer_low_autonomy(self):
        assert NPC_REGISTRY["radio_officer"].autonomy == 1

    def test_murray_carrier_filter(self):
        assert NPC_REGISTRY["murray"].carrier_filter == "Enterprise"

    def test_mitscher_carrier_filter(self):
        assert NPC_REGISTRY["mitscher"].carrier_filter == "Hornet"


# ─────────────────────────────────────────────────────────────
# Info Scope Tests
# ─────────────────────────────────────────────────────────────

class TestInfoScope:
    """Test that each NPC only sees data within its info_scope."""

    def _get_prompt(self, npc, state):
        return npc.build_system_prompt(state)

    def test_browning_sees_fleet_global(self):
        state = build_initial_state()
        npc = BrowningNPC()
        prompt = npc.build_system_prompt(state)
        # Browning sees both carriers
        assert "Enterprise" in prompt
        assert "Hornet" in prompt

    def test_murray_sees_only_enterprise(self):
        state = build_initial_state()
        npc = MurrayNPC()
        summary = npc.get_state_summary(state)
        # Only Enterprise in the summary
        for tf in summary["task_forces"]:
            for c in tf["carriers"]:
                assert "enterprise" in c["name"].lower()

    def test_mitscher_sees_only_hornet(self):
        state = build_initial_state()
        npc = MitscherNPC()
        summary = npc.get_state_summary(state)
        for tf in summary["task_forces"]:
            for c in tf["carriers"]:
                assert "hornet" in c["name"].lower()

    def test_radio_officer_sees_messages_only(self):
        state = build_initial_state()
        state.incoming_messages.append("TEST MESSAGE: enemy spotted")
        npc = RadioOfficerNPC()
        summary = npc.get_state_summary(state)
        # Should have no fleet data
        assert summary["task_forces"] == []
        assert summary["known_enemy"] == []
        # Should have messages
        assert "incoming_messages" in summary
        assert "TEST MESSAGE" in summary["incoming_messages"][0]

    def test_intel_officer_sees_enemy_not_fleet(self):
        state = build_initial_state()
        npc = IntelOfficerNPC()
        summary = npc.get_state_summary(state)
        # No fleet operational data
        assert summary["task_forces"] == []
        # Can see known_enemy
        assert "known_enemy" in summary

    def test_hidden_data_never_leaks(self):
        """No NPC prompt should contain hidden enemy data."""
        state = build_initial_state()
        npcs = [BrowningNPC(), MurrayNPC(), MitscherNPC(),
                RadioOfficerNPC(), IntelOfficerNPC()]
        for npc in npcs:
            prompt = npc.build_system_prompt(state)
            assert "Kido Butai" not in prompt, f"{npc.name} leaked hidden data"
            assert "Akagi" not in prompt, f"{npc.name} leaked hidden data"


# ─────────────────────────────────────────────────────────────
# Tool Filtering Tests
# ─────────────────────────────────────────────────────────────

class TestToolFiltering:
    """Test that each NPC only has access to its allowed tools."""

    def test_browning_has_all_tools(self):
        npc = BrowningNPC()
        tool_names = {t["function"]["name"] for t in npc.tools}
        assert "query_fleet_status" in tool_names
        assert "execute_action" in tool_names
        assert "propose_recon" in tool_names

    def test_murray_has_limited_tools(self):
        npc = MurrayNPC()
        tool_names = {t["function"]["name"] for t in npc.tools}
        assert "query_fleet_status" in tool_names
        assert "execute_action" in tool_names
        assert "propose_recon" not in tool_names

    def test_radio_officer_has_no_tools(self):
        npc = RadioOfficerNPC()
        assert npc.tools == []
        assert npc.tool_handlers == {}

    def test_intel_officer_query_only(self):
        npc = IntelOfficerNPC()
        tool_names = {t["function"]["name"] for t in npc.tools}
        assert "query_fleet_status" in tool_names
        assert "execute_action" not in tool_names
        assert "propose_recon" not in tool_names


# ─────────────────────────────────────────────────────────────
# NPC Isolation Tests
# ─────────────────────────────────────────────────────────────

class TestNPCIsolation:
    """Test that NPCs have independent conversation histories."""

    def test_separate_message_histories(self):
        browning = BrowningNPC()
        murray = MurrayNPC()
        # They should have independent message lists
        assert browning.messages is not murray.messages

    def test_npc_names_unique(self):
        names = [cfg.name for cfg in NPC_REGISTRY.values()]
        assert len(names) == len(set(names))

    def test_npc_roles_unique(self):
        roles = [cfg.role for cfg in NPC_REGISTRY.values()]
        assert len(roles) == len(set(roles))
