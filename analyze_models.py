#!/usr/bin/env python3
"""
Multi-model LLM Analysis Script

This script runs the LLM analysis for each available model and saves outputs to CSV files.
It operates independently of KiCad and can be used from the command line.

Usage:
    python analyze_models.py --netlist path/to/netlist.net [--output-dir outputs] [--models model1,model2,...]
"""

import argparse
import csv
import os
import sys
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add plugins directory to path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), "plugins"))

from llm_operations import LLMOperations
from models import Finding, TokenUsage, AnalysisResult
from config import ConfigManager
from gui import AVAILABLE_MODELS


class MultiModelAnalyzer:
    def __init__(
        self,
        netlist_path: str,
        schematic_path: str = None,
        output_dir: str = "outputs",
        selected_models: List[str] = None,
    ):
        self.netlist_path = netlist_path
        self.schematic_path = schematic_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.config_manager = ConfigManager()
        self.selected_models = selected_models

        # Setup error logging
        self.log_file = (
            self.output_dir
            / f"analysis_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        self.setup_logging()
        self.errors = {}  # Track errors per model

        # Load netlist content
        with open(netlist_path, "r") as f:
            self.netlist_content = f.read()

        # Load schematic content if provided
        self.schematic_content = None
        if schematic_path and os.path.exists(schematic_path):
            try:
                with open(schematic_path, "r", encoding="utf-8") as f:
                    self.schematic_content = f.read()
            except Exception as e:
                error_msg = (
                    f"Warning: Could not read schematic file {schematic_path}: {e}"
                )
                print(error_msg)
                logging.warning(error_msg)

    def setup_logging(self):
        """Setup logging to file."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(self.log_file), logging.StreamHandler()],
        )
        logging.info(f"Starting analysis - log file: {self.log_file}")

    def get_available_models_with_keys(self) -> List[str]:
        """Get list of models that have API keys available, filtered by selected models if specified."""
        available = []
        for model in AVAILABLE_MODELS:
            api_key = self.config_manager.get_api_key(model)
            if api_key:
                # If specific models were selected, only include those
                if self.selected_models is None or model in self.selected_models:
                    available.append(model)
        return available

    def analyze_with_model(self, model_name: str) -> Optional[AnalysisResult]:
        """Run analysis with a specific model."""
        api_key = self.config_manager.get_api_key(model_name)
        if not api_key:
            error_msg = f"No API key found for model {model_name}"
            print(error_msg)
            logging.error(error_msg)
            self.errors[model_name] = error_msg
            return None

        try:
            print(f"Running analysis with {model_name}...")
            logging.info(f"Starting analysis with model: {model_name}")
            llm_ops = LLMOperations(model_name, api_key)

            # Use combined schematic and netlist analysis if schematic is available
            if self.schematic_content:
                result = llm_ops.analyze_schematic_and_netlist(
                    self.netlist_content, self.schematic_content
                )
                success_msg = f"✓ {model_name}: {len(result.findings)} findings (schematic + netlist)"
                print(success_msg)
                logging.info(success_msg)
            else:
                result = llm_ops.analyze_netlist(self.netlist_content)
                success_msg = (
                    f"✓ {model_name}: {len(result.findings)} findings (netlist only)"
                )
                print(success_msg)
                logging.info(success_msg)

            return result
        except Exception as e:
            error_msg = f"✗ {model_name}: Error - {str(e)}"
            print(error_msg)
            logging.error(error_msg)
            logging.error(f"Traceback for {model_name}:\n{traceback.format_exc()}")
            self.errors[model_name] = str(e)
            return None

    def save_to_csv(
        self, model_name: str, findings: List[Finding], token_usage: TokenUsage
    ):
        """Save findings to CSV file."""
        # Create safe filename from model name
        safe_model_name = model_name.replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_model_name}_{timestamp}.csv"
        filepath = self.output_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(
                ["ID", "Level", "Description", "Recommendation", "Reference"]
            )

            # Write findings
            for finding in findings:
                writer.writerow(
                    [
                        finding.id,
                        finding.level,
                        finding.description,
                        finding.recommendation,
                        finding.reference,
                    ]
                )

        print(f"  Saved {len(findings)} findings to {filepath}")
        logging.info(f"Saved CSV output to {filepath}")

    def save_to_html(
        self, model_name: str, findings: List[Finding], token_usage: TokenUsage
    ):
        """Save findings to HTML file with link to error log if errors occurred."""
        # Create safe filename from model name
        safe_model_name = model_name.replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_model_name}_{timestamp}.html"
        filepath = self.output_dir / filename

        # Define colors for each severity level
        level_colors = {
            "Fatal": "#8b0000",  # Dark red
            "Major": "#ff0000",  # Red
            "Minor": "#ffa500",  # Orange
            "Best Practice": "#0000ff",  # Blue
            "Nice To Have": "#808080",  # Gray
        }

        # Sort findings by severity
        level_priority = {
            "Fatal": 0,
            "Major": 1,
            "Minor": 2,
            "Best Practice": 3,
            "Nice To Have": 4,
        }
        sorted_findings = sorted(
            findings, key=lambda f: level_priority.get(f.level, 99)
        )

        # Generate error section if there are errors
        error_section = ""
        if self.errors:
            log_filename = self.log_file.name
            error_section = f"""
        <div class="error-banner">
            <p><strong>⚠️ Some models encountered errors during analysis.</strong></p>
            <p>View detailed error log: <a href="{log_filename}" target="_blank">{log_filename}</a></p>
            <details>
                <summary>Click to see error summary</summary>
                <ul>"""
            for error_model, error_msg in self.errors.items():
                error_section += f"\n                    <li><strong>{error_model}:</strong> {error_msg}</li>"
            error_section += """
                </ul>
            </details>
        </div>
"""

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schematic Analysis Findings - {model_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}

        .header {{
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}

        .header h1 {{
            color: #333;
            margin: 0 0 10px 0;
            font-size: 28px;
        }}

        .metadata {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            border-left: 4px solid #007bff;
        }}

        .error-banner {{
            background-color: #fff3cd;
            border-left: 4px solid #ff9800;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }}

        .error-banner a {{
            color: #d84315;
            font-weight: bold;
            text-decoration: underline;
        }}

        .error-banner details {{
            margin-top: 10px;
        }}

        .error-banner summary {{
            cursor: pointer;
            font-weight: bold;
            color: #d84315;
        }}

        .error-banner ul {{
            margin-top: 10px;
            padding-left: 20px;
        }}

        .error-banner li {{
            margin: 5px 0;
            color: #666;
        }}

        .findings-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}

        .findings-table th {{
            background-color: #343a40;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}

        .findings-table td {{
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            vertical-align: top;
        }}

        .findings-table tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}

        .level-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            color: white;
            text-transform: uppercase;
        }}

        .location {{
            font-family: monospace;
            background-color: #f1f3f4;
            padding: 2px 4px;
            border-radius: 3px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Schematic Analysis Findings</h1>
            <h2 style="color: #666; font-weight: normal; margin: 0;">{model_name}</h2>
        </div>

        <div class="metadata">
            <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p><strong>Model:</strong> {model_name}</p>
            <p><strong>Token Usage:</strong> {token_usage.get_breakdown_text()}</p>
            <p><strong>Total Findings:</strong> {len(findings)}</p>
        </div>
{error_section}
        <table class="findings-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Level</th>
                    <th>Description</th>
                    <th>Location</th>
                    <th>Recommendation</th>
                </tr>
            </thead>
            <tbody>
"""

        for finding in sorted_findings:
            level_color = level_colors.get(finding.level, "#666666")
            description_html = finding.description.replace("\n", "<br>")
            recommendation_html = finding.recommendation.replace("\n", "<br>")

            html_content += f"""                <tr>
                    <td>{finding.id}</td>
                    <td><span class="level-badge" style="background-color: {level_color}">{finding.level}</span></td>
                    <td>{description_html}</td>
                    <td><span class="location">{finding.reference}</span></td>
                    <td>{recommendation_html}</td>
                </tr>
"""

        html_content += """            </tbody>
        </table>
    </div>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as htmlfile:
            htmlfile.write(html_content)

        print(f"  Saved {len(findings)} findings to {filepath}")
        logging.info(f"Saved HTML output to {filepath}")

    def save_summary_csv(self, results: Dict[str, AnalysisResult]):
        """Save summary of all model results to a CSV file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"model_comparison_{timestamp}.csv"
        filepath = self.output_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(
                [
                    "Model",
                    "Status",
                    "Total_Findings",
                    "Fatal",
                    "Major",
                    "Minor",
                    "Best_Practice",
                    "Nice_To_Have",
                    "Total_Tokens",
                    "Input_Tokens",
                    "Output_Tokens",
                    "Response_Time_Seconds",
                    "Error",
                ]
            )

            # Write summary for each model
            for model_name, result in results.items():
                if result is None:
                    # Model had an error
                    error_msg = self.errors.get(model_name, "Unknown error")
                    writer.writerow(
                        [model_name, "ERROR", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, error_msg]
                    )
                    continue

                # Count findings by level
                level_counts = {
                    "Fatal": 0,
                    "Major": 0,
                    "Minor": 0,
                    "Best Practice": 0,
                    "Nice To Have": 0,
                }
                for finding in result.findings:
                    if finding.level in level_counts:
                        level_counts[finding.level] += 1

                writer.writerow(
                    [
                        model_name,
                        "SUCCESS",
                        len(result.findings),
                        level_counts["Fatal"],
                        level_counts["Major"],
                        level_counts["Minor"],
                        level_counts["Best Practice"],
                        level_counts["Nice To Have"],
                        result.token_usage.total_tokens,
                        result.token_usage.input_tokens,
                        result.token_usage.output_tokens,
                        result.token_usage.response_time_seconds,
                        "",
                    ]
                )

        print(f"Saved model comparison summary to {filepath}")
        logging.info(f"Saved comparison summary to {filepath}")

    def run_analysis(self) -> Dict[str, AnalysisResult]:
        """Run analysis for all available models."""
        available_models = self.get_available_models_with_keys()

        if not available_models:
            error_msg = "No models with API keys found. Please configure API keys using the KiCad plugin first."
            print(error_msg)
            logging.error(error_msg)
            return {}

        if self.selected_models:
            # Check if any selected models are not available
            unavailable = [m for m in self.selected_models if m not in available_models]
            if unavailable:
                warning_msg = f"Warning: The following selected models are not available (no API key or invalid): {', '.join(unavailable)}"
                print(warning_msg)
                logging.warning(warning_msg)

        print(
            f"Found API keys for {len(available_models)} models: {', '.join(available_models)}"
        )
        logging.info(
            f"Testing {len(available_models)} models: {', '.join(available_models)}"
        )
        print(f"Analyzing netlist: {self.netlist_path}")
        logging.info(f"Netlist: {self.netlist_path}")

        if self.schematic_content:
            print(f"Including schematic: {self.schematic_path}")
            logging.info(f"Schematic: {self.schematic_path}")
        else:
            print("No schematic file provided - analyzing netlist only")
            logging.info("Netlist-only analysis (no schematic)")

        print(f"Output directory: {self.output_dir}")
        print(f"Error log: {self.log_file}")
        print("-" * 60)

        results = {}

        for model_name in available_models:
            result = self.analyze_with_model(model_name)
            results[model_name] = result

            if result and result.findings:
                self.save_to_html(model_name, result.findings, result.token_usage)
                print(f"  Token usage: {result.token_usage.get_breakdown_text()}")

            print()  # Add spacing between models

        # Save summary comparison
        self.save_summary_csv(results)

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Run LLM analysis on a netlist and optional schematic using multiple models",
        epilog=f'Available models: {", ".join(AVAILABLE_MODELS)}',
    )
    parser.add_argument(
        "--netlist", required=True, help="Path to the netlist file (.net)"
    )
    parser.add_argument(
        "--schematic",
        help="Path to the schematic file (.kicad_sch) for enhanced analysis",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Output directory for HTML files (default: outputs)",
    )
    parser.add_argument(
        "--models",
        help="Comma-separated list of models to test (default: all models with API keys). Example: openai/gpt-4o,google/gemini-2.5-flash",
    )
    parser.add_argument(
        "--list-models", action="store_true", help="List all available models and exit"
    )

    args = parser.parse_args()

    # Handle --list-models
    if args.list_models:
        print("Available models:")
        for model in AVAILABLE_MODELS:
            print(f"  - {model}")
        sys.exit(0)

    # Validate netlist file exists
    if not os.path.exists(args.netlist):
        print(f"Error: Netlist file not found: {args.netlist}")
        sys.exit(1)

    # Validate schematic file if provided
    if args.schematic and not os.path.exists(args.schematic):
        print(f"Error: Schematic file not found: {args.schematic}")
        sys.exit(1)

    # Parse selected models
    selected_models = None
    if args.models:
        selected_models = [m.strip() for m in args.models.split(",")]
        # Validate selected models
        invalid_models = [m for m in selected_models if m not in AVAILABLE_MODELS]
        if invalid_models:
            print(f"Error: Invalid model(s): {', '.join(invalid_models)}")
            print(f"Use --list-models to see available models")
            sys.exit(1)
        print(f"Selected models to test: {', '.join(selected_models)}")

    # Run analysis
    analyzer = MultiModelAnalyzer(
        args.netlist, args.schematic, args.output_dir, selected_models
    )
    results = analyzer.run_analysis()

    # Print final summary
    successful_analyses = [
        model for model, result in results.items() if result is not None
    ]
    failed_analyses = [model for model, result in results.items() if result is None]

    print("=" * 60)
    print(f"Analysis complete!")
    print(f"  Successful: {len(successful_analyses)} models")
    if failed_analyses:
        print(f"  Failed: {len(failed_analyses)} models - {', '.join(failed_analyses)}")
        print(f"  See error log for details: {analyzer.log_file}")
    print(f"Results saved to: {analyzer.output_dir}")


if __name__ == "__main__":
    main()
