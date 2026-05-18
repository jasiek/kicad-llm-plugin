"""
KiCad LLM Plugin — __init__.py
Version: 1.6.0
Original: jasiek/kicad-llm-plugin  (MIT)
Fork:     northstarcomp/kicad-llm-plugin

v1.6.0 additions
=================
- Dual-context awareness: detects whether a .kicad_sch file exists alongside
  the .kicad_pcb and parses it automatically
- Schematic data collection: extracts symbols, power symbols, net labels and
  no-connect flags from the .kicad_sch file using a lightweight regex parser
  (KiCad 10 does not expose a live schematic Python API from ActionPlugin —
   reading the saved file is the same approach KiCad's own exporters use)
- Context-aware prompts:
    'pcb'       — PCB layout, DRC, placement, copper
    'schematic' — symbols, pin connections, power, decoupling caps (future)
    'both'      — cross-references schematic intent against PCB implementation
- FIX-2:  config path → ~/.local/share/kicad/ (KiCad 10 Linux standard)
- FIX-3:  Copy no longer shows a modal MessageBox; uses a ✓ status label
- NOTE-2: Anthropic total_tokens computed from input+output (not "N/A")

Carried from v1.5.1
====================
- show_toolbar_button = True                     (FIX-4)
- Absolute icon paths via _HERE                  (FIX-5)
- dark_icon_file_name                            (FIX-6)
- str() on all KiCad API returns                 (FIX-7)
- GetFootprints() replaces GetModules()          (FIX-8)
- int(GetSelection())                            (FIX-10)
- pcbnew/wx inside try/except                    (FIX-17)
- _make_config() safe factory                    (FIX-18)
- parents=True on mkdir                          (FIX-16)
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
import re
import json
import traceback
from pathlib import Path

# ── Capture plugin directory at module load time ────────────────────────────
# MUST be module-level: KiCad may change cwd between load and defaults().
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# ═══════════════════════════════════════════════════════════════════════════
#  Persistent config (API keys + last model)
# ═══════════════════════════════════════════════════════════════════════════

class ConfigManager:
    def __init__(self):
        # FIX-2: KiCad 10 Linux standard location
        self.config_path = (
            Path.home() / ".local" / "share" / "kicad" / "kicad_llm_config.json"
        )
        self.config_path.parent.mkdir(parents=True, exist_ok=True)  # FIX-16
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
        self.data.setdefault("api_keys", {})[provider] = key
        self.save()

    def get_last_model_index(self) -> int:
        return self.data.get("last_model_index", 0)

    def set_last_model_index(self, idx: int):
        self.data["last_model_index"] = idx
        self.save()


def _make_config():
    """Safe factory — failures don't crash the plugin at import time."""
    try:
        return ConfigManager()
    except Exception:
        traceback.print_exc()
        class _NullConfig:
            def get_api_key(self, p):          return ""
            def set_api_key(self, p, k):       pass
            def get_last_model_index(self):    return 0
            def set_last_model_index(self, i): pass
        return _NullConfig()


# ═══════════════════════════════════════════════════════════════════════════
#  Plugin registration
# ═══════════════════════════════════════════════════════════════════════════

try:
    import pcbnew   # FIX-17: inside try/except so errors reach scripting console
    import wx       # FIX-17

    config = _make_config()  # FIX-18: safe, after wx/pcbnew confirmed available

    class LLMAnalyserPlugin(pcbnew.ActionPlugin):

        def defaults(self):
            self.name        = "LLM Schematic/PCB Analyser"
            self.category    = "Analyse"
            self.description = ("Analyse your schematic and/or PCB with an LLM. "
                                "Detects schematic file automatically.")
            self.show_toolbar_button = True   # FIX-4: required for KiCad 10 toolbar
            icon      = os.path.join(_HERE, "icon.png")
            icon_dark = os.path.join(_HERE, "icon_dark.png")
            # FIX-5: absolute paths required in KiCad 10
            self.icon_file_name      = icon      if os.path.isfile(icon)      else ""
            # FIX-6: dark theme support
            self.dark_icon_file_name = icon_dark if os.path.isfile(icon_dark) else self.icon_file_name

        def Run(self):
            board = pcbnew.GetBoard()
            if board is None:
                wx.MessageBox(
                    "No PCB is open.\n"
                    "Open the PCB editor first (even an empty board works).\n\n"
                    "Tip: save your schematic before running — the plugin reads "
                    "the .kicad_sch file alongside the .kicad_pcb.",
                    "LLM Analyser", wx.OK | wx.ICON_WARNING)
                return
            info = _collect_context(board)
            dlg  = _LLMDialog(None, info)
            dlg.ShowModal()
            dlg.Destroy()

    LLMAnalyserPlugin().register()

