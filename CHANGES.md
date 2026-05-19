# KiCad LLM Plugin — Change Annotations
## Original (jasiek) → v1.5.0 (northstarcomp)

All fixes are marked with `[FIX-N]` tags, summarised at the bottom.

---

```python
"""
KiCad LLM Plugin — __init__.py
Original: jasiek/kicad-llm-plugin  (MIT)
Fork:     northstarcomp/kicad-llm-plugin
Version:  1.5.0                                    # [FIX-1] version number added

KiCad 10 fixes
==============
1. show_toolbar_button = True  set explicitly in defaults()
2. icon_file_name uses os.path.abspath(__file__) — required for KiCad 10
3. dark_icon_file_name provided for dark-theme support
4. GetFootprints() replaces removed GetModules()

API support
===========
- Anthropic  : /v1/messages
- xAI        : /v1/responses  (Responses API — recommended, supports all Grok models)
- OpenAI     : /v1/chat/completions
- Ollama     : /v1/chat/completions  (OpenAI-compatible)
"""

import os
import sys
import traceback

# [FIX-2] Capture the plugin directory at module load time using abspath(__file__).
# This MUST be done at module level, not inside defaults(), because KiCad may
# change the working directory between module load and defaults() being called.
# Without abspath() the icon is never found and the toolbar button has no icon.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# [FIX-3] Wrap ALL registration code in try/except + traceback.print_exc().
# Without this, any import or class error silently prevents the plugin loading.
# With it, the full traceback appears in KiCad's scripting console for debugging.
try:
    import pcbnew
    import wx

    class LLMAnalyserPlugin(pcbnew.ActionPlugin):

        def defaults(self):
            self.name        = "LLM Schematic Analyser"
            self.category    = "Analyse"
            self.description = ("Inspect your schematic with an LLM "
                                "and get design improvement suggestions")

            # [FIX-4] show_toolbar_button MUST be explicitly True in KiCad 10.
            # If omitted or False the toolbar button never appears — no error shown.
            self.show_toolbar_button = True

            # [FIX-5] Icon paths MUST be absolute in KiCad 10.
            # Relative paths worked in KiCad 9 but silently fail in KiCad 10.
            # We use _HERE (captured at module level above) to build absolute paths.
            # isfile() check means a missing icon degrades gracefully (no crash).
            icon       = os.path.join(_HERE, "icon.png")
            icon_dark  = os.path.join(_HERE, "icon_dark.png")
            self.icon_file_name      = icon      if os.path.isfile(icon)      else ""
            self.dark_icon_file_name = icon_dark if os.path.isfile(icon_dark) else self.icon_file_name
            # [FIX-6] dark_icon_file_name is new in KiCad 9/10 — without it the
            # icon looks wrong or fails to load on dark themes.

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
    traceback.print_exc()   # visible in KiCad scripting console


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _collect_board_info(board):
    # [FIX-7] ALL KiCad API calls (GetTitle, GetReference, GetValue,
    # GetLayerName, NetsByName keys) return wxString objects, NOT Python str.
    # wxString does not support Python's < comparison operator, so any operation
    # that sorts, compares, or uses them as dict keys raises:
    #   "'<' not supported between instances of 'wxString' and 'wxString'"
    # Fix: wrap every KiCad string return in str() at the point of collection.
    info = {
        "title":      str(board.GetTitleBlock().GetTitle()) or "(untitled)",
        "footprints": [],
        "nets":       [],
    }

    # [FIX-8] GetModules() was removed in KiCad 7. Replaced with GetFootprints().
    # GetModules() raises AttributeError on KiCad 7/8/9/10 — silent crash on load.
    for fp in board.GetFootprints():
        info["footprints"].append({
            "ref":   str(fp.GetReference()),   # [FIX-7] wxString → str
            "value": str(fp.GetValue()),        # [FIX-7] wxString → str
            "layer": str(board.GetLayerName(fp.GetLayer())),  # [FIX-7] wxString → str
        })
    net_info = board.GetNetInfo()
    for net_code, net in net_info.NetsByName().items():
        if net_code:
            info["nets"].append(str(net_code))  # [FIX-7] wxString → str
    return info


# ═══════════════════════════════════════════════════════════════════════════
#  Dialog
# ═══════════════════════════════════════════════════════════════════════════

class _LLMDialog(wx.Dialog):

    # [FIX-9] Model list extended with 4-tuple (label, model_id, base_url, api_type).
    # The api_type field ('anthropic', 'xai', 'openai') drives which API format
    # is used in _call_llm — cleaner than string-matching on URLs or model IDs.
    # xAI models added using the Responses API endpoint.
    _MODELS = [
        # label,                              model_id,                    base_url,                   api_type
        ("Grok 4 (xAI)",                      "grok-4",                    "https://api.x.ai/v1",      "xai"),
        ("Grok 4 Fast (xAI)",                 "grok-4-fast",               "https://api.x.ai/v1",      "xai"),
        ("Grok 3 (xAI)",                      "grok-3-latest",             "https://api.x.ai/v1",      "xai"),
        ("Grok 3 Mini (xAI)",                 "grok-3-mini-latest",        "https://api.x.ai/v1",      "xai"),
        ("Claude Sonnet 4 (Anthropic)",       "claude-sonnet-4-20250514",  None,                       "anthropic"),
        ("Claude Opus 4 (Anthropic)",         "claude-opus-4-20250514",    None,                       "anthropic"),
        ("GPT-4o (OpenAI)",                   "gpt-4o",                    None,                       "openai"),
        ("GPT-4o-mini (OpenAI)",              "gpt-4o-mini",               None,                       "openai"),
        ("Ollama llama3 (local)",             "llama3",                    "http://localhost:11434/v1", "openai"),
        ("Ollama mistral (local)",            "mistral",                   "http://localhost:11434/v1", "openai"),
        ("Ollama gemma2 (local)",             "gemma2",                    "http://localhost:11434/v1", "openai"),
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
        # [FIX-10] KiCad's bundled wxPython can return a wxString from
        # GetSelection() instead of a Python int. Using it directly as a list
        # index raises "'<' not supported between instances of 'wxString' and
        # 'wxString'". Fix: always wrap GetSelection() with int().
        idx = int(self._model.GetSelection())
        self._url.SetValue(self._MODELS[idx][2] or "")

    def _on_run(self, _event):
        idx = int(self._model.GetSelection())          # [FIX-10] wxString → int
        _, model_id, default_url, api_type = self._MODELS[idx]
        api_key  = str(self._key.GetValue()).strip()   # [FIX-7]  wxString → str
        base_url = str(self._url.GetValue()).strip() or default_url  # [FIX-7]

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
        # [FIX-7] sorted() uses < to compare — would crash on wxString.
        # Safe because net_code was already cast to str() in _collect_board_info.
        for net in sorted(self._info["nets"])[:120]:
            lines.append(f"  {net}")
        return "\n".join(lines)

    def _call_llm(self, model_id, api_key, base_url, api_type):
        import json, urllib.request
        prompt = self._prompt()
        system = "You are an electronics design expert reviewing a KiCad schematic/PCB."

        # ── Build request ──────────────────────────────────────────────────

        if api_type == "anthropic":
            # Anthropic Messages API — unchanged, was working in original
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
            # [FIX-11] xAI uses the Responses API, NOT /v1/chat/completions.
            # Key differences from OpenAI format:
            #   - endpoint:  /v1/responses  (not /v1/chat/completions)
            #   - input key: "input"        (not "messages")
            #   - token key: "max_output_tokens" (not "max_tokens")
            #   - input value: plain string (not array of role/content objects)
            #     (array format caused HTTP 400 Bad Request on some Grok models)
            url  = (base_url or "https://api.x.ai/v1") + "/responses"
            hdrs = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            body = {
                "model": model_id,
                "max_output_tokens": 4096,
                "input": f"{system}\n\n{prompt}",   # plain string — always valid
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
            # [FIX-12] Original code let HTTPError propagate as a raw exception
            # showing only "HTTP Error 400: Bad Request" with no detail.
            # Now we read the response body and surface the actual API error
            # message (e.g. "model not found", "invalid field") in the UI.
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                err_msg  = err_json.get("error", {})
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get("message", err_body)
            except Exception:
                err_msg = err_body
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_msg}")

        # ── Parse response + token usage ───────────────────────────────────

        if api_type == "anthropic":
            # Response shape: {"content": [{"type": "text", "text": "..."}],
            #                  "usage": {"input_tokens": N, "output_tokens": N}}
            result = data["content"][0]["text"]
            u = data.get("usage", {})
            # [FIX-13] Anthropic uses input_tokens/output_tokens — NOT
            # prompt_tokens/completion_tokens (those are OpenAI field names).
            usage_text = (f"\n\n--- Token Usage ---\n"
                          f"Input: {u.get('input_tokens', 0)} | "
                          f"Output: {u.get('output_tokens', 0)}")

        elif api_type == "xai":
            # [FIX-14] xAI Responses API shape is completely different from
            # OpenAI. Text is nested at output[0].content[0].text, not at
            # choices[0].message.content.
            # Response shape: {"output": [{"type": "message",
            #                   "content": [{"type": "output_text",
            #                               "text": "..."}]}],
            #                  "usage": {"input_tokens": N, "output_tokens": N,
            #                            "total_tokens": N}}
            result = data["output"][0]["content"][0]["text"]
            u = data.get("usage", {})
            usage_text = (f"\n\n--- Token Usage ---\n"
                          f"Input: {u.get('input_tokens', 0)} | "
                          f"Output: {u.get('output_tokens', 0)} | "
                          f"Total: {u.get('total_tokens', 0)}")

        else:
            # OpenAI shape: {"choices": [{"message": {"content": "..."}}],
            #                "usage": {"prompt_tokens": N,
            #                          "completion_tokens": N, "total_tokens": N}}
            result = data["choices"][0]["message"]["content"]
            u = data.get("usage", {})
            usage_text = (f"\n\n--- Token Usage ---\n"
                          f"Prompt: {u.get('prompt_tokens', 0)} | "
                          f"Completion: {u.get('completion_tokens', 0)} | "
                          f"Total: {u.get('total_tokens', 0)}")

        # [FIX-15] Original code had return result + usage_text as dead code
        # after separate if/else return statements — it was never reached.
        # Restructured so result and usage_text are always built first,
        # then returned together in a single return at the end.
        return result + usage_text
```

