"""NPC Agent base class."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.llm import LLMClient, get_client
from src.state import GameState

logger = logging.getLogger("midway.npc")


@dataclass
class NPCResponse:
    """NPC response to player input."""

    text: str
    mood: str = "neutral"
    urgency: str = "normal"


class NPCAgent(ABC):
    """Abstract base class for NPC agents.

    Each NPC is an independent LLM session. They do not share conversation
    history — all cross-NPC information flows through the player.
    """

    name: str = ""
    role: str = ""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or get_client()
        self.messages: list[dict] = []

    @abstractmethod
    def build_system_prompt(self, state: GameState) -> str:
        """Build system prompt injected with current state."""
        pass

    def get_state_summary(self, state: GameState) -> dict:
        """Return state summary visible to this NPC."""
        return {
            "game_time": state.clock.game_time.strftime("%H:%M"),
            "task_forces": [
                {
                    "name": tf.name,
                    "course": tf.course,
                    "speed": tf.speed,
                    "carriers": [
                        {
                            "name": c.name,
                            "position": (
                                f"{c.position.lat:.1f}N "
                                f"{abs(c.position.lon):.1f}W"
                            ),
                            "cap": c.cap_strength,
                            "air_groups": [
                                {
                                    "type": ag.type.value,
                                    "count": ag.count,
                                    "status": ag.status.value,
                                    "fuel": ag.fuel_pct,
                                    "ammo": ag.ammo_pct,
                                }
                                for ag in c.air_groups
                            ],
                        }
                        for c in tf.carriers
                    ],
                }
                for tf in state.task_forces
            ],
            "known_enemy": (
                [
                    {
                        "description": e.description,
                        "confidence": e.confidence,
                        "source": e.source,
                    }
                    for e in state.known_enemy
                ]
                if state.known_enemy
                else "None"
            ),
        }

    def chat(
        self,
        player_input: str,
        state: GameState,
        tools: Optional[list] = None,
        tool_handlers: Optional[dict] = None,
    ) -> NPCResponse:
        """Process player input and return NPC response."""
        system_prompt = self.build_system_prompt(state)
        logger.info(f"[{self.name}] System prompt built ({len(system_prompt)} chars)")
        logger.debug(f"[{self.name}] System prompt preview: {system_prompt[:300]}...")

        self.messages.append({"role": "user", "content": player_input})
        logger.info(f"[{self.name}] Player message appended. Total messages: {len(self.messages)}")

        logger.info(f"[{self.name}] Calling LLM... tools={'yes' if tools else 'no'}")
        result = self.client.chat(
            messages=self.messages,
            system_prompt=system_prompt,
            tools=tools,
            tool_handlers=tool_handlers,
        )
        logger.info(f"[{self.name}] LLM response received. Input_tokens={result.input_tokens}, Output_tokens={result.output_tokens}")

        if result.tool_calls:
            for tc in result.tool_calls:
                logger.info(f"[{self.name}] Tool call: {tc.name}({tc.input}) -> {tc.result}")

        text = result.text
        mood = self._detect_mood(text)
        urgency = self._detect_urgency(text)
        logger.info(f"[{self.name}] Detected mood={mood}, urgency={urgency}")
        logger.info(f"[{self.name}] LLM Response:\n{text}")

        self.messages.append({"role": "assistant", "content": text})
        logger.info(f"[{self.name}] Assistant message appended. Response length: {len(text)} chars")

        return NPCResponse(text=text, mood=mood, urgency=urgency)

    def _detect_mood(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["该死", "见鬼", "蠢货", "愤怒"]):
            return "angry"
        if any(w in text_lower for w in ["立即", "马上", "快", "危机"]):
            return "urgent"
        if any(w in text_lower for w in ["担心", "恐怕", "谨慎"]):
            return "concerned"
        return "neutral"

    def _detect_urgency(self, text: str) -> str:
        text_lower = text.lower()
        if any(
            w in text_lower for w in ["立即起飞", "马上", "刻不容缓", "现在"]
        ):
            return "critical"
        if any(w in text_lower for w in ["建议", "应该", "尽快"]):
            return "high"
        return "normal"