except Exception:
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
#  Context detection and data collection
# ═══════════════════════════════════════════════════════════════════════════

def _collect_context(board) -> dict:
    """
    Collect all available data for the current project.

    PCB data comes from the live board object.
    Schematic data is read from the saved .kicad_sch file if it exists
    alongside the .kicad_pcb.  KiCad 10's ActionPlugin has no live schematic
    API — reading the file is the correct approach (same as KiCad's own
    BOM/netlist exporters use in a scripting context).
    """
    info = {
        "context":     "pcb",   # 'pcb' | 'both'
        "title":       str(board.GetTitleBlock().GetTitle()) or "(untitled)",  # FIX-7
        "footprints":  [],
        "nets":        [],
        # Schematic fields (populated when .kicad_sch found)
        "sch_file":    "",
        "symbols":     [],
        "pwr_symbols": [],
        "sch_nets":    [],
        "no_connects": 0,
    }

    # ── PCB data ────────────────────────────────────────────────────────────
    for fp in board.GetFootprints():                          # FIX-8
        info["footprints"].append({
            "ref":   str(fp.GetReference()),                  # FIX-7
            "value": str(fp.GetValue()),                      # FIX-7
            "layer": str(board.GetLayerName(fp.GetLayer())),  # FIX-7
        })
    for net_code, _net in board.GetNetInfo().NetsByName().items():
        if net_code:
            info["nets"].append(str(net_code))                # FIX-7

    # ── Schematic data ──────────────────────────────────────────────────────
    pcb_path = str(board.GetFileName())
    if pcb_path:
        sch_data = _find_and_parse_schematic(Path(pcb_path))
        if sch_data:
            info.update(sch_data)
            info["context"] = "both"

    return info


def _find_and_parse_schematic(pcb_path: Path):
    """
    Locate the root schematic alongside the PCB file.
    KiCad saves myproject.kicad_pcb and myproject.kicad_sch in the same dir.
    Falls back to any .kicad_sch in the directory if names don't match.
    Returns a data dict or None.
    """
    candidates = list(pcb_path.parent.glob("*.kicad_sch"))
    if not candidates:
        return None
    preferred = [f for f in candidates if f.stem == pcb_path.stem]
    sch_file  = preferred[0] if preferred else candidates[0]
    try:
        return _parse_kicad_sch(sch_file)
    except Exception:
        traceback.print_exc()
        return None


def _parse_kicad_sch(sch_file: Path) -> dict:
    """
    Lightweight regex parser for .kicad_sch (s-expression format).
    Extracts symbols, net labels, power symbols, and no-connect flags.
    No third-party library required.
    """
    text = sch_file.read_text(encoding="utf-8", errors="replace")

    symbols    = []
    pwr_syms   = []
    sch_nets   = set()

    # ── Symbol blocks ────────────────────────────────────────────────────────
    # Matches: (symbol (lib_id "Device:R") ... )
    for lib_id, body in re.findall(
        r'\(symbol\s+\(lib_id\s+"([^"]+)"\)(.*?)\n\s*\)',
        text, re.DOTALL
    ):
        ref   = _sch_prop(body, "Reference") or "?"
        value = _sch_prop(body, "Value")     or "?"
        entry = {"lib_id": lib_id, "ref": ref, "value": value}
        if lib_id.lower().startswith("power:"):
            pwr_syms.append(entry)
        else:
            symbols.append(entry)

    # ── Net labels ───────────────────────────────────────────────────────────
    for label in re.findall(
        r'\(?(?:net_label|global_label|hierarchical_label)\s+\(text\s+"([^"]+)"',
        text
    ):
        sch_nets.add(label)

    # ── No-connect flags ─────────────────────────────────────────────────────
    no_connects = len(re.findall(r'\(no_connect\s+', text))

    return {
        "sch_file":    sch_file.name,
        "symbols":     symbols,
        "pwr_symbols": pwr_syms,
        "sch_nets":    sorted(sch_nets),
        "no_connects": no_connects,
    }


