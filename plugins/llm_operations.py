from llm_interface import llm_from_config
from .models import Findings
from typing import List

llm = llm_from_config(provider="openai", model_name="gpt-4o-mini")

SYSTEM_PROMPT = """
You are an expert electrical engineer and PCB designer with extensive experience in analyzing KiCad netlists.
You are meticulous and detail-oriented, ensuring that every aspect of the netlist is thoroughly examined for potential issues and improvements.
"""

USER_PROMPT_TEMPLATE = """
Given the following KiCad netlist, identify potential issues and suggest improvements.
Focus on the schematic only, ignore everything related to PCB layout, including footprint assignments.
Respond with a list of Findings, where each Finding includes:
- id: A unique identifier for the finding (integer).
- level: The severity level of the finding (one of: Fatal, Major, Minor, Best Practice, Nice To Have).
- description: A brief description of the finding.
- recommendation: A suggested action to address the finding.
- reference: reference to a component

<netlist>
{netlist}
</netlist>
"""

def analyze_netlist(netlist: str) -> Findings:   
    response = llm.generate_pydantic(
        prompt_template=USER_PROMPT_TEMPLATE,
        output_schema=Findings,
        system=SYSTEM_PROMPT,
        netlist=netlist
    )
    
    return response
