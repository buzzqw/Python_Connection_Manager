"""
exporter.py - Esportazione connessioni e inventario da PCM
Supporta:
  • OpenSSH Config  (~/.ssh/config)
  • CSV / Foglio di calcolo (.csv)
  • JSON Portabile / Backup (.json)
  • mRemoteNG XML (confCons.xml)
"""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

_PROTO_TO_MREMOTENG: dict[str, str] = {
    "ssh": "SSH2",
    "rdp": "RDP",
    "vnc": "VNC",
    "telnet": "Telnet",
    "sftp": "SFTP",
    "ftp": "FTP",
    "file_transfer": "SFTP",
    "serial": "Serial",
}


def _filtra_profili(profili: dict, gruppo: str | None = None) -> dict:
    """Filtra i profili in base al gruppo (se specificato). Include sottogruppi."""
    if not gruppo:
        return {k: dict(v) for k, v in profili.items() if isinstance(v, dict)}

    risultato = {}
    gruppo_slash = f"{gruppo}/"
    for nome, dati in profili.items():
        if not isinstance(dati, dict):
            continue
        g = dati.get("group", "")
        if g == gruppo or g.startswith(gruppo_slash):
            risultato[nome] = dict(dati)
    return risultato


def esporta_ssh_config(profili: dict, gruppo: str | None = None) -> tuple[str, int]:
    """
    Esporta le sessioni SSH compatibili in formato ~/.ssh/config di OpenSSH.
    Ritorna (testo_config, conteggio_sessioni).
    """
    filtrati = _filtra_profili(profili, gruppo)
    righe = [
        "# ==============================================================================",
        "# OpenSSH Configuration — Esportata da Python Connection Manager (PCM)",
        "# ==============================================================================",
        "",
    ]
    conteggio = 0

    for nome, dati in sorted(filtrati.items()):
        proto = dati.get("protocol", "ssh")
        if proto not in ("ssh", "sftp", "mosh"):
            continue

        host = (dati.get("host") or "").strip()
        if not host:
            continue

        # Alias SSH: rimuove caratteri non validi
        alias_clean = nome.replace(" ", "_").replace("/", "-")
        user = (dati.get("user") or "").strip()
        port = str(dati.get("port") or "22").strip()
        pkey = (dati.get("private_key") or "").strip()
        jump = (dati.get("jump_host") or "").strip()
        notes = (dati.get("notes") or "").strip()
        compress = dati.get("compression", False)
        keepalive = dati.get("keepalive", False)

        righe.append(f"Host {alias_clean}")
        if alias_clean != nome:
            righe.append(f"    # Nome PCM: {nome}")
        if notes:
            for n_line in notes.splitlines():
                if n_line.strip():
                    righe.append(f"    # {n_line.strip()}")

        righe.append(f"    HostName {host}")
        if user:
            righe.append(f"    User {user}")
        if port and port != "22":
            righe.append(f"    Port {port}")
        if pkey:
            righe.append(f"    IdentityFile {pkey}")
        if jump:
            jump_clean = jump.replace(" ", "_").replace("/", "-")
            righe.append(f"    ProxyJump {jump_clean}")
        if compress:
            righe.append("    Compression yes")
        if keepalive:
            righe.append("    ServerAliveInterval 30")
            righe.append("    ServerAliveCountMax 3")

        righe.append("")
        conteggio += 1

    return "\n".join(righe), conteggio


def esporta_csv(profili: dict, gruppo: str | None = None) -> tuple[str, int]:
    """
    Esporta le sessioni in formato CSV compatibile Excel / LibreOffice.
    Ritorna (testo_csv, conteggio_sessioni).
    """
    filtrati = _filtra_profili(profili, gruppo)
    output = io.StringIO()
    writer = csv.writer(output, dialect="excel")

    writer.writerow(["Nome", "Protocollo", "Host", "Porta", "Utente", "Gruppo", "Tag", "Note"])
    conteggio = 0

    for nome, dati in sorted(filtrati.items()):
        proto = dati.get("protocol", "ssh")
        host = dati.get("host", "")
        port = str(dati.get("port", ""))
        user = dati.get("user", "")
        grp = dati.get("group", "")
        tags_raw = dati.get("tags", [])
        if isinstance(tags_raw, list):
            tags_str = ", ".join(str(t).strip() for t in tags_raw if str(t).strip())
        else:
            tags_str = str(tags_raw).strip()
        notes = (dati.get("notes") or "").replace("\r\n", " ").replace("\n", " ").strip()

        writer.writerow([nome, proto, host, port, user, grp, tags_str, notes])
        conteggio += 1

    return output.getvalue(), conteggio


