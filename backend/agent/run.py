import asyncio

from agent.agent import Agent

if __name__ == "__main__":
    agent = Agent()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        pass
    finally:
        print("Application terminated.")
