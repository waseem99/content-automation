from pydantic import BaseModel, ConfigDict


class FrozenRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
