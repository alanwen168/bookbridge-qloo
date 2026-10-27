"""Real SDK stdio protocol, no key and no upstream network."""
import os
import sys
from pathlib import Path
import asyncio
import pytest
from mcp import Client, StdioServerParameters

@pytest.mark.asyncio
async def test_actual_stdio_discovery_and_safe_missing_key():
 env={k:v for k,v in os.environ.items() if k in {'PATH','LANG','HOME','SYSTEMROOT'}}
 env['QLOO_API_KEY']=''
 params=StdioServerParameters(command=sys.executable,args=['-m','bookbridge.mcp_server'],cwd=Path(__file__).resolve().parents[1],env=env)
 async with asyncio.timeout(15):
  async with Client(params) as client:
   tools=(await client.list_tools()).tools
   assert {x.name for x in tools}=={'search_taste_anchors','find_shared_read'}
   assert all(x.annotations.read_only_hint for x in tools)
   result=await client.call_tool('search_taste_anchors',{'query':'invented','kind':'book'})
   assert result.is_error
   assert 'pending' in str(result).lower()
