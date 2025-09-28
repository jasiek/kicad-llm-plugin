#!/usr/bin/env python3
"""
Multi-model LLM Analysis Script

This script runs the LLM analysis for each available model and saves outputs to CSV files.
It operates independently of KiCad and can be used from the command line.

Usage:
    python analyze_models.py --netlist path/to/netlist.net [--output-dir outputs]
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add plugins directory to path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'plugins'))

from llm_operations import LLMOperations
from models import Finding, TokenUsage, AnalysisResult
from config import ConfigManager

# Available models and their providers
AVAILABLE_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/gpt-5",
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash"
]

class MultiModelAnalyzer:
    def __init__(self, netlist_path: str, output_dir: str = "outputs"):
        self.netlist_path = netlist_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.config_manager = ConfigManager()

        # Load netlist content
        with open(netlist_path, 'r') as f:
            self.netlist_content = f.read()

    def get_available_models_with_keys(self) -> List[str]:
        """Get list of models that have API keys available."""
        available = []
        for model in AVAILABLE_MODELS:
            api_key = self.config_manager.get_api_key(model)
            if api_key:
                available.append(model)
        return available

    def analyze_with_model(self, model_name: str) -> Optional[AnalysisResult]:
        """Run analysis with a specific model."""
        api_key = self.config_manager.get_api_key(model_name)
        if not api_key:
            print(f"No API key found for model {model_name}")
            return None

        try:
            print(f"Running analysis with {model_name}...")
            llm_ops = LLMOperations(model_name, api_key)
            result = llm_ops.analyze_netlist(self.netlist_content)
            print(f"✓ {model_name}: {len(result.findings)} findings")
            return result
        except Exception as e:
            print(f"✗ {model_name}: Error - {str(e)}")
            return None

    def save_to_csv(self, model_name: str, findings: List[Finding], token_usage: TokenUsage):
        """Save findings to CSV file."""
        # Create safe filename from model name
        safe_model_name = model_name.replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_model_name}_{timestamp}.csv"
        filepath = self.output_dir / filename

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow([
                'ID', 'Level', 'Description', 'Recommendation', 'Reference'
            ])

            # Write findings
            for finding in findings:
                writer.writerow([
                    finding.id,
                    finding.level,
                    finding.description,
                    finding.recommendation,
                    finding.reference
                ])

        print(f"  Saved {len(findings)} findings to {filepath}")

    def save_summary_csv(self, results: Dict[str, AnalysisResult]):
        """Save summary of all model results to a CSV file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"model_comparison_{timestamp}.csv"
        filepath = self.output_dir / filename

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow([
                'Model', 'Total_Findings', 'Fatal', 'Major', 'Minor',
                'Best_Practice', 'Nice_To_Have', 'Total_Tokens',
                'Input_Tokens', 'Output_Tokens', 'Response_Time_Seconds'
            ])

            # Write summary for each model
            for model_name, result in results.items():
                if result is None:
                    continue

                # Count findings by level
                level_counts = {'Fatal': 0, 'Major': 0, 'Minor': 0, 'Best Practice': 0, 'Nice To Have': 0}
                for finding in result.findings:
                    if finding.level in level_counts:
                        level_counts[finding.level] += 1

                writer.writerow([
                    model_name,
                    len(result.findings),
                    level_counts['Fatal'],
                    level_counts['Major'],
                    level_counts['Minor'],
                    level_counts['Best Practice'],
                    level_counts['Nice To Have'],
                    result.token_usage.total_tokens,
                    result.token_usage.input_tokens,
                    result.token_usage.output_tokens,
                    result.token_usage.response_time_seconds
                ])

        print(f"Saved model comparison summary to {filepath}")

    def run_analysis(self) -> Dict[str, AnalysisResult]:
        """Run analysis for all available models."""
        available_models = self.get_available_models_with_keys()

        if not available_models:
            print("No models with API keys found. Please configure API keys using the KiCad plugin first.")
            return {}

        print(f"Found API keys for {len(available_models)} models: {', '.join(available_models)}")
        print(f"Analyzing netlist: {self.netlist_path}")
        print(f"Output directory: {self.output_dir}")
        print("-" * 60)

        results = {}

        for model_name in available_models:
            result = self.analyze_with_model(model_name)
            results[model_name] = result

            if result and result.findings:
                self.save_to_csv(model_name, result.findings, result.token_usage)
                print(f"  Token usage: {result.token_usage.get_breakdown_text()}")

            print()  # Add spacing between models

        # Save summary comparison
        self.save_summary_csv(results)

        return results

def main():
    parser = argparse.ArgumentParser(
        description='Run LLM analysis on a netlist using multiple models'
    )
    parser.add_argument(
        '--netlist',
        required=True,
        help='Path to the netlist file (.net)'
    )
    parser.add_argument(
        '--output-dir',
        default='outputs',
        help='Output directory for CSV files (default: outputs)'
    )

    args = parser.parse_args()

    # Validate netlist file exists
    if not os.path.exists(args.netlist):
        print(f"Error: Netlist file not found: {args.netlist}")
        sys.exit(1)

    # Run analysis
    analyzer = MultiModelAnalyzer(args.netlist, args.output_dir)
    results = analyzer.run_analysis()

    # Print final summary
    successful_analyses = [model for model, result in results.items() if result is not None]
    print("=" * 60)
    print(f"Analysis complete! Successfully analyzed with {len(successful_analyses)} models.")
    print(f"Results saved to: {analyzer.output_dir}")

if __name__ == "__main__":
    main()