"""
KiCad LLM Plugin — __init__.py
Original: jasiek/kicad-llm-plugin  (MIT)
Fork:     northstarcomp/kicad-llm-plugin

KiCad 10 fixes applied
=======================
1. show_toolbar_button = True  set explicitly in defaults()
2. icon_file_name uses os.path.abspath(__file__) — required for KiCad 10
3. dark_icon_file_name provided for dark-theme support
4. GetFootprints() replaces removed GetModules()
5. Entire plugin in __init__.py so the icon path is always correct
   regardless of whether the plugin is installed via PCM or cloned directly

Icon path notes
---------------
KiCad resolves icon_file_name at the time defaults() is called, which
happens during plugin discovery. The path MUST be absolute. Using
os.path.dirname(os.path.abspath(__file__)) guarantees this works whether
the plugin is:
  - cloned into  .../scripting/plugins/kicad-llm-plugin/
  - installed by PCM into .../scripting/plugins/com.github.northstarcomp.kicad-llm-plugin/plugins/
"""

import os
import sys
import traceback

# ── make sure our own directory is importable (for future submodules) ──────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── guard the whole registration so a crash here doesn't break KiCad ───────
try:
    import pcbnew
    import wx

    class LLMAnalyserPlugin(pcbnew.ActionPlugin):

        def defaults(self):
            self.name        = "LLM Schematic Analyser"
            self.category    = "Analyse"
            self.description = ("Inspect your schematic with an LLM "
                                "and get design improvement suggestions")

            # ── CRITICAL for KiCad 10 toolbar button ──────────────────────
            self.show_toolbar_button = True

            # ── CRITICAL: icon path must be absolute ──────────────────────
            # _HERE is set at module level (top of this file) to the
            # directory containing this __init__.py — i.e. the plugins/ dir.
            icon       = os.path.join(_HERE, "icon.png")
            icon_dark  = os.path.join(_HERE, "icon_dark.png")

            self.icon_file_name      = icon      if os.path.isfile(icon)      else ""
            self.dark_icon_file_name = icon_dark if os.path.isfile(icon_dark) else self.icon_file_name

        # ── called when toolbar button or menu item is clicked ─────────────
        def Run(self):
            board = pcbnew.GetBoard()
            if board is None:
                wx.MessageBox(
                    "No board is open.\n"
                    "Open the PCB editor first (even an empty board works).",
                    "LLM Analyser", wx.OK | wx.ICON_WARNING)
                return

            info = _collect_board_info(board)
            dlg  = _LLMDialog(None, info)
            dlg.ShowModal()
            dlg.Destroy()

    # ── register ───────────────────────────────────────────────────────────
    LLMAnalyserPlugin().register()

except Exception:
    traceback.print_exc()   # visible in KiCad scripting console


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _collect_board_info(board):
    """Return a dict of board data. Uses KiCad 7+ API (GetFootprints)."""
    info = {
        "title":      board.GetTitleBlock().GetTitle() or "(untitled)",
        "footprints": [],
        "nets":       [],
    }
    for fp in board.GetFootprints():          # GetModules() removed in KiCad 7
        info["footprints"].append({
            "ref":   fp.GetReference(),
            "value": fp.GetValue(),
            "layer": board.GetLayerName(fp.GetLayer()),
        })
    net_info = board.GetNetInfo()
    for net_code, net in net_info.NetsByName().items():
        if net_code:
            info["nets"].append(net_code)
    return info


# ═══════════════════════════════════════════════════════════════════════════
#  Dialog
# ═══════════════════════════════════════════════════════════════════════════

