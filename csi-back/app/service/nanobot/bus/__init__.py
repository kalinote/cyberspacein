"""Message bus module for decoupled channel-agent communication."""

from app.service.nanobot.bus.events import InboundMessage, OutboundMessage
from app.service.nanobot.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
