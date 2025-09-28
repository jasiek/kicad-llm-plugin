import os

import instructor
from models import Findings


SYSTEM_PROMPT = """
You are a helpful assistant that helps people find potential issues and improvements in KiCad netlists.
"""

USER_PROMPT_TEMPLATE = """
You are meticulous and detail-oriented, ensuring that every aspect of the netlist is thoroughly examined for potential issues and improvements.
Given the following KiCad netlist, identify potential issues and suggest improvements.
Focus on the schematic only, ignore everything related to PCB layout, including footprint assignments.

<netlist>
{netlist}
</netlist>
"""

class LLMOperations:
    def __init__(self, model_name, api_key):
        self.client = instructor.from_provider(model_name, api_key=api_key)

    def analyze_netlist(self, netlist: str) -> Findings:
        response = self.client.chat.completions.create(
            response_model=Findings,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(netlist=netlist)}
            ]
        )
        return response