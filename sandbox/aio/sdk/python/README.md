# Agent Sandbox Python SDK

A Python SDK for the All-in-One Sandbox API, providing access to sandbox, shell, file, jupyter, nodejs, and mcp services.

## Installation

```bash
pip install agent-sandbox
```

## Usage

```python
from agent_sandbox import Sandbox

client = Sandbox(base_url="http://localhost:8091")

ctx = client.sandbox.get_context()
print(ctx)

result = client.shell.exec_command(command="ls -la")
print(result)
```

## Async Support

The SDK also provides async support through the `AsyncSandbox` class:

```python
import asyncio
from agent_sandbox import AsyncSandbox

async def main():
    client = AsyncSandbox(base_url="http://localhost:8091")
    
    # Get sandbox context
    ctx = await client.sandbox.get_context()
    print(ctx)

    result = await client.shell.exec_command(command="ls -la")
    print(result)

asyncio.run(main())
```

## Features

- **Sandbox**: Access sandbox environment information and installed packages
- **Shell**: Execute shell commands with session management
- **File**: Read, write, search, and manage files
- **Jupyter**: Execute Python code in Jupyter kernels
- **Node.js**: Execute JavaScript code in Node.js environment
- **MCP**: Interact with Model Context Protocol servers

## Requirements

- Python 3.8+
- httpx
- pydantic
- typing_extensions (for Python < 3.10)