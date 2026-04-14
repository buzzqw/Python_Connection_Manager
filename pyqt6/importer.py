"""
importer.py - Importazione connessioni da app esterne in PCM
Supporta:
  • Remmina  (.remmina — INI, cartella o file singolo)
  • Remote Desktop Manager  (XML .rdm  oppure  JSON .json)

Formato RDM XML reale
---------------------
  <Connection>
    <n>nome</n>                          ← nome connessione
    <ConnectionType>SSHShell|RDPConfigured|VNC|Group|…</ConnectionType>
    <Group>nome gruppo</Group>
    <Url>ip_rdp</Url>                    ← host per RDP
    <Terminal>
      <Host>…</Host>                     ← host SSH
      <HostPort>…</HostPort>             ← porta SSH
      <Username>…</Username>
    </Terminal>
    <RDP>
      <UserName>…</UserName>
    </RDP>
    <VNC>
      <Host>…</Host>
      <Port>…</Port>
    </VNC>
  </Connection>

Formato RDM JSON reale
----------------------
  ConnectionType è un intero:
    1  = RDPConfigured
    4  = VNC
    25 = Group
    76 = SSHTunnel / proxy
    77 = SSHShell
  Nome in "Name", dati SSH in "Terminal":{Host, HostPort, Username}
  Dati RDP: host in "Url", utente in "RDP":{UserName}
  Dati VNC in "VNC":{Host, Port}
"""

from __future__ import annotations
import configparser
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import config_manager

# ---------------------------------------------------------------------------
# Mappe ConnectionType
# ---------------------------------------------------------------------------

# XML: stringa → protocollo PCM
_RDM_XML_PROTO: dict[str, str] = {
    "RDPConfigured":         "rdp",
    "RDPCertificate":        "rdp",
    "RemoteDesktopProtocol": "rdp",
    "SSHShell":              "ssh",
    "SSH":                   "ssh",
    "SecureShell":           "ssh",
    "SFTP":                  "sftp",
    "FTP":                   "ftp",
    "FTPS":                  "ftp",
    "VNC":                   "vnc",
    "Telnet":                "telnet",
    "Serial":                "serial",
    "SSHTunnel":             "ssh_tunnel",
    # tipi da ignorare
    "Group":                 "__group__",
    "Credential":            "__skip__",
}

# JSON: intero → protocollo PCM
_RDM_JSON_PROTO: dict[int, str] = {
    1:  "rdp",        # RDPConfigured
    4:  "vnc",        # VNC
    7:  "ssh",        # SSH (vecchio)
    25: "__group__",  # Group/folder
    30: "ftp",
    31: "ftp",        # FTPS
    61: "telnet",
    76: "ssh_tunnel",
    77: "ssh",        # SSHShell
    78: "sftp",
}

_PORTE_DEFAULT: dict[str, str] = {
    "ssh": "22", "rdp": "3389", "vnc": "5900",
    "sftp": "22", "telnet": "23", "ftp": "21",
    "ssh_tunnel": "22",
}

_REMMINA_PROTO: dict[str, str] = {
    "SSH": "ssh", "SFTP": "sftp", "RDP": "rdp",
    "VNC": "vnc", "TELNET": "telnet",
    "X2GO": "ssh", "SPICE": "vnc",
}


# ===========================================================================
# REMMINA
# ===========================================================================

def importa_remmina(percorso: Optional[str] = None) -> dict:
    if percorso is None:
        percorso = os.path.expanduser("~/.local/share/remmina")
    p = Path(percorso)
    if p.is_file() and p.suffix == ".remmina":
        file_list = [p]
    elif p.is_dir():
        file_list = sorted(p.glob("*.remmina"))
    else:
        raise FileNotFoundError(f"Percorso Remmina non trovato: {percorso}")
    if not file_list:
        raise ValueError(f"Nessun file .remmina trovato in: {percorso}")

    profili: dict = {}
    for f in file_list:
        try:
            pr = _parse_remmina_file(f)
            if pr:
                nome = pr.pop("__nome__")
                profili[_univoco(nome, profili)] = pr
        except Exception as e:
            print(f"[importer/remmina] {f.name}: {e}")
    return profili


