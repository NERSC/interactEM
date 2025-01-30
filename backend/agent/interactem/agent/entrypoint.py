import asyncio

from interactem.agent.agent import Agent


async def main():
    agent = Agent()
    try:
        await agent.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("Application terminated.")


def entrypoint():
    asyncio.run(main())
