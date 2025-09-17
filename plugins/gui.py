import wx
from models import FindingLevel, Finding
from core import run
from config import config_manager
from typing import List

AVAILABLE_MODELS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
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
            recommendation=finding.recommendation
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
        self.api_key_text = wx.TextCtrl(self, value=current_api_key, style=wx.TE_PASSWORD)
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
        self.setup_ui()
        self.update_findings_display()

    def load_findings(self):
        """Load findings from schematic analysis."""
        try:
            selected_model = config_manager.get_selected_model()
            api_key = config_manager.get_api_key(selected_model)

            if not api_key:
                wx.MessageBox(f"No API key configured for {selected_model}. Please configure it in Settings.", "Configuration Error", wx.OK | wx.ICON_WARNING)
                return False

            real_findings = run(selected_model, api_key)
            if real_findings:
                self.findings = [FindingItem.from_finding(f) for f in real_findings]
                self.filtered_findings = self.findings.copy()
                return True
            else:
                self.findings = []
                self.filtered_findings = []
                wx.MessageBox("No findings from analysis. The schematic may have no issues or analysis failed.", "Analysis Complete", wx.OK | wx.ICON_INFORMATION)
                return True
        except Exception as e:
            self.findings = []
            self.filtered_findings = []
            wx.MessageBox(f"Error during analysis: {str(e)}", "Analysis Error", wx.OK | wx.ICON_ERROR)
            return False

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

        main_sizer.Add(self.findings_list, 1, wx.ALL | wx.EXPAND, 5)

        # Filter checkboxes
        filter_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Filter by Level"), wx.HORIZONTAL)

        self.checkboxes = {}

        # "All" checkbox
        self.all_checkbox = wx.CheckBox(self, label="All")
        self.all_checkbox.SetValue(True)
        self.all_checkbox.Bind(wx.EVT_CHECKBOX, self.on_all_checkbox)
        filter_box.Add(self.all_checkbox, 0, wx.ALL, 5)

        filter_box.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5)

        # Individual level checkboxes
        for level in FindingLevel.ALL_LEVELS:
            checkbox = wx.CheckBox(self, label=level)
            checkbox.SetValue(True)
            checkbox.Bind(wx.EVT_CHECKBOX, self.on_level_checkbox)
            self.checkboxes[level] = checkbox
            filter_box.Add(checkbox, 0, wx.ALL, 5)

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

        run_button = wx.Button(self, label="Run")
        run_button.Bind(wx.EVT_BUTTON, self.on_run)
        button_sizer.Add(run_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)

    def apply_current_filters(self):
        """Apply the current filter settings to the findings."""
        if self.all_checkbox.GetValue():
            self.filtered_findings = self.findings.copy()
        else:
            selected_levels = [level for level, checkbox in self.checkboxes.items() if checkbox.GetValue()]
            if selected_levels:
                self.filtered_findings = [f for f in self.findings if f.level in selected_levels]
            else:
                self.filtered_findings = []

    def on_all_checkbox(self, event):
        if self.all_checkbox.GetValue():
            # Deselect all individual checkboxes
            for checkbox in self.checkboxes.values():
                checkbox.SetValue(False)
            # Show all findings
            self.filtered_findings = self.findings.copy()
        else:
            # If "All" is unchecked, show no findings
            self.filtered_findings = []

        self.update_findings_display()

    def on_level_checkbox(self, event):
        # If any individual checkbox is selected, deselect "All"
        if any(checkbox.GetValue() for checkbox in self.checkboxes.values()):
            self.all_checkbox.SetValue(False)

        # Filter findings based on selected levels
        selected_levels = [level for level, checkbox in self.checkboxes.items() if checkbox.GetValue()]

        if selected_levels:
            self.filtered_findings = [f for f in self.findings if f.level in selected_levels]
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
                self.findings_list.SetItemTextColour(index, wx.Colour(139, 0, 0))  # Dark red
            elif finding.level == FindingLevel.MAJOR:
                self.findings_list.SetItemTextColour(index, wx.Colour(255, 0, 0))  # Red
            elif finding.level == FindingLevel.MINOR:
                self.findings_list.SetItemTextColour(index, wx.Colour(255, 165, 0))  # Orange
            elif finding.level == FindingLevel.BEST_PRACTICE:
                self.findings_list.SetItemTextColour(index, wx.Colour(0, 0, 255))  # Blue
            elif finding.level == FindingLevel.NICE_TO_HAVE:
                self.findings_list.SetItemTextColour(index, wx.Colour(128, 128, 128))  # Gray

    def on_run(self, event):
        """Run the schematic analysis and update findings."""
        # Show progress dialog or disable button during analysis
        run_button = event.GetEventObject()
        run_button.Enable(False)
        run_button.SetLabel("Running...")

        wx.CallAfter(self._run_analysis, run_button)

    def _run_analysis(self, run_button):
        """Perform the analysis in the background and update UI."""
        try:
            if self.load_findings():
                self.apply_current_filters()
                self.update_findings_display()
        finally:
            run_button.Enable(True)
            run_button.SetLabel("Run")

    def on_configuration(self, event):
        config_dialog = ConfigurationDialog(self)
        config_dialog.ShowModal()
        config_dialog.Destroy()

    def on_close(self, event):
        self.EndModal(wx.ID_CLOSE)

def show_dialog():
    app = wx.App(False)

    dialog = SchematicLLMCheckerDialog()
    dialog.ShowModal()
    dialog.Destroy()
    app.Destroy()

if __name__ == "__main__":
    show_dialog()