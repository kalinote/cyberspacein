import aiohttp

async def async_get(url: str, params: dict = None, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, **kwargs) as response:
            return await response.json()
        
async def async_post(url: str, data: dict = None, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, **kwargs) as response:
            return await response.json()
        