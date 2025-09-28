from typing import List, Optional

from kicad_operations import export_netlist
from llm_operations import LLMOperations
from models import Finding

def run(model_name, api_key) -> tuple[Optional[List[Finding]], Optional[str]]:
    """Run the schematic analysis and return findings along with project path."""
    facade = LLMOperations(model_name, api_key)
    netlist, project_path = export_netlist()
    if netlist:
        findings_result = facade.analyze_netlist(netlist)
        findings = findings_result.findings if findings_result else []
        return findings, project_path
    return None, None

if __name__ == "__main__":
    import os

    findings, project_path = run("openai/gpt-4o-mini", os.getenv("OPENAI_API_KEY"))
    if findings:
        print(f"Project path: {project_path}")
        for finding in findings:
            print(f"ID: {finding.id}")
            print(f"Level: {finding.level}")
            print(f"Description: {finding.description}")
            print(f"Recommendation: {finding.recommendation}")
            print(f"Reference: {finding.reference}")
            print("-" * 40)
