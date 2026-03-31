"""Cover letter file templates exposed from the /templates directory."""

from typing import List

from pydantic import BaseModel, Field


class LetterTemplateItem(BaseModel):
    """One .template file under templates/{folder}/."""

    name: str = Field(
        ...,
        description="Folder/category display name (title-cased, e.g. Formal, Informal).",
    )
    template: str = Field(
        ...,
        description="Full UTF-8 file contents; newlines preserved.",
    )
    index: str = Field(
        ...,
        description="File stem without the .template suffix (e.g. 1, 2).",
    )


class LetterTemplatesResponse(BaseModel):
    templates: List[LetterTemplateItem]
