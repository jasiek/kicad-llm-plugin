import subprocess
import os
from kipy import KiCad
from kipy.proto.common.types import DocumentType

# This only works when invoked from a pcb editor, because the way the API is built.
# If you go via .get_open_documents(DocumentType.DOCTYPE_SCHEMATIC) you get a document which is tied to an empty project.
# So then when you call .path on the project you get ''.

def export_netlist():
    kicad = KiCad()
    pcb_docs = kicad.get_open_documents(DocumentType.DOCTYPE_PCB)
    if not pcb_docs:
        print("No PCB document is open.")
        return None, None
    pcb_doc = pcb_docs[0]
    project = pcb_doc.project
    print(project.path)
    if not project or not project.path:
        print("No valid project found.")
        return None, None
    input_file = os.path.join(project.path, project.name + ".kicad_sch")
    output_file = os.path.join(project.path, project.name + ".net")

    kicad_cli_binary = kicad.get_kicad_binary_path("kicad-cli")
    if not kicad_cli_binary:
        print("kicad-cli binary not found.")
        return None, None
    cmd = [
        kicad_cli_binary,
        "sch",
        "export",
        "netlist",
        "-o",
        output_file,
        input_file
    ]


    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.returncode != 0:
            return None, None
        with open(output_file, 'r') as f:
            netlist_content = f.read()
        return netlist_content, project.path
    except subprocess.CalledProcessError as e:
        print(f"Error exporting netlist: {e.stderr} {input_file}")
        return None, None