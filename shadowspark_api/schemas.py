from pydantic import BaseModel, ConfigDict, Field


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exception_id: str = Field(min_length=1, max_length=128)


class AnnotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    annotation: str = Field(min_length=1, max_length=2000)
