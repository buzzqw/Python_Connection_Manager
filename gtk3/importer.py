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
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Optional

import config_manager
from pcm_logging import get_logger as _get_log

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
            _get_log(__name__).warning("errore parsing remmina %s: %s", f.name, e)
    return profili


def _parse_remmina_file(path: Path) -> Optional[dict]:
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(str(path), encoding="utf-8")
    if "remmina" not in cp:
        return None
    sec   = cp["remmina"]
    proto = _REMMINA_PROTO.get(sec.get("protocol", "RDP").upper(), "rdp")
    nome  = sec.get("name", path.stem).strip() or path.stem
    server = sec.get("server", "").strip()
    # Un endpoint IPv6 letterale è [2001:db8::1]:3389: dividere su ':'
    # spezzerebbe l'indirizzo. Gestiamo prima i bracket, poi host:porta.
    m = re.match(r"^\[([^\]]+)\](?::(\d+))?$", server)
    if m:
        host, porta = m.group(1), m.group(2) or ""
    elif ":" in server:
        host, porta = server.rsplit(":", 1)
    else:
        host, porta = server, ""
    host = host.strip()
    porta = porta.strip()
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
# mRemoteNG XML (confCons.xml)
# ===========================================================================

_MREMOTENG_PROTO: dict[str, str] = {
    "SSH2":    "ssh",
    "SSH1":    "ssh",
    "SSH":     "ssh",
    "RDP":     "rdp",
    "VNC":     "vnc",
    "TELNET":  "telnet",
    "RAW":     "serial",
    "SERIAL":  "serial",
    "SFTP":    "sftp",
    "FTP":     "ftp",
}


def importa_mremoteng(percorso: str) -> dict:
    """Importa connessioni e gruppi da un file XML esportato da mRemoteNG (confCons.xml)."""
    p = Path(percorso)
    if not p.exists():
        raise FileNotFoundError(f"File non trovato: {percorso}")
    tree = ET.parse(str(p))
    root = tree.getroot()
    profili: dict = {}

    def _tag(el: ET.Element) -> str:
        return el.tag.split("}")[-1] if "}" in el.tag else el.tag

    def _traverse(node: ET.Element, current_group: str = ""):
        tag = _tag(node)
        if tag.lower() == "node":
            node_type = node.attrib.get("Type", "").strip()
            name = node.attrib.get("Name", "").strip()
            is_container = node_type.lower() == "container" or (
                not node_type and not node.attrib.get("Hostname") and not node.attrib.get("Host")
                and any(_tag(c).lower() == "node" for c in node)
            )
            if is_container:
                new_group = current_group
                if name and name.lower() not in ("root", "connections"):
                    new_group = f"{current_group}/{name}" if current_group else name
                for child in node:
                    _traverse(child, new_group)
                return
            elif node_type.lower() == "connection" or node.attrib.get("Hostname") or node.attrib.get("Host"):
                pr = _mremoteng_node_to_profile(node, current_group)
                if pr:
                    nome = pr.pop("__nome__")
                    profili[_univoco(nome, profili)] = pr
                for child in node:
                    _traverse(child, current_group)
                return

        for child in node:
            _traverse(child, current_group)

    _traverse(root)
    return profili


def _mremoteng_node_to_profile(node: ET.Element, current_group: str) -> Optional[dict]:
    proto_raw = node.attrib.get("Protocol", "SSH2").strip().upper()
    proto = _MREMOTENG_PROTO.get(proto_raw, "ssh")
    nome = node.attrib.get("Name", "").strip()
    host = (node.attrib.get("Hostname") or node.attrib.get("Host") or "").strip()
    porta = (node.attrib.get("Port") or "").strip()
    if not porta or porta == "0":
        porta = _PORTE_DEFAULT.get(proto, "22")
    user = (node.attrib.get("Username") or node.attrib.get("User") or "").strip()
    note = (node.attrib.get("Description") or "").strip()

    if not host and not nome:
        return None

    pr: dict = {
        "__nome__":   nome or host,
        "protocol":   proto,
        "host":       host,
        "port":       str(porta),
        "user":       user,
        "password":   "",
        "notes":      note,
        "group":      current_group,
        "_sorgente":  "mremoteng",
    }

    if proto == "rdp":
        pr.update({
            "rdp_client": "xfreerdp",
            "fullscreen": False,
            "redirect_clipboard": node.attrib.get("RedirectClipboard", "True").lower() in ("true", "1", "yes"),
            "redirect_drives": node.attrib.get("RedirectDrives", "False").lower() in ("true", "1", "yes"),
        })
        dom = node.attrib.get("Domain", "").strip()
        if dom:
            pr["rdp_domain"] = dom
    elif proto in ("ssh", "sftp"):
        pr.update({
            "private_key": "",
            "compression": False,
            "x11": False,
            "keepalive": False,
            "sftp_browser": proto == "sftp",
        })
    elif proto == "vnc":
        pr.update({
            "vnc_client": "vncviewer",
            "vnc_color": "Truecolor (32 bpp)",
            "vnc_quality": "Buona",
        })
    elif proto == "ftp":
        pr.update({
            "protocol": "file_transfer",
            "ft_protocol": "FTP",
            "ftp_passive": True,
        })
    elif proto == "serial":
        pr.update({
            "host": host or "/dev/ttyS0",
            "port": str(porta) if porta != "22" else "9600",
        })

    return pr


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


