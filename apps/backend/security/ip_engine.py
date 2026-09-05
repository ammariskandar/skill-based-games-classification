"""
High-performance VPN / datacenter IP detection — SBGC-106.

Committed CIDR lists are converted to sorted, merged integer intervals at
load time and queried with ``bisect`` (O(log N)) so that thousands of subnets
never produce a multi-second linear scan on the login hot path.
"""

from __future__ import annotations

import bisect
import ipaddress
import logging
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger("django.security")


class IPRange(NamedTuple):
    start: int
    end: int


class IPSubnetMatcher:
    """Match an IP address against flagged VPN/datacenter ranges via bisect."""

    def __init__(self) -> None:
        self.ipv4_ranges: list[IPRange] = []
        self.ipv6_ranges: list[IPRange] = []
        self.loaded = False

    def load_subnets(self, data_dir: Path) -> None:
        """Load and index the committed IPv4/IPv6 subnet files."""
        v4_file = data_dir / "vpn-ipv4.txt"
        v6_file = data_dir / "vpn-ipv6.txt"

        raw_v4 = self._parse_file(v4_file, ipaddress.IPv4Network)
        raw_v6 = self._parse_file(v6_file, ipaddress.IPv6Network)

        self.ipv4_ranges = self._merge_and_sort_ranges(raw_v4)
        self.ipv6_ranges = self._merge_and_sort_ranges(raw_v6)
        self.loaded = True
        logger.info(
            "Loaded %d IPv4 ranges and %d IPv6 ranges for VPN detection.",
            len(self.ipv4_ranges),
            len(self.ipv6_ranges),
        )

    def _parse_file(self, filepath: Path, network_cls: type) -> list[IPRange]:
        """Parse a plain-text CIDR file into a list of integer ranges."""
        ranges: list[IPRange] = []
        if not filepath.exists():
            logger.warning("VPN IP file missing: %s", filepath)
            return ranges

        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    net = network_cls(line, strict=False)
                    ranges.append(
                        IPRange(
                            int(net.network_address),
                            int(net.broadcast_address),
                        )
                    )
                except ValueError:
                    continue
        return ranges

    @staticmethod
    def _merge_and_sort_ranges(ranges: list[IPRange]) -> list[IPRange]:
        """Sort and merge overlapping/adjacent ranges into disjoint intervals."""
        if not ranges:
            return []
        ranges.sort(key=lambda r: r.start)
        merged: list[IPRange] = [ranges[0]]
        for current in ranges[1:]:
            prev = merged[-1]
            if current.start <= prev.end + 1:
                merged[-1] = IPRange(prev.start, max(prev.end, current.end))
            else:
                merged.append(current)
        return merged

    def is_vpn_or_datacenter(self, ip_str: str) -> bool:
        """Return True when *ip_str* falls inside a flagged range."""
        try:
            ip_obj = ipaddress.ip_address(ip_str.strip())
        except ValueError:
            return False

        ip_int = int(ip_obj)
        target_ranges = self.ipv4_ranges if ip_obj.version == 4 else self.ipv6_ranges
        if not target_ranges:
            return False

        idx = bisect.bisect_right(target_ranges, ip_int, key=lambda r: r.start)
        if idx > 0:
            match = target_ranges[idx - 1]
            if match.start <= ip_int <= match.end:
                return True
        return False


# Process-wide singleton loaded lazily from the committed data directory.
_DATA_DIR = Path(__file__).resolve().parent / "data"
ip_matcher = IPSubnetMatcher()


def _ensure_loaded() -> None:
    if not ip_matcher.loaded:
        ip_matcher.load_subnets(_DATA_DIR)


def is_flagged_ip(ip_str: str) -> bool:
    """Convenience wrapper around the process-wide matcher."""
    _ensure_loaded()
    return ip_matcher.is_vpn_or_datacenter(ip_str)
