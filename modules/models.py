from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class DiffItem:
    relative_path: str
    status: str
    vendor_path: str | None
    custom_path: str | None
    file_ext: str | None
    is_our_added: bool = False
    contains_our_markers: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "DiffItem":
        return DiffItem(
            relative_path=data["relative_path"],
            status=data["status"],
            vendor_path=data.get("vendor_path"),
            custom_path=data.get("custom_path"),
            file_ext=data.get("file_ext"),
            is_our_added=data.get("is_our_added", False),
            contains_our_markers=data.get("contains_our_markers", False),
        )


@dataclass
class StepTiming:
    step_name: str
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunReport:
    config: dict[str, Any]
    items: list[DiffItem]
    generated_object_cards: int = 0
    total_vendor_files: int = 0
    total_custom_files: int = 0
    step_timings: list[StepTiming] = field(default_factory=list)
    total_duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "items": [item.to_dict() for item in self.items],
            "generated_object_cards": self.generated_object_cards,
            "total_vendor_files": self.total_vendor_files,
            "total_custom_files": self.total_custom_files,
            "step_timings": [step.to_dict() for step in self.step_timings],
            "total_duration_seconds": self.total_duration_seconds,
        }