# Campi che gli importatori non riportano mai: se un profilo viene
# sovrascritto non vanno persi (altrimenti l'import cancella credenziali).
_CREDENZIALI = ("password", "totp_secret", "private_key")


def unisci_in_pcm(nuovi: dict, sostituzione: bool = False) -> tuple[int, int]:
    esistenti = config_manager.load_profiles()
    aggiunti = ignorati = 0
    for nome, dati in nuovi.items():
        if nome in esistenti and not sostituzione:
            esistenti[_univoco(nome, esistenti)] = dati
        elif nome in esistenti and isinstance(esistenti[nome], dict) and isinstance(dati, dict):
            # Sovrascrittura: mantieni le credenziali già salvate se l'import
            # non ne porta di nuove.
            vecchio = esistenti[nome]
            if _ssh_proviene_da_config(dati) and _ssh_proviene_da_config(vecchio):
                # ~/.ssh/config non possiede l'intero profilo: aggiorna solo
                # i campi SSH e lascia gruppo, tag e preferenze dell'utente.
                merged = dict(vecchio)
                for campo in _SSH_CAMPI_SYNC:
                    if campo in dati:
                        merged[campo] = dati[campo]
                if dati.get("notes") and (
                        not (vecchio.get("notes") or "").strip()
                        or _ssh_nota_generata(vecchio.get("notes") or "")):
                    merged["notes"] = dati["notes"]
                merged["_sorgente"] = _SSH_CONFIG_SOURCE
                merged["_ssh_alias"] = dati.get("_ssh_alias") or nome
                esistenti[nome] = merged
            else:
                merged = dict(dati)
                for campo in _CREDENZIALI:
                    if not dati.get(campo) and vecchio.get(campo):
                        merged[campo] = vecchio[campo]
                esistenti[nome] = merged
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
# Import PuTTY sessions (~/.putty/sessions/)
# ===========================================================================

def importa_putty(percorso: Optional[str] = None) -> dict:
    """
    Legge le sessioni PuTTY dalla cartella ~/.putty/sessions/.
    Ogni file è un INI senza header di sezione — viene aggiunto [Session] artificialmente.
    """
    sessioni_dir = percorso or os.path.expanduser("~/.putty/sessions")
    if not os.path.isdir(sessioni_dir):
        return {}

    profili: dict = {}
    for filename in os.listdir(sessioni_dir):
        filepath = os.path.join(sessioni_dir, filename)
        if not os.path.isfile(filepath):
            continue
        nome = filename.replace("%20", " ").replace("%2F", "/")
        if nome.lower() == "default%20settings" or nome.lower() == "default settings":
            continue

        cp = configparser.ConfigParser(strict=False)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = "[Session]\n" + f.read()
            cp.read_string(content)
            sec = cp["Session"]
        except Exception:
            continue

        host     = sec.get("HostName", "").strip()
        port     = sec.get("PortNumber", "22").strip()
        user     = sec.get("UserName", "").strip()
        protocol = sec.get("Protocol", "ssh").strip().lower()
        pkey     = sec.get("PublicKeyFile", "").strip()

        if protocol not in ("ssh", "telnet", "serial", "raw"):
            protocol = "ssh"
        if protocol == "raw":
            protocol = "telnet"

        if not host and protocol != "serial":
            continue

        profili[nome] = {
            "protocol":    protocol,
            "host":        host,
            "port":        port,
            "user":        user,
            "private_key": pkey,
            "group":       "PuTTY",
            "notes":       f"Importato da PuTTY: {filename}",
        }

    return profili


# ===========================================================================
# Import ~/.ssh/config
# ===========================================================================
#
# Il parser segue la semantica di OpenSSH:
#   • Include ricorsivi (glob, ~, percorsi relativi a ~/.ssh) con anti-ciclo
#   • Host con alias multipli ("Host a b c") → una sessione per alias
#   • Host con wildcard (*, ?) e negazioni (!): usati come default, non
#     generano sessioni
#   • "prima occorrenza vince" e default globali prima del primo Host
#   • token %%, %h, %n, %p, %r, %u, %d e tilde
#   • blocchi Match ignorati (non supportiamo i criteri condizionali)
#
# Limiti noti: ProxyCommand/ProxyJump a più salti vengono ridotti al primo
# hop (PCM gestisce un solo jump host); le direttive non mappate sono scartate.

