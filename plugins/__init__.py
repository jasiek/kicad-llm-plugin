"""
KiCad LLM Plugin — __init__.py
Version: 1.5.1
Original: jasiek/kicad-llm-plugin
Fork:     northstarcomp/kicad-llm-plugin

Critical stability fixes applied on top of v1.5.0
"""

"""
KiCad LLM Plugin — __init__.py
Original: jasiek/kicad-llm-plugin  (MIT)
Fork:     northstarcomp/kicad-llm-plugin
Version:  1.5.0

KiCad 10 fixes
==============
1. show_toolbar_button = True  set explicitly in defaults()
2. icon_file_name uses os.path.abspath(__file__) — required for KiCad 10
3. dark_icon_file_name provided for dark-theme support
4. GetFootprints() replaces removed GetModules()

API support
===========
- Anthropic  : /v1/messages
- xAI        : /v1/responses  (Responses API — recommended by xAI, supports all Grok models)
- OpenAI     : /v1/chat/completions
- Ollama     : /v1/chat/completions  (OpenAI-compatible)
"""

import os
import sys
import json
import traceback
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


class ConfigManager:
    def __init__(self):
        self.config_path = Path.home() / ".kicad" / "kicad_llm_config.json"
        # [FIX-16] Added parents=True so it works on fresh installs where ~/.kicad doesn't exist yet
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except Exception:
                pass
        return {"last_model_index": 0, "api_keys": {}}

    def save(self):
        try:
            self.config_path.write_text(json.dumps(self.data, indent=2))
        except Exception:
            pass

    def get_api_key(self, provider: str) -> str:
        return self.data.get("api_keys", {}).get(provider, "")

    def set_api_key(self, provider: str, key: str):
        if "api_keys" not in self.data:
            self.data["api_keys"] = {}
        self.data["api_keys"][provider] = key
        self.save()

    def get_last_model_index(self) -> int:
        return self.data.get("last_model_index", 0)

    def set_last_model_index(self, index: int):
        self.data["last_model_index"] = index
        self.save()


def _make_config():
    """Safe factory so ConfigManager failures don't kill the plugin at import time."""
    try:
        return ConfigManager()
    except Exception:
        traceback.print_exc()
        class _NullConfig:
            def get_api_key(self, p): return ""
            def set_api_key(self, p, k): pass
            def get_last_model_index(self): return 0
            def set_last_model_index(self, i): pass
        return _NullConfig()


try:
    import pcbnew          # [FIX-17] Moved inside try/except so import errors are visible in KiCad console
    import wx              # [FIX-17]

    config = _make_config()   # [FIX-18] Safe creation — prevents module-level crash on fresh installs

    class LLMAnalyserPlugin(pcbnew.ActionPlugin):

        def defaults(self):
            self.name = "LLM Schematic Analyser"
            self.category = "Analyse"
            self.description = "Inspect your schematic with an LLM and get design improvement suggestions"
            self.show_toolbar_button = True                    # [OK] FIX-4
            icon = os.path.join(_HERE, "icon.png")
            icon_dark = os.path.join(_HERE, "icon_dark.png")
            self.icon_file_name = icon if os.path.isfile(icon) else ""                    # [OK] FIX-5
            self.dark_icon_file_name = icon_dark if os.path.isfile(icon_dark) else self.icon_file_name  # [OK] FIX-6

        def Run(self):
            board = pcbnew.GetBoard()
            if board is None:
                wx.MessageBox("No board is open. Open the PCB editor first.", "LLM Analyser", wx.OK | wx.ICON_WARNING)
                return
            dlg = _LLMDialog(None, _collect_board_info(board))
            dlg.ShowModal()
            dlg.Destroy()

    LLMAnalyserPlugin().register()

except Exception:
    traceback.print_exc()


def _collect_board_info(board):
    info = {
        "title": str(board.GetTitleBlock().GetTitle()) or "(untitled)",
        "footprints": [],
        "nets": [],
    }
    for fp in board.GetFootprints():                           # [OK] FIX-8
        info["footprints"].append({
            "ref":   str(fp.GetReference()),                   # [OK] FIX-7
            "value": str(fp.GetValue()),                       # [OK] FIX-7
            "layer": str(board.GetLayerName(fp.GetLayer())),   # [OK] FIX-7
        })
    for net_code, net in board.GetNetInfo().NetsByName().items():
        if net_code:
            info["nets"].append(str(net_code))                 # [OK] FIX-7
    return info


