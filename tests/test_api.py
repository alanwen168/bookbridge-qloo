import httpx, pytest
from bookbridge.app import app

@pytest.mark.asyncio
async def test_sample_end_to_end():
 tr=httpx.ASGITransport(app=app)
 async with httpx.AsyncClient(transport=tr,base_url="http://test") as c:
  s=await c.post('/api/search',json={'query':'Lattice Lanterns','kind':'movie','mode':'sample'})
  assert s.status_code==200 and s.json()['results']
  a=s.json()['results'][0]
  b=(await c.post('/api/search',json={'query':'Harbor','kind':'artist','mode':'sample'})).json()['results'][0]
  r=await c.post('/api/shared',json={'members':[[a],[b]],'mode':'sample','top_k':3})
  assert r.status_code==200 and r.json()['candidate_pool_size']==5

@pytest.mark.asyncio
async def test_no_live_fallback_and_validation(monkeypatch):
 monkeypatch.delenv('QLOO_API_KEY',raising=False)
 tr=httpx.ASGITransport(app=app)
 async with httpx.AsyncClient(transport=tr,base_url='http://test') as c:
  r=await c.post('/api/search',json={'query':'x','kind':'movie','mode':'live'})
  assert r.status_code==503 and 'pending' in r.text and 'sample' not in r.text.lower()
  assert 'secret' not in r.text
  assert (await c.post('/api/search',json={'query':'x'*121,'kind':'movie'})).status_code==422
