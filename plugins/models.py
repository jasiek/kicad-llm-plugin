from pydantic import BaseModel
from typing import List

class FindingLevel:
    FATAL = "Fatal"
    MAJOR = "Major"
    MINOR = "Minor"
    BEST_PRACTICE = "Best Practice"
    NICE_TO_HAVE = "Nice To Have"

    ALL_LEVELS = [FATAL, MAJOR, MINOR, BEST_PRACTICE, NICE_TO_HAVE]

class Finding(BaseModel):
    id: int
    level: str
    description: str
    recommendation: str
    reference: str

class Findings(BaseModel):
    findings: List[Finding]