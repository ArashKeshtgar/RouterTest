"""One unit under test.

The demo runs a single unit on the PC's only Ethernet port. Every unit still
carries its own network interface and admin URL so the same code can later
drive several units at once (one USB adapter or VLAN per unit). All units share
the same factory LAN IP, so traffic must be bound to the right interface -
that part is TODO for the multi-unit phase.
"""

from dataclasses import dataclass, field

from .qr import Label


@dataclass
class Unit:
    slot: int
    label: Label
    admin_url: str = "http://192.168.1.1"
    interface: str | None = None  # e.g. "Ethernet 3"; None = OS default route
    manually_reset: bool = False  # operator already reset it during this run
    results: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)
