import wx

with open('/tmp/ran', 'w') as f:
    f.write('ran')

# Global settings storage (in-memory for now)
SETTINGS = {
    'backend': 'ChatGPT 5',
    'api_key': ''
}

class ViolationLevel:
    FATAL = "Fatal"
    MAJOR = "Major"
    MINOR = "Minor"
    BEST_PRACTICE = "Best Practice"
    NICE_TO_HAVE = "Nice To Have"

    ALL_LEVELS = [FATAL, MAJOR, MINOR, BEST_PRACTICE, NICE_TO_HAVE]

class ViolationItem:
    def __init__(self, level, description, location=""):
        self.level = level
        self.description = description
        self.location = location

    def __str__(self):
        if self.location:
            return f"[{self.level}] {self.description} (at {self.location})"
        else:
            return f"[{self.level}] {self.description}"

class ConfigurationDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Configuration", size=(400, 250))

        self.temp_settings = SETTINGS.copy()  # Temporary copy for editing
        self.setup_ui()
        self.Center()

    def setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Backend selection
        backend_sizer = wx.BoxSizer(wx.HORIZONTAL)
        backend_label = wx.StaticText(self, label="Backend:")
        backend_sizer.Add(backend_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.backend_choice = wx.Choice(self, choices=["ChatGPT 5"])
        self.backend_choice.SetSelection(0)  # Default to ChatGPT 5
        backend_sizer.Add(self.backend_choice, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(backend_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # API Key input
        api_key_label = wx.StaticText(self, label="API Key:")
        main_sizer.Add(api_key_label, 0, wx.ALL, 5)

        self.api_key_text = wx.TextCtrl(self, value=SETTINGS['api_key'], style=wx.TE_PASSWORD)
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

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def on_save(self, event):
        # Save settings to global SETTINGS
        SETTINGS['backend'] = self.backend_choice.GetStringSelection()
        SETTINGS['api_key'] = self.api_key_text.GetValue()
        self.EndModal(wx.ID_OK)

class SchematicLLMCheckerDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Schematic LLM Checker", size=(800, 600))

        # Sample violations for demonstration
        self.violations = [
            ViolationItem(ViolationLevel.FATAL, "Power supply missing decoupling capacitor", "U1"),
            ViolationItem(ViolationLevel.MAJOR, "High-speed signal without proper termination", "Net CLK"),
            ViolationItem(ViolationLevel.MINOR, "Pull-up resistor value not optimal", "R5"),
            ViolationItem(ViolationLevel.BEST_PRACTICE, "Consider adding test points for debugging", "VCC rail"),
            ViolationItem(ViolationLevel.NICE_TO_HAVE, "Add component reference designators", "Various components"),
        ]

        self.filtered_violations = self.violations.copy()
        self.setup_ui()
        self.update_violations_display()

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

        # Violations list
        violations_label = wx.StaticText(self, label="Violations:")
        main_sizer.Add(violations_label, 0, wx.ALL, 5)

        self.violations_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.violations_list.AppendColumn("Level", width=120)
        self.violations_list.AppendColumn("Description", width=400)
        self.violations_list.AppendColumn("Location", width=150)

        main_sizer.Add(self.violations_list, 1, wx.ALL | wx.EXPAND, 5)

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
        for level in ViolationLevel.ALL_LEVELS:
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

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)

    def on_all_checkbox(self, event):
        if self.all_checkbox.GetValue():
            # Deselect all individual checkboxes
            for checkbox in self.checkboxes.values():
                checkbox.SetValue(False)
            # Show all violations
            self.filtered_violations = self.violations.copy()
        else:
            # If "All" is unchecked, show no violations
            self.filtered_violations = []

        self.update_violations_display()

    def on_level_checkbox(self, event):
        # If any individual checkbox is selected, deselect "All"
        if any(checkbox.GetValue() for checkbox in self.checkboxes.values()):
            self.all_checkbox.SetValue(False)

        # Filter violations based on selected levels
        selected_levels = [level for level, checkbox in self.checkboxes.items() if checkbox.GetValue()]

        if selected_levels:
            self.filtered_violations = [v for v in self.violations if v.level in selected_levels]
        else:
            # If no individual levels are selected, show nothing
            self.filtered_violations = []

        self.update_violations_display()

    def update_violations_display(self):
        self.violations_list.DeleteAllItems()

        for i, violation in enumerate(self.filtered_violations):
            index = self.violations_list.InsertItem(i, violation.level)
            self.violations_list.SetItem(index, 1, violation.description)
            self.violations_list.SetItem(index, 2, violation.location)

            # Set color based on level
            if violation.level == ViolationLevel.FATAL:
                self.violations_list.SetItemTextColour(index, wx.Colour(139, 0, 0))  # Dark red
            elif violation.level == ViolationLevel.MAJOR:
                self.violations_list.SetItemTextColour(index, wx.Colour(255, 0, 0))  # Red
            elif violation.level == ViolationLevel.MINOR:
                self.violations_list.SetItemTextColour(index, wx.Colour(255, 165, 0))  # Orange
            elif violation.level == ViolationLevel.BEST_PRACTICE:
                self.violations_list.SetItemTextColour(index, wx.Colour(0, 0, 255))  # Blue
            elif violation.level == ViolationLevel.NICE_TO_HAVE:
                self.violations_list.SetItemTextColour(index, wx.Colour(128, 128, 128))  # Gray

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