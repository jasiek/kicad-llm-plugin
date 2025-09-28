import os
import hashlib
import json
import tempfile

import instructor
from models import Findings, AnalysisResult


SYSTEM_PROMPT = """
You are a helpful assistant that helps people find potential issues and improvements in KiCad netlists.
"""

USER_PROMPT_TEMPLATE = """
You are meticulous and detail-oriented, ensuring that every aspect of the netlist is thoroughly examined for potential issues and improvements.
Given the following KiCad netlist, identify potential issues and suggest improvements.
Focus on the schematic only, ignore everything related to PCB layout, including footprint assignments.

--- Netlist below ---
"""

class LLMOperations:
    def __init__(self, model_name, api_key):
        self.client = instructor.from_provider(model_name, api_key=api_key)
        self.model_name = model_name
        self.cache_dir = os.path.join(tempfile.gettempdir(), "kicad_llm_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def analyze_netlist(self, netlist: str) -> AnalysisResult:
        response = self.client.chat.completions.create(
            response_model=Findings,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user", "content": [
                        {"type": "text", "text": USER_PROMPT_TEMPLATE},
                        {"type": "text", "text": netlist, "cache_control": { "type": "ephemeral"}}
                    ]
                }
            ]
        )

        # Extract token usage from response
        token_usage = 0
        if hasattr(response, '_raw_response') and response._raw_response:
            usage = getattr(response._raw_response, 'usage', None)
            if usage:
                token_usage = getattr(usage, 'total_tokens', 0)

        return AnalysisResult(findings=response.findings, token_usage=token_usage)