def _sch_prop(body: str, prop_name: str) -> str:
    """Extract a named property value from a symbol s-expression body."""
    m = re.search(rf'\(property\s+"{re.escape(prop_name)}"\s+"([^"]*)"', body)
    return m.group(1) if m else ""


# ═══════════════════════════════════════════════════════════════════════════
#  Dialog
# ═══════════════════════════════════════════════════════════════════════════

class _LLMDialog(wx.Dialog):

    _MODELS = [
        # label,                              model_id,                    base_url,                   api_type
        ("Grok 4 (xAI)",           "grok-4",                    "https://api.x.ai/v1",      "xai"),
        ("Grok 4 Fast (xAI)",      "grok-4-fast",               "https://api.x.ai/v1",      "xai"),
        ("Grok 3 (xAI)",           "grok-3-latest",             "https://api.x.ai/v1",      "xai"),
        ("Grok 3 Mini (xAI)",      "grok-3-mini-latest",        "https://api.x.ai/v1",      "xai"),
        ("Claude Sonnet 4",        "claude-sonnet-4-20250514",  None,                        "anthropic"),
        ("Claude Opus 4",          "claude-opus-4-20250514",    None,                        "anthropic"),
        ("GPT-4o (OpenAI)",        "gpt-4o",                    None,                        "openai"),
        ("GPT-4o-mini (OpenAI)",   "gpt-4o-mini",               None,                        "openai"),
        ("Ollama llama3 (local)",  "llama3",                    "http://localhost:11434/v1", "openai"),
        ("Ollama mistral (local)", "mistral",                   "http://localhost:11434/v1", "openai"),
    ]

    _PROVIDER_MAP = {
        "anthropic": "Anthropic",
        "openai":    "OpenAI / Ollama",
        "xai":       "xAI (Grok)",
    }

    def __init__(self, parent, info):
        ctx_label = {"pcb": "PCB Only", "both": "Schematic + PCB"}.get(
            info.get("context", "pcb"), "PCB Only")
        super().__init__(parent, title=f"LLM Analyser — {ctx_label}",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._info = info
        self._build_ui()
        self._load_last_model_and_key()

    def _build_ui(self):
        p   = self
        s   = wx.BoxSizer(wx.VERTICAL)
        ctx = self._info.get("context", "pcb")

        # ── Context summary header ───────────────────────────────────────────
        fp_ct  = len(self._info.get("footprints", []))
        net_ct = len(self._info.get("nets", []))
        sym_ct = len(self._info.get("symbols", []))
        pwr_ct = len(self._info.get("pwr_symbols", []))
        nc_ct  = self._info.get("no_connects", 0)
        sch_f  = self._info.get("sch_file", "")

        if ctx == "both":
            summary = (
                f"✓ Schematic found: {sch_f}\n"
                f"  Symbols: {sym_ct}  Power: {pwr_ct}  No-connects: {nc_ct}\n"
                f"  PCB: {fp_ct} footprints, {net_ct} nets  |  Board: {self._info['title']}"
            )
        else:
            summary = (
                f"PCB only — no .kicad_sch found alongside .kicad_pcb\n"
                f"Board: {self._info['title']}  |  "
                f"Footprints: {fp_ct}  Nets: {net_ct}\n"
                f"Tip: save your schematic first to enable dual analysis."
            )

        header = wx.StaticText(p, label=summary)
        header.SetFont(header.GetFont().Bold())
        s.Add(header, 0, wx.ALL, 8)

        # ── Model + key row ──────────────────────────────────────────────────
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="Model:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._model = wx.Choice(p, choices=[m[0] for m in self._MODELS])
        self._model.Bind(wx.EVT_CHOICE, self._on_model_changed)
        row.Add(self._model, 1, wx.RIGHT, 12)
        row.Add(wx.StaticText(p, label="API Key:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._key = wx.TextCtrl(p, style=wx.TE_PASSWORD, size=(220, -1))
        row.Add(self._key, 0)
        self._btn_clear = wx.Button(p, label="Clear Key", size=(75, 24))
        self._btn_clear.Bind(wx.EVT_BUTTON, self._on_clear_keys)
        row.Add(self._btn_clear, 0, wx.LEFT, 6)
        s.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── Base URL row ─────────────────────────────────────────────────────
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        row3.Add(wx.StaticText(p, label="Base URL:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._url = wx.TextCtrl(p)
        self._url.SetHint("Leave blank for cloud providers")
        row3.Add(self._url, 1)
        s.Add(row3, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── Run button ───────────────────────────────────────────────────────
        self._run_btn = wx.Button(p, label="▶  Run Analysis")
        self._run_btn.Bind(wx.EVT_BUTTON, self._on_run)
        s.Add(self._run_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── Results header with copy button and status label ─────────────────
        h1 = wx.BoxSizer(wx.HORIZONTAL)
        h1.Add(wx.StaticText(p, label="AI Response:"), 0, wx.ALIGN_CENTER_VERTICAL)
        h1.AddStretchSpacer()
        # FIX-3: status label replaces disruptive MessageBox popup
        self._copy_status = wx.StaticText(p, label="")
        h1.Add(self._copy_status, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._btn_copy_result = wx.Button(p, label="Copy", size=(60, 24))
        self._btn_copy_result.Bind(wx.EVT_BUTTON, self._on_copy_result)
        h1.Add(self._btn_copy_result, 0)
        s.Add(h1, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self._result = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP, size=(-1, 260))
        s.Add(self._result, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── Token usage panel ────────────────────────────────────────────────
        token_box = wx.StaticBoxSizer(wx.StaticBox(p, label="Token Usage"), wx.VERTICAL)
        grid = wx.FlexGridSizer(3, 2, 4, 12)
        self._token_input  = wx.StaticText(p, label="—")
        self._token_output = wx.StaticText(p, label="—")
        self._token_total  = wx.StaticText(p, label="—")
        for lbl, val in (("Input:", self._token_input),
                         ("Output:", self._token_output),
                         ("Total:", self._token_total)):
            grid.Add(wx.StaticText(p, label=lbl))
            grid.Add(val)
        token_box.Add(grid, 0, wx.ALL, 8)
        self._btn_copy_tokens = wx.Button(p, label="Copy Token Usage", size=(140, 24))
        self._btn_copy_tokens.Bind(wx.EVT_BUTTON, self._on_copy_tokens)
        token_box.Add(self._btn_copy_tokens, 0, wx.LEFT | wx.BOTTOM, 8)
        s.Add(token_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── Close ────────────────────────────────────────────────────────────
        btn_close = wx.Button(p, wx.ID_CLOSE, label="Close")
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        s.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        p.SetSizerAndFit(s)
        self.SetSize((740, 680))

    # ── Model / key helpers ──────────────────────────────────────────────────

    def _load_last_model_and_key(self):
        idx = config.get_last_model_index()
        if idx < len(self._MODELS):
            self._model.SetSelection(idx)
            self._on_model_changed(None)

    def _on_model_changed(self, _event):
        idx = int(self._model.GetSelection())   # FIX-10: wxString → int
        _, _, default_url, api_type = self._MODELS[idx]
        self._url.SetValue(default_url or "")
        self._key.SetValue(config.get_api_key(api_type))

    def _on_clear_keys(self, _event):
        idx  = int(self._model.GetSelection())  # FIX-10
        _, _, _, api_type = self._MODELS[idx]
        name = self._PROVIDER_MAP.get(api_type, api_type)
        if wx.MessageBox(f"Clear saved key for {name}?", "Clear Key", wx.YES_NO) == wx.YES:
            config.set_api_key(api_type, "")
            self._key.SetValue("")

    # ── Run ──────────────────────────────────────────────────────────────────

    def _on_run(self, _event):
        idx = int(self._model.GetSelection())   # FIX-10
        _, model_id, default_url, api_type = self._MODELS[idx]
        api_key  = str(self._key.GetValue()).strip()           # FIX-7
        base_url = str(self._url.GetValue()).strip() or default_url  # FIX-7

        if api_key:
            config.set_api_key(api_type, api_key)
        config.set_last_model_index(idx)

        if not api_key and api_type != "openai":
            wx.MessageBox("Please enter an API key.", "Error", wx.OK | wx.ICON_WARNING)
            return

        self._run_btn.Disable()
        self._copy_status.SetLabel("")
        self._result.SetValue("Running…")
        self._token_input.SetLabel("—")
        self._token_output.SetLabel("—")
        self._token_total.SetLabel("—")
        wx.Yield()

        try:
            text, usage = self._call_llm(model_id, api_key, base_url, api_type)
        except Exception as e:
            text  = f"Error: {e}"
            usage = {}

        self._result.SetValue(text)

        if api_type == "anthropic":
            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            self._token_input.SetLabel(str(inp))
            self._token_output.SetLabel(str(out))
            self._token_total.SetLabel(str(inp + out))   # NOTE-2: compute total
        elif api_type == "xai":
            self._token_input.SetLabel(str(usage.get("input_tokens", 0)))
            self._token_output.SetLabel(str(usage.get("output_tokens", 0)))
            self._token_total.SetLabel(str(usage.get("total_tokens", 0)))
        else:
            self._token_input.SetLabel(str(usage.get("prompt_tokens", 0)))
            self._token_output.SetLabel(str(usage.get("completion_tokens", 0)))
            self._token_total.SetLabel(str(usage.get("total_tokens", 0)))

        self._run_btn.Enable()

    # ── Clipboard ────────────────────────────────────────────────────────────

    def _on_copy_result(self, _event):
        self._copy_to_clipboard(str(self._result.GetValue()))

    def _on_copy_tokens(self, _event):
        self._copy_to_clipboard(
            f"Input:  {self._token_input.GetLabel()}\n"
            f"Output: {self._token_output.GetLabel()}\n"
            f"Total:  {self._token_total.GetLabel()}"
        )

    def _copy_to_clipboard(self, text: str):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
        # FIX-3: quiet status label, auto-clears after 3 s — no modal popup
        self._copy_status.SetLabel("✓ Copied")
        wx.CallLater(3000, lambda: self._copy_status.SetLabel("") if self else None)

    # ── Prompt builders ──────────────────────────────────────────────────────

    def _prompt(self) -> str:
        ctx = self._info.get("context", "pcb")
        return self._prompt_both() if ctx == "both" else self._prompt_pcb_only()

    def _prompt_pcb_only(self) -> str:
        lines = [
            "You are an expert PCB design engineer reviewing a KiCad PCB.",
            "The schematic file was not found — PCB analysis only.",
            "Identify:",
            "1. Fatal layout flaws (missing connections, wrong layers, no GND plane)",
            "2. DRC / best-practice violations (trace width, via sizes, clearances)",
            "3. Component placement issues (bypass caps far from ICs, poor connector access)",
            "4. Nice-to-have improvements",
            "",
            f"Board: {self._info['title']}",
            "",
            "Footprints (ref, value, layer):",
        ]
        for fp in self._info["footprints"]:
            lines.append(f"  {fp['ref']}  {fp['value']}  ({fp['layer']})")
        lines += ["", "Net names (up to 120):"]
        for net in sorted(self._info["nets"])[:120]:
            lines.append(f"  {net}")
        return "\n".join(lines)

    def _prompt_both(self) -> str:
        """Cross-reference schematic intent against PCB implementation."""
        syms = self._info.get("symbols", [])
        pwr  = self._info.get("pwr_symbols", [])
        nets = self._info.get("sch_nets", [])
        nc   = self._info.get("no_connects", 0)
        lines = [
            "You are an expert electronics engineer reviewing a KiCad project.",
            "You have BOTH schematic and PCB data — cross-reference them.",
            "Identify:",
            "1. Schematic errors:",
            "   - Unconnected pins, missing power connections",
            "   - Missing decoupling caps on IC power pins",
            "   - Wrong passive values (pull-ups, filter caps, termination)",
            "   - Power symbol issues (missing PWR_FLAG, wrong voltage labels)",
            "   - Pin assignment problems (swapped diff pairs, wrong GPIO use)",
            "2. PCB errors:",
            "   - Layout flaws, DRC violations, placement issues",
            "   - Bypass caps not adjacent to IC power pins",
            "3. Schematic↔PCB mismatches:",
            "   - Nets in schematic missing from PCB",
            "   - Footprints on PCB with no corresponding schematic symbol",
            "4. Signal integrity / EMC issues visible from both views",
            "5. Nice-to-have improvements",
            "",
            "Reference components by their actual designators (R1, U3, etc.)",
            "and net names from the data below.",
            "",
            "════ SCHEMATIC ════",
            f"File: {self._info.get('sch_file', 'unknown')}",
            f"No-connect flags: {nc}",
            "",
            f"Symbols ({len(syms)}):",
        ]
        for sym in syms[:150]:
            lines.append(f"  {sym['ref']}  {sym['value']}  [{sym['lib_id']}]")
        if len(syms) > 150:
            lines.append(f"  … and {len(syms)-150} more")

        lines += ["", f"Power symbols ({len(pwr)}):"]
        for sym in pwr:
            lines.append(f"  {sym['ref']}  {sym['value']}")

        lines += ["", f"Net labels ({len(nets)}):"]
        for net in nets[:80]:
            lines.append(f"  {net}")
        if len(nets) > 80:
            lines.append(f"  … and {len(nets)-80} more")

        lines += [
            "",
            "════ PCB ════",
            f"Board: {self._info['title']}",
            "",
            f"Footprints ({len(self._info['footprints'])}):",
        ]
        for fp in self._info["footprints"][:150]:
            lines.append(f"  {fp['ref']}  {fp['value']}  ({fp['layer']})")
        if len(self._info["footprints"]) > 150:
            lines.append(f"  … and {len(self._info['footprints'])-150} more")

        lines += ["", f"PCB net names ({len(self._info['nets'])}, up to 80):"]
        for net in sorted(self._info["nets"])[:80]:
            lines.append(f"  {net}")

        return "\n".join(lines)

    # ── API call ──────────────────────────────────────────────────────────────

    def _call_llm(self, model_id, api_key, base_url, api_type):
        import urllib.request
        prompt = self._prompt()
        system = ("You are an expert electronics engineer. "
                  "Be specific — reference actual designators (R1, U3) and net names.")

        if api_type == "anthropic":
            url  = "https://api.anthropic.com/v1/messages"
            hdrs = {"Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01"}
            body = {"model": model_id, "max_tokens": 4096,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}]}

        elif api_type == "xai":
            url  = (base_url or "https://api.x.ai/v1") + "/responses"
            hdrs = {"Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"}
            body = {"model": model_id, "max_output_tokens": 4096,
                    "input": f"{system}\n\n{prompt}"}   # plain string avoids HTTP 400

        else:
            url  = (base_url or "https://api.openai.com/v1") + "/chat/completions"
            hdrs = {"Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"}
            body = {"model": model_id, "max_tokens": 4096,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user",   "content": prompt}]}

        req = urllib.request.Request(
            url, json.dumps(body).encode(), hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                err_msg  = err_json.get("error", {})
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get("message", err_body)
            except Exception:
                err_msg = err_body
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_msg}")

        if api_type == "anthropic":
            return data["content"][0]["text"], data.get("usage", {})
        elif api_type == "xai":
            return data["output"][0]["content"][0]["text"], data.get("usage", {})
        else:
            return data["choices"][0]["message"]["content"], data.get("usage", {})
