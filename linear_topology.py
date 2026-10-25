"""Configurable linear Mininet topology specification.

Pure Python (no Mininet import) and compatible with the VM's Python 3.8. A
linear topology with N switches has two end hosts, N switches connected in
order, and N-1 inter-switch candidate links. The configured bottleneck link is
the middle candidate link, which is s2-s3 for the original four-switch study.
"""

from collections import OrderedDict

SUPPORTED_SWITCH_COUNTS = (4, 8, 12)
BOTTLENECK_PARAMS = {"bw": 10, "delay": "5ms"}
HOSTS = ("h1", "h2")
FAULT_TYPE = "link_failure"
# Registry per topology size. Logical IDs identify the intended scenario,
# physical IDs identify a collection execution; both are disjoint from the
# four-switch registry (logical 1-27, 40, 41; physical 1-45).
TOPOLOGY_ID_REGISTRY = {
    8: {"logical_start": 101, "physical_start": 1101, "slots": 30},
    # Extended from 30 to 60 slots on 2026-10-24 after a VM suspend and its
    # aftermath consumed IDs 208-215; the first 30 assignments are unchanged.
    12: {"logical_start": 201, "physical_start": 1201, "slots": 60},
}
TARGET_VALID_EXPERIMENTS = 25


class LinearTopology(object):
    def __init__(self, switch_count):
        try:
            count = int(switch_count)
        except (TypeError, ValueError):
            raise ValueError("switch_count must be an integer")
        if count < 2:
            raise ValueError("A linear topology needs at least two switches")
        self.switch_count = count
        self.switches = tuple("s%d" % index for index in range(1, count + 1))
        self.hosts = HOSTS
        self.candidate_links = tuple(
            "%s-%s" % (self.switches[index], self.switches[index + 1])
            for index in range(count - 1)
        )
        self.bottleneck_link = self.candidate_links[(count - 1) // 2]
        definitions = [("h1", "s1", None)]
        for link in self.candidate_links:
            left, right = link.split("-")
            params = dict(BOTTLENECK_PARAMS) if link == self.bottleneck_link else None
            definitions.append((left, right, params))
        definitions.append((self.switches[-1], "h2", None))
        self.link_definitions = tuple(definitions)
        self.nodes = ("h1",) + self.switches + ("h2",)
        self.edges = [[left, right] for left, right, _params in self.link_definitions]
        self.switch_indices = list(range(1, count + 1))

    @property
    def candidate_count(self):
        return len(self.candidate_links)

    def is_candidate(self, link):
        return link in self.candidate_links

    def link_endpoints(self, link):
        if not self.is_candidate(link):
            raise ValueError("Not an inter-switch candidate link: %r" % (link,))
        left, right = link.split("-")
        return left, right

    def link_name(self, node_a, node_b):
        """Canonical name of the link between two adjacent nodes."""
        order = {name: index for index, name in enumerate(self.nodes)}
        if node_a not in order or node_b not in order:
            raise ValueError("Unknown node in link: %r-%r" % (node_a, node_b))
        if abs(order[node_a] - order[node_b]) != 1:
            raise ValueError("Nodes are not adjacent: %r-%r" % (node_a, node_b))
        first, second = sorted((node_a, node_b), key=lambda name: order[name])
        return "%s-%s" % (first, second)

    def remote_switches(self, link):
        left, right = self.link_endpoints(link)
        return tuple(switch for switch in self.switches if switch not in (left, right))

    def to_metadata(self):
        return OrderedDict([
            ("kind", "linear"),
            ("switch_count", self.switch_count),
            ("switches", list(self.switches)),
            ("hosts", list(self.hosts)),
            ("candidate_links", list(self.candidate_links)),
            ("candidate_count", self.candidate_count),
            ("bottleneck_link", self.bottleneck_link),
            ("bottleneck_params", dict(BOTTLENECK_PARAMS)),
            ("link_definitions", [
                {"left": left, "right": right, "params": params or {}}
                for left, right, params in self.link_definitions
            ]),
        ])

    @classmethod
    def from_metadata(cls, metadata):
        if not isinstance(metadata, dict) or metadata.get("kind") != "linear":
            raise ValueError("Topology metadata must describe a linear topology")
        topology = cls(metadata.get("switch_count"))
        expected = topology.to_metadata()
        for key in ("switches", "hosts", "candidate_links", "bottleneck_link", "link_definitions"):
            if metadata.get(key) != expected[key]:
                raise ValueError("Topology metadata disagrees with the linear specification: %s" % key)
        return topology

    def __eq__(self, other):
        return isinstance(other, LinearTopology) and other.switch_count == self.switch_count

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(("LinearTopology", self.switch_count))

    def __repr__(self):
        return "LinearTopology(%d)" % self.switch_count


def balanced_fault_assignment(candidate_links, count):
    """Round-robin fault links so every prefix of the schedule stays balanced."""
    links = tuple(candidate_links)
    if not links:
        raise ValueError("At least one candidate link is required")
    if int(count) < 1:
        raise ValueError("count must be positive")
    return tuple(links[index % len(links)] for index in range(int(count)))


def topology_run_registry(switch_count):
    """Fixed logical/physical ID pairs and fault links for a topology size."""
    count = int(switch_count)
    if count not in TOPOLOGY_ID_REGISTRY:
        raise ValueError("No run registry for a %d-switch topology" % count)
    spec = TOPOLOGY_ID_REGISTRY[count]
    topology = LinearTopology(count)
    links = balanced_fault_assignment(topology.candidate_links, spec["slots"])
    registry = OrderedDict()
    for slot in range(spec["slots"]):
        logical = spec["logical_start"] + slot
        registry[logical] = {
            "logical_experiment_id": logical,
            "physical_run_id": spec["physical_start"] + slot,
            "fault_link": links[slot],
            "run_purpose": "topology_%d_switches_candidate" % count,
            "slot": slot,
        }
    return registry


def registry_entry(switch_count, logical_id, physical_id):
    registry = topology_run_registry(switch_count)
    entry = registry.get(int(logical_id))
    if entry is None or entry["physical_run_id"] != int(physical_id):
        raise ValueError(
            "Only the reserved logical/physical ID pairs are allowed for the "
            "%d-switch topology" % int(switch_count)
        )
    return entry


def assert_registries_disjoint(four_switch_logical_to_physical):
    """Guard: new topology IDs never collide with the four-switch registry."""
    used_logical = set(int(key) for key in four_switch_logical_to_physical)
    used_physical = set(int(value) for value in four_switch_logical_to_physical.values())
    used_logical.update(range(1, 20))
    used_physical.update(range(1, 20))
    for count in TOPOLOGY_ID_REGISTRY:
        for entry in topology_run_registry(count).values():
            if entry["logical_experiment_id"] in used_logical:
                raise ValueError("Logical ID collision: %d" % entry["logical_experiment_id"])
            if entry["physical_run_id"] in used_physical:
                raise ValueError("Physical ID collision: %d" % entry["physical_run_id"])
            used_logical.add(entry["logical_experiment_id"])
            used_physical.add(entry["physical_run_id"])
    return True
