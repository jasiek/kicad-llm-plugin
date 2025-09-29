import subprocess
import os
from kipy import KiCad
from kipy.proto.common.types import DocumentType

# This only works when invoked from a pcb editor, because the way the API is built.
# If you go via .get_open_documents(DocumentType.DOCTYPE_SCHEMATIC) you get a document which is tied to an empty project.
# So then when you call .path on the project you get ''.

def export_netlist_and_schematic():
    kicad = KiCad()
    pcb_docs = kicad.get_open_documents(DocumentType.DOCTYPE_PCB)
    if not pcb_docs:
        print("No PCB document is open.")
        return None, None, None
    pcb_doc = pcb_docs[0]
    project = pcb_doc.project
    print(project.path)
    if not project or not project.path:
        print("No valid project found.")
        return None, None, None
    input_file = os.path.join(project.path, project.name + ".kicad_sch")
    output_file = os.path.join(project.path, project.name + ".net")

    kicad_cli_binary = kicad.get_kicad_binary_path("kicad-cli")
    if not kicad_cli_binary:
        print("kicad-cli binary not found.")
        return None, None, None
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
            return None, None, None

        # Read netlist content
        with open(output_file, 'r') as f:
            netlist_content = f.read()

        # Read schematic file content
        schematic_content = None
        if os.path.exists(input_file):
            try:
                with open(input_file, 'r', encoding='utf-8') as f:
                    schematic_content = f.read()
            except Exception as e:
                print(f"Warning: Could not read schematic file: {e}")

        return netlist_content, schematic_content, project.path
    except subprocess.CalledProcessError as e:
        print(f"Error exporting netlist: {e.stderr} {input_file}")
        return None, None, None

# Backward compatibility function
def export_netlist():
    """Backward compatibility function that returns only netlist and project path."""
    netlist, schematic, project_path = export_netlist_and_schematic()
    return netlist, project_path