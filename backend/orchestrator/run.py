import asyncio

from interactem.orchestrator.app import app

if __name__ == "__main__":
    asyncio.run(app.run())