_SSH_INCLUDE_MAX_DEPTH = 16
_SSH_CONFIG_GROUP = "SSH Config"
_SSH_CONFIG_SOURCE = "sshconfig"

# Campi che ~/.ssh/config possiede. Durante la sincronizzazione vengono
# riallineati solo questi: gruppo, tag, credenziali e preferenze del terminale
# restano dell'utente.
_SSH_CAMPI_SYNC: tuple[str, ...] = (
    "protocol", "host", "port", "user", "private_key",
    "jump_host", "jump_user", "jump_port",
)


def _ssh_unquote(valore: str) -> str:
    """Rimuove le virgolette di apertura/chiusura usate da OpenSSH."""
    if len(valore) >= 2 and valore[0] == valore[-1] and valore[0] in "\"'":
        return valore[1:-1]
    return valore


def _ssh_dividi_direttiva(riga: str) -> "tuple[str, str]":
    """Divide 'Key value' oppure 'Key=value' in (chiave_lower, valore)."""
    riga = riga.strip()
    if "=" in riga:
        chiave, valore = riga.split("=", 1)
        # Non confondere 'ProxyCommand ssh -o Foo=bar' con un 'Key=value'
        if " " not in chiave.strip() and "\t" not in chiave.strip():
            return chiave.strip().lower(), valore.strip()
    parti = riga.split(None, 1)
    chiave = parti[0].lower()
    valore = parti[1].strip() if len(parti) > 1 else ""
    return chiave, valore


def _ssh_tokens(valore: str, alias: str, hostname: str, user: str,
                port: str) -> str:
    """Espande i token OpenSSH (%%, %h, %n, %p, %r, %u, %d) e la tilde.

    I token sconosciuti (%C, %L, %i, ...) restano invariati.
    """
    if not isinstance(valore, str) or not valore:
        return valore
    out: list[str] = []
    i = 0
    while i < len(valore):
        ch = valore[i]
        if ch != "%" or i + 1 >= len(valore):
            out.append(ch)
            i += 1
            continue
        tok = valore[i + 1]
        i += 2
        if tok == "%":
            out.append("%")
        elif tok == "h":
            out.append(hostname)
        elif tok == "n":
            out.append(alias)
        elif tok == "p":
            out.append(str(port))
        elif tok == "r":
            out.append(user)
        elif tok == "u":
            out.append(os.environ.get("USER") or os.environ.get("LOGNAME") or "")
        elif tok == "d":
            out.append(os.path.expanduser("~"))
        else:
            out.append("%" + tok)
    return os.path.expanduser("".join(out))


def _ssh_righe_config(percorso: str, visitati: Optional[set] = None,
                      depth: int = 0):
    """Generatore di (chiave, valore) con gli Include espansi sul posto.

    Un Include dentro un blocco Host continua quel blocco, esattamente come
    se il contenuto fosse stato incollato nel file (semantica OpenSSH).
    """
    if visitati is None:
        visitati = set()
    if depth > _SSH_INCLUDE_MAX_DEPTH:
        return

    reale = os.path.realpath(os.path.expanduser(percorso))
    if reale in visitati:          # ciclo di Include (solo sulla catena corrente)
        return
    visitati.add(reale)

    try:
        f = open(reale, "r", encoding="utf-8", errors="replace")
    except OSError:
        visitati.discard(reale)
        return

    try:
        with f:
            for riga in f:
                riga = riga.strip()
                if not riga or riga.startswith("#"):
                    continue
                chiave, valore = _ssh_dividi_direttiva(riga)
                if not chiave:
                    continue

                if chiave == "include" and valore:
                    for pattern in valore.split():
                        espanso = os.path.expanduser(_ssh_unquote(pattern))
                        base_ssh = os.path.join(os.path.expanduser("~"), ".ssh")
                        if not os.path.isabs(espanso):
                            # OpenSSH risolve i percorsi relativi in ~/.ssh.
                            # Se lì non esiste nulla, ripiega sulla cartella del
                            # file che contiene l'Include (utile per import da
                            # path arbitrari e per i test).
                            candidato = os.path.join(base_ssh, espanso)
                            if glob.glob(candidato):
                                espanso = candidato
                            else:
                                espanso = os.path.join(
                                    os.path.dirname(reale), espanso)
                        for incluso in sorted(glob.glob(espanso)):
                            yield from _ssh_righe_config(
                                incluso, visitati, depth + 1)
                    continue

                yield chiave, _ssh_unquote(valore)
    finally:
        # Solo i file della catena corrente contano per il rilevamento cicli:
        # un Include ripetuto in blocchi Host diversi è legittimo per OpenSSH
        # e deve essere applicato ogni volta.
        visitati.discard(reale)


def _ssh_pattern_match(pattern: str, alias: str) -> bool:
    return fnmatchcase(alias.lower(), pattern.lower())


