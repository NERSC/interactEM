import asyncio

from interactem.agent.agent import Agent, logger


async def main():
    agent = Agent()
    try:
        await agent.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        logger.info("Application terminated.")


def entrypoint():
    asyncio.run(main())
