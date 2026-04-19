"""Auto-discovery and registration of feature modules."""

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Map module directory names to their .env toggle
MODULE_TOGGLES: dict[str, str] = {
    "payments": "enable_payments",
    "tracking": "enable_tracking",
    "chatbot": "enable_chatbot",
    "marketing": "enable_marketing",
}

# Modules that are always enabled (no toggle)
ALWAYS_ENABLED = {"auth", "gdpr", "seo"}

# Template-specific modules
TEMPLATE_MODULES = {
    "ecommerce": {"ecommerce"},
    "saas": {"saas"},
}


def _is_module_enabled(module_name: str) -> bool:
    """Check if a module should be loaded based on config."""
    if module_name in ALWAYS_ENABLED:
        return True

    if module_name in TEMPLATE_MODULES.get(settings.app_template, set()):
        return True

    toggle = MODULE_TOGGLES.get(module_name)
    if toggle is None:
        return False

    return getattr(settings, toggle, False)


def load_modules(app: "FastAPI") -> list[str]:
    """Discover and register all enabled modules with the FastAPI app.

    Each module must have:
    - modules/{name}/config.py with an `enabled` attribute
    - modules/{name}/routes/ with a FastAPI router

    Returns list of loaded module names.
    """
    modules_dir = Path(__file__).resolve().parent.parent.parent / "modules"
    loaded: list[str] = []

    if not modules_dir.exists():
        logger.warning("Modules directory not found: %s", modules_dir)
        return loaded

    for module_path in sorted(modules_dir.iterdir()):
        if not module_path.is_dir():
            continue

        module_name = module_path.name

        # Skip hidden dirs and __pycache__
        if module_name.startswith((".", "_")):
            continue

        # Check .env toggle first
        if not _is_module_enabled(module_name):
            logger.debug("Module '%s' is disabled by configuration", module_name)
            continue

        # Check for config.py with enabled flag
        config_file = module_path / "config.py"
        if not config_file.exists():
            logger.debug("Module '%s' has no config.py, skipping", module_name)
            continue

        try:
            config_mod = importlib.import_module(f"modules.{module_name}.config")
            if not getattr(config_mod, "enabled", False):
                logger.debug("Module '%s' is disabled in its config.py", module_name)
                continue
        except ImportError as e:
            logger.warning(
                "Failed to import config for module '%s': %s", module_name, e
            )
            continue

        # Try to load and register routes
        try:
            routes_mod = importlib.import_module(f"modules.{module_name}.routes")
            router = getattr(routes_mod, "router", None)
            if router is not None:
                app.include_router(router, prefix=f"/api/{module_name}")
                loaded.append(module_name)
                logger.info("Loaded module: %s", module_name)
            else:
                logger.debug(
                    "Module '%s' has no router in routes, skipping", module_name
                )
        except ImportError:
            # Module has config but no routes yet — that's fine in early phases
            logger.debug("Module '%s' has no routes package yet, skipping", module_name)

    logger.info("Loaded modules: %s", loaded if loaded else "[]")
    return loaded
