import wx

with open('/tmp/ran', 'w') as f:
    f.write('ran')

def show_dialog():
    app = wx.App(False)
    
    dialog = wx.MessageDialog(
        None,
        "Schematic LLM Checker",
        "LLM Analysis",
        wx.OK | wx.ICON_INFORMATION
    )
    
    dialog.ShowModal()
    dialog.Destroy()
    app.Destroy()

if __name__ == "__main__":
    show_dialog()