def _parse_remmina_file(path: Path) -> Optional[dict]:
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(str(path), encoding="utf-8")
    if "remmina" not in cp:
        return None
    sec   = cp["remmina"]
    proto = _REMMINA_PROTO.get(sec.get("protocol", "RDP").upper(), "rdp")
    nome  = sec.get("name", path.stem).strip() or path.stem
    server = sec.get("server", "")
    host   = server.split(":")[0].strip()
    porta  = server.split(":", 1)[1].strip() if ":" in server else ""
    if not porta:
        porta = _PORTE_DEFAULT.get(proto, "")

    pr: dict = {
        "__nome__":  nome,
        "protocol":  proto,
        "host":      host,
        "port":      porta,
        "user":      sec.get("username", "").strip(),
        "password":  "",
        "notes":     sec.get("notes", "").strip(),
        "group":     sec.get("group", "").strip(),
        "_sorgente": "remmina",
    }
    if proto == "rdp":
        pr.update({"rdp_client": "xfreerdp", "fullscreen": False,
                   "redirect_clipboard": True, "redirect_drives": False})
    elif proto in ("ssh", "sftp"):
        pr.update({"private_key": sec.get("ssh_privatekey", "").strip(),
                   "compression": sec.get("ssh_compression", "0") == "1",
                   "x11": False, "keepalive": False,
                   "sftp_browser": proto == "sftp"})
    elif proto == "vnc":
        pr.update({"vnc_client": "vncviewer", "vnc_color": "Truecolor (32 bpp)",
                   "vnc_quality": "Buona"})
    return pr


# ===========================================================================
# REMOTE DESKTOP MANAGER — dispatcher
# ===========================================================================

def importa_rdm(percorso: str) -> dict:
    p = Path(percorso)
    if not p.exists():
        raise FileNotFoundError(f"File non trovato: {percorso}")
    suff = p.suffix.lower()
    if suff == ".json":
        return _parse_rdm_json(p)
    else:   # .rdm, .xml, o ignoto → tentiamo XML
        try:
            return _parse_rdm_xml(p)
        except ET.ParseError:
            return _parse_rdm_json(p)


# ===========================================================================
# RDM XML
# ===========================================================================

def _parse_rdm_xml(path: Path) -> dict:
    tree = ET.parse(str(path))
    root = tree.getroot()
    # Radice può essere <RDMExport> o <Connections>
    conns_el = root.find("Connections")
    conns = conns_el if conns_el is not None else root
    profili: dict = {}
    for child in conns:
        if child.tag != "Connection":
            continue
        pr = _rdm_xml_connection(child)
        if pr is None:
            continue
        nome = pr.pop("__nome__")
        profili[_univoco(nome, profili)] = pr
    return profili


