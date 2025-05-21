import asyncio

from interactem.agent.broker import app, logger


async def main():
    try:
        await app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        logger.info("Application terminated.")


def entrypoint():
    asyncio.run(main())