class _LLMDialog(wx.Dialog):

    _MODELS = [
        ("Grok 4 (xAI)",           "grok-4",           "https://api.x.ai/v1", "xai"),
        ("Grok 4 Fast (xAI)",      "grok-4-fast",      "https://api.x.ai/v1", "xai"),
        ("Grok 3 (xAI)",           "grok-3-latest",    "https://api.x.ai/v1", "xai"),
        ("Grok 3 Mini (xAI)",      "grok-3-mini-latest","https://api.x.ai/v1","xai"),
        ("Claude Sonnet 4",        "claude-sonnet-4-20250514", None,          "anthropic"),
        ("Claude Opus 4",          "claude-opus-4-20250514",   None,          "anthropic"),
        ("GPT-4o (OpenAI)",        "gpt-4o",           None,                  "openai"),
        ("GPT-4o-mini (OpenAI)",   "gpt-4o-mini",      None,                  "openai"),
        ("Ollama llama3 (local)",  "llama3",           "http://localhost:11434/v1", "openai"),
        ("Ollama mistral (local)", "mistral",          "http://localhost:11434/v1", "openai"),
    ]

    _PROVIDER_MAP = {"anthropic": "Anthropic", "openai": "OpenAI / Ollama", "xai": "xAI (Grok)"}

    def __init__(self, parent, board_info):
        super().__init__(parent, title="LLM Schematic Analyser", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._info = board_info
        self._build_ui()
        self._load_last_model_and_key()

    def _build_ui(self):
        p = self
        s = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(p, label=f"Board: {self._info['title']}  |  Footprints: {len(self._info['footprints'])}  Nets: {len(self._info['nets'])}")
        header.SetFont(header.GetFont().Bold())
        s.Add(header, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="Model:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._model = wx.Choice(p, choices=[m[0] for m in self._MODELS])
        self._model.Bind(wx.EVT_CHOICE, self._on_model_changed)
        row.Add(self._model, 1, wx.RIGHT, 12)

        row.Add(wx.StaticText(p, label="API Key:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._key = wx.TextCtrl(p, style=wx.TE_PASSWORD, size=(220, -1))
        row.Add(self._key, 0)

        self._btn_clear = wx.Button(p, label="Clear Keys", size=(80, 24))
        self._btn_clear.Bind(wx.EVT_BUTTON, self._on_clear_keys)
        row.Add(self._btn_clear, 0, wx.LEFT, 6)
        s.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        row3 = wx.BoxSizer(wx.HORIZONTAL)
        row3.Add(wx.StaticText(p, label="Base URL:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._url = wx.TextCtrl(p)
        self._url.SetHint("Leave blank for cloud providers")
        row3.Add(self._url, 1)
        s.Add(row3, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._run_btn = wx.Button(p, label="▶  Run Analysis")
        self._run_btn.Bind(wx.EVT_BUTTON, self._on_run)
        s.Add(self._run_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        h1 = wx.BoxSizer(wx.HORIZONTAL)
        h1.Add(wx.StaticText(p, label="AI Response:"), 0)
        h1.AddStretchSpacer()
        self._btn_copy_result = wx.Button(p, label="Copy", size=(60, 24))
        self._btn_copy_result.Bind(wx.EVT_BUTTON, self._on_copy_result)
        h1.Add(self._btn_copy_result, 0)
        s.Add(h1, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self._result = wx.TextCtrl(p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP, size=(-1, 260))
        s.Add(self._result, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        token_box = wx.StaticBoxSizer(wx.StaticBox(p, label="Token Usage"), wx.VERTICAL)
        grid = wx.FlexGridSizer(3, 2, 4, 12)
        grid.Add(wx.StaticText(p, label="Input:"))
        self._token_input = wx.StaticText(p, label="0")
        grid.Add(self._token_input)
        grid.Add(wx.StaticText(p, label="Output:"))
        self._token_output = wx.StaticText(p, label="0")
        grid.Add(self._token_output)
        grid.Add(wx.StaticText(p, label="Total:"))
        self._token_total = wx.StaticText(p, label="0")
        grid.Add(self._token_total)
        token_box.Add(grid, 0, wx.ALL, 8)

        self._btn_copy_tokens = wx.Button(p, label="Copy Token Usage", size=(140, 24))
        self._btn_copy_tokens.Bind(wx.EVT_BUTTON, self._on_copy_tokens)
        token_box.Add(self._btn_copy_tokens, 0, wx.LEFT | wx.BOTTOM, 8)
        s.Add(token_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        btn_close = wx.Button(p, wx.ID_CLOSE, label="Close")
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        s.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        p.SetSizerAndFit(s)
        self.SetSize((720, 640))

    def _load_last_model_and_key(self):
        idx = config.get_last_model_index()
        if idx < len(self._MODELS):
            self._model.SetSelection(idx)
            self._on_model_changed(None)

    def _on_model_changed(self, _event):
        idx = int(self._model.GetSelection())                    # [OK] FIX-10
        _, _, default_url, api_type = self._MODELS[idx]
        self._url.SetValue(default_url or "")
        self._key.SetValue(config.get_api_key(api_type))

    def _on_clear_keys(self, _event):
        idx = int(self._model.GetSelection())
        _, _, _, api_type = self._MODELS[idx]
        name = self._PROVIDER_MAP.get(api_type, api_type)
        if wx.MessageBox(f"Clear saved key for {name}?", "Clear Key", wx.YES_NO) == wx.YES:
            config.set_api_key(api_type, "")
            self._key.SetValue("")

    def _on_run(self, _event):
        idx = int(self._model.GetSelection())
        _, model_id, default_url, api_type = self._MODELS[idx]
        api_key = str(self._key.GetValue()).strip()
        base_url = str(self._url.GetValue()).strip() or default_url

        if api_key:
            config.set_api_key(api_type, api_key)
        config.set_last_model_index(idx)

        if not api_key and api_type != "openai":
            wx.MessageBox("Please enter an API key.", "Error", wx.OK | wx.ICON_WARNING)
            return

        self._run_btn.Disable()
        self._result.SetValue("Running…")
        self._token_input.SetLabel("0")
        self._token_output.SetLabel("0")
        self._token_total.SetLabel("0")
        wx.Yield()

        try:
            text, usage = self._call_llm(model_id, api_key, base_url, api_type)
        except Exception as e:
            text = f"Error: {e}"
            usage = {}

        self._result.SetValue(text)

        if api_type == "anthropic":
            self._token_input.SetLabel(str(usage.get("input_tokens", 0)))
            self._token_output.SetLabel(str(usage.get("output_tokens", 0)))
            self._token_total.SetLabel("N/A")
        elif api_type == "xai":
            self._token_input.SetLabel(str(usage.get("input_tokens", 0)))
            self._token_output.SetLabel(str(usage.get("output_tokens", 0)))
            self._token_total.SetLabel(str(usage.get("total_tokens", 0)))
        else:
            self._token_input.SetLabel(str(usage.get("prompt_tokens", 0)))
            self._token_output.SetLabel(str(usage.get("completion_tokens", 0)))
            self._token_total.SetLabel(str(usage.get("total_tokens", 0)))

        self._run_btn.Enable()

    def _on_copy_result(self, _event):
        self._copy_to_clipboard(self._result.GetValue())

    def _on_copy_tokens(self, _event):
        text = f"Input: {self._token_input.GetLabel()}\nOutput: {self._token_output.GetLabel()}\nTotal: {self._token_total.GetLabel()}"
        self._copy_to_clipboard(text)

    def _copy_to_clipboard(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
            wx.MessageBox("Copied to clipboard", "Success", wx.OK | wx.ICON_INFORMATION)

    def _prompt(self):
        lines = [
            "You are an electronics design expert reviewing a KiCad schematic/PCB.",
            "Based on the component list and net names below, identify:",
            "1. Fatal flaws", "2. Design-rule / best-practice violations", "3. Nice-to-have improvements",
            "", f"Board: {self._info['title']}", "", "Footprints (ref, value, layer):",
        ]
        for fp in self._info["footprints"]:
            lines.append(f"  {fp['ref']}  {fp['value']}  ({fp['layer']})")
        lines += ["", "Nets (up to 120):"]
        for net in sorted(self._info["nets"])[:120]:
            lines.append(f"  {net}")
        return "\n".join(lines)

    def _call_llm(self, model_id, api_key, base_url, api_type):
        import urllib.request
        prompt = self._prompt()
        system = "You are an electronics design expert reviewing a KiCad schematic/PCB."

        if api_type == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            hdrs = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
            body = {"model": model_id, "max_tokens": 4096, "system": system,
                    "messages": [{"role": "user", "content": prompt}]}
        elif api_type == "xai":
            url = (base_url or "https://api.x.ai/v1") + "/responses"
            hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            body = {"model": model_id, "max_output_tokens": 4096, "input": f"{system}\n\n{prompt}"}
        else:
            url = (base_url or "https://api.openai.com/v1") + "/chat/completions"
            hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            body = {"model": model_id, "max_tokens": 4096,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}

        req = urllib.request.Request(url, json.dumps(body).encode(), hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("error", {})
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get("message", err_body)
            except Exception:
                err_msg = err_body
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_msg}")

        if api_type == "anthropic":
            result = data["content"][0]["text"]
            usage = data.get("usage", {})
        elif api_type == "xai":
            result = data["output"][0]["content"][0]["text"]
            usage = data.get("usage", {})
        else:
            result = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

        return result, usage
