"""Synthetic wire data only: no Qloo responses or real user tastes."""
import asyncio
from uuid import UUID
import httpx
import pytest
from bookbridge.qloo import Entity, QlooClient, QlooError
from bookbridge.core import find_shared
from bookbridge.models import Anchor
from bookbridge.app import app, hits, global_hits


def wire(n=1, name='Invented Wire Book'):
 return {'id':f'AAAAAAAA-AAAA-4AAA-8AAA-{n:012d}', 'name':name, 'type':'urn:entity:book'}

@pytest.mark.asyncio
async def test_insights_exact_pool_contract_and_normalized_uuid():
 async def handler(req):
  assert req.url.host=='hackathon.api.qloo.com'
  assert req.headers['X-Api-Key']=='private-test-key'
  assert req.url.path=='/v2/insights'
  assert dict(req.url.params)=={'filter.type':'urn:entity:book','signal.interests.entities':'11111111-1111-4111-8111-111111111111','take':'40','filter.results.entities':'aaaaaaaa-aaaa-4aaa-8aaa-000000000001'}
  return httpx.Response(200,json={'results':{'entities':[wire()]}})
 c=QlooClient('private-test-key', transport=httpx.MockTransport(handler))
 rows=await c.books(['11111111-1111-4111-8111-111111111111'],40,['aaaaaaaa-aaaa-4aaa-8aaa-000000000001'])
 assert rows[0].id=='aaaaaaaa-aaaa-4aaa-8aaa-000000000001'

@pytest.mark.asyncio
@pytest.mark.parametrize('status',[301,401,403,429,500])
async def test_upstream_status_redaction_and_no_redirect(status):
 calls=[]
 async def handler(req):
  calls.append(req)
  return httpx.Response(status, text='private-test-key',headers={'Location':'https://foreign.invalid/?key=private-test-key'})
 c=QlooClient('private-test-key',transport=httpx.MockTransport(handler))
 with pytest.raises(QlooError) as e: await c.search('query','book')
 assert 'private-test-key' not in str(e.value) and len(calls)==1

@pytest.mark.asyncio
@pytest.mark.parametrize('problem',['large','json','type','uuid','filter','protocol','timeout','count'])
async def test_bad_wire_fails_closed(problem):
 async def handler(req):
  if problem=='protocol': raise httpx.RemoteProtocolError('private-test-key')
  if problem=='timeout': raise httpx.ReadTimeout('private-test-key')
  if problem=='large': return httpx.Response(200,content=b'x'*101)
  if problem=='json': return httpx.Response(200,content=b'{')
  row=wire()
  if problem=='type': row['type']='urn:entity:movie'
  if problem=='uuid': row['id']='not-an-id'
  return httpx.Response(200,json={'results':{'entities':[row]*41 if problem=='count' else [row]}})
 c=QlooClient('private-test-key',max_bytes=100 if problem=='large' else 100000,transport=httpx.MockTransport(handler))
 with pytest.raises(QlooError) as e:
  await c.books(['11111111-1111-4111-8111-111111111111'],40,['bbbbbbbb-bbbb-4bbb-8bbb-000000000001'] if problem=='filter' else None)
 assert 'private-test-key' not in str(e.value)

@pytest.mark.asyncio
async def test_atomic_budget_cache_ttl_and_rolling_window():
 count=0; now=[100.]
 async def handler(req):
  nonlocal count
  count+=1
  await asyncio.sleep(0)
  return httpx.Response(200,json={'results':[]})
 c=QlooClient('test',transport=httpx.MockTransport(handler),call_budget=2,cache_ttl=10,clock=lambda:now[0])
 await asyncio.gather(*(c.search('same','book') for _ in range(5)))
 assert count==1
 now[0]+=11; await c.search('same','book'); assert count==2
 with pytest.raises(QlooError): await c.search('other','book')
 assert count==2
 now[0]+=86400; await c.search('other','book'); assert count==3


