import wx
import threading
import os
from models import FindingLevel, Finding, TokenUsage
from core import run
from config import config_manager
from typing import List, Optional

AVAILABLE_MODELS = [
    "openai/gpt-5.2",
    "openai/gpt-5-mini",
    "openai/gpt-5-nano",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "google/gemini-3-flash-preview",
    "google/gemini-3-pro-preview",
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
    "groq/llama-3.3-70b-versatile",
    "groq/meta-llama/llama-4-maverick-17b-128e-instruct",
    "groq/openai/gpt-oss-120b",
    "groq/openai/gpt-oss-20b",
]


class FindingItem:
    def __init__(self, level, description, location="", recommendation=""):
        self.level = level
        self.description = description
        self.location = location
        self.recommendation = recommendation

    @classmethod
    def from_finding(cls, finding: Finding):
        """Create a FindingItem from a Finding model."""
        return cls(
            level=finding.level,
            description=finding.description,
            location=finding.reference,
            recommendation=finding.recommendation,
        )

    def __str__(self):
        if self.location:
            return f"[{self.level}] {self.description} (at {self.location})"
        else:
            return f"[{self.level}] {self.description}"


class ConfigurationDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Configuration", size=(400, 300))

        self.selected_model = config_manager.get_selected_model()
        self.setup_ui()
        self.Center()

    def setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Backend selection
        backend_sizer = wx.BoxSizer(wx.HORIZONTAL)
        backend_label = wx.StaticText(self, label="Backend:")
        backend_sizer.Add(backend_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.backend_choice = wx.Choice(self, choices=AVAILABLE_MODELS)
        # Set selection based on config
        try:
            selection_index = AVAILABLE_MODELS.index(self.selected_model)
            self.backend_choice.SetSelection(selection_index)
        except ValueError:
            self.backend_choice.SetSelection(0)

        self.backend_choice.Bind(wx.EVT_CHOICE, self.on_backend_change)
        backend_sizer.Add(self.backend_choice, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(backend_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # API Key input
        provider = self.get_provider_from_model(self.selected_model)
        api_key_label = wx.StaticText(self, label=f"API Key for {provider.upper()}:")
        self.api_key_label = api_key_label
        main_sizer.Add(api_key_label, 0, wx.ALL, 5)

        current_api_key = config_manager.get_api_key(self.selected_model) or ""
        self.api_key_text = wx.TextCtrl(
            self, value=current_api_key, style=wx.TE_PASSWORD
        )
        main_sizer.Add(self.api_key_text, 0, wx.ALL | wx.EXPAND, 5)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        save_button = wx.Button(self, wx.ID_OK, "Save")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        button_sizer.Add(save_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)

    def get_provider_from_model(self, model_name: str) -> str:
        """Extract provider name from model name."""
        if "/" in model_name:
            return model_name.split("/")[0]
        return model_name

    def on_backend_change(self, event):
        """Handle backend model change."""
        new_model = self.backend_choice.GetStringSelection()
        if new_model != self.selected_model:
            old_provider = self.get_provider_from_model(self.selected_model)
            new_provider = self.get_provider_from_model(new_model)

            self.selected_model = new_model

            # Update API key field for the new model's provider
            current_api_key = config_manager.get_api_key(self.selected_model) or ""
            self.api_key_text.SetValue(current_api_key)

            # Update label to show provider instead of full model name
            self.api_key_label.SetLabel(f"API Key for {new_provider.upper()}:")
            self.Layout()

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def on_save(self, event):
        # Save settings to configuration manager
        config_manager.set_selected_model(self.selected_model)
        api_key = self.api_key_text.GetValue().strip()
        if api_key:
            config_manager.set_api_key(self.selected_model, api_key)
        else:
            config_manager.remove_api_key(self.selected_model)

        self.EndModal(wx.ID_OK)


class SchematicLLMCheckerDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Schematic LLM Checker", size=(800, 600))

        self.findings: List[FindingItem] = []
        self.filtered_findings: List[FindingItem] = []
        self.project_path: Optional[str] = None
        self.token_usage: TokenUsage = TokenUsage()

        # Define severity level priority for sorting (lower number = higher priority)
        self.level_priority = {
            FindingLevel.FATAL: 0,
            FindingLevel.MAJOR: 1,
            FindingLevel.MINOR: 2,
            FindingLevel.BEST_PRACTICE: 3,
            FindingLevel.NICE_TO_HAVE: 4,
        }

        self.setup_ui()
        self.update_findings_display()

    def setup_ui(self):
        # Main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(self, label="Schematic Analysis Results")
        title_font = title.GetFont()
        title_font.SetPointSize(12)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        # Findings list
        findings_label = wx.StaticText(self, label="Findings:")
        main_sizer.Add(findings_label, 0, wx.ALL, 5)

        self.findings_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.findings_list.AppendColumn("Level", width=120)
        self.findings_list.AppendColumn("Description", width=400)
        self.findings_list.AppendColumn("Location", width=150)

        # Bind mouse motion event for tooltips
        self.findings_list.Bind(wx.EVT_MOTION, self.on_mouse_motion)
        self.findings_list.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_window)

        # Initialize tooltip tracking
        self.current_tooltip_item = -1
        self.tooltip_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_tooltip_timer)

        main_sizer.Add(self.findings_list, 1, wx.ALL | wx.EXPAND, 5)

        # Token usage display
        self.token_usage_label = wx.StaticText(self, label="Tokens used: 0")
        main_sizer.Add(self.token_usage_label, 0, wx.ALL, 5)

        # Filter checkboxes and save button
        filter_box = wx.StaticBoxSizer(
            wx.StaticBox(self, label="Filter by Level"), wx.HORIZONTAL
        )

        self.checkboxes = {}

        # "All" checkbox
        self.all_checkbox = wx.CheckBox(self, label="All")
        self.all_checkbox.SetValue(True)
        self.all_checkbox.Bind(wx.EVT_CHECKBOX, self.on_all_checkbox)
        filter_box.Add(self.all_checkbox, 0, wx.ALL, 5)

        filter_box.Add(
            wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5
        )

        # Individual level checkboxes
        for level in FindingLevel.ALL_LEVELS:
            checkbox = wx.CheckBox(self, label=level)
            checkbox.SetValue(True)
            checkbox.Bind(wx.EVT_CHECKBOX, self.on_level_checkbox)
            self.checkboxes[level] = checkbox
            filter_box.Add(checkbox, 0, wx.ALL, 5)

        # Add stretch spacer to push save button to the right
        filter_box.AddStretchSpacer()

        # Save findings button
        self.save_button = wx.Button(self, label="Export HTML...")
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save_findings)
        filter_box.Add(self.save_button, 0, wx.ALL, 5)

        main_sizer.Add(filter_box, 0, wx.ALL | wx.EXPAND, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        config_button = wx.Button(self, label="Configuration...")
        config_button.Bind(wx.EVT_BUTTON, self.on_configuration)
        button_sizer.Add(config_button, 0, wx.ALL, 5)

        button_sizer.AddStretchSpacer()

        close_button = wx.Button(self, wx.ID_CLOSE, "Close")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        button_sizer.Add(close_button, 0, wx.ALL, 5)

        self.run_button = wx.Button(self, label="Run")
        self.run_button.Bind(wx.EVT_BUTTON, self.on_run)
        button_sizer.Add(self.run_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)

    def sort_findings(self, findings_list: List[FindingItem]) -> List[FindingItem]:
        """Sort findings by severity level, with Fatal at the top."""
        return sorted(findings_list, key=lambda f: self.level_priority.get(f.level, 99))

    def apply_current_filters(self):
        """Apply the current filter settings to the findings."""
        if self.all_checkbox.GetValue():
            self.filtered_findings = self.sort_findings(self.findings.copy())
        else:
            selected_levels = [
                level
                for level, checkbox in self.checkboxes.items()
                if checkbox.GetValue()
            ]
            if selected_levels:
                filtered = [f for f in self.findings if f.level in selected_levels]
                self.filtered_findings = self.sort_findings(filtered)
            else:
                self.filtered_findings = []

    def on_all_checkbox(self, event):
        if self.all_checkbox.GetValue():
            # Deselect all individual checkboxes
            for checkbox in self.checkboxes.values():
                checkbox.SetValue(False)
            # Show all findings, sorted
            self.filtered_findings = self.sort_findings(self.findings.copy())
        else:
            # If "All" is unchecked, show no findings
            self.filtered_findings = []

        self.update_findings_display()

    def on_level_checkbox(self, event):
        # If any individual checkbox is selected, deselect "All"
        if any(checkbox.GetValue() for checkbox in self.checkboxes.values()):
            self.all_checkbox.SetValue(False)

        # Filter findings based on selected levels
        selected_levels = [
            level for level, checkbox in self.checkboxes.items() if checkbox.GetValue()
        ]

        if selected_levels:
            filtered = [f for f in self.findings if f.level in selected_levels]
            self.filtered_findings = self.sort_findings(filtered)
        else:
            # If no individual levels are selected, show nothing
            self.filtered_findings = []

        self.update_findings_display()

    def update_findings_display(self):
        self.findings_list.DeleteAllItems()

        for i, finding in enumerate(self.filtered_findings):
            index = self.findings_list.InsertItem(i, finding.level)
            self.findings_list.SetItem(index, 1, finding.description)
            self.findings_list.SetItem(index, 2, finding.location)

            # Set color based on level
            if finding.level == FindingLevel.FATAL:
                self.findings_list.SetItemTextColour(
                    index, wx.Colour(139, 0, 0)
                )  # Dark red
            elif finding.level == FindingLevel.MAJOR:
                self.findings_list.SetItemTextColour(index, wx.Colour(255, 0, 0))  # Red
            elif finding.level == FindingLevel.MINOR:
                self.findings_list.SetItemTextColour(
                    index, wx.Colour(255, 165, 0)
                )  # Orange
            elif finding.level == FindingLevel.BEST_PRACTICE:
                self.findings_list.SetItemTextColour(
                    index, wx.Colour(0, 0, 255)
                )  # Blue
            elif finding.level == FindingLevel.NICE_TO_HAVE:
                self.findings_list.SetItemTextColour(
                    index, wx.Colour(128, 128, 128)
                )  # Gray

    def on_run(self, event):
        """Run the schematic analysis and update findings."""
        # Disable the run button during analysis
        self.run_button.Enable(False)
        self.run_button.SetLabel("Running...")

        # Start analysis in background thread
        analysis_thread = threading.Thread(target=self._run_analysis_thread)
        analysis_thread.daemon = True
        analysis_thread.start()

    def _run_analysis_thread(self):
        """Perform the analysis in a background thread."""
        try:
            selected_model = config_manager.get_selected_model()
            api_key = config_manager.get_api_key(selected_model)

            if not api_key:
                wx.CallAfter(
                    self._show_error,
                    f"No API key configured for {selected_model}. Please configure it in Settings.",
                    "Configuration Error",
                )
                return

            # Run the analysis (this is the blocking operation)
            real_findings, project_path, token_usage = run(selected_model, api_key)

            # Update UI on the main thread
            wx.CallAfter(
                self._analysis_complete, real_findings, project_path, token_usage
            )

        except Exception as e:
            wx.CallAfter(
                self._show_error, f"Error during analysis: {str(e)}", "Analysis Error"
            )
        finally:
            # Re-enable the run button on the main thread
            wx.CallAfter(self._reset_run_button)

    def _analysis_complete(self, real_findings, project_path, token_usage):
        """Handle analysis completion on the main thread."""
        # Store the project path and token usage
        self.project_path = project_path
        self.token_usage = token_usage

        # Update token usage display
        self.token_usage_label.SetLabel(
            f"Tokens used: {token_usage.get_breakdown_text()}"
        )

        if real_findings:
            self.findings = [FindingItem.from_finding(f) for f in real_findings]
            self.findings = self.sort_findings(
                self.findings
            )  # Sort the initial findings
            self.filtered_findings = self.findings.copy()
            self.apply_current_filters()
            self.update_findings_display()
        else:
            self.findings = []
            self.filtered_findings = []
            wx.MessageBox(
                "No findings from analysis. The schematic may have no issues or analysis failed.",
                "Analysis Complete",
                wx.OK | wx.ICON_INFORMATION,
            )
            self.update_findings_display()

    def _show_error(self, message, title):
        """Show error message on the main thread."""
        wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR)

    def _reset_run_button(self):
        """Reset the run button state on the main thread."""
        self.run_button.Enable(True)
        self.run_button.SetLabel("Run")

    def on_configuration(self, event):
        config_dialog = ConfigurationDialog(self)
        config_dialog.ShowModal()
        config_dialog.Destroy()

    def on_save_findings(self, event):
        """Save the currently displayed findings to an HTML file."""
        if not self.filtered_findings:
            wx.MessageBox(
                "No findings to save. Please run an analysis first.",
                "No Data",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Show file dialog to select save location
        wildcard = "HTML files (*.html)|*.html|All files (*.*)|*.*"

        # Use project path as default directory if available
        default_dir = self.project_path if self.project_path else ""

        # Use project name as default filename if available
        if self.project_path:
            project_name = os.path.basename(self.project_path)
            default_filename = f"{project_name}_findings.html"
        else:
            default_filename = "schematic_findings.html"

        dialog = wx.FileDialog(
            self,
            "Save findings as HTML",
            defaultDir=default_dir,
            defaultFile=default_filename,
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dialog.ShowModal() == wx.ID_OK:
            file_path = dialog.GetPath()
            try:
                self._export_to_html(file_path)
                wx.MessageBox(
                    f"Findings saved to {file_path}",
                    "Export Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as e:
                wx.MessageBox(
                    f"Error saving file: {str(e)}",
                    "Export Error",
                    wx.OK | wx.ICON_ERROR,
                )

        dialog.Destroy()

    def _export_to_html(self, file_path: str):
        """Export the filtered findings to an HTML file with embedded styles."""
        from datetime import datetime

        selected_model = config_manager.get_selected_model()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        project_name = (
            os.path.basename(self.project_path)
            if self.project_path
            else "Unknown Project"
        )

        # Define colors for each severity level
        level_colors = {
            "Fatal": "#8b0000",  # Dark red
            "Major": "#ff0000",  # Red
            "Minor": "#ffa500",  # Orange
            "Best Practice": "#0000ff",  # Blue
            "Nice To Have": "#808080",  # Gray
        }

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schematic Analysis Findings - {project_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
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

        .metadata p {{
            margin: 5px 0;
            color: #666;
        }}

        .summary {{
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}

        .summary-card {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            flex: 1;
            min-width: 150px;
            text-align: center;
            border: 1px solid #e0e0e0;
        }}

        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 14px;
            text-transform: uppercase;
        }}

        .summary-card .number {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
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

        .findings-table tr:hover {{
            background-color: #e9ecef;
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
            font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
            background-color: #f1f3f4;
            padding: 2px 4px;
            border-radius: 3px;
            font-size: 13px;
        }}

        .description {{
            max-width: 400px;
            word-wrap: break-word;
        }}

        .recommendation {{
            max-width: 350px;
            word-wrap: break-word;
            color: #666;
            font-style: italic;
        }}

        .no-findings {{
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Schematic Analysis Findings</h1>
            <h2 style="color: #666; font-weight: normal; margin: 0;">{project_name}</h2>
        </div>

        <div class="metadata">
            <p><strong>Generated:</strong> {timestamp}</p>
            <p><strong>Model:</strong> {selected_model}</p>
            <p><strong>Token Usage:</strong> {self.token_usage.get_breakdown_text()}</p>
            <p><strong>Total Findings:</strong> {len(self.filtered_findings)}</p>
        </div>
"""

        # Add summary cards
        if self.filtered_findings:
            level_counts = {}
            for level in ["Fatal", "Major", "Minor", "Best Practice", "Nice To Have"]:
                count = sum(1 for f in self.filtered_findings if f.level == level)
                level_counts[level] = count

            html_content += '        <div class="summary">\n'
            for level, count in level_counts.items():
                if count > 0:
                    html_content += f"""            <div class="summary-card">
                <h3>{level}</h3>
                <div class="number" style="color: {level_colors.get(level, '#007bff')}">{count}</div>
            </div>
"""
            html_content += "        </div>\n\n"

        # Add findings table
        if self.filtered_findings:
            html_content += """        <table class="findings-table">
            <thead>
                <tr>
                    <th>Level</th>
                    <th>Description</th>
                    <th>Location</th>
                    <th>Recommendation</th>
                </tr>
            </thead>
            <tbody>
"""

            for finding in self.filtered_findings:
                level_color = level_colors.get(finding.level, "#666666")
                description_html = finding.description.replace("\n", "<br>")
                recommendation_html = finding.recommendation.replace("\n", "<br>")

                html_content += f"""                <tr>
                    <td><span class="level-badge" style="background-color: {level_color}">{finding.level}</span></td>
                    <td class="description">{description_html}</td>
                    <td><span class="location">{finding.location}</span></td>
                    <td class="recommendation">{recommendation_html}</td>
                </tr>
"""

            html_content += """            </tbody>
        </table>
"""
        else:
            html_content += """        <div class="no-findings">
            <p>No findings to display.</p>
        </div>
"""

        html_content += """    </div>
</body>
</html>"""

        with open(file_path, "w", encoding="utf-8") as htmlfile:
            htmlfile.write(html_content)

    def on_mouse_motion(self, event):
        """Handle mouse motion over the findings list to show tooltips."""
        # Get the item and column under the mouse
        item, flags = self.findings_list.HitTest(event.GetPosition())

        if item != wx.NOT_FOUND and item < len(self.filtered_findings):
            if item != self.current_tooltip_item:
                # Mouse moved to a new item
                self.current_tooltip_item = item
                self.tooltip_timer.Stop()
                self.tooltip_timer.Start(100, True)  # 100ms

                # Hide existing tooltip
                self.findings_list.SetToolTip(None)
        else:
            # Mouse not over a valid item
            if self.current_tooltip_item != -1:
                self.current_tooltip_item = -1
                self.tooltip_timer.Stop()
                self.findings_list.SetToolTip(None)

        event.Skip()

    def on_leave_window(self, event):
        """Handle mouse leaving the findings list window."""
        self.current_tooltip_item = -1
        self.tooltip_timer.Stop()
        self.findings_list.SetToolTip(None)
        event.Skip()

    def on_tooltip_timer(self, event):
        """Show tooltip after timer expires."""
        if self.current_tooltip_item >= 0 and self.current_tooltip_item < len(
            self.filtered_findings
        ):
            finding = self.filtered_findings[self.current_tooltip_item]

            # Create comprehensive tooltip text
            tooltip_text = f"Level: {finding.level}\n"
            tooltip_text += f"Location: {finding.location}\n\n"
            tooltip_text += f"Description:\n{finding.description}\n\n"
            tooltip_text += f"Recommendation:\n{finding.recommendation}"

            self.findings_list.SetToolTip(tooltip_text)

    def on_close(self, event):
        # Clean up timer
        if hasattr(self, "tooltip_timer"):
            self.tooltip_timer.Stop()
        self.EndModal(wx.ID_CLOSE)

    def Destroy(self):
        # Clean up timer before destroying
        if hasattr(self, "tooltip_timer"):
            self.tooltip_timer.Stop()
        super().Destroy()


def show_dialog():
    app = wx.App(False)

    dialog = SchematicLLMCheckerDialog()
    dialog.ShowModal()
    dialog.Destroy()
    app.Destroy()


if __name__ == "__main__":
    show_dialog()
