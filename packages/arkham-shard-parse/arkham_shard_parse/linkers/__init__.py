"""Entity linking and coreference resolution."""

from .entity_linker import EntityLinker
from .coreference import CoreferenceResolver

__all__ = [
    "EntityLinker",
    "CoreferenceResolver",
]
