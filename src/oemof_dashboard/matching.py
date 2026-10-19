"""Pure matching of Result Entries against a Datapackage's names: Flows (from, to) or nodes (node, None)."""

from dataclasses import dataclass, field

from oemof_dashboard.datapackage import Datapackage
from oemof_dashboard.result import Result

NODE_SUFFIX = "None"  # oemof writes node entries as `<node>-None`


@dataclass
class Matching:
    """Result Entries resolved to Flows or nodes, and the ones that couldn't be, with the reason.

    A Flow without a Connection is in both: drawn from `matched`, listed (and counted against `ratio`) from
    `unmatched`.
    """

    matched: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    unmatched: dict[str, str] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        """Share of Result Entries not listed as unmatched; 1.0 for a Result without entries."""
        total = len(self.matched.keys() | self.unmatched.keys())
        return 1 - len(self.unmatched) / total if total else 1.0

    def entries_of(self, nodes: set[str]) -> set[str]:
        """Matched Result Entries that are Flows from or to, or node entries of, any of these nodes."""
        return {entry for entry, pair in self.matched.items() if nodes & set(pair)}


def match(result: Result, package: Datapackage) -> Matching:
    """Split each Result Entry name at the one `-` where both sides are Datapackage names (or `None` on the right).

    Args:
        result: Result whose Result Entries to match.
        package: Datapackage giving the Bus and Component names.

    Returns:
        Matching of every Result Entry.
    """
    names = package.buses.keys() | package.components.keys()
    connections = set(package.connections)
    matching = Matching()
    for entry in result.entries:
        parts = entry.split("-")
        splits = [("-".join(parts[:index]), "-".join(parts[index:])) for index in range(1, len(parts))]
        valid = [
            (source, target)
            for source, target in splits
            if source in names and (target in names or target == NODE_SUFFIX)
        ]
        if not valid:
            matching.unmatched[entry] = "no split into two Datapackage names"
        elif len(valid) > 1:
            matching.unmatched[entry] = "ambiguous: " + ", ".join(f"{source} → {target}" for source, target in valid)
        else:
            ((source, target),) = valid
            if target == NODE_SUFFIX:
                matching.matched[entry] = (source, None)
                continue
            matching.matched[entry] = (source, target)
            # Connections are undirected, so a Flow attaches to the Connection in either direction.
            if (source, target) not in connections and (target, source) not in connections:
                matching.unmatched[entry] = f"not in Datapackage: no Connection between {source} and {target}"
    return matching