def _ssh_host_matches(patterns: list[str], alias: str) -> bool:
    """True se alias rientra nei pattern di un blocco Host (con negazioni)."""
    positivo = False
    for p in patterns:
        if not p:
            continue
        if p.startswith("!"):
            if _ssh_pattern_match(p[1:], alias):
                return False
        elif _ssh_pattern_match(p, alias):
            positivo = True
    return positivo


def _ssh_blocchi(percorso: str) -> "list[tuple[list[str], dict]]":
    """Legge la config in blocchi (patterns, opzioni) in ordine di apparizione.

    Le direttive prima del primo Host valgono per tutti gli host e diventano
    un blocco implicito ['*'].
    """
    blocchi: list[tuple[list[str], dict]] = []
    patterns: Optional[list[str]] = None   # None = ancora in stato globale
    opts: dict = {}
    in_match = False

    def _chiudi():
        if patterns is not None and patterns:
            blocchi.append((patterns, dict(opts)))
        elif patterns is None and opts:
            blocchi.append((["*"], dict(opts)))

    for chiave, valore in _ssh_righe_config(percorso):
        if chiave == "host":
            _chiudi()
            patterns = valore.split()
            opts = {}
            in_match = False
        elif chiave == "match":
            _chiudi()
            patterns = None
            opts = {}
            in_match = True
        elif in_match:
            continue
        else:
            # Prima occorrenza vince (ssh usa il primo valore trovato)
            opts.setdefault(chiave, valore)

    _chiudi()
    return blocchi


def _ssh_scomponi_salto(valore: str) -> "tuple[str, str, str]":
    """Divide un hop ProxyJump (host, utente, porta).

    Supporta: host, user@host, host:porta, user@host:porta,
    [user@host]:porta, ssh://user@host:porta.
    """
    v = valore.strip()
    if v.lower().startswith("ssh://"):
        v = v[6:]

    # IPv6 tra parentesi quadre: [utente@host]:porta — va gestito prima
    # dello split su '@', altrimenti l'utente resterebbe attaccato alla '['
    if v.startswith("["):
        fine = v.find("]")
        if fine > 0:
            interno = v[1:fine]
            resto = v[fine + 1:]
            utente = ""
            if "@" in interno:
                utente, interno = interno.rsplit("@", 1)
            porta = resto[1:] if resto.startswith(":") else "22"
            return interno, utente, porta or "22"

    utente = ""
    if "@" in v:
        utente, v = v.rsplit("@", 1)
    if ":" in v:
        host, porta = v.rsplit(":", 1)
        return host, utente, porta or "22"
    return v, utente, "22"


def _ssh_proxy_jump(raw: str, alias: str, hostname: str, user: str,
                    port: str) -> "tuple[str, str, str, str]":
    """Ritorna (jump_host, jump_user, jump_port, catena_completa)."""
    if not raw:
        return "", "", "22", ""
    if raw.strip().lower() == "none":
        return "", "", "22", ""
    catena = [_ssh_tokens(h.strip(), alias, hostname, user, port)
              for h in raw.split(",") if h.strip()]
    if not catena:
        return "", "", "22", ""
    host, utente, porta = _ssh_scomponi_salto(catena[0])
    return host, utente, porta or "22", ",".join(catena)


def importa_ssh_config(percorso: Optional[str] = None) -> dict:
    """Importa ~/.ssh/config creando una sessione SSH per ogni alias Host.

    Gestisce Include, alias multipli, default globali/Host * e token OpenSSH.
    Gli host con wildcard non generano sessioni (ma restano come default).
    """
    cfg_path = percorso or os.path.expanduser("~/.ssh/config")
    if not os.path.isfile(os.path.expanduser(cfg_path)):
        return {}

    blocchi = _ssh_blocchi(cfg_path)

    # Alias concreti nell'ordine di comparsa, senza duplicati
    alias_list: list[str] = []
    visti: set[str] = set()
    for patterns, _ in blocchi:
        for p in patterns:
            if not p or p.startswith("!") or "*" in p or "?" in p:
                continue
            if p.lower() in visti:
                continue
            visti.add(p.lower())
            alias_list.append(p)

    profili: dict = {}
    for alias in alias_list:
        eff: dict = {}
        for patterns, opts in blocchi:
            if not _ssh_host_matches(patterns, alias):
                continue
            for k, v in opts.items():
                eff.setdefault(k, v)

        port = eff.get("port", "22") or "22"
        user = eff.get("user", "")
        hostname = _ssh_tokens(eff.get("hostname", "") or alias,
                               alias, alias, user, port)
        pkey = _ssh_tokens(eff.get("identityfile", ""),
                           alias, hostname, user, port)
        jump_host, jump_user, jump_port, catena = _ssh_proxy_jump(
            eff.get("proxyjump", ""), alias, hostname, user, port)

        note = f"Importato da {os.path.basename(cfg_path)} (alias: {alias})"
        if catena and "," in catena:
            note += f" — ProxyJump: {catena} (PCM usa il primo hop)"

        profili[alias] = {
            "protocol":    "ssh",
            "host":        hostname,
            "port":        port,
            "user":        user,
            "private_key": pkey,
            "jump_host":   jump_host,
            "jump_user":   jump_user,
            "jump_port":   jump_port or "22",
            "group":       _SSH_CONFIG_GROUP,
            "notes":       note,
            "_sorgente":   _SSH_CONFIG_SOURCE,
            "_ssh_alias":  alias,
        }

    return profili


