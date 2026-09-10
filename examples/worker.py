"""Small source fixture for a two-minute handoff. Not executed by kdebt."""

import asyncio


async def fetch_batch(client, urls):
    gate = asyncio.Semaphore(4)

    async def fetch(url):
        async with gate:
            return await client.get(url)

    return await asyncio.gather(*(fetch(url) for url in urls))


async def retry_read(client, key):
    for attempt in range(3):
        try:
            return await client.get(key)
        except TimeoutError:
            await asyncio.sleep(2 ** attempt)
    raise TimeoutError("Read exhausted its retry budget")


def consume(connection):
    try:
        return connection.read()
    finally:
        connection.close()
