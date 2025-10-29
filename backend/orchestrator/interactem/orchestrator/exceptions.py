
from pydantic import BaseModel

from interactem.core.models.base import IdType
from interactem.core.models.runtime import RuntimeOperator


class CyclicDependenciesError(Exception):
    pass


class NoAgentsError(Exception):
    pass


class UnassignableOperatorsError(Exception):
    pass


class NetworkPreferenceError(Exception):
    pass


class AssignmentState(BaseModel):
    assignments: dict[IdType, list[RuntimeOperator]]
    operator_networks: dict[IdType, set[str]]