# ---------------------------------------------------------------------------
# Sincronizzazione con ~/.ssh/config
# ---------------------------------------------------------------------------

def _ssh_nota_generata(nota: str) -> bool:
    """True se la nota è quella scritta dall'importatore (non dall'utente)."""
    n = (nota or "").strip()
    return (n.startswith("Importato da ") and " (alias: " in n
            and n.endswith(")"))


def _ssh_proviene_da_config(profilo: dict) -> bool:
    """True se il profilo è (o sembra) importato da ~/.ssh/config.

    Il controllo sulla nota serve a riconoscere i profili creati prima
    dell'introduzione del tag ``_sorgente``, così l'aggiornamento non
    duplica le sessioni già esistenti.
    """
    if not isinstance(profilo, dict):
        return False
    sorgente = (profilo.get("_sorgente") or "").strip().lower()
    if sorgente:
        return sorgente == _SSH_CONFIG_SOURCE
    return (profilo.get("group") == _SSH_CONFIG_GROUP
            and _ssh_nota_generata(profilo.get("notes") or ""))


def _ssh_confronta_valore(valore) -> str:
    """Normalizza un valore per il confronto (porta int vs stringa, None)."""
    if valore is None:
        return ""
    return str(valore).strip()


def confronta_ssh_config(profili: dict, esistenti: Optional[dict] = None,
                         percorso: Optional[str] = None) -> dict:
    """Confronta l'import di ~/.ssh/config con i profili PCM esistenti.

    Non modifica nulla: restituisce un piano con ``nuovi``, ``aggiornati``
    (campo per campo), ``rimossi`` (solo profili di provenienza SSH) e
    ``invariati``. Il piano viene applicato da
    :func:`applica_piano_ssh_config`.
    """
    if esistenti is None:
        esistenti = config_manager.load_profiles()

    # Indice dei profili già riconducibili a ~/.ssh/config. Il match esatto ha
    # la precedenza; il fallback case-insensitive evita doppioni quando
    # l'alias cambia solo di maiuscole/minuscole.
    per_nome: dict[str, str] = {}
    per_case: dict[str, str] = {}
    per_alias: dict[str, str] = {}
    for nome, profilo in esistenti.items():
        if not _ssh_proviene_da_config(profilo):
            continue
        per_nome.setdefault(nome, nome)
        per_case.setdefault(nome.casefold(), nome)
        # L'alias SSH è l'identità stabile: resta valido anche se la sessione
        # è stata rinominata in PCM.
        chiave_alias = (profilo.get("_ssh_alias") or "").strip().casefold()
        if chiave_alias:
            per_alias.setdefault(chiave_alias, nome)

    piano: dict = {
        "percorso": percorso or os.path.expanduser("~/.ssh/config"),
        "nuovi": [],
        "aggiornati": [],
        "rimossi": [],
        "invariati": [],
    }
    usati: set[str] = set()
    nomi_occupati: set[str] = set(esistenti)

    for alias, dati in profili.items():
        esistente = (per_alias.get(alias.casefold())
                     or per_nome.get(alias)
                     or per_case.get(alias.casefold()))
        if esistente is not None and esistente not in usati:
            usati.add(esistente)
            attuale = esistenti.get(esistente) or {}
            campi: dict[str, tuple] = {}
            for campo in _SSH_CAMPI_SYNC:
                nuovo = dati.get(campo)
                if _ssh_confronta_valore(nuovo) == \
                        _ssh_confronta_valore(attuale.get(campo)):
                    continue
                campi[campo] = (attuale.get(campo), nuovo)

            # La nota è solo provenienza: si aggiorna se è quella generata,
            # altrimenti restano le note scritte dall'utente.
            nota = dati.get("notes", "")
            nota_attuale = attuale.get("notes") or ""
            if nota and nota != nota_attuale and (
                    not nota_attuale.strip() or _ssh_nota_generata(nota_attuale)):
                campi["notes"] = (nota_attuale, nota)

            unito = dict(attuale)
            for campo in campi:
                if campo in dati:
                    unito[campo] = dati[campo]
            unito["_sorgente"] = _SSH_CONFIG_SOURCE
            unito["_ssh_alias"] = alias

            if campi:
                piano["aggiornati"].append({
                    "alias": alias,
                    "nome": esistente,
                    "prima": attuale,
                    "dati": unito,
                    "campi": campi,
                })
            else:
                piano["invariati"].append(
                    {"nome": esistente, "alias": alias})
            continue

        # Host nuovo. Se il nome è già usato da un profilo di un'altra
        # sorgente non lo si sovrascrive: viene creato con un suffisso.
        nome = alias
        if nome in nomi_occupati:
            nome = _univoco(nome, nomi_occupati)
        nomi_occupati.add(nome)
        piano["nuovi"].append({
            "alias": alias,
            "nome": nome,
            "dati": dict(dati),
        })

    for nome, profilo in esistenti.items():
        if nome in usati:
            continue
        if _ssh_proviene_da_config(profilo):
            piano["rimossi"].append({"nome": nome, "profilo": profilo})

    return piano