def _rdm_xml_connection(conn: ET.Element) -> Optional[dict]:
    tipo_raw = _xt(conn, "ConnectionType") or ""
    proto    = _RDM_XML_PROTO.get(tipo_raw, None)

    if proto in ("__group__", "__skip__") or proto is None:
        return None   # gruppi e credenziali vengono saltati

    nome   = _xt(conn, "n") or _xt(conn, "Name") or ""
    gruppo = _xt(conn, "Group") or ""
    note   = _xt(conn, "Description") or ""

    # ── Estrazione host/porta/utente per tipo ────────────────────────
    host  = ""
    porta = ""
    user  = ""

    if proto == "rdp":
        host  = _xt(conn, "Url") or ""
        porta = _PORTE_DEFAULT["rdp"]
        rdp   = conn.find("RDP")
        if rdp is not None:
            user = _xt(rdp, "UserName") or ""

    elif proto in ("ssh", "sftp", "ssh_tunnel"):
        term  = conn.find("Terminal")
        if term is not None:
            host  = _xt(term, "Host") or ""
            porta = _xt(term, "HostPort") or _PORTE_DEFAULT.get(proto, "22")
            user  = _xt(term, "Username") or ""
        if not host:
            host  = _xt(conn, "Url") or ""

    elif proto == "vnc":
        vnc = conn.find("VNC")
        if vnc is not None:
            host  = _xt(vnc, "Host") or ""
            porta = _xt(vnc, "Port") or _PORTE_DEFAULT["vnc"]
        if not host:
            host = _xt(conn, "Url") or ""

    elif proto == "telnet":
        term = conn.find("Terminal")
        if term is not None:
            host  = _xt(term, "Host") or _xt(conn, "Url") or ""
            porta = _xt(term, "HostPort") or _PORTE_DEFAULT["telnet"]
            user  = _xt(term, "Username") or ""

    elif proto == "ftp":
        host  = _xt(conn, "Url") or ""
        porta = _PORTE_DEFAULT["ftp"]

    # Se non abbiamo almeno un host, ignoriamo
    if not host and not nome:
        return None

    if not porta:
        porta = _PORTE_DEFAULT.get(proto, "")

    pr: dict = {
        "__nome__":  nome or host,
        "protocol":  proto,
        "host":      host.strip(),
        "port":      str(porta).strip(),
        "user":      user.strip(),
        "password":  "",
        "notes":     note.strip(),
        "group":     gruppo.strip(),
        "_sorgente": "rdm",
    }
    _rdm_extra(pr, proto, tipo_raw.upper())
    return pr


# ===========================================================================
# RDM JSON
# ===========================================================================

def _parse_rdm_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    entries: list
    if isinstance(data, dict):
        entries = data.get("Connections", [])
    elif isinstance(data, list):
        entries = data
    else:
        entries = []

    profili: dict = {}
    for entry in entries:
        pr = _rdm_json_entry(entry)
        if pr is None:
            continue
        nome = pr.pop("__nome__")
        profili[_univoco(nome, profili)] = pr
    return profili


def _rdm_json_entry(entry: dict) -> Optional[dict]:
    tipo_int = entry.get("ConnectionType", -1)
    proto    = _RDM_JSON_PROTO.get(tipo_int, None)

    if proto in ("__group__", "__skip__") or proto is None:
        return None

    nome   = entry.get("Name", "").strip()
    gruppo = entry.get("Group", "").strip()
    note   = entry.get("Description", "").strip()

    # ── Estrazione host/porta/utente ────────────────────────────────
    host  = ""
    porta = ""
    user  = ""

    if proto == "rdp":
        host  = entry.get("Url", "").strip()
        porta = str(entry.get("Port", _PORTE_DEFAULT["rdp"]))
        rdp   = entry.get("RDP", {})
        user  = rdp.get("UserName", rdp.get("Username", "")).strip()

    elif proto in ("ssh", "sftp", "ssh_tunnel"):
        term  = entry.get("Terminal", {})
        host  = term.get("Host", entry.get("Url", "")).strip()
        porta = str(term.get("HostPort", term.get("Port",
                    _PORTE_DEFAULT.get(proto, "22"))))
        user  = term.get("Username", term.get("UserName", "")).strip()

    elif proto == "vnc":
        vnc   = entry.get("VNC", {})
        host  = vnc.get("Host", entry.get("Url", "")).strip()
        porta = str(vnc.get("Port", _PORTE_DEFAULT["vnc"]))

    elif proto == "telnet":
        term  = entry.get("Terminal", {})
        host  = term.get("Host", entry.get("Url", "")).strip()
        porta = str(term.get("HostPort", _PORTE_DEFAULT["telnet"]))
        user  = term.get("Username", "").strip()

    elif proto == "ftp":
        host  = entry.get("Url", "").strip()
        porta = str(entry.get("Port", _PORTE_DEFAULT["ftp"]))

    if not host and not nome:
        return None
    if not porta or porta == "0":
        porta = _PORTE_DEFAULT.get(proto, "")

    tipo_str = {
        1: "RDPConfigured", 4: "VNC", 77: "SSHShell",
        76: "SSHTunnel", 78: "SFTP", 31: "FTPS",
    }.get(tipo_int, "")

    pr: dict = {
        "__nome__":  nome or host,
        "protocol":  proto,
        "host":      host,
        "port":      porta,
        "user":      user,
        "password":  "",
        "notes":     note,
        "group":     gruppo,
        "_sorgente": "rdm",
    }
    _rdm_extra(pr, proto, tipo_str.upper())
    return pr