def esporta_json(profili: dict, gruppo: str | None = None, include_passwords: bool = False) -> tuple[str, int]:
    """
    Esporta le sessioni in formato JSON portabile (sanificato).
    Ritorna (testo_json, conteggio_sessioni).
    """
    filtrati = _filtra_profili(profili, gruppo)
    puliti = {}
    conteggio = 0

    for nome, dati in sorted(filtrati.items()):
        copia = dict(dati)
        # Rimuove chiavi di runtime e metadati interni
        copia.pop("_inherits_from", None)
        copia.pop("_sorgente", None)
        if not include_passwords:
            copia["password"] = ""
        puliti[nome] = copia
        conteggio += 1

    return json.dumps(puliti, indent=2, ensure_ascii=False), conteggio


def esporta_mremoteng(profili: dict, gruppo: str | None = None) -> tuple[str, int]:
    """
    Esporta le sessioni in formato mRemoteNG XML (confCons.xml).
    Organizza ricorsivamente le cartelle in base al gruppo.
    Ritorna (testo_xml, conteggio_sessioni).
    """
    filtrati = _filtra_profili(profili, gruppo)
    root = ET.Element("Connections")
    container_cache: dict[str, ET.Element] = {"": root}

    conteggio = 0
    for nome, dati in sorted(filtrati.items()):
        proto_pcm = dati.get("protocol", "ssh")
        proto_mrng = _PROTO_TO_MREMOTENG.get(proto_pcm, "SSH2")
        host = (dati.get("host") or "").strip()
        port = str(dati.get("port") or "22").strip()
        user = (dati.get("user") or "").strip()
        notes = (dati.get("notes") or "").strip()
        grp = (dati.get("group") or "").strip()

        # Risolvi gerarchia cartelle container
        parent_el = root
        if grp:
            parti = [p.strip() for p in grp.split("/") if p.strip()]
            path_accum = ""
            for p in parti:
                prev_accum = path_accum
                path_accum = f"{path_accum}/{p}" if path_accum else p
                if path_accum not in container_cache:
                    p_node = ET.SubElement(container_cache[prev_accum], "Node")
                    p_node.attrib["Name"] = p
                    p_node.attrib["Type"] = "Container"
                    p_node.attrib["Expanded"] = "True"
                    container_cache[path_accum] = p_node
            parent_el = container_cache[path_accum]

        conn_node = ET.SubElement(parent_el, "Node")
        conn_node.attrib["Name"] = nome
        conn_node.attrib["Type"] = "Connection"
        conn_node.attrib["Protocol"] = proto_mrng
        conn_node.attrib["Hostname"] = host
        conn_node.attrib["Port"] = port
        conn_node.attrib["Username"] = user
        conn_node.attrib["Description"] = notes

        if proto_pcm == "rdp":
            conn_node.attrib["Domain"] = dati.get("rdp_domain", "")
            conn_node.attrib["RedirectClipboard"] = "True" if dati.get("redirect_clipboard", True) else "False"
            conn_node.attrib["RedirectDrives"] = "True" if dati.get("redirect_drives", False) else "False"

        conteggio += 1

    # Formatta XML con indentazione
    ET.indent(root, space="  ", level=0)
    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml_str, conteggio


def esporta_su_file(contenuto: str, percorso: str | Path) -> None:
    """Scrive il contenuto esportato su disco con codifica UTF-8."""
    p = Path(percorso)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenuto, encoding="utf-8")
