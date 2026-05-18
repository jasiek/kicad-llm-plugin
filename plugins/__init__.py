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
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    import pcbnew
    import wx

    class LLMAnalyserPlugin(pcbnew.ActionPlugin):

        def defaults(self):
            self.name        = "LLM Schematic Analyser"
            self.category    = "Analyse"
            self.description = ("Inspect your schematic with an LLM "
                                "and get design improvement suggestions")
            self.show_toolbar_button = True
            icon       = os.path.join(_HERE, "icon.png")
            icon_dark  = os.path.join(_HERE, "icon_dark.png")
            self.icon_file_name      = icon      if os.path.isfile(icon)      else ""
            self.dark_icon_file_name = icon_dark if os.path.isfile(icon_dark) else self.icon_file_name

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

    LLMAnalyserPlugin().register()

except Exception:
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _collect_board_info(board):
    """Return a dict of board data. Uses KiCad 7+ API (GetFootprints).
    All KiCad API calls return wxString objects — cast everything to str()
    immediately so Python string ops (sorted, comparison, f-strings) work.
    """
    info = {
        "title":      str(board.GetTitleBlock().GetTitle()) or "(untitled)",
        "footprints": [],
        "nets":       [],
    }
    for fp in board.GetFootprints():
        info["footprints"].append({
            "ref":   str(fp.GetReference()),
            "value": str(fp.GetValue()),
            "layer": str(board.GetLayerName(fp.GetLayer())),
        })
    net_info = board.GetNetInfo()
    for net_code, net in net_info.NetsByName().items():
        if net_code:
            info["nets"].append(str(net_code))  # wxString — must cast to str
    return info


# ═══════════════════════════════════════════════════════════════════════════
#  Dialog
# ═══════════════════════════════════════════════════════════════════════════