# ---------------------------------------------------------------------------
# Campi extra per protocollo
# ---------------------------------------------------------------------------

def _rdm_extra(pr: dict, proto: str, tipo_upper: str):
    if proto == "rdp":
        pr.update({"rdp_client": "xfreerdp", "fullscreen": False,
                   "redirect_clipboard": True, "redirect_drives": False})
    elif proto in ("ssh", "sftp"):
        pr.update({"private_key": "", "compression": False, "x11": False,
                   "keepalive": False, "sftp_browser": proto == "sftp"})
    elif proto == "vnc":
        pr.update({"vnc_client": "vncviewer", "vnc_color": "Truecolor (32 bpp)",
                   "vnc_quality": "Buona"})
    elif proto == "ftp":
        pr.update({"ftp_tls": "FTPS" in tipo_upper, "ftp_passive": True})


# ===========================================================================
# Utility
# ===========================================================================

def _xt(node: ET.Element, tag: str) -> Optional[str]:
    el = node.find(tag)
    return el.text.strip() if el is not None and el.text else None


def _univoco(nome: str, profili: dict) -> str:
    if nome not in profili:
        return nome
    i = 2
    while f"{nome} ({i})" in profili:
        i += 1
    return f"{nome} ({i})"


def unisci_in_pcm(nuovi: dict, sostituzione: bool = False) -> tuple[int, int]:
    esistenti = config_manager.load_profiles()
    aggiunti = ignorati = 0
    for nome, dati in nuovi.items():
        if nome in esistenti and not sostituzione:
            esistenti[_univoco(nome, esistenti)] = dati
        else:
            esistenti[nome] = dati
        aggiunti += 1
    config_manager.save_profiles(esistenti)
    return aggiunti, ignorati


# ===========================================================================
# Test rapido sui file reali
# ===========================================================================

def _test_file(percorso: str):
    p = Path(percorso)
    print(f"\n=== Test: {p.name} ===")
    profili = importa_rdm(percorso)
    print(f"  Trovate {len(profili)} connessioni:")
    for nome, d in profili.items():
        print(f"  [{d['protocol'].upper():10}] {nome:40} {d.get('user','')}@{d.get('host','')}:{d.get('port','')}  (gruppo: {d.get('group','—')})")


# ===========================================================================
# CLI
# ===========================================================================

def _uso():
    print("Uso:")
    print("  python importer.py remmina [percorso]")
    print("  python importer.py rdm     file.xml|json")
    print("  python importer.py test    file.xml|json   ← solo stampa, non salva")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _uso()

    cmd = sys.argv[1].lower()

    if cmd == "test" and len(sys.argv) >= 3:
        _test_file(sys.argv[2])
        sys.exit(0)

    if cmd == "remmina":
        percorso = sys.argv[2] if len(sys.argv) > 2 else None
        print(f"[importer] Remmina: {percorso or '~/.local/share/remmina'}")
        profili = importa_remmina(percorso)
    elif cmd == "rdm":
        if len(sys.argv) < 3:
            _uso()
        print(f"[importer] RDM: {sys.argv[2]}")
        profili = importa_rdm(sys.argv[2])
    else:
        _uso()

    print(f"  → {len(profili)} connessioni trovate")
    for n, d in profili.items():
        g = d.get("group", "")
        print(f"  [{d['protocol'].upper():10}] {n:40} {d.get('host','')}  (gruppo: {g or '—'})")

    risposta = input("\nUnire a connections.json? [s/N] ").strip().lower()
    if risposta == "s":
        aggiunti, _ = unisci_in_pcm(profili)
        print(f"  ✓ {aggiunti} connessioni aggiunte")
    else:
        print("  Annullato.")
