from pydantic import BaseModel, Field
from typing import List

class FindingLevel:
    FATAL = "Fatal"
    MAJOR = "Major"
    MINOR = "Minor"
    BEST_PRACTICE = "Best Practice"
    NICE_TO_HAVE = "Nice To Have"

    ALL_LEVELS = [FATAL, MAJOR, MINOR, BEST_PRACTICE, NICE_TO_HAVE]

class Finding(BaseModel):
    id: int = Field(..., description="A unique identifier for the finding")
    level: str = Field(
        ..., description="The severity level of the finding (Fatal, Major, Minor, Best Practice, Nice To Have)"
    )
    description: str = Field(..., description="A brief description of the finding")
    recommendation: str = Field(..., description="A suggested action to address the finding")
    reference: str = Field(..., description="Reference to a component or net (e.g., 'U1', 'R5', 'Net CLK')")

class Findings(BaseModel):
    findings: List[Finding] = Field(
        ..., description="List of findings from the schematic analysis"
    )

class TokenUsage(BaseModel):
    """Detailed token usage information."""
    input_tokens: int = Field(default=0, description="Number of input tokens used")
    output_tokens: int = Field(default=0, description="Number of output tokens generated")
    cache_creation_input_tokens: int = Field(default=0, description="Tokens used for cache creation")
    cache_read_input_tokens: int = Field(default=0, description="Tokens read from cache")
    total_tokens: int = Field(default=0, description="Total tokens used")
    response_time_seconds: float = Field(default=0.0, description="Time taken to generate the response in seconds")

    def get_breakdown_text(self) -> str:
        """Return a formatted breakdown of token usage."""
        lines = [f"Total: {self.total_tokens}"]
        if self.input_tokens > 0:
            lines.append(f"Input: {self.input_tokens}")
        if self.output_tokens > 0:
            lines.append(f"Output: {self.output_tokens}")
        if self.cache_creation_input_tokens > 0:
            lines.append(f"Cache creation: {self.cache_creation_input_tokens}")
        if self.cache_read_input_tokens > 0:
            lines.append(f"Cache read: {self.cache_read_input_tokens}")
        if self.response_time_seconds > 0:
            lines.append(f"Time: {self.response_time_seconds:.2f}s")
        return " | ".join(lines)

class AnalysisResult:
    """Container for analysis results including findings and detailed token usage."""
    def __init__(self, findings: List[Finding], token_usage: TokenUsage = None):
        self.findings = findings
        self.token_usage = token_usage or TokenUsage()