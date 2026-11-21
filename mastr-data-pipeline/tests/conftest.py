"""Test bootstrap: allow importing package modules without GCP libs installed."""

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

try:
    import google.cloud.bigquery  # noqa: F401
except ModuleNotFoundError:
    google = sys.modules.setdefault("google", ModuleType("google"))
    cloud = sys.modules.setdefault("google.cloud", ModuleType("google.cloud"))
    bq_mod = ModuleType("google.cloud.bigquery")
    bq_mod.Client = MagicMock
    bq_mod.Dataset = MagicMock
    bq_mod.Table = MagicMock
    bq_mod.SchemaField = MagicMock
    bq_mod.LoadJobConfig = MagicMock
    bq_mod.QueryJobConfig = MagicMock
    bq_mod.ScalarQueryParameter = MagicMock
    bq_mod.SourceFormat = MagicMock()
    bq_mod.SourceFormat.CSV = "CSV"
    bq_mod.WriteDisposition = MagicMock()
    bq_mod.WriteDisposition.WRITE_TRUNCATE = "WRITE_TRUNCATE"
    bq_mod.TimePartitioning = MagicMock
    bq_mod.TimePartitioningType = MagicMock()
    bq_mod.TimePartitioningType.DAY = "DAY"
    sys.modules["google.cloud.bigquery"] = bq_mod
