import asyncio
from fastmcp import Client

# Määritä etäpalvelimen URL (korvaa IP ja portti omillasi).
# Huom: FastMCP:n HTTP-palvelin käyttää tyypillisesti /mcp päätepistettä.
REMOTE_SERVER_URL = "http://localhost:8000/mcp"
EXPECTED_TOKEN = "my-super-secret-api-key"

async def main():
    # Luodaan asiakasinstanssi osoitteella
    client = Client(REMOTE_SERVER_URL, auth=EXPECTED_TOKEN)
    
    # Yhteys täytyy avata asynkronisella kontekstinhallinnalla (async with)
    async with client:
        print("Yhteys muodostettu etäpalvelimeen!")
        
        # 1. Listataan kaikki palvelimen tarjoamat työkalut
        tools = await client.list_tools()
        print(f"Löydetyt työkalut: {[t.name for t in tools]}")

        # 2. Kutsutaan jotain palvelimen työkalua (esimerkkinä aiempi 'public'-työkalu)
        for t in tools:
            result = await client.call_tool(t.name, {"user": "Anssi"})
            print(f"Työkalun vastaus: {result}")

if __name__ == "__main__":
    asyncio.run(main())