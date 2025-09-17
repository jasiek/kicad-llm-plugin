from typing import List, Optional

from kicad_operations import export_netlist
from llm_operations import LLMOperations
from models import Finding

def run(model_name, api_key) -> Optional[List[Finding]]:
    """Run the schematic analysis and return findings."""
    facade = LLMOperations(model_name, api_key)
    netlist = export_netlist()
    if netlist:
        findings_result = facade.analyze_netlist(netlist)
        return findings_result.findings if findings_result else []
    return None

if __name__ == "__main__":
    import os

    findings = run("openai/gpt-4o-mini", os.getenv("OPENAI_API_KEY"))
    for finding in findings:
        print(f"ID: {finding.id}")
        print(f"Level: {finding.level}")
        print(f"Description: {finding.description}")
        print(f"Recommendation: {finding.recommendation}")
        print(f"Reference: {finding.reference}")
        print("-" * 40)
