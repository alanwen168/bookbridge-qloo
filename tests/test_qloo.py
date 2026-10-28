import httpx, pytest
from bookbridge.qloo import QlooClient,QlooError

@pytest.mark.asyncio
async def test_header_contract_and_shape():
 async def handler(req):
  assert req.headers['X-Api-Key']=='top-secret' and 'top-secret' not in str(req.url)
  assert req.url.path=='/search' and req.url.params['types']=='urn:entity:movie'
  return httpx.Response(200,json={'results':[{'id':'10000000-0000-4000-8000-000000000001','name':'Safe','type':'urn:entity:movie'}]})
 rows=await QlooClient('top-secret',transport=httpx.MockTransport(handler)).search('safe','movie')
 assert rows[0].name=='Safe'

@pytest.mark.asyncio
async def test_unknown_shape_is_failure():
 async def handler(req): return httpx.Response(200,json={'items':[]})
 with pytest.raises(QlooError): await QlooClient('secret',transport=httpx.MockTransport(handler)).search('x','book')

@pytest.mark.asyncio
async def test_search_accepts_wire_types_list():
 async def handler(req):
  return httpx.Response(200,json={'results':[{'entity_id':'20000000-0000-4000-8000-000000000001','name':'Invented Film','types':['urn:entity:movie'],'properties':{}}]})
 rows=await QlooClient('synthetic-key',transport=httpx.MockTransport(handler)).search('invented','movie')
 assert [(row.id,row.name,row.kind) for row in rows]==[('20000000-0000-4000-8000-000000000001','Invented Film','movie')]

@pytest.mark.asyncio
async def test_books_accepts_generic_type_and_book_subtype():
 async def handler(req):
  return httpx.Response(200,json={'success':True,'results':{'entities':[{'entity_id':'30000000-0000-4000-8000-000000000001','name':'Invented Book','type':'urn:entity','subtype':'urn:entity:book','properties':{}}]}})
 rows=await QlooClient('synthetic-key',transport=httpx.MockTransport(handler)).books(['40000000-0000-4000-8000-000000000001'])
 assert [(row.id,row.name,row.kind) for row in rows]==[('30000000-0000-4000-8000-000000000001','Invented Book','book')]

@pytest.mark.asyncio
@pytest.mark.parametrize('entity',[
 {'entity_id':'50000000-0000-4000-8000-000000000001','name':'Wrong Singular','type':'urn:entity:book','types':['urn:entity:movie']},
 {'entity_id':'50000000-0000-4000-8000-000000000002','name':'Mixed Types','types':['urn:entity:movie','urn:entity:book']},
 {'entity_id':'50000000-0000-4000-8000-000000000003','name':'Nonstring Type','types':['urn:entity:movie',None]},
 {'entity_id':'50000000-0000-4000-8000-000000000004','name':'Empty Types','types':[]},
 {'entity_id':'50000000-0000-4000-8000-000000000005','name':'Malformed Types','types':'urn:entity:movie'},
])
async def test_search_rejects_wrong_or_malformed_types(entity):
 async def handler(req): return httpx.Response(200,json={'results':[entity]})
 with pytest.raises(QlooError):
  await QlooClient('synthetic-key',transport=httpx.MockTransport(handler)).search('invented','movie')

@pytest.mark.asyncio
@pytest.mark.parametrize('entity',[
 {'entity_id':'60000000-0000-4000-8000-000000000001','name':'Missing Subtype','type':'urn:entity'},
 {'entity_id':'60000000-0000-4000-8000-000000000002','name':'Wrong Subtype','type':'urn:entity','subtype':'urn:entity:movie'},
 {'entity_id':'60000000-0000-4000-8000-000000000003','name':'Wrong Singular','type':'urn:entity:movie','subtype':'urn:entity:book'},
])
async def test_books_rejects_wrong_or_missing_type_contract(entity):
 async def handler(req): return httpx.Response(200,json={'results':{'entities':[entity]}})
 with pytest.raises(QlooError):
  await QlooClient('synthetic-key',transport=httpx.MockTransport(handler)).books(['70000000-0000-4000-8000-000000000001'])
