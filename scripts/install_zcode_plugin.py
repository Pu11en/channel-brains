"""Install the bundled Channel Brains plugin into ZCode user scope."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def _load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"ZCode config must contain a JSON object: {path}")
    return value


def _same_path(left: str, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(str(right))
    )


def _validate_source(source: Path) -> None:
    manifest_path = source / ".zcode-plugin" / "plugin.json"
    mcp_path = source / ".mcp.json"
    if not manifest_path.is_file() or not mcp_path.is_file():
        raise ValueError(f"Bundled ZCode plugin is incomplete: {source}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("name") != "channel-brains":
        raise ValueError(f"Unexpected ZCode plugin manifest: {manifest_path}")


def _validate_existing_target(target: Path) -> None:
    if not target.exists():
        return
    if target.is_symlink():
        raise ValueError(f"Refusing to replace a symbolic-link plugin directory: {target}")
    manifest_path = target / ".zcode-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Refusing to replace an unrecognized plugin directory: {target}") from exc
    if not isinstance(manifest, dict) or manifest.get("name") != "channel-brains":
        raise ValueError(f"Refusing to replace an unrelated plugin directory: {target}")


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        assert temporary_path is not None
        os.replace(temporary_path, path)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def install(source: Path, target: Path, config_path: Path) -> dict[str, object]:
    source = source.resolve()
    target = target.resolve()
    config_path = config_path.resolve()
    _validate_source(source)
    _validate_existing_target(target)

    config = _load_object(config_path)
    plugins = config.get("plugins")
    if plugins is None:
        plugins = {}
        config["plugins"] = plugins
    if not isinstance(plugins, dict):
        raise ValueError(f"ZCode config field 'plugins' must be an object: {config_path}")

    directories = plugins.get("dirs")
    if directories is None:
        directories = []
        plugins["dirs"] = directories
    if not isinstance(directories, list) or not all(
        isinstance(item, str) for item in directories
    ):
        raise ValueError(f"ZCode config field 'plugins.dirs' must be a string array: {config_path}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)

    changed = plugins.get("enabled") is not True
    plugins["enabled"] = True
    if not any(_same_path(item, target) for item in directories):
        directories.append(str(target))
        changed = True

    rendered = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    if not config_path.exists() or config_path.read_text(encoding="utf-8") != rendered:
        _write_json_atomically(config_path, config)
        changed = True

    return {
        "status": "installed",
        "client": "zcode",
        "plugin": "channel-brains",
        "plugin_path": str(target),
        "config_path": str(config_path),
        "config_changed": changed,
    }


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Install the bundled Channel Brains plugin into ZCode user scope."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=repository_root / "plugins" / "channel-brains",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".zcode" / "plugins" / "channel-brains",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".zcode" / "cli" / "config.json",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    print(json.dumps(install(args.source, args.target, args.config)))


if __name__ == "__main__":
    main()
