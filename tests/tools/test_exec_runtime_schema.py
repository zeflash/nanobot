from __future__ import annotations

import shlex
import subprocess
import sys

import pytest

from nanobot.agent.tools.exec_session import ExecSessionManager
from nanobot.agent.tools.registry import ToolRegistry, is_tool_error_result
from nanobot.agent.tools.shell import ExecTool


def _command() -> str:
    args = [sys.executable, '-c', 'print("exec-schema-ok")']
    return subprocess.list2cmdline(args) if sys.platform == 'win32' else shlex.join(args)


async def test_exec_model_filling_advertised_fields_has_one_runtime(tmp_path):
    manager = ExecSessionManager()
    tool = ExecTool(working_dir=str(tmp_path), session_manager=manager)
    registry = ToolRegistry()
    registry.register(tool)
    # Reproduce a provider that fills every advertised field, including aliases.
    values = {
        'command': _command(), 'cmd': '',
        'working_dir': str(tmp_path), 'workdir': '',
        'max_runtime': 5, 'timeout': 5,
        'shell': None, 'login': False, 'yield_time_ms': 1000,
        'max_output_chars': 1000, 'max_output_tokens': None,
    }
    properties = registry.get_definitions()[0]['function']['parameters']['properties']
    arguments = {name: values[name] for name in properties}
    try:
        result = await registry.execute('exec', arguments)
        assert not is_tool_error_result(result), result
        assert 'exec-schema-ok' in result
        assert 'Exit code: 0' in result
    finally:
        await manager.close_all()


@pytest.mark.parametrize('runtime_name', ['max_runtime', 'timeout'])
async def test_exec_registry_preserves_runtime_parameter_compatibility(tmp_path, runtime_name):
    manager = ExecSessionManager()
    registry = ToolRegistry()
    registry.register(ExecTool(working_dir=str(tmp_path), session_manager=manager))
    try:
        result = await registry.execute('exec', {'command': _command(), runtime_name: 5})
        assert not is_tool_error_result(result), result
        assert 'exec-schema-ok' in result
    finally:
        await manager.close_all()


@pytest.mark.parametrize('runtime_name', ['max_runtime', 'timeout'])
@pytest.mark.parametrize('value', [0, 11])
async def test_exec_registry_checks_hidden_alias_bounds(tmp_path, runtime_name, value):
    registry = ToolRegistry()
    registry.register(ExecTool(working_dir=str(tmp_path), max_runtime_limit=10))
    result = await registry.execute('exec', {'command': _command(), runtime_name: value})
    assert is_tool_error_result(result)
    assert 'Invalid parameters' in result


async def test_exec_registry_still_rejects_conflicting_runtime_parameters(tmp_path):
    registry = ToolRegistry()
    registry.register(ExecTool(working_dir=str(tmp_path)))
    result = await registry.execute('exec', {'command': _command(), 'max_runtime': 5, 'timeout': 5})
    assert is_tool_error_result(result)
    assert 'mutually exclusive' in result
