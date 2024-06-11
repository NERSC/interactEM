from zmglue.agent import Agent


def test_start_operators(init_agent_without_orchestrator: Agent):
    agent = init_agent_without_orchestrator
    processes = agent.start_operators()
    assert len(processes) == len(agent.pipeline.operators)
    for process in processes.values():
        assert process.poll() is None  # Check that the process is still running

    agent.stop()
    agent.shutdown()
