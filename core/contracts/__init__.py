"""Stable contracts shared by JARVIS layers.

This package is intentionally dependency-light. It owns the data contracts and
validation rules between architecture layers; it does not implement cognition.
"""

from .schemas import CONTRACTS, ContractError, LayerPayload, validate_input, validate_output

__all__ = [
    "CONTRACTS",
    "ContractError",
    "LayerPayload",
    "validate_input",
    "validate_output",
]
