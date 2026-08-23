from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_ASSET_ROOT = Path(__file__).resolve().parent


@dataclass
class AssetBundle:
    prompts: dict[str, str] = field(default_factory=dict)
    styles: dict[str, str] = field(default_factory=dict)


def _read(rel: str) -> str:
    path = _ASSET_ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_bundle(style: str = "default") -> AssetBundle:
    prompts = {
        "coordinator": _read("prompts/coordinator.md"),
        "writer": _read("prompts/writer.md"),
    }
    styles = {
        "default": _read("styles/default.md"),
        style: _read(f"styles/{style}.md") if style else "",
    }
    return AssetBundle(prompts=prompts, styles=styles)


def style_text(style: str) -> str:
    text = _read(f"styles/{style}.md") if style else ""
    return text or _read("styles/default.md")