class _LLMDialog(wx.Dialog):

   _MODELS = [
    # label,                              model_id,                    base_url
    ("Grok 3 (xAI)",                      "grok-3-latest",             "https://api.x.ai/v1"),
    ("Grok 3 Mini (xAI)",                 "grok-3-mini-latest",        "https://api.x.ai/v1"),
    ("Claude Sonnet 4 (Anthropic)",       "claude-sonnet-4-20250514",  None),
    ("Claude Opus 4 (Anthropic)",         "claude-opus-4-20250514",    None),
    ("GPT-4o (OpenAI)",                   "gpt-4o",                    None),
    ("GPT-4o-mini (OpenAI)",              "gpt-4o-mini",               None),
    ("Ollama llama3 (local)",             "llama3",                    "http://localhost:11434/v1"),
    ("Ollama mistral (local)",            "mistral",                   "http://localhost:11434/v1"),
    ("Ollama gemma2 (local)",             "gemma2",                    "http://localhost:11434/v1"),
]

    def __init__(self, parent, board_info):
        super().__init__(parent, title="LLM Schematic Analyser",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._info = board_info
        self._build_ui()

    def _build_ui(self):
        p = self
        s = wx.BoxSizer(wx.VERTICAL)

        # summary
        fp_count  = len(self._info["footprints"])
        net_count = len(self._info["nets"])
        s.Add(wx.StaticText(p, label=(
            f"Board: {self._info['title']}\n"
            f"Footprints: {fp_count}   Nets: {net_count}"
        )), 0, wx.ALL, 8)

        # model
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="Model:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._model = wx.Choice(p, choices=[m[0] for m in self._MODELS])
        self._model.SetSelection(0)
        self._model.Bind(wx.EVT_CHOICE, self._on_model)
        row.Add(self._model, 1)
        s.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # API key
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(wx.StaticText(p, label="API Key:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._key = wx.TextCtrl(p, style=wx.TE_PASSWORD)
        row2.Add(self._key, 1)
        s.Add(row2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # base URL (local models)
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        row3.Add(wx.StaticText(p, label="Base URL:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._url = wx.TextCtrl(p)
        self._url.SetHint("Leave blank for cloud providers")
        row3.Add(self._url, 1)
        s.Add(row3, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # run button
        self._run_btn = wx.Button(p, label="▶  Run Analysis")
        self._run_btn.Bind(wx.EVT_BUTTON, self._on_run)
        s.Add(self._run_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # results
        s.Add(wx.StaticText(p, label="Results:"), 0, wx.LEFT, 8)
        self._result = wx.TextCtrl(p,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(-1, 300))
        s.Add(self._result, 1, wx.EXPAND | wx.ALL, 8)

        # close
        btn_close = wx.Button(p, wx.ID_CLOSE, label="Close")
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        s.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        p.SetSizerAndFit(s)
        self.SetSize((620, 580))

    def _on_model(self, _event):
        idx = self._model.GetSelection()
        self._url.SetValue(self._MODELS[idx][2] or "")

    def _on_run(self, _event):
        idx       = self._model.GetSelection()
        _, model_id, default_url = self._MODELS[idx]
        api_key   = self._key.GetValue().strip()
        base_url  = self._url.GetValue().strip() or default_url

        if not api_key and not base_url:
            wx.MessageBox("Please enter an API key.", "LLM Analyser",
                          wx.OK | wx.ICON_WARNING)
            return

        self._run_btn.Disable()
        self._result.SetValue("Running… please wait.")
        wx.Yield()

        try:
            text = self._call_llm(model_id, api_key, base_url)
        except Exception as exc:
            text = f"Error:\n{exc}"

        self._result.SetValue(text)
        self._run_btn.Enable()

    def _prompt(self):
        lines = [
            "You are an electronics design expert reviewing a KiCad schematic/PCB.",
            "Based on the component list and net names below, identify:",
            "1. Fatal flaws",
            "2. Design-rule / best-practice violations",
            "3. Nice-to-have improvements",
            "",
            f"Board: {self._info['title']}",
            "",
            "Footprints (ref, value, layer):",
        ]
        for fp in self._info["footprints"]:
            lines.append(f"  {fp['ref']}  {fp['value']}  ({fp['layer']})")
        lines += ["", "Nets (up to 120):"]
        for net in sorted(self._info["nets"])[:120]:
            lines.append(f"  {net}")
        return "\n".join(lines)

    def _call_llm(self, model_id, api_key, base_url):
    import json, urllib.request

    prompt = self._prompt()
    is_anthropic = model_id.startswith("claude")
    is_xai = base_url and "x.ai" in base_url

    if is_anthropic:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        body = {
            "model": model_id,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
    else:
        # OpenAI-compatible (OpenAI, xAI, Ollama)
        url = (base_url or "https://api.openai.com/v1") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        body = {
            "model": model_id,
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": "You are an electronics design expert reviewing a KiCad schematic/PCB."},
                {"role": "user", "content": prompt}
            ]
        }

    req = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())

    # Extract token usage when available
    usage_text = ""
    if "usage" in data:
        u = data["usage"]
        usage_text = (f"\n\n--- Token Usage ---\n"
                      f"Prompt: {u.get('prompt_tokens', 0)} | "
                      f"Completion: {u.get('completion_tokens', 0)} | "
                      f"Total: {u.get('total_tokens', 0)}")

    if is_anthropic:
        result = data["content"][0]["text"]
    else:
        result = data["choices"][0]["message"]["content"]

    return result + usage_text
