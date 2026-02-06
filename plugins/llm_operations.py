import os
import hashlib
import json
import tempfile
import time

import instructor
from models import Findings, AnalysisResult, TokenUsage


SYSTEM_PROMPT = """
You are a helpful assistant that helps people find potential issues and improvements in KiCad schematics and netlists.
"""

USER_PROMPT_TEMPLATE = """
You are meticulous and detail-oriented, ensuring that every aspect of the schematic and netlist is thoroughly examined for potential issues and improvements.
Given the following KiCad schematic file and netlist, identify potential issues and suggest improvements.
Focus on the schematic only, ignore everything related to PCB layout, including footprint assignments.

Analyze both the schematic structure and the netlist connectivity to provide comprehensive feedback on:
- Component values and selections
- Circuit topology and connectivity
- Power supply design
- Signal integrity considerations
- Missing connections or components
- Best practices and design improvements

--- Schematic file (.kicad_sch) below ---
{schematic_content}
"""

# --- Netlist (.net) below ---
# {netlist_content}
# """


class LLMOperations:
    def __init__(self, model_name, api_key):
        self.client = instructor.from_provider(model_name, api_key=api_key, mode=None)
        self.model_name = model_name
        self.cache_dir = os.path.join(tempfile.gettempdir(), "kicad_llm_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def analyze_netlist(self, netlist: str) -> AnalysisResult:
        # Start timing the response
        start_time = time.time()

        # Create messages based on provider
        if self.model_name.startswith("google/"):
            # Google models use simple string content
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE + netlist},
            ]
        else:
            # OpenAI and other models support content list with cache control
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT_TEMPLATE},
                        {
                            "type": "text",
                            "text": netlist,
                            "cache_control": {"type": "ephemeral"},
                        },
                    ],
                },
            ]

        response = self.client.chat.completions.create(
            response_model=Findings, messages=messages
        )

        # Calculate response time
        response_time = time.time() - start_time

        # Extract detailed token usage from response
        token_usage = TokenUsage()
        token_usage.response_time_seconds = response_time

        if hasattr(response, "_raw_response") and response._raw_response:
            usage = getattr(response._raw_response, "usage", None)
            if usage:
                token_usage.total_tokens = getattr(usage, "total_tokens", 0)
                token_usage.input_tokens = getattr(usage, "prompt_tokens", 0)
                token_usage.output_tokens = getattr(usage, "completion_tokens", 0)

                # Check for cache-specific token counts (Anthropic models)
                if hasattr(usage, "cache_creation_input_tokens"):
                    token_usage.cache_creation_input_tokens = (
                        usage.cache_creation_input_tokens
                    )
                if hasattr(usage, "cache_read_input_tokens"):
                    token_usage.cache_read_input_tokens = usage.cache_read_input_tokens

        return AnalysisResult(findings=response.findings, token_usage=token_usage)

    def analyze_schematic_and_netlist(
        self, netlist: str, schematic: str = None
    ) -> AnalysisResult:
        """Analyze both schematic file and netlist content together."""
        # Start timing the response
        start_time = time.time()

        # If no schematic content provided, fall back to netlist-only analysis
        if not schematic:
            return self.analyze_netlist(netlist)

        # Format the prompt with both schematic and netlist content
        formatted_prompt = USER_PROMPT_TEMPLATE.format(
            schematic_content=schematic, netlist_content=netlist
        )

        # Create messages based on provider
        if self.model_name.startswith("google/"):
            # Google models use simple string content
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": formatted_prompt},
            ]
        else:
            # OpenAI and other models support content list with cache control
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": formatted_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
            ]

        response = self.client.chat.completions.create(
            response_model=Findings, messages=messages
        )

        # Calculate response time
        response_time = time.time() - start_time

        # Extract detailed token usage from response
        token_usage = TokenUsage()
        token_usage.response_time_seconds = response_time

        if hasattr(response, "_raw_response") and response._raw_response:
            usage = getattr(response._raw_response, "usage", None)
            if usage:
                token_usage.total_tokens = getattr(usage, "total_tokens", 0)
                token_usage.input_tokens = getattr(usage, "prompt_tokens", 0)
                token_usage.output_tokens = getattr(usage, "completion_tokens", 0)

                # Check for cache-specific token counts (Anthropic models)
                if hasattr(usage, "cache_creation_input_tokens"):
                    token_usage.cache_creation_input_tokens = (
                        usage.cache_creation_input_tokens
                    )
                if hasattr(usage, "cache_read_input_tokens"):
                    token_usage.cache_read_input_tokens = usage.cache_read_input_tokens

        return AnalysisResult(findings=response.findings, token_usage=token_usage)
