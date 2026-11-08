"""Exercise the installed candidate without credentials, network, or persistent data."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import nanobot.agent.tools.shell as shell_module
import nanobot.channels.slack.runtime as slack_module
from nanobot.agent.tools.registry import ToolRegistry, is_tool_error_result
from nanobot.agent.tools.shell import ExecTool
from nanobot.bus.queue import MessageBus
from nanobot.channels.websocket.runtime import WebSocketChannel  # noqa: F401


async def main() -> None:
    expected = os.environ["EXPECTED_SHELL_SHA"]
    for path in [Path(shell_module.__file__), Path("/app/nanobot/agent/tools/shell.py")]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
    for path in [Path(slack_module.__file__), Path("/app/nanobot/channels/slack/runtime.py")]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == os.environ["EXPECTED_SLACK_SHA"], path
    assert Path("/app/nanobot/web/dist/index.html").is_file()
    assert shutil.which("ssh")
    assert shutil.which("git")
    assert os.getuid() != 0
    with tempfile.TemporaryDirectory() as workspace:
        tool = ExecTool(working_dir=workspace, restrict_to_workspace=True)
        registry = ToolRegistry()
        registry.register(tool)
        properties = registry.get_definitions()[0]["function"]["parameters"]["properties"]
        arguments = {"command": "printf fork-image-ok", "max_runtime": 10}
        # Match the observed model pattern: fill both names if both are advertised.
        if "timeout" in properties:
            arguments["timeout"] = 10
        result = await registry.execute("exec", arguments)
        assert not is_tool_error_result(result), result
        assert "fork-image-ok\nExit code: 0" in str(result), result
    bus = MessageBus()
    channel = slack_module.SlackChannel(
        slack_module.SlackConfig(enabled=True, group_policy="open"), bus,
    )
    client = SimpleNamespace(send_socket_mode_response=AsyncMock())
    event = {
        "type": "message",
        "user": "UAPP",
        "bot_id": "BAPP",
        "channel": "C123",
        "channel_type": "channel",
        "text": "notification",
        "ts": "1700000000.000100",
    }
    await channel._on_socket_request(
        client,
        SimpleNamespace(type="events_api", envelope_id="bot", payload={"event": event}),
    )
    assert client.send_socket_mode_response.await_count == 1
    assert bus.inbound_size == 0, "Bot notification reached the agent"
    human = {key: value for key, value in event.items() if key != "bot_id"}
    await channel._on_socket_request(
        client,
        SimpleNamespace(type="events_api", envelope_id="human", payload={"event": human}),
    )
    assert client.send_socket_mode_response.await_count == 2
    assert bus.inbound_size == 1, "Human message did not reach the agent"
    assert bus.inbound.get_nowait().content == "notification"
    print("PASS: installed code, WebUI assets, channel imports, SSH, real exec, and Slack bot filtering")


if __name__ == "__main__":
    asyncio.run(main())
