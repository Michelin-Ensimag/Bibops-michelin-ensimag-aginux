"""Compatibility shim — eval_bank.probes has been moved to src.bibops.probes."""
from src.bibops.probes import Probe, ProbeSet, list_categories, load_probes

__all__ = ["Probe", "ProbeSet", "list_categories", "load_probes"]
