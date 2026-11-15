"""Test bootstrap: allow importing package modules without GCS installed."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

try:
    import google.cloud.storage  # noqa: F401
except ModuleNotFoundError:
    google = ModuleType("google")
    cloud = ModuleType("google.cloud")
    storage_mod = ModuleType("google.cloud.storage")
    storage_mod.Client = MagicMock
    sys.modules.setdefault("google", google)
    sys.modules.setdefault("google.cloud", cloud)
    sys.modules["google.cloud.storage"] = storage_mod
