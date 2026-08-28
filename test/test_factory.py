from customagents.factory import AgentFactory
from agent.events import AgentType


def test_factory_registry_covers_all_agent_types(config):
    for agent_type in AgentType:
        # The registry keys mirror the enum values.
        assert agent_type.value in AgentFactory._agent_registry


def test_factory_unknown_agent_raises(config):
    import pytest

    with pytest.raises(ValueError):
        AgentFactory.create("does_not_exist", config, session=None)
