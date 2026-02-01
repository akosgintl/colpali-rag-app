from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class Reference(BaseModel):
    id: int = Field(
        description="Sequential numeric identifier for the reference, starting from 1, used for citations in the answer"
    )
    title: str
    filename: str


class FinalResponse(BaseModel):
    model_config = ConfigDict(
        # Suppress warnings for partial objects during streaming
        validate_assignment=True,
    )
    
    references: list[Reference | dict[str, Any]] = Field(
        description="List of unique reference entries indicating where the supporting information was found."
    )
    answer: str = Field(
        description="The complete answer text based solely on the provided context. The answer must include in-text citations in the format [id] corresponding to the references."
    )
    
    @field_serializer('references')
    def serialize_references(self, refs: list[Reference | dict[str, Any]] | None, _info) -> list[dict[str, Any]]:
        """Serialize references, handling both complete Reference objects and partial dicts during streaming."""
        if refs is None:
            return []
        result = []
        for ref in refs:
            if isinstance(ref, Reference):
                result.append(ref.model_dump())
            else:
                # During streaming, instructor may provide partial dicts
                result.append(ref)
        return result