def applica_piano_ssh_config(piano: dict, rimuovi: bool = False) -> dict:
    """Applica un piano prodotto da :func:`confronta_ssh_config`.

    L'aggiornamento è per campo: solo i valori posseduti da ~/.ssh/config
    vengono scritti, il resto del profilo (gruppo, tag, credenziali,
    preferenze) resta intatto. ``rimuovi`` abilita la cancellazione dei
    profili non più presenti nella config.
    """
    esistenti = config_manager.load_profiles()
    aggiunti = aggiornati = rimossi = marcati = 0
    rinominati: list[tuple[str, str]] = []

    for voce in piano.get("nuovi", []):
        alias = voce.get("alias") or voce.get("nome") or ""
        nome = voce.get("nome") or alias
        if not nome:
            continue
        if nome in esistenti:
            nome = _univoco(nome, esistenti)
        if nome != alias:
            rinominati.append((alias, nome))
        dati = dict(voce.get("dati") or {})
        dati.setdefault("_sorgente", _SSH_CONFIG_SOURCE)
        dati.setdefault("_ssh_alias", alias)
        esistenti[nome] = dati
        aggiunti += 1

    for voce in piano.get("aggiornati", []):
        nome = voce.get("nome")
        attuale = esistenti.get(nome)
        if not nome or not isinstance(attuale, dict):
            continue
        dati = voce.get("dati") or {}
        for campo in voce.get("campi") or {}:
            if campo == "notes":
                if (not (attuale.get("notes") or "").strip()
                        or _ssh_nota_generata(attuale.get("notes") or "")):
                    attuale["notes"] = dati.get("notes", "")
            elif campo in dati:
                attuale[campo] = dati[campo]
        attuale["_sorgente"] = _SSH_CONFIG_SOURCE
        if voce.get("alias"):
            attuale["_ssh_alias"] = voce["alias"]
        aggiornati += 1

    # I profili già allineati vengono solo etichettati, così i futuri
    # confronti non dipendono più dall'euristica sulla nota.
    for voce in piano.get("invariati", []):
        nome = voce.get("nome") if isinstance(voce, dict) else voce
        profilo = esistenti.get(nome)
        if not isinstance(profilo, dict):
            continue
        etichettato = False
        if profilo.get("_sorgente") != _SSH_CONFIG_SOURCE:
            profilo["_sorgente"] = _SSH_CONFIG_SOURCE
            etichettato = True
        alias = voce.get("alias") if isinstance(voce, dict) else ""
        if alias and profilo.get("_ssh_alias") != alias:
            profilo["_ssh_alias"] = alias
            etichettato = True
        if etichettato:
            marcati += 1

    if rimuovi:
        for voce in piano.get("rimossi", []):
            nome = voce.get("nome")
            profilo = esistenti.get(nome)
            if profilo is None or not _ssh_proviene_da_config(profilo):
                continue
            del esistenti[nome]
            rimossi += 1

    modificato = bool(aggiunti or aggiornati or rimossi or marcati)
    if modificato:
        config_manager.save_profiles(esistenti)

    return {
        "aggiunti": aggiunti,
        "aggiornati": aggiornati,
        "rimossi": rimossi,
        "marcati": marcati,
        "rinominati": rinominati,
        "salvato": modificato,
    }


def sincronizza_ssh_config(percorso: Optional[str] = None,
                           rimuovi: bool = False) -> dict:
    """Import + confronto + applicazione in un solo passaggio (CLI/test)."""
    profili = importa_ssh_config(percorso)
    piano = confronta_ssh_config(profili, percorso=percorso)
    risultato = applica_piano_ssh_config(piano, rimuovi=rimuovi)
    risultato["piano"] = piano
    return risultato


# ===========================================================================
# MobaXterm (.mxtsessions / .mobaconf)
# ===========================================================================

# Tipo sessione → protocollo PCM
_MOBA_TYPES: dict[int, str] = {
    0: "ssh",
    1: "telnet",
    4: "rdp",
    5: "vnc",
    6: "ftp",
    7: "sftp",
    8: "serial",
}


