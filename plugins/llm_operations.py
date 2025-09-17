import os

import instructor
from models import Findings


SYSTEM_PROMPT = """
You are an expert electrical engineer and PCB designer with extensive experience in analyzing KiCad netlists.
You are meticulous and detail-oriented, ensuring that every aspect of the netlist is thoroughly examined for potential issues and improvements.
"""

USER_PROMPT_TEMPLATE = """
Given the following KiCad netlist, identify potential issues and suggest improvements.
Focus on the schematic only, ignore everything related to PCB layout, including footprint assignments.

<netlist>
{netlist}
</netlist>
"""

class LLMOperations:
    def __init__(self, model_name, api_key):
        if model_name.startswith("openai/"):
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            self.client = instructor.from_provider(model_name)
        else:
            raise ValueError(f"Provider {model_name} not supported with instructor library")

    def analyze_netlist(self, netlist: str) -> Findings:
        response = self.client.chat.completions.create(
            response_model=Findings,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(netlist=netlist)}
            ]
        )
        return response