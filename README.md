# PCM — Python Connection Manager

[![License](https://img.shields.io/badge/License-EUPL%201.2-blue.svg)](EUPL-1.2%20EN.txt)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Donate](https://img.shields.io/badge/Donate-PayPal-00457C.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

> Gestore grafico di connessioni remote per Linux, ispirato a MobaXterm.
> Scritto in Python, disponibile in due versioni: **GTK3** (sviluppo attivo) e **PyQt6** (manutenzione).

---

## Versioni disponibili

| Versione | Cartella | Framework | Terminale | Wayland | Stato |
|---|---|---|---|---|---|
| **GTK3** | [`gtk3/`](./gtk3/) | GTK3 (PyGObject) | VTE nativo | ✅ Nativo | **Sviluppo attivo** |
| PyQt6 | [`pyqt6/`](./pyqt6/) | PyQt6 | xterm | XWayland richiesto | Solo bugfix critici |

> **Versione in sviluppo: GTK3.** La versione GTK3 è quella attivamente sviluppata: nuove funzionalità, miglioramenti e allineamento alle feature sono concentrati qui. Il terminale nativo VTE garantisce rendering dei font perfetto e supporto Wayland nativo senza strati di compatibilità.
>
> **Versione PyQt6: manutenzione.** La versione PyQt6 riceve esclusivamente bugfix critici. Non sono previste nuove funzionalità. È consigliata per chi la usa già; le nuove installazioni dovrebbero preferire GTK3.

---

## Protocolli supportati

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Seriale · SSH Tunnel**

---

## Funzionalità principali

- **Sessioni organizzate per gruppo** con ricerca istantanea
- **Quick Connect** dalla toolbar — `utente@host:porta`
- **Cifratura credenziali** AES-256 (PBKDF2-SHA256, 480k iterazioni) con master password
- **Browser FTP/SFTP** dual-pane stile WinSCP con coda trasferimenti
- **SSH Tunnel** gestiti graficamente (SOCKS, locale, remoto)
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

## Screenshot — Versione GTK3 (sviluppo attivo)

### Dialogo nuova sessione — SSH

| | |
|---|---|
| ![SSH Connection GTK3](immagini/pcm41.png) | ![SSH Terminal GTK3](immagini/pcm42.png) |
| *Tab Connessione SSH — host, porta, utente, chiave privata, gestione chiavi SSH (genera ed25519/RSA, copia sul server, mostra pubblica)* | *Tab Terminale — tema, font, dimensione, log su file, incolla con tasto destro, modalità apertura SSH/SFTP* |

| | |
|---|---|
| ![SSH Advanced GTK3](immagini/pcm43.png) | ![SSH Tunnel tab GTK3](immagini/pcm44.png) |
| *Tab Avanzate — X11 forwarding, compressione, keepalive, strict host, browser SFTP automatico, startup command, jump host, FTP/FTPS (TLS, PASV), Wake-on-LAN, pre-comando locale* | *Tab Tunnel — configurazione SOCKS proxy (-D) o port forwarding direttamente nella sessione* |

---

### Dialogo nuova sessione — RDP

| | |
|---|---|
| ![RDP Connection GTK3](immagini/pcm46.png) | ![RDP Advanced GTK3](immagini/pcm47.png) |
| *Tab Connessione RDP — host, porta 3389, utente, password* | *Tab Avanzate RDP — client xfreerdp3, autenticazione NTLM/Kerberos, dominio, fullscreen, clipboard, cartelle locali, Wake-on-LAN, pre-comando locale* |

---

### Dialogo nuova sessione — VNC e Seriale

| | |
|---|---|
| ![VNC Advanced GTK3](immagini/pcm48.png) | ![Serial GTK3](immagini/pcm49.png) |
| *Tab Avanzate VNC — apertura con gtk-vnc integrato o client esterno, profondità colore, qualità, Wake-on-LAN, pre-comando locale* | *Connessione Seriale — device (/dev/ttyUSB0), baud rate, data bit, parity, stop bit* |

---

### SSH Tunnel Manager e sblocco credenziali

| | |
|---|---|
| ![SSH Tunnel Manager GTK3](immagini/pcm45.png) | ![Unlock Credentials GTK3](immagini/pcm40.png) |
| *SSH Tunnel Manager — elenco tunnel con tipo, host, porte, stato; pulsanti Add/Edit/Delete/Start/Stop; log output integrato* | *Sblocco credenziali — master password per decifrare le credenziali salvate (AES-256)* |

---

## Screenshot — Versione PyQt6 (manutenzione)

### Finestra principale e menu Tools

![PCM Main Window](immagini/pcm1.png)
*Finestra principale — sidebar con gruppi e sessioni, quick connect, benvenuto*

| | |
|---|---|
| ![Tools menu](immagini/pcm34.png) | ![Import submenu](immagini/pcm39.png) |
| *Menu Tools — Tunnel Manager, Multi-exec, variabili globali, server FTP locale, modalità protetta* | *Import da Remmina e Remote Desktop Manager (XML/JSON)* |

---

### Dialogo nuova sessione — SSH (PyQt6)

| | |
|---|---|
| ![SSH Connection](immagini/pcm20.png) | ![SSH Authentication](immagini/pcm21.png) |
| *Tab Connessione SSH — host, porta, utente, Wake-on-LAN integrato* | *Tab Autenticazione — password, chiave privata, generazione chiavi SSH, jump host (bastion)* |
| ![SSH Terminal](immagini/pcm22.png) | ![SSH Advanced](immagini/pcm23.png) |
| *Tab Terminale — tema, font, startup command, pre-cmd VPN, log su file, incolla con tasto destro* | *Tab Avanzate — X11 forwarding, compressione, keepalive, strict host, modalità apertura* |
| ![SSH Notes](immagini/pcm24.png) | ![SSH Macros](immagini/pcm25.png) |
| *Tab Note — annotazioni libere per sessione* | *Tab Macro — comandi a un clic, riordinabili* |

---

### Dialogo nuova sessione — FTP/FTPS (PyQt6)

| | |
|---|---|
| ![FTP Connection](immagini/pcm27.png) | ![FTP Advanced](immagini/pcm29.png) |
| *FTP/FTPS — TLS esplicito, modalità passiva PASV, nota informativa* | *Avanzate FTP — modalità apertura (browser interno/esterno, lftp CLI)* |

---

### Dialogo nuova sessione — RDP e Seriale (PyQt6)

| | |
|---|---|
| ![RDP Connection](immagini/pcm30.png) | ![RDP Auth](immagini/pcm31.png) |
| *RDP — client xfreerdp3, dominio, fullscreen, clipboard, cartelle locali, autenticazione NTLM/Kerberos, WoL* | *Autenticazione RDP — password Windows con visualizzazione toggle* |

![Serial Connection](immagini/pcm32.png)
*Connessione seriale — device, baud rate, data bit, parity, stop bit*

---

### Browser SFTP/FTP e strumenti (PyQt6)

![SFTP Browser](immagini/pcm11.png)
*Browser SFTP/FTP dual-pane — navigazione locale e remota con coda trasferimenti*

| | |
|---|---|
| ![SSH Tunnel Manager](immagini/pcm37.png) | ![Local FTP Server](immagini/pcm36.png) |
| *SSH Tunnel Manager — SOCKS proxy, port forwarding locale/remoto, avvio/arresto per tunnel* | *Server FTP locale — gestione utenti, permessi granulari, log connessioni* |

---

## Installazione rapida (GTK3 — versione raccomandata)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/gtk3
bash ../setup.sh       # installa automaticamente per Debian/Ubuntu/Arch/Fedora/FreeBSD
python3 PCM.py
```

> Lo script `setup.sh` rileva la distribuzione e installa le dipendenze di sistema (GTK3, VTE, gtk-vnc) e Python (paramiko, cryptography, pyftpdlib). Crea anche un lanciatore `.desktop` nel menu applicazioni.

### Installazione PyQt6 (manutenzione)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/pyqt6
pip install PyQt6
python3 PCM.py
```

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
> Written in Python, available in two versions: **GTK3** (active development) and **PyQt6** (maintenance).

---

## Available versions

| Version | Folder | Framework | Terminal | Wayland | Status |
|---|---|---|---|---|---|
| **GTK3** | [`gtk3/`](./gtk3/) | GTK3 (PyGObject) | Native VTE | ✅ Native | **Active development** |
| PyQt6 | [`pyqt6/`](./pyqt6/) | PyQt6 | xterm | XWayland required | Critical bugfixes only |

> **Active development: GTK3.** The GTK3 version is where all new features and improvements are concentrated. The native VTE terminal delivers perfect font rendering and full Wayland support with no compatibility layers.
>
> **PyQt6: maintenance only.** The PyQt6 version receives critical bugfixes only. No new features are planned. Existing users can stay on it; new installations should prefer GTK3.

---

## Supported protocols

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Serial · SSH Tunnel**

---

## Key features

- **Sessions organized by group** with instant search
- **Quick Connect** from toolbar — `user@host:port`
- **Credential encryption** AES-256 (PBKDF2-SHA256, 480k iterations) with master password
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

## Screenshots — GTK3 version (active development)

### New session dialog — SSH

| | |
|---|---|
| ![SSH Connection GTK3](immagini/pcm41.png) | ![SSH Terminal GTK3](immagini/pcm42.png) |
| *Connection tab — host, port, user, private key, SSH key management (generate ed25519/RSA, copy to server, show public key)* | *Terminal tab — theme, font, size, file logging, paste with right-click, SSH/SFTP open mode* |

| | |
|---|---|
| ![SSH Advanced GTK3](immagini/pcm43.png) | ![SSH Tunnel tab GTK3](immagini/pcm44.png) |
| *Advanced tab — X11 forwarding, compression, keepalive, strict host, auto-open SFTP browser, startup command, jump host, FTP/FTPS (TLS, PASV), Wake-on-LAN, local pre-command* | *Tunnel tab — SOCKS proxy (-D) or port forwarding configured directly inside the session* |

---

### New session dialog — RDP

| | |
|---|---|
| ![RDP Connection GTK3](immagini/pcm46.png) | ![RDP Advanced GTK3](immagini/pcm47.png) |
| *Connection tab — host, port 3389, user, password* | *Advanced tab — xfreerdp3 client, NTLM/Kerberos auth, domain, fullscreen, clipboard, local folders, Wake-on-LAN, local pre-command* |

---

### New session dialog — VNC and Serial

| | |
|---|---|
| ![VNC Advanced GTK3](immagini/pcm48.png) | ![Serial GTK3](immagini/pcm49.png) |
| *VNC Advanced tab — open with embedded gtk-vnc or external client, color depth, quality, Wake-on-LAN, local pre-command* | *Serial connection — device (/dev/ttyUSB0), baud rate, data bits, parity, stop bits* |

---

### SSH Tunnel Manager and credential unlock

| | |
|---|---|
| ![SSH Tunnel Manager GTK3](immagini/pcm45.png) | ![Unlock Credentials GTK3](immagini/pcm40.png) |
| *SSH Tunnel Manager — tunnel list with type, host, ports, status; Add/Edit/Delete/Start/Stop buttons; integrated output log* | *Credential unlock — master password to decrypt saved credentials (AES-256)* |

---

## Screenshots — PyQt6 version (maintenance)

### Main window and Tools menu

![PCM Main Window](immagini/pcm1.png)
*Main window — session sidebar with groups, quick connect, welcome panel*

| | |
|---|---|
| ![Tools menu](immagini/pcm34.png) | ![Import submenu](immagini/pcm39.png) |
| *Tools menu — Tunnel Manager, Multi-exec, global variables, local FTP server, protected mode* | *Import from Remmina and Remote Desktop Manager (XML/JSON)* |

---

### New session dialog — SSH (PyQt6)

| | |
|---|---|
| ![SSH Connection](immagini/pcm20.png) | ![SSH Authentication](immagini/pcm21.png) |
| *Connection tab — host, port, user, integrated Wake-on-LAN* | *Authentication tab — password, private key, SSH key generation, jump host (bastion)* |
| ![SSH Terminal](immagini/pcm22.png) | ![SSH Advanced](immagini/pcm23.png) |
| *Terminal tab — theme, font, startup command, VPN pre-cmd, file logging, paste with right-click* | *Advanced tab — X11 forwarding, compression, keepalive, strict host, open mode* |
| ![SSH Notes](immagini/pcm24.png) | ![SSH Macros](immagini/pcm25.png) |
| *Notes tab — free-form notes per session* | *Macros tab — one-click commands, reorderable* |

---

### New session dialog — FTP/FTPS (PyQt6)

| | |
|---|---|
| ![FTP Connection](immagini/pcm27.png) | ![FTP Advanced](immagini/pcm29.png) |
| *FTP/FTPS — explicit TLS, PASV passive mode, informational note* | *FTP Advanced — open mode (internal browser, external, lftp CLI)* |

---

### New session dialog — RDP and Serial (PyQt6)

| | |
|---|---|
| ![RDP Connection](immagini/pcm30.png) | ![RDP Auth](immagini/pcm31.png) |
| *RDP — xfreerdp3 client, domain, fullscreen, clipboard, local folders, NTLM/Kerberos auth, WoL* | *RDP Authentication — Windows password with show/hide toggle* |

![Serial Connection](immagini/pcm32.png)
*Serial connection — device, baud rate, data bits, parity, stop bits*

---

### SFTP/FTP browser and tools (PyQt6)

![SFTP Browser](immagini/pcm11.png)
*SFTP/FTP dual-pane browser — local and remote navigation with transfer queue*

| | |
|---|---|
| ![SSH Tunnel Manager](immagini/pcm37.png) | ![Local FTP Server](immagini/pcm36.png) |
| *SSH Tunnel Manager — SOCKS proxy, local/remote port forwarding, per-tunnel start/stop* | *Local FTP server — user management, granular permissions, connection log* |

---

## Quick install (GTK3 — recommended)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/gtk3
bash ../setup.sh       # automatically installs for Debian/Ubuntu/Arch/Fedora/FreeBSD
python3 PCM.py
```

> The `setup.sh` script detects the distribution and installs system dependencies (GTK3, VTE, gtk-vnc) and Python packages (paramiko, cryptography, pyftpdlib). It also creates a `.desktop` launcher in the application menu.

### PyQt6 install (maintenance)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/pyqt6
pip install PyQt6
python3 PCM.py
```

---

## Support the project

If you find PCM useful and want to thank the developer, you can buy him a coffee via PayPal. Any contribution is greatly appreciated and helps keep the project alive!

[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

*Thank you so much!*

---

## Author

**Andres Zanzani** — license [EUPL-1.2](EUPL-1.2%20EN.txt)

[![GitHub](https://img.shields.io/badge/GitHub-buzzqw%2FPython__Connection__Manager-blue?logo=github)](https://github.com/buzzqw/Python_Connection_Manager)