def importa_mobaxterm(percorso: str) -> dict:
    """
    Legge sessioni da file MobaXterm (.mxtsessions o .mobaconf).
    Formato INI con sezioni [Bookmarks] / [Bookmarks_N].
    """
    p = Path(percorso)
    if not p.exists():
        raise FileNotFoundError(f"File non trovato: {percorso}")

    try:
        content = p.read_text(encoding="cp1252")
    except Exception:
        content = p.read_text(encoding="utf-8", errors="replace")

    profili: dict = {}
    current_subrep = ""
    in_bookmarks = False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue

        # Sezione
        if line.startswith("[") and line.endswith("]"):
            sec = line[1:-1]
            in_bookmarks = sec.lower().startswith("bookmarks")
            current_subrep = ""
            continue

        if not in_bookmarks:
            continue

        # SubRep / ImgNum (metadati della sezione, nessun #)
        if "#" not in line:
            eq = line.find("=")
            if eq == -1:
                continue
            k = line[:eq].strip().lower()
            v = line[eq + 1:].strip()
            if k == "subrep":
                current_subrep = v.replace("\\", "/")
            continue

        # Riga sessione: key=...=#IconNum#Type%...  oppure  key=#IconNum#Type%...
        hash_pos = line.find("#")
        prefix   = line[:hash_pos]
        eq_pos   = prefix.rfind("=")
        if eq_pos == -1:
            continue
        nome_raw = prefix[:eq_pos].strip()
        value    = line[hash_pos:]          # inizia con #

        pr = _parse_moba_entry(nome_raw, value, current_subrep)
        if pr:
            nome = pr.pop("__nome__")
            profili[_univoco(nome, profili)] = pr

    return profili


def _moba_decode(s: str) -> str:
    return (s.replace("__PTVIRG__", ";")
             .replace("__DBLQUO__", '"')
             .replace("__PIPE__",   "|")
             .replace("__DIEZE__",  "#")
             .replace("__PERCENT__", "%")
             .replace("_CurrentDrive_", "C:"))


def _parse_moba_entry(nome_raw: str, value: str, subrep: str) -> Optional[dict]:
    """
    Decodifica una singola riga sessione MobaXterm.
    value = '#IconNum#Type%field1%field2%...#termfields#displaymode#comment#color'
    """
    parts = value.split("#")
    # parts[0]='', parts[1]=IconNum, parts[2]='Type%f1%f2...', parts[3+]=terminal/meta
    if len(parts) < 3:
        return None

    conn_parts = parts[2].split("%")
    if not conn_parts:
        return None

    try:
        sess_type = int(conn_parts[0])
    except (ValueError, IndexError):
        return None

    proto = _MOBA_TYPES.get(sess_type)
    if proto is None:
        return None

    def _f(idx: int, default: str = "") -> str:
        try:
            v = conn_parts[idx].strip()
            return _moba_decode(v) if v else default
        except IndexError:
            return default

    def _jump_first(raw: str) -> str:
        # gateway field può contenere più host separati da __PIPE__ (già decodificato da _f)
        return raw.split("|")[0].strip() if raw else ""

    group   = subrep or "MobaXterm"
    comment = _moba_decode(parts[5].strip()) if len(parts) > 5 else ""
    nome    = _moba_decode(nome_raw) or ""

    if proto == "ssh":
        host = _f(1);  port = _f(2, "22") or "22"
        user = _f(3)
        x11         = _f(5, "0") == "-1"
        compression = _f(6, "0") == "-1"
        exec_cmd    = _f(7)
        jump_raw    = _f(8)
        jump_host   = _jump_first(_moba_decode(jump_raw)) if jump_raw else ""
        jump_port   = _jump_first(_f(9, "22")) or "22"
        jump_user   = _jump_first(_f(10))
        pkey        = _f(14)
        if not host:
            return None
        return {
            "__nome__":    nome or host,
            "protocol":   "ssh",
            "host":        host,      "port":      port,
            "user":        user,      "password":  "",
            "private_key": pkey,
            "x11":         x11,       "compression": compression,
            "startup_cmd": exec_cmd,
            "jump_host":   jump_host, "jump_port": jump_port, "jump_user": jump_user,
            "group":       group,     "notes":     comment,
            "_sorgente":  "mobaxterm",
        }

    elif proto == "rdp":
        host = _f(1);  port = _f(2, "3389") or "3389"
        user = _f(3)
        if not host or host.lower() == "localhost":
            return None
        return {
            "__nome__":         nome or host,
            "protocol":        "rdp",
            "host":             host,   "port":              port,
            "user":             user,   "password":          "",
            "rdp_client":      "xfreerdp",
            "fullscreen":       False,
            "redirect_clipboard": True,
            "redirect_drives":  False,
            "group":            group,  "notes":             comment,
            "_sorgente":       "mobaxterm",
        }

    elif proto == "vnc":
        host = _f(1);  port = _f(2, "5900") or "5900"
        if not host:
            return None
        return {
            "__nome__":   nome or host,
            "protocol":  "vnc",
            "host":       host,   "port":     port,
            "user":       "",     "password": "",
            "vnc_client": "vncviewer",
            "group":      group,  "notes":    comment,
            "_sorgente": "mobaxterm",
        }

    elif proto == "ftp":
        host = _f(1);  port = _f(2, "21") or "21"
        user = _f(3)
        if not host:
            return None
        return {
            "__nome__":    nome or host,
            "protocol":   "file_transfer",
            "ft_protocol": "FTP",
            "host":        host,   "port":     port,
            "user":        user,   "password": "",
            "ftp_passive": True,
            "group":       group,  "notes":    comment,
            "_sorgente":  "mobaxterm",
        }

    elif proto == "sftp":
        host = _f(1);  port = _f(2, "22") or "22"
        user = _f(3);  pkey = _f(9)
        if not host:
            return None
        return {
            "__nome__":    nome or host,
            "protocol":   "file_transfer",
            "ft_protocol": "SFTP",
            "host":        host,   "port":     port,
            "user":        user,   "password": "",
            "private_key": pkey,
            "group":       group,  "notes":    comment,
            "_sorgente":  "mobaxterm",
        }

    elif proto == "telnet":
        host = _f(1);  port = _f(2, "23") or "23"
        user = _f(3)
        if not host:
            return None
        return {
            "__nome__":  nome or host,
            "protocol": "telnet",
            "host":      host,   "port":     port,
            "user":      user,   "password": "",
            "group":     group,  "notes":    comment,
            "_sorgente": "mobaxterm",
        }

    elif proto == "serial":
        device = _f(1, "/dev/ttyS0")
        baud   = _f(2, "9600")
        return {
            "__nome__":  nome or device,
            "protocol": "serial",
            "host":      device,
            "port":      baud,
            "user":      "",    "password": "",
            "group":     group, "notes":    comment,
            "_sorgente": "mobaxterm",
        }

    return None


