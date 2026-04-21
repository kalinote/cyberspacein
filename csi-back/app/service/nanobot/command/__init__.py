"""Slash command routing and built-in handlers."""

from app.service.nanobot.command.builtin import register_builtin_commands
from app.service.nanobot.command.router import CommandContext, CommandRouter

__all__ = ["CommandContext", "CommandRouter", "register_builtin_commands"]
