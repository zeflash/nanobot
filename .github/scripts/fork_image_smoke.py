"""Exercise the installed candidate without credentials, network, or persistent data."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

import nanobot.agent.tools.shell as shell_module
from nanobot.agent.tools.registry import ToolRegistry, is_tool_error_result
from nanobot.agent.tools.shell import ExecTool
from nanobot.channels.slack.runtime import SlackChannel  # noqa: F401
from nanobot.channels.websocket.runtime import WebSocketChannel  # noqa: F401


async def main() -> None:
    expected = os.environ["EXPECTED_SHELL_SHA"]
    for path in [Path(shell_module.__file__), Path("/app/nanobot/agent/tools/shell.py")]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
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
    print("PASS: installed code, WebUI assets, channel imports, SSH, and real exec")


if __name__ == "__main__":
    asyncio.run(main())
