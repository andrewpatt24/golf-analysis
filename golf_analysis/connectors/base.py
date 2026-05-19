from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from golf_analysis.models import IngestPayload


class Connector(ABC):
    """One source system (Rapsodo export, Garmin FIT, …). Register new subclasses on the registry."""

    id: str

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Return True if this connector should try to parse the given path."""

    @abstractmethod
    def ingest(self, path: Path) -> IngestPayload:
        """Parse file and return normalized payload."""


def default_connectors() -> list[Connector]:
    # Lazy imports keep optional heavy paths out of import graph if we split later
    from golf_analysis.connectors.garmin_fit import GarminFitConnector
    from golf_analysis.connectors.garmin_golf_community import GarminGolfCommunityConnector
    from golf_analysis.connectors.rapsodo import RapsodoCsvConnector

    return [RapsodoCsvConnector(), GarminFitConnector(), GarminGolfCommunityConnector()]


def pick_connector(path: Path, connectors: list[Connector] | None = None) -> Connector | None:
    c_list = connectors if connectors is not None else default_connectors()
    for c in c_list:
        if c.can_handle(path):
            return c
    return None
