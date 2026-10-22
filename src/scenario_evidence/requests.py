"""Strict request boundaries for the local workbench."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Credentials(Input):
    name: str = Field(min_length=1, max_length=64, pattern=r'^[\w .-]+$')
    password: str = Field(min_length=12, max_length=256)


class NewUser(Credentials):
    role: Literal['author', 'reviewer']


class ProjectInput(Input):
    name: str = Field(min_length=1, max_length=100)


class GenerateInput(Input):
    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=3, max_length=2000)
    count: int = Field(default=3, ge=1, le=20, strict=True)
    seed: int = Field(default=42, ge=0, le=2**31-1, strict=True)
    map_name: str = Field(default='DemoStraight', min_length=1, max_length=64,
                          pattern=r'^[A-Za-z][A-Za-z0-9_]*$')
    kind: Literal['cut_in', 'lead_brake', 'pedestrian_crossing'] | None = None
    engine: Literal['templates', 'openai'] = 'templates'


class ImportInput(Input):
    project_id: str = Field(min_length=1, max_length=64)
    xml: str = Field(min_length=1, max_length=500_000)


class RevisionInput(Input):
    scenario: dict


class ReviewInput(Input):
    decision: Literal['approved', 'rejected']
    note: str = Field(default='', max_length=1000)


class SuiteInput(Input):
    project_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    case_ids: list[str] = Field(min_length=1, max_length=100)


class RunInput(Input):
    suite_id: str = Field(min_length=1, max_length=64)
    mode: Literal['offline', 'carla'] = 'offline'
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[\w-]+$')
