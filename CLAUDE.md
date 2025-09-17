# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a KiCad LLM plugin for schematic analysis that provides AI-powered schematic verification and analysis. The plugin integrates with KiCad 9.0 as a PCB editor action and uses various LLM providers (OpenAI, Google Gemini) to analyze netlists and provide findings categorized by severity levels.

## Architecture

### Core Components

- **`core.py`**: Main analysis pipeline - orchestrates netlist export and LLM analysis
- **`gui.py`**: wxPython GUI with configuration dialog, progress tracking, and results display
- **`kicad_operations.py`**: KiCad integration layer using kipy library for netlist export
- **`llm_operations.py`**: LLM provider abstraction using instructor library for structured outputs
- **`models.py`**: Pydantic data models for findings and severity levels
- **`config.py`**: JSON-based configuration management with per-provider API key storage

### Data Flow

1. User triggers analysis from KiCad PCB editor
2. GUI launches with threaded execution and progress dialog
3. Core pipeline exports netlist via kicad-cli
4. LLM analyzes netlist and returns structured findings
5. Results displayed in GUI with filtering by severity level

### Plugin Integration

- **Entry point**: `gui.py` (defined in `plugin.json`)
- **Scope**: PCB editor only (requires open PCB document to access project)
- **Dependencies**: Listed in `plugins/requirements.txt`

## Development Commands

### Python Interpreter
Use KiCad's Python interpreter for testing:
```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
```

### Testing Core Functionality
Run the core analysis pipeline directly (requires OPENAI_API_KEY environment variable):
```bash
cd plugins
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 core.py
```

### Testing GUI Dialog
Test the GUI dialog without launching from KiCad:
```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gui.py
```

### Dependencies
Install required packages using KiCad's Python:
```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/pip install -r plugins/requirements.txt
```

## Configuration System

### API Keys
- Stored per provider (not per model) in `~/.kicad/kicad_llm_config.json`
- Providers: `openai`, `google`
- Models supported: `openai/gpt-4o-mini`, `google/gemini-2.5-flash-lite`, `google/gemini-2.5-flash`

### Configuration Structure
```json
{
  "selected_model": "openai/gpt-4o-mini",
  "provider_api_keys": {
    "openai": "sk-...",
    "google": "AIza..."
  }
}
```

## Key Design Patterns

### Structured LLM Outputs
- Uses instructor library for Pydantic model validation
- Consistent finding format with ID, level, description, recommendation, reference
- Error handling with graceful fallbacks

### Provider Abstraction
- Model names use `provider/model` format
- Extensible for adding new providers

## Plugin Distribution

### Metadata
- Plugin metadata defined in `metadata.json` for KiCad PCM (Plugin and Content Manager)
- Entry point defined in `gui.py` (referenced by plugin manifest)
- Plugin type: PCB editor action plugin

### Installation
Plugin installed via KiCad's Plugin and Content Manager or manual installation to KiCad's plugin directory

## KiCad Integration Notes

### Critical Limitations
- **PCB document requirement**: Plugin only works when PCB document is open (limitation of kipy API)
- Schematic-only projects cannot be analyzed directly due to API constraints

### Technical Details
- Uses kicad-cli for reliable netlist export from `.kicad_sch` files
- Requires Python 3.9+ compatibility (KiCad's Python version)
- Netlist export process: PCB document → project path → schematic file → kicad-cli → netlist