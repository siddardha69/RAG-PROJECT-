import asyncio
from neo4j import AsyncGraphDatabase

uri = "neo4j+s://a4338fb7.databases.neo4j.io"
user = "a4338fb7"
password = "10upf86hO77qbT5prB_MCkrRuTDaTKa1pkaasO60xtw"

async def main():
    print(f"Testing Neo4j connection to {uri} with user {user}...")
    try:
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        await driver.verify_connectivity()
        print("Success! Connection verified.")
        await driver.close()
    except Exception as e:
        print(f"Connection failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
