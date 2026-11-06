from fastmcp import Client
import asyncio
import httpx2 as httpx
import os

CLIENT_ID = "mcp:huutoapp:admin"
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
SCOPES = ["mcp:huutoapp:public", "mcp:huutoapp:admin"]

def get_jwt(client_id: str, client_secret: str, scopes: list[str]) -> str:

    with httpx.Client() as client:
        url = "https://keycloak.anyman.homelab:8443/realms/homelab/protocol/openid-connect/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": " ".join(scopes)
        }
        response = httpx.post(url, data=payload, verify=False)
        token_data = response.json()

        if response.status_code != 200:
            return ""        

        jwt_token = token_data.get("access_token")
        print(f"Token: {jwt_token}")
        return jwt_token



async def main():

    if jwt := get_jwt(CLIENT_ID, CLIENT_SECRET, SCOPES):
        async with Client("http://localhost:8000/mcp", auth=jwt) as client:
            tools = await client.list_tools()
            print(f"Tools: {[t.name for t in tools]}")

            for t in tools:
                print(t) 
                print(t.name)
                print(t.description)

            result = await client.call_tool("list_titles", {"condition": "like-new", "status": "open"})
            print(f"Tool list_titles result: {result}")

            result = await client.call_tool("search_titles", {"search_criteria": "Bronson"})
            print(f"Tool search_titles result: {result}")

if __name__ == "__main__":
    asyncio.run(main())