---

## Fix Summary

| # | What | Why it broke |
|---|------|-------------|
| FIX-1 | Version set to `1.5.0` in docstring and `metadata.json` | PCM showed stale version |
| FIX-2 | `_HERE` captured at module level with `os.path.abspath(__file__)` | KiCad 10 changes working dir; relative paths for icons silently fail |
| FIX-3 | Entire registration wrapped in `try/except + traceback.print_exc()` | Silent load failures gave no diagnostic output |
| FIX-4 | `self.show_toolbar_button = True` set explicitly | KiCad 10 requires explicit True; omitting it hides the toolbar button |
| FIX-5 | Icon paths built from `_HERE` (absolute) | KiCad 10 requires absolute icon paths; relative paths silently fail |
| FIX-6 | `dark_icon_file_name` attribute added | Icon missing or wrong on dark themes in KiCad 9/10 |
| FIX-7 | All KiCad API returns wrapped in `str()` | KiCad returns `wxString`; `sorted()` and `<` comparisons crash on wxString |
| FIX-8 | `GetFootprints()` replaces `GetModules()` | `GetModules()` removed in KiCad 7; raises `AttributeError` on load |
| FIX-9 | Model list extended to 4-tuple with explicit `api_type` field | Clean routing to correct API format without fragile string matching |
| FIX-10 | `int(self._model.GetSelection())` | KiCad's bundled wx returns `wxString` from `GetSelection()`; crashes as list index |
| FIX-11 | xAI uses `/v1/responses` with `input` string and `max_output_tokens` | xAI Responses API is different from OpenAI `/v1/chat/completions`; wrong format → HTTP 400 |
| FIX-12 | `HTTPError` caught and body decoded for readable error messages | Raw `HTTPError` only shows status code, not the API's actual error message |
| FIX-13 | Anthropic token fields: `input_tokens` / `output_tokens` | Anthropic uses different field names from OpenAI |
| FIX-14 | xAI response parsed from `output[0].content[0].text` | xAI Responses API nests the text differently from OpenAI `choices[0].message.content` |
| FIX-15 | Single `return result + usage_text` at end of `_call_llm` | Original had `return result + usage_text` as unreachable dead code after early returns |

## metadata.json fixes

| Issue | Fix |
|-------|-----|
| `"$schema"` pointing to v2 | Changed to v1 — v2 caused validator failures |
| Extra top-level fields (`version`, `kicad_version`, `url`) | Removed — these belong only inside `versions[]` |
| `"web"` contact key | Changed to `"github"` — only specific keys are valid in v1 schema |
| `download_sha256: ""`, `download_size: 0` | Removed entirely — empty/zero optional fields fail schema validation |
| `kicad_version: "10.0"` | Changed to `"8.0"` — validator is proven against this value |
| Zip built from parent folder | Rebuilt from inside plugin folder so `metadata.json` is at archive root |
