# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a KiCad LLM plugin for schematic analysis. The project is in its early development stage, with the core architecture centered around a `SchematicLLMChecker` module that will integrate with KiCad to provide AI-powered schematic verification and analysis.

## Architecture

- **Root Package**: The main `__init__.py` imports the `SchematicLLMChecker` module
- **SchematicLLMChecker/**: Directory intended to contain the core LLM-based schematic checking functionality
- **Plugin Structure**: Follows Python package structure suitable for KiCad plugin integration

## Development Commands

This project appears to be in initial setup phase. Standard Python development commands should apply:

- **Testing**: No test framework identified yet - check for `pytest`, `unittest`, or other testing setup when implementing tests
- **Linting**: No specific linter configuration found - standard Python linting tools (flake8, pylint, black) may be appropriate
- **Dependencies**: No `requirements.txt` or `pyproject.toml` found yet - dependency management setup needed

## KiCad Plugin Context

This plugin is designed to work within the KiCad ecosystem. Key considerations:
- KiCad plugins typically use the `pcbnew` or `eeschema` Python APIs
- Plugin registration and initialization will likely be handled in the main `__init__.py`
- Schematic analysis will require KiCad's schematic object model understanding

## Current State

The repository is in initial development with minimal code structure established. The project will likely need:
- Implementation of the `SchematicLLMChecker` module
- KiCad API integration
- LLM integration (likely via API calls)
- Plugin registration and configuration