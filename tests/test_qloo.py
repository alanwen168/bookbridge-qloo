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
