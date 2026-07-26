from abc import abstractmethod
from typing import Dict, Any
from pydantic import BaseModel, ConfigDict


class BaseAction(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    parameters: Dict[str, Any] = None

    @abstractmethod
    async def __call__(self, **kwargs) -> str:
        """Execute the action with given parameters."""

    def to_param(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
