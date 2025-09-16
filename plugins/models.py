from pydantic import BaseModel, Field
from typing import List, Literal

class FindingLevel:
    FATAL = "Fatal"
    MAJOR = "Major"
    MINOR = "Minor"
    BEST_PRACTICE = "Best Practice"
    NICE_TO_HAVE = "Nice To Have"

    ALL_LEVELS = [FATAL, MAJOR, MINOR, BEST_PRACTICE, NICE_TO_HAVE]

class Finding(BaseModel):
    id: int = Field(..., description="A unique identifier for the finding")
    level: Literal["Fatal", "Major", "Minor", "Best Practice", "Nice To Have"] = Field(
        ..., description="The severity level of the finding"
    )
    description: str = Field(..., description="A brief description of the finding")
    recommendation: str = Field(..., description="A suggested action to address the finding")
    reference: str = Field(..., description="Reference to a component or net (e.g., 'U1', 'R5', 'Net CLK')")

class Findings(BaseModel):
    findings: List[Finding] = Field(
        ..., description="List of findings from the schematic analysis"
    )