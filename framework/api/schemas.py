from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class Project(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    status: str
    description: str = ""
    team_members: List[str] = []
    tenant_id: Optional[str] = None


def parse_project(payload):
    return Project.model_validate(payload)