class _LLMDialog(wx.Dialog):

    _MODELS = [
        # label,                              model_id,                    base_url,                  api_type
        ("Grok 4 (xAI)",                      "grok-4",                    "https://api.x.ai/v1",     "xai"),
        ("Grok 4 Fast (xAI)",                 "grok-4-fast",               "https://api.x.ai/v1",     "xai"),
        ("Grok 3 (xAI)",                      "grok-3-latest",             "https://api.x.ai/v1",     "xai"),
        ("Grok 3 Mini (xAI)",                 "grok-3-mini-latest",        "https://api.x.ai/v1",     "xai"),
        ("Claude Sonnet 4 (Anthropic)",       "claude-sonnet-4-20250514",  None,                      "anthropic"),
        ("Claude Opus 4 (Anthropic)",         "claude-opus-4-20250514",    None,                      "anthropic"),
        ("GPT-4o (OpenAI)",                   "gpt-4o",                    None,                      "openai"),
        ("GPT-4o-mini (OpenAI)",              "gpt-4o-mini",               None,                      "openai"),
        ("Ollama llama3 (local)",             "llama3",                    "http://localhost:11434/v1","openai"),
        ("Ollama mistral (local)",            "mistral",                   "http://localhost:11434/v1","openai"),
        ("Ollama gemma2 (local)",             "gemma2",                    "http://localhost:11434/v1","openai"),
    ]

    def __init__(self, parent, board_info):
        super().__init__(parent, title="LLM Schematic Analyser",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._info = board_info
        self._build_ui()

    def _build_ui(self):
        p = self
        s = wx.BoxSizer(wx.VERTICAL)

        fp_count  = len(self._info["footprints"])
        net_count = len(self._info["nets"])
        s.Add(wx.StaticText(p, label=(
            f"Board: {self._info['title']}\n"
            f"Footprints: {fp_count}   Nets: {net_count}"
        )), 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="Model:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._model = wx.Choice(p, choices=[m[0] for m in self._MODELS])
        self._model.SetSelection(0)
        self._model.Bind(wx.EVT_CHOICE, self._on_model)
        row.Add(self._model, 1)
        s.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(wx.StaticText(p, label="API Key:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._key = wx.TextCtrl(p, style=wx.TE_PASSWORD)
        row2.Add(self._key, 1)
        s.Add(row2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        row3 = wx.BoxSizer(wx.HORIZONTAL)
        row3.Add(wx.StaticText(p, label="Base URL:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._url = wx.TextCtrl(p)
        self._url.SetHint("Leave blank for cloud providers")
        row3.Add(self._url, 1)
        s.Add(row3, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._run_btn = wx.Button(p, label="▶  Run Analysis")
        self._run_btn.Bind(wx.EVT_BUTTON, self._on_run)
        s.Add(self._run_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        s.Add(wx.StaticText(p, label="Results:"), 0, wx.LEFT, 8)
        self._result = wx.TextCtrl(p,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(-1, 300))
        s.Add(self._result, 1, wx.EXPAND | wx.ALL, 8)

        btn_close = wx.Button(p, wx.ID_CLOSE, label="Close")
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        s.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        p.SetSizerAndFit(s)
        self.SetSize((620, 580))

    def _on_model(self, _event):
        idx = int(self._model.GetSelection())   # cast: KiCad's wx can return wxString
        self._url.SetValue(self._MODELS[idx][2] or "")

    def _on_run(self, _event):
        idx = int(self._model.GetSelection())   # cast: KiCad's wx can return wxString
        _, model_id, default_url, api_type = self._MODELS[idx]
        api_key  = str(self._key.GetValue()).strip()
        base_url = str(self._url.GetValue()).strip() or default_url

        if not api_key and api_type != "openai":  # Ollama needs no key
            wx.MessageBox("Please enter an API key.", "LLM Analyser",
                          wx.OK | wx.ICON_WARNING)
            return

        self._run_btn.Disable()
        self._result.SetValue("Running… please wait.")
        wx.Yield()

        try:
            text = self._call_llm(model_id, api_key, base_url, api_type)
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

    def _call_llm(self, model_id, api_key, base_url, api_type):
        import json, urllib.request
        prompt = self._prompt()
        system = "You are an electronics design expert reviewing a KiCad schematic/PCB."

        # ── Build request ──────────────────────────────────────────────────

        if api_type == "anthropic":
            # Anthropic Messages API
            url  = "https://api.anthropic.com/v1/messages"
            hdrs = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            body = {
                "model": model_id,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }

        elif api_type == "xai":
            # xAI Responses API — https://docs.x.ai/developers/rest-api-reference/inference/chat
            # input accepts a string or array of message objects
            url  = (base_url or "https://api.x.ai/v1") + "/responses"
            hdrs = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            body = {
                "model": model_id,
                "max_output_tokens": 4096,
                "input": f"{system}\n\n{prompt}",  # plain string — simplest valid format
            }

        else:
            # OpenAI-compatible: OpenAI, Ollama
            url  = (base_url or "https://api.openai.com/v1") + "/chat/completions"
            hdrs = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            body = {
                "model": model_id,
                "max_tokens": 4096,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
            }

        # ── Execute request ────────────────────────────────────────────────

        req = urllib.request.Request(
            url, json.dumps(body).encode(), hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            # Read the error body so we can show the actual API error message
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                err_msg  = err_json.get("error", {})
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get("message", err_body)
            except Exception:
                err_msg = err_body
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_msg}")

        # ── Parse response text ────────────────────────────────────────────

        if api_type == "anthropic":
            # {"content": [{"type": "text", "text": "..."}], "usage": {"input_tokens": N, "output_tokens": N}}
            result = data["content"][0]["text"]
            u = data.get("usage", {})
            usage_text = (f"\n\n--- Token Usage ---\n"
                          f"Input: {u.get('input_tokens', 0)} | "
                          f"Output: {u.get('output_tokens', 0)}")

        elif api_type == "xai":
            # {"output": [{"type": "message", "content": [{"type": "output_text", "text": "..."}]}],
            #  "usage": {"input_tokens": N, "output_tokens": N, "total_tokens": N}}
            result = data["output"][0]["content"][0]["text"]
            u = data.get("usage", {})
            usage_text = (f"\n\n--- Token Usage ---\n"
                          f"Input: {u.get('input_tokens', 0)} | "
                          f"Output: {u.get('output_tokens', 0)} | "
                          f"Total: {u.get('total_tokens', 0)}")

        else:
            # {"choices": [{"message": {"content": "..."}}], "usage": {"prompt_tokens": N, ...}}
            result = data["choices"][0]["message"]["content"]
            u = data.get("usage", {})
            usage_text = (f"\n\n--- Token Usage ---\n"
                          f"Prompt: {u.get('prompt_tokens', 0)} | "
                          f"Completion: {u.get('completion_tokens', 0)} | "
                          f"Total: {u.get('total_tokens', 0)}")

        return result + usage_text
