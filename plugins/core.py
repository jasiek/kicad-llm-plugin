from typing import List, Optional

from kicad_operations import export_netlist
from llm_operations import LLMOperations
from models import Finding

def run(model_name, api_key) -> tuple[Optional[List[Finding]], Optional[str], int]:
    """Run the schematic analysis and return findings, project path, and token usage."""
    facade = LLMOperations(model_name, api_key)
    netlist, project_path = export_netlist()
    if netlist:
        analysis_result = facade.analyze_netlist(netlist)
        findings = analysis_result.findings if analysis_result else []
        token_usage = analysis_result.token_usage if analysis_result else 0
        return findings, project_path, token_usage
    return None, None, 0

if __name__ == "__main__":
    import os

    findings, project_path, token_usage = run("openai/gpt-4o-mini", os.getenv("OPENAI_API_KEY"))
    if findings:
        print(f"Project path: {project_path}")
        print(f"Tokens used: {token_usage}")
        for finding in findings:
            print(f"ID: {finding.id}")
            print(f"Level: {finding.level}")
            print(f"Description: {finding.description}")
            print(f"Recommendation: {finding.recommendation}")
            print(f"Reference: {finding.reference}")
            print("-" * 40)
