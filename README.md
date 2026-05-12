# PCM — Python Connection Manager

[![License](https://img.shields.io/badge/License-EUPL%201.2-blue.svg)](EUPL-1.2%20EN.txt)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Donate](https://img.shields.io/badge/Donate-PayPal-00457C.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

> Gestore grafico di connessioni remote per Linux, ispirato a MobaXterm.
> Scritto in Python, disponibile in due versioni: **PyQt6** (attiva) e **GTK3** (stabile/manutenzione).

---

![PCM Main Window](immagini/pcm1.png)
*Schermata principale — sidebar sessioni con tutti i protocolli, quick connect, schermata di benvenuto*

---

## Versioni disponibili

| Versione | Cartella | Framework | Terminale | Wayland | Stato |
|---|---|---|---|---|---|
| **PyQt6** | [`pyqt6/`](./pyqt6/) | PyQt6 | xterm | XWayland richiesto | **Sviluppo attivo** |
| GTK3 | [`gtk3/`](./gtk3/) | GTK3 (PyGObject) | VTE nativo | ✅ Nativo | Stabile — solo bugfix critici |

> **Nota sulla versione GTK3**: la versione GTK3 è considerata **stabile e completa**. Non è previsto ulteriore sviluppo di nuove funzionalità; verranno applicati esclusivamente bugfix critici. La versione **PyQt6** è quella attivamente sviluppata e raccomandata per nuove installazioni.

---

## Protocolli supportati

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Seriale · SSH Tunnel**

---

## Funzionalità principali

- **Sessioni organizzate per gruppo** con ricerca istantanea
- **Quick Connect** dalla toolbar — `utente@host:porta`
- **Cifratura credenziali** AES-256 (PBKDF2-SHA256, 480k iterazioni)
- **Browser FTP/SFTP** dual-pane stile WinSCP con coda trasferimenti
- **Tunnel SSH** gestiti graficamente (SOCKS, locale, remoto)
- **Split terminale** verticale/orizzontale — più sessioni in parallelo
- **Macro per sessione** e **Multi-exec** su più server contemporaneamente
- **Wake-on-LAN** integrato prima della connessione
- **Import** da Remmina e Remote Desktop Manager
- **Gestione chiavi SSH**: genera, copia sul server, mostra chiave pubblica
- **Jump Host (Bastion)** con supporto trasparente `ssh -J`
- **Pre-comando locale** (es. `wg-quick up vpn0`) prima della connessione
- **Server FTP locale** integrato (pyftpdlib) con gestione utenti e permessi
- **Modalità protetta** — nasconde le password nell'interfaccia
- **5 lingue**: Italiano · English · Deutsch · Français · Español

---

## Screenshot — Versione PyQt6

### Finestra principale e menu Tools

![PCM Main Window](immagini/pcm1.png)
*Finestra principale — sidebar con gruppi e sessioni, quick connect, benvenuto*

| | |
|---|---|
| ![Tools menu](immagini/pcm34.png) | ![Import submenu](immagini/pcm39.png) |
| *Menu Tools — Tunnel Manager, Multi-exec, variabili globali, server FTP locale, modalità protetta* | *Import da Remmina e Remote Desktop Manager (XML/JSON)* |

---

### Dialogo nuova sessione — SSH

| | |
|---|---|
| ![SSH Connection](immagini/pcm20.png) | ![SSH Authentication](immagini/pcm21.png) |
| *Tab Connessione SSH — host, porta, utente, Wake-on-LAN integrato* | *Tab Autenticazione — password, chiave privata, generazione chiavi SSH, jump host (bastion)* |
| ![SSH Terminal](immagini/pcm22.png) | ![SSH Advanced](immagini/pcm23.png) |
| *Tab Terminale — tema, font, startup command, pre-cmd VPN, log su file, incolla con tasto destro* | *Tab Avanzate — X11 forwarding, compressione, keepalive, strict host, modalità apertura* |
| ![SSH Notes](immagini/pcm24.png) | ![SSH Macros](immagini/pcm25.png) |
| *Tab Note — annotazioni libere per sessione* | *Tab Macro — comandi a un clic, riordinabili, con Add/Update/Delete* |

---

### Dialogo nuova sessione — FTP/FTPS

| | |
|---|---|
| ![FTP Connection](immagini/pcm27.png) | ![FTP Advanced](immagini/pcm29.png) |
| *FTP/FTPS — TLS esplicito, modalità passiva PASV, nota informativa* | *Avanzate FTP — modalità apertura (browser interno/esterno, lftp CLI)* |

---

### Dialogo nuova sessione — RDP

| | |
|---|---|
| ![RDP Connection](immagini/pcm30.png) | ![RDP Auth](immagini/pcm31.png) |
| *RDP — client xfreerdp3, dominio, fullscreen, clipboard, cartelle locali, autenticazione NTLM/Kerberos, WoL* | *Autenticazione RDP — password Windows con visualizzazione toggle* |

---

### Dialogo nuova sessione — Seriale

![Serial Connection](immagini/pcm32.png)
*Connessione seriale — device, baud rate, data bit, parity, stop bit*

---

### Browser SFTP/FTP e strumenti

![SFTP Browser](immagini/pcm11.png)
*Browser SFTP/FTP dual-pane — navigazione locale e remota con coda trasferimenti*

| | |
|---|---|
| ![SSH Tunnel Manager](immagini/pcm37.png) | ![Local FTP Server](immagini/pcm36.png) |
| *SSH Tunnel Manager — SOCKS proxy, port forwarding locale/remoto, avvio/arresto per tunnel* | *Server FTP locale — gestione utenti, permessi granulari, log connessioni* |

---

## Installazione rapida (PyQt6)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/pyqt6
pip install PyQt6
python3 PCM.py
```

### Installazione GTK3 (stabile)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/gtk3
bash setup.sh          # installa automaticamente con uv per Debian/Ubuntu/Arch/Fedora/openSUSE
python3 PCM.py
```

> Il progetto GTK3 utilizza [**uv**](https://github.com/astral-sh/uv) come gestore di pacchetti Python. Lo script `setup.sh` installa automaticamente uv e crea un ambiente virtuale ottimizzato.

---

## Supporta il progetto

Se PCM ti è utile e vuoi ringraziare lo sviluppatore, puoi offrire un caffè tramite PayPal. Ogni contributo è molto apprezzato e aiuta a mantenere il progetto attivo!

[![Dona con PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

*Grazie mille!*

---

## Autore

**Andres Zanzani** — licenza [EUPL-1.2](EUPL-1.2%20EN.txt)

[![GitHub](https://img.shields.io/badge/GitHub-buzzqw%2FPython__Connection__Manager-blue?logo=github)](https://github.com/buzzqw/Python_Connection_Manager)

---
---

# PCM — Python Connection Manager 🇬🇧

> Graphical remote connection manager for Linux, inspired by MobaXterm.
> Written in Python, available in two versions: **PyQt6** (active) and **GTK3** (stable/maintenance).

---

![PCM Main Window](immagini/pcm1.png)
*Main window — session sidebar with all protocols, quick connect, welcome screen*

---

## Available versions

| Version | Folder | Framework | Terminal | Wayland | Status |
|---|---|---|---|---|---|
| **PyQt6** | [`pyqt6/`](./pyqt6/) | PyQt6 | xterm | XWayland required | **Active development** |
| GTK3 | [`gtk3/`](./gtk3/) | GTK3 (PyGObject) | Native VTE | ✅ Native | Stable — critical bugfixes only |

> **Note on the GTK3 version**: the GTK3 version is considered **stable and feature-complete**. No new features are planned; only critical bugfixes will be applied. The **PyQt6** version is the actively developed one and is recommended for new installations.

---

## Supported protocols

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Serial · SSH Tunnel**

---

## Key features

- **Sessions organized by group** with instant search
- **Quick Connect** from toolbar — `user@host:port`
- **Credential encryption** AES-256 (PBKDF2-SHA256, 480k iterations)
- **FTP/SFTP dual-pane browser** WinSCP-style with transfer queue
- **SSH Tunnels** managed graphically (SOCKS, local, remote)
- **Split terminal** vertical/horizontal — multiple sessions in parallel
- **Per-session macros** and **Multi-exec** on multiple servers simultaneously
- **Wake-on-LAN** integrated before connection
- **Import** from Remmina and Remote Desktop Manager
- **SSH key management**: generate, copy to server, show public key
- **Jump Host (Bastion)** with transparent `ssh -J` support
- **Local pre-command** (e.g. `wg-quick up vpn0`) before connecting
- **Integrated local FTP server** (pyftpdlib) with user management and permissions
- **Protected mode** — hides passwords in the UI
- **5 languages**: Italiano · English · Deutsch · Français · Español

---

## Screenshots — PyQt6 version

### Main window and Tools menu

![PCM Main Window](immagini/pcm1.png)
*Main window — session sidebar with groups, quick connect, welcome panel*

| | |
|---|---|
| ![Tools menu](immagini/pcm34.png) | ![Import submenu](immagini/pcm39.png) |
| *Tools menu — Tunnel Manager, Multi-exec, global variables, local FTP server, protected mode* | *Import from Remmina and Remote Desktop Manager (XML/JSON)* |

---

### New session dialog — SSH

| | |
|---|---|
| ![SSH Connection](immagini/pcm20.png) | ![SSH Authentication](immagini/pcm21.png) |
| *Connection tab — host, port, user, integrated Wake-on-LAN* | *Authentication tab — password, private key, SSH key generation, jump host (bastion)* |
| ![SSH Terminal](immagini/pcm22.png) | ![SSH Advanced](immagini/pcm23.png) |
| *Terminal tab — theme, font, startup command, VPN pre-cmd, file logging, paste with right-click* | *Advanced tab — X11 forwarding, compression, keepalive, strict host, open mode* |
| ![SSH Notes](immagini/pcm24.png) | ![SSH Macros](immagini/pcm25.png) |
| *Notes tab — free-form notes per session* | *Macros tab — one-click commands, reorderable, with Add/Update/Delete* |

---

### New session dialog — FTP/FTPS

| | |
|---|---|
| ![FTP Connection](immagini/pcm27.png) | ![FTP Advanced](immagini/pcm29.png) |
| *FTP/FTPS — explicit TLS, PASV passive mode, informational note* | *FTP Advanced — open mode (internal browser, external, lftp CLI)* |

---

### New session dialog — RDP

| | |
|---|---|
| ![RDP Connection](immagini/pcm30.png) | ![RDP Auth](immagini/pcm31.png) |
| *RDP — xfreerdp3 client, domain, fullscreen, clipboard, local folders, NTLM/Kerberos auth, WoL* | *RDP Authentication — Windows password with show/hide toggle* |

---

### New session dialog — Serial

![Serial Connection](immagini/pcm32.png)
*Serial connection — device, baud rate, data bits, parity, stop bits*

---

### SFTP/FTP browser and tools

![SFTP Browser](immagini/pcm11.png)
*SFTP/FTP dual-pane browser — local and remote navigation with transfer queue*

| | |
|---|---|
| ![SSH Tunnel Manager](immagini/pcm37.png) | ![Local FTP Server](immagini/pcm36.png) |
| *SSH Tunnel Manager — SOCKS proxy, local/remote port forwarding, per-tunnel start/stop* | *Local FTP server — user management, granular permissions, connection log* |

---

## Quick install (PyQt6)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/pyqt6
pip install PyQt6
python3 PCM.py
```

### GTK3 install (stable)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/gtk3
bash setup.sh          # automatically installs with uv for Debian/Ubuntu/Arch/Fedora/openSUSE
python3 PCM.py
```

> The GTK3 project uses [**uv**](https://github.com/astral-sh/uv) as a modern Python package manager. The `setup.sh` script automatically installs uv and creates an optimized virtual environment.

---

## Support the project

If you find PCM useful and want to thank the developer, you can buy him a coffee via PayPal. Any contribution is greatly appreciated and helps keep the project alive!

[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

*Thank you so much!*

---

## Author

**Andres Zanzani** — license [EUPL-1.2](EUPL-1.2%20EN.txt)

[![GitHub](https://img.shields.io/badge/GitHub-buzzqw%2FPython__Connection__Manager-blue?logo=github)](https://github.com/buzzqw/Python_Connection_Manager)
