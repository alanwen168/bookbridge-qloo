import pytest
from uuid import UUID
from bookbridge.core import find_shared
from bookbridge.models import Anchor
from bookbridge.qloo import Entity

class T:
 async def books(self,seeds,take=20,candidates=None):
  base=[Entity(f"00000000-0000-4000-8000-{i:012d}",n,"book") for i,n in enumerate(["A","B","C"],1)]
  rows=base if seeds[0].endswith("1") else [base[1],base[2]]
  return [x for x in rows if candidates is None or x.id in candidates]

@pytest.mark.asyncio
async def test_same_pool_and_unknown_coverage():
 a=lambda n: Anchor(id=UUID(f"10000000-0000-4000-8000-{n:012d}"),name="x",kind="movie")
 out=await find_shared(T(),[[a(1)],[a(2)]],2)
 assert [x["name"] for x in out["shared"]]==["B","C"]
 assert out["coverage"][1]["missing"]==1
 assert "unknown" in out["method"]
