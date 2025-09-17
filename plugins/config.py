import json
import os
from typing import Dict, Optional, List
from pathlib import Path


class ConfigManager:
    def __init__(self, config_file: str = "kicad_llm_config.json"):
        self.config_file = Path.home() / ".kicad" / config_file
        self.config_file.parent.mkdir(exist_ok=True)
        self._config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from disk."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Return default configuration
        return {
            "selected_model": "openai/gpt-4o-mini",
            "provider_api_keys": {},
            "last_updated": None
        }

    def _save_config(self) -> None:
        """Save configuration to disk."""
        import datetime
        self._config["last_updated"] = datetime.datetime.now().isoformat()

        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            print(f"Failed to save configuration: {e}")

    def get_selected_model(self) -> str:
        """Get the currently selected model."""
        return self._config.get("selected_model", "openai/gpt-4o-mini")

    def set_selected_model(self, model_name: str) -> None:
        """Set the currently selected model."""
        self._config["selected_model"] = model_name
        self._save_config()

    def _extract_provider_from_model(self, model_name: str) -> str:
        """Extract provider name from model name (e.g., 'openai/gpt-4' -> 'openai')."""
        if "/" in model_name:
            return model_name.split("/")[0]
        return model_name

    def get_api_key(self, model_name: str) -> Optional[str]:
        """Get API key for a specific model by extracting its provider."""
        provider = self._extract_provider_from_model(model_name)
        return self._config.get("provider_api_keys", {}).get(provider)

    def set_api_key_for_provider(self, provider: str, api_key: str) -> None:
        """Set API key for a specific provider."""
        if "provider_api_keys" not in self._config:
            self._config["provider_api_keys"] = {}

        self._config["provider_api_keys"][provider] = api_key
        self._save_config()

    def get_all_provider_api_keys(self) -> Dict[str, str]:
        """Get all stored provider API keys."""
        return self._config.get("provider_api_keys", {}).copy()

    def remove_api_key_for_provider(self, provider: str) -> None:
        """Remove API key for a specific provider."""
        if "provider_api_keys" in self._config and provider in self._config["provider_api_keys"]:
            del self._config["provider_api_keys"][provider]
            self._save_config()

    def get_providers_with_keys(self) -> List[str]:
        """Get list of providers that have API keys configured."""
        return list(self._config.get("provider_api_keys", {}).keys())

    # Backward compatibility methods
    def set_api_key(self, model_name: str, api_key: str) -> None:
        """Set API key for a model (extracts provider automatically)."""
        provider = self._extract_provider_from_model(model_name)
        self.set_api_key_for_provider(provider, api_key)

    def remove_api_key(self, model_name: str) -> None:
        """Remove API key for a model (extracts provider automatically)."""
        provider = self._extract_provider_from_model(model_name)
        self.remove_api_key_for_provider(provider)

    def get_config_file_path(self) -> str:
        """Get the full path to the configuration file."""
        return str(self.config_file)


# Global configuration instance
config_manager = ConfigManager()