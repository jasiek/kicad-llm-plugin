from plugins.kicad_operations import export_netlist
from plugins.llm_operations import analyze_netlist

if __name__ == "__main__":
    netlist = export_netlist()
    if netlist:
        findings = analyze_netlist(netlist)
        for finding in findings.findings:
            print(f"ID: {finding.id}")
            print(f"Level: {finding.level}")
            print(f"Description: {finding.description}")
            print(f"Recommendation: {finding.recommendation}")
            print(f"Reference: {finding.reference}")
            print("-" * 40)