# ===========================================================================
# CLI
# ===========================================================================

def _uso():
    print("Uso:")
    print("  python importer.py remmina   [percorso]")
    print("  python importer.py rdm       file.xml|json")
    print("  python importer.py mremoteng confCons.xml")
    print("  python importer.py putty     [percorso]")
    print("  python importer.py sshconfig [percorso]")
    print("  python importer.py sync      [percorso] [--remove]")
    print("  python importer.py mobaxterm file.mxtsessions|.mobaconf")
    print("  python importer.py test      file.xml|json   ← solo stampa, non salva")
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
    elif cmd == "mremoteng":
        if len(sys.argv) < 3:
            _uso()
        print(f"[importer] mRemoteNG: {sys.argv[2]}")
        profili = importa_mremoteng(sys.argv[2])
    elif cmd == "putty":
        percorso = sys.argv[2] if len(sys.argv) > 2 else None
        print(f"[importer] PuTTY: {percorso or '~/.putty/sessions'}")
        profili = importa_putty(percorso)
    elif cmd == "sshconfig":
        percorso = sys.argv[2] if len(sys.argv) > 2 else None
        print(f"[importer] SSH config: {percorso or '~/.ssh/config'}")
        profili = importa_ssh_config(percorso)
    elif cmd == "sync":
        percorso = next((a for a in sys.argv[2:] if not a.startswith("-")),
                        None)
        rimuovi = "--remove" in sys.argv[2:]
        print(f"[importer] Sync SSH config: {percorso or '~/.ssh/config'}")
        risultato = sincronizza_ssh_config(percorso, rimuovi=rimuovi)
        piano = risultato.get("piano", {})
        print(f"  nuovi: {len(piano.get('nuovi', []))}  "
              f"aggiornati: {len(piano.get('aggiornati', []))}  "
              f"rimossi: {len(piano.get('rimossi', []))}  "
              f"invariati: {len(piano.get('invariati', []))}")
        for voce in piano.get("nuovi", []):
            print(f"  + {voce['nome']}  ({voce['alias']})")
        for voce in piano.get("aggiornati", []):
            campi = ", ".join(voce["campi"])
            print(f"  ~ {voce['nome']}  [{campi}]")
        for voce in piano.get("rimossi", []):
            print(f"  - {voce['nome']}")
        print("  ✓ Sincronizzazione applicata" if risultato.get("salvato")
              else "  Nessuna modifica")
        sys.exit(0)
    elif cmd == "mobaxterm":
        if len(sys.argv) < 3:
            _uso()
        print(f"[importer] MobaXterm: {sys.argv[2]}")
        profili = importa_mobaxterm(sys.argv[2])
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
