"""Small, bounded TCP discovery scanner used by the PCM UI."""

from __future__ import annotations

import ipaddress
import math
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


DEFAULT_PORTS = {
    "ssh": 22,
    "rdp": 3389,
    "vnc": 5900,
    "telnet": 23,
}


class ScanError(ValueError):
    pass


def parse_ports(value: str) -> list[int]:
    """Parse ``22,80,443`` and ranges such as ``5900-5902``."""
    ports: set[int] = set()
    for part in str(value or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                first, last = (int(piece.strip()) for piece in part.split("-", 1))
                if first > last:
                    raise ScanError("Intervallo porte invertito")
                ports.update(range(first, last + 1))
            else:
                ports.add(int(part))
        except ValueError as exc:
            raise ScanError(f"Porta non valida: {part}") from exc
    if not ports or any(port < 1 or port > 65535 for port in ports):
        raise ScanError("Le porte devono essere comprese tra 1 e 65535")
    if len(ports) > 256:
        raise ScanError("Sono consentite al massimo 256 porte per scansione")
    return sorted(ports)


def parse_hosts(first: str, last: str, max_hosts: int = 4096) -> list[str]:
    try:
        start = ipaddress.ip_address(str(first).strip())
        end = ipaddress.ip_address(str(last).strip())
    except ValueError as exc:
        raise ScanError("Indirizzo IP non valido") from exc
    if start.version != end.version or int(start) > int(end):
        raise ScanError("Intervallo IP non valido")
    count = int(end) - int(start) + 1
    if count > max_hosts:
        raise ScanError(f"Intervallo troppo grande: massimo {max_hosts} host")
    return [str(ipaddress.ip_address(int(start) + offset)) for offset in range(count)]


def scan_range(
    first: str,
    last: str,
    ports: list[int],
    timeout: float = 0.5,
    workers: int = 64,
    stop_event: threading.Event | None = None,
):
    """Yield open ``{"host", "port"}`` results as they are discovered."""
    hosts = parse_hosts(first, last)
    if not ports or any(not isinstance(port, int) or port < 1 or port > 65535 for port in ports):
        raise ScanError("Lista porte non valida")
    if len(ports) > 256:
        raise ScanError("Sono consentite al massimo 256 porte per scansione")
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 30:
        raise ScanError("Il timeout deve essere compreso tra 0 e 30 secondi")
    if len(hosts) * len(ports) > 65536:
        raise ScanError("Scansione troppo grande: massimo 65536 verifiche")
    workers = max(1, min(128, int(workers)))

    def probe(item):
        host, port = item
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return {"host": host, "port": port}
        except (OSError, TimeoutError):
            return None

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(probe, (host, port)) for host in hosts for port in ports]
        for future in as_completed(futures):
            if stop_event is not None and stop_event.is_set():
                for pending in futures:
                    pending.cancel()
                return
            result = future.result()
            if result is not None:
                yield result


def profile_for_result(result: dict, protocol: str) -> tuple[str, dict]:
    """Convert a selected scan result into a PCM profile."""
    host = str(result["host"])
    port = str(result["port"])
    if protocol == "file_transfer":
        data = {"protocol": protocol, "ft_protocol": "SFTP"}
    else:
        data = {"protocol": protocol}
    data.update({"host": host, "port": port, "user": "", "password": ""})
    name = f"{protocol.upper()} {host}:{port}"
    return name, data