def anchor(n): return Anchor(id=UUID(f'10000000-0000-4000-8000-{n:012d}'),name='Invented Anchor',kind='movie')
def entity(n): return Entity(f'20000000-0000-4000-8000-{n:012d}',f'Invented Book {n}','book')
class Ranks:
 def __init__(self, rows): self.rows=rows; self.pools=[]
 async def books(self,seeds,take=20,candidates=None):
  if candidates is None: return [entity(i) for i in range(1,6)]
  self.pools.append(tuple(candidates))
  return [entity(i) for i in self.rows[0 if seeds[0].endswith('1') else 1]]

@pytest.mark.asyncio
async def test_maximin_expected_order_stretch_and_member_swap():
 t=Ranks([[1,2,3,4,5],[2,3,4,5,1]])
 r=await find_shared(t,[[anchor(1)],[anchor(2)]],2)
 assert [x['name'] for x in r['shared']]==['Invented Book 2','Invented Book 3']
 assert r['stretch']['name']=='Invented Book 1' and r['stretch']['rank_gap']==4
 assert t.pools[0]==t.pools[1] and len(t.pools[0])==5
 swapped=await find_shared(Ranks(t.rows),[[anchor(2)],[anchor(1)]],2)
 assert [x['id'] for x in swapped['shared']]==[x['id'] for x in r['shared']]
 assert all(x['missing']==0 for x in r['coverage'])

@pytest.mark.asyncio
async def test_duplicates_missing_and_equal_rank_not_stretch():
 r=await find_shared(Ranks([[1,1,2],[1,2]]),[[anchor(1)],[anchor(2)]],1)
 assert r['stretch'] is None
 assert [x['returned'] for x in r['coverage']]==[2,2]
 assert r['coverage'][0]['missing']==3

@pytest.mark.asyncio
async def test_rescore_outside_pool_rejected():
 with pytest.raises(QlooError): await find_shared(Ranks([[1,6],[1,2]]),[[anchor(1)],[anchor(2)]])

@pytest.mark.asyncio
async def test_body_caps_chunked_limits_and_no_key_redaction(monkeypatch):
 monkeypatch.delenv('QLOO_API_KEY',raising=False)
 hits.clear();global_hits.clear()
 async def chunks():
  yield b' '*8000
  yield b' '*9000
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  assert (await c.post('/api/search',content=chunks(),headers={'Content-Type':'application/json'})).status_code==413
  assert (await c.post('/api/search',content=b' '*17000)).status_code==413
  r=await c.post('/api/search',json={'query':'x','kind':'not-a-kind-private-input'})
  assert r.status_code==422 and 'private-input' not in r.text
  for _ in range(27): assert (await c.get('/api/status')).status_code==200
  assert (await c.get('/api/status')).status_code==429
 hits.clear();global_hits.clear()

@pytest.mark.asyncio
async def test_same_title_ids_ranked_before_title_dedup_and_swap():
 class Editions:
  async def books(self,seeds,take=20,candidates=None):
   rows=[Entity(entity(1).id,'Invented Same Title','book'),Entity(entity(2).id,'Invented Same Title','book'),entity(3)]
   if candidates is None: return [rows[0],rows[2]] if seeds[0].endswith('1') else [rows[1],rows[2]]
   return rows if seeds[0].endswith('1') else [rows[1],rows[0],rows[2]]
 a=await find_shared(Editions(),[[anchor(1)],[anchor(2)]],3)
 b=await find_shared(Editions(),[[anchor(2)],[anchor(1)]],3)
 assert a['candidate_pool_size']==3
 assert [x['id'] for x in a['shared']]==[x['id'] for x in b['shared']]
 assert len(a['shared'])==2 and a['shared'][0]['id']==entity(1).id

@pytest.mark.asyncio
async def test_total_deadline_covers_slow_stream():
 class Slow(httpx.AsyncByteStream):
  async def __aiter__(self):
   for _ in range(50):
    await asyncio.sleep(.005)
    yield b' '
 async def handler(req): return httpx.Response(200,stream=Slow())
 c=QlooClient('test',timeout=.02,transport=httpx.MockTransport(handler))
 with pytest.raises(QlooError,match='timed out'): await c.search('x','book')
