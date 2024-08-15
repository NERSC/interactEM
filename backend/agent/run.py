import asyncio

from agent.agent import Agent

if __name__ == "__main__":
    agent = Agent()
    asyncio.run(agent.run())
