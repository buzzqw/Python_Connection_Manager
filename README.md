# PCM — Python Connection Manager

[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](EUPL-1.2%20EN.txt)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GTK3](https://img.shields.io/badge/UI-GTK3-green.svg)](https://docs.gtk.org/gtk3/)
[![Wayland](https://img.shields.io/badge/Wayland-nativo-purple.svg)](#note-wayland)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20FreeBSD-lightgrey.svg)](#installazione)
[![Donate](https://img.shields.io/badge/Donate-PayPal-00457C.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

> **L'alternativa Linux a MobaXterm** — tutto in una finestra: SSH, RDP, VNC, SFTP, FTP, Telnet, Mosh, Seriale.  
> Scritto in Python con GTK3 e terminale VTE nativo. Funziona su **X11 e Wayland** senza XWayland.

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

## Perché PCM?

| | PCM | Remmina | mRemoteNG |
|---|---|---|---|
| SSH con terminale integrato | ✅ VTE nativo | ❌ solo RDP/VNC | ✅ |
| RDP + VNC + SSH + FTP in un tool | ✅ | parziale | ✅ |
| Browser SFTP/FTP integrato | ✅ dual-pane | ❌ | ❌ |
| Tunnel SSH grafici | ✅ | ❌ | ❌ |
| Broadcast a più terminali | ✅ | ❌ | ❌ |
| KeePassXC integrato | ✅ | ❌ | ❌ |
| Wayland nativo (no XWayland) | ✅ | parziale | ❌ Linux |
| Password MAI sulla command line | ✅ feed_child | ❌ | — |
| Configurazione in JSON leggibile | ✅ | XML complesso | XML |
| Licenza | EUPL-1.2 | GPL-2 | GPL-2 |

---

## Protocolli supportati

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Seriale · Exec · SSH Tunnel**

---

## Funzionalità principali

### 🖥 Protocolli — tutto in una finestra

| Protocollo | Come si apre | Punti di forza |
|---|---|---|
| **SSH** | Tab VTE interno o terminale esterno | Jump Host, X11, Agent Forward, pre-cmd VPN, macro |
| **SFTP** | Browser dual-pane integrato | Drag & drop, coda trasferimenti, rinomina |
| **FTP / FTPS** | Browser integrato o file manager | TLS esplicito, modalità PASV |
| **RDP** | Pannello interno o finestra esterna | xfreerdp3/xfreerdp/rdesktop, multi-monitor |
| **VNC** | gtk-vnc nativo o client esterno | Scala, grab input, screenshot |
| **Telnet** | Tab VTE interno | — |
| **Mosh** | Tab VTE interno | Resistente a disconnessioni |
| **Seriale** | Tab VTE interno | Baud, parità, stop bit configurabili |
| **Exec** | Tab VTE interno | Qualsiasi comando shell in una scheda |
| **SSH Tunnel** | Background gestito graficamente | SOCKS -D, locale -L, remoto -R |

### 🔐 Sicurezza — sopra la media

- **Password mai sulla command line**: PCM digita la password nel terminale VTE quando il server la richiede (`feed_child`), come farebbe un utente. Nessun `sshpass`, nessun argomento visibile in `ps aux`.
- **Fallback SSH_ASKPASS** per OpenSSH ≥ 8.4: se SSH gestisce l'auth prima che appaia un prompt (keyboard-interactive), uno script helper temp mode `0700` passa la password silenziosamente.
- **Cifratura AES-256** (Fernet + PBKDF2-SHA256, 480k iterazioni): utenti e password in `connections.json` cifrati con password master. La chiave non tocca mai il disco.
- **KeePassXC integrato** via Browser Protocol v2 (NaCl box): cerca e compila credenziali direttamente dal database KeePassXC aperto — nessun browser necessario.
- **Modalità protetta**: nasconde tutte le password nell'interfaccia.
- **Gestione chiavi SSH**: genera, copia sul server, visualizza la chiave pubblica.
- **Agent Forwarding** (`-A`): propaga le chiavi ssh-agent per hop multipli senza copiare le chiavi private.

### 💻 Terminale avanzato

- **VTE nativo** — zero dipendenze X11, funziona su Wayland puro
- **Split verticale/orizzontale** — più sessioni affiancate nella stessa finestra
- **Temi**: Dracula, Nord, Gruvbox, Solarized Dark/Light, One Dark, Monokai, Cobalt, Tomorrow Night e altri
- **Macro per sessione** — comandi inviati con un clic dalla sidebar
- **Broadcast terminali** — invia lo stesso testo a tutti i terminali selezionati contemporaneamente (ideale per cluster)
- **Multi-exec** — esegui un comando su più sessioni in sequenza
- Log output su file per ogni sessione (con `script(1)`)
- Scrollback configurabile o infinito per sessione
- Pre-comando locale: attiva VPN o monta volume prima di aprire la connessione

### 📁 Gestione sessioni

- Organizzate per **gruppo** con barra di ricerca live
- **Sezione Recenti** in cima alla sidebar: ultime 20 sessioni con timestamp
- **Quick Connect**: `utente@host:porta` dalla toolbar — si connette senza salvare un profilo
- Doppio clic per connettere, tasto destro per menu contestuale ricco
- **Ping TCP** dalla sidebar — verifica raggiungibilità sulla porta configurata (ms)
- Duplica, modifica, elimina, esporta script `.sh` per riaprire da terminale
- **Import** da: Remmina (`.remmina`), Remote Desktop Manager (`.rdm`/`.json`), PuTTY (`~/.putty/sessions/`), `~/.ssh/config`

### 🛠 Strumenti integrati

- **Tunnel SSH** grafici — avvia, ferma, monitora tunnel in background
- **Server FTP locale** (pyftpdlib) — espone una cartella locale via FTP/FTPS in un clic
- **Variabili globali** `{NOME}` — riutilizzabili nei comandi di tutte le sessioni
- **Wake-on-LAN** — invia magic packet prima di connettersi
- **Audit log** — storico connessioni con timestamp, durata, protocollo, stato; esportabile CSV
- **Verifica dipendenze** — controlla automaticamente quali tool sono installati

### 🌍 Internazionalizzazione

5 lingue complete: 🇮🇹 Italiano · 🇬🇧 English · 🇩🇪 Deutsch · 🇫🇷 Français · 🇪🇸 Español  
Cambio lingua immediato dalle impostazioni senza riavvio.

---

## Screenshot — Versione GTK3 (sviluppo attivo)

<table>
<tr>
<td><img src="immagini/pcm1.png" width="380"/><br><em>Finestra principale: sidebar gruppi, sezione Recenti, quick connect</em></td>
<td><img src="immagini/pcm2.png" width="380"/><br><em>Sessione SSH: host, porta, WoL integrato, pulsante KeePassXC</em></td>
</tr>
<tr>
<td><img src="immagini/pcm3.png" width="380"/><br><em>Autenticazione avanzata: chiavi SSH, Jump Host, Agent Forwarding</em></td>
<td><img src="immagini/pcm4.png" width="380"/><br><em>Browser SFTP dual-pane integrato — stile WinSCP</em></td>
</tr>
<tr>
<td><img src="immagini/pcm6.png" width="380"/><br><em>Sessione RDP: multi-monitor, clipboard, client selezionabile</em></td>
<td><img src="immagini/pcm10.png" width="380"/><br><em>Browser FTP/FTPS dual-pane con coda trasferimenti</em></td>
</tr>
</table>

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

### Menu Tools e import

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

## Installazione

### GTK3 — versione raccomandata

#### Automatica

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager
bash setup.sh
```

Lo script rileva la distribuzione (Debian/Ubuntu, Arch, Fedora, openSUSE, FreeBSD) e installa tutte le dipendenze di sistema e Python. Crea anche un launcher `.desktop` nel menu applicazioni.

```bash
# Solo verifica dipendenze, senza installare:
bash setup.sh --check
```

#### Avvio

```bash
cd Python_Connection_Manager/gtk3
python3 PCM.py
```

Al primo avvio PCM crea `connections.json` con sessioni di esempio e propone di abilitare la cifratura AES-256 delle credenziali.

#### Manuale per distribuzione

<details>
<summary><b>Debian / Ubuntu / Linux Mint</b></summary>

```bash
sudo apt install \
    python3 python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-vte-2.91 gir1.2-gtkvnc-2.0 \
    openssh-client freerdp3-x11 tigervnc-viewer \
    xdotool xdg-utils wakeonlan

pip install --user cryptography paramiko pyftpdlib
```
</details>

<details>
<summary><b>Arch Linux</b></summary>

```bash
sudo pacman -Sy --needed \
    python python-gobject gtk3 vte3 gtk-vnc \
    openssh freerdp tigervnc xdotool xdg-utils wol \
    python-cryptography python-paramiko python-pyftpdlib
```
</details>

<details>
<summary><b>Fedora</b></summary>

```bash
sudo dnf install \
    python3-gobject gtk3 vte291 gtk-vnc2 \
    openssh-clients freerdp tigervnc xdotool xdg-utils

pip install --user cryptography paramiko pyftpdlib
```
</details>

<details>
<summary><b>openSUSE</b></summary>

```bash
sudo zypper install \
    python3-gobject typelib-1_0-Gtk-3_0 \
    typelib-1_0-Vte-2.91 typelib-1_0-GtkVnc-2_0 \
    openssh freerdp tigervnc xdotool xdg-utils

pip install --user cryptography paramiko pyftpdlib
```
</details>

<details>
<summary><b>FreeBSD</b></summary>

```bash
sudo pkg install \
    python3 py311-gobject gtk3 vte3 gtk-vnc \
    mosh freerdp3 tigervnc-viewer xdotool wakeonlan \
    py311-cryptography py311-paramiko py311-pyftpdlib
```
</details>

### PyQt6 — versione manutenzione

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/pyqt6
pip install PyQt6
python3 PCM.py
```

---

## Dipendenze opzionali

| Pacchetto | Funzionalità abilitata |
|---|---|
| `gir1.2-gtkvnc-2.0` / `gtk-vnc` | VNC integrato nativo (raccomandato) |
| `tigervnc-viewer` / `xtightvncviewer` | VNC via client esterno (fallback) |
| `freerdp3-x11` / `xfreerdp` | RDP |
| `mosh` | Connessioni Mosh |
| `picocom` / `minicom` | Porte seriali |
| `xdotool` | RDP in pannello interno (richiede XWayland) |
| `wakeonlan` / `wol` | Wake-on-LAN |
| `keepassxc` | Integrazione KeePassXC |
| `pynacl` | Cifratura protocollo KeePassXC Browser v2 |

---

## Note Wayland

GTK3 + VTE funzionano **nativamente su Wayland** senza XWayland.

L'unica eccezione è la modalità **RDP pannello interno** (embedding xfreerdp tramite xdotool) che richiede XWayland. Per uso Wayland puro, impostare RDP su **"Finestra esterna"**.

Il viewer VNC `gtk-vnc` funziona nativamente su Wayland.

---

## File di configurazione

| File | Contenuto |
|---|---|
| `gtk3/connections.json` | Profili sessione — JSON leggibile, modificabile a mano |
| `gtk3/pcm_settings.json` | Impostazioni globali, scorciatoie, sessioni recenti |
| `gtk3/audit_log.json` | Log audit connessioni (solo metadata, nessuna credenziale) |
| `/tmp/pcm_logs/` | Log output terminali, percorso configurabile |

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

> **The Linux alternative to MobaXterm** — everything in one window: SSH, RDP, VNC, SFTP, FTP, Telnet, Mosh, Serial.  
> Written in Python with GTK3 and native VTE terminal. Works on **X11 and Wayland** without XWayland.

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

## Why PCM?

| | PCM | Remmina | mRemoteNG |
|---|---|---|---|
| SSH with integrated terminal | ✅ Native VTE | ❌ RDP/VNC only | ✅ |
| RDP + VNC + SSH + FTP in one tool | ✅ | partial | ✅ |
| Integrated SFTP/FTP browser | ✅ dual-pane | ❌ | ❌ |
| Graphical SSH tunnels | ✅ | ❌ | ❌ |
| Broadcast to multiple terminals | ✅ | ❌ | ❌ |
| KeePassXC integration | ✅ | ❌ | ❌ |
| Native Wayland (no XWayland) | ✅ | partial | ❌ Linux |
| Password NEVER on command line | ✅ feed_child | ❌ | — |
| Human-readable JSON config | ✅ | complex XML | XML |
| License | EUPL-1.2 | GPL-2 | GPL-2 |

---

## Supported protocols

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Serial · Exec · SSH Tunnel**

---

## Key features

### 🖥 Protocols — everything in one window

| Protocol | How it opens | Strengths |
|---|---|---|
| **SSH** | Internal VTE tab or external terminal | Jump Host, X11, Agent Forward, VPN pre-cmd, macros |
| **SFTP** | Integrated dual-pane browser | Drag & drop, transfer queue, rename |
| **FTP / FTPS** | Integrated browser or file manager | Explicit TLS, PASV mode |
| **RDP** | Internal panel or external window | xfreerdp3/xfreerdp/rdesktop, multi-monitor |
| **VNC** | Native gtk-vnc or external client | Scale, grab input, screenshot |
| **Telnet** | Internal VTE tab | — |
| **Mosh** | Internal VTE tab | Resilient to disconnections |
| **Serial** | Internal VTE tab | Baud, parity, stop bits configurable |
| **Exec** | Internal VTE tab | Any shell command in a tab |
| **SSH Tunnel** | Background, managed graphically | SOCKS -D, local -L, remote -R |

### 🔐 Security — above average

- **Password never on command line**: PCM types the password into the VTE terminal when the server asks for it (`feed_child`), just like a user would. No `sshpass`, nothing visible in `ps aux`.
- **SSH_ASKPASS fallback** for OpenSSH ≥ 8.4: if SSH handles auth before a prompt appears (keyboard-interactive), a temp helper script (mode `0700`) passes the password silently.
- **AES-256 encryption** (Fernet + PBKDF2-SHA256, 480k iterations): usernames and passwords in `connections.json` encrypted with a master password. The key never touches the disk.
- **KeePassXC integration** via Browser Protocol v2 (NaCl box): find and fill credentials directly from the open KeePassXC database — no browser needed.
- **Protected mode**: hides all passwords in the interface.
- **SSH key management**: generate, copy to server, display public key.
- **Agent Forwarding** (`-A`): propagates ssh-agent keys for multiple hops without copying private keys.

### 💻 Advanced terminal

- **Native VTE** — zero X11 dependencies, works on pure Wayland
- **Vertical/horizontal split** — multiple sessions side by side in one window
- **Themes**: Dracula, Nord, Gruvbox, Solarized Dark/Light, One Dark, Monokai, Cobalt, Tomorrow Night and more
- **Per-session macros** — commands sent with one click from the sidebar
- **Terminal broadcast** — send the same text to all selected terminals simultaneously (ideal for clusters)
- **Multi-exec** — run a command across multiple sessions in sequence
- File output logging per session (via `script(1)`)
- Configurable or infinite scrollback per session
- Local pre-command: activate VPN or mount volume before opening the connection

### 📁 Session management

- Organized by **group** with live search bar
- **Recent sessions** section at the top of the sidebar: last 20 sessions with timestamps
- **Quick Connect**: `user@host:port` from the toolbar — connects without saving a profile
- Double-click to connect, right-click for rich context menu
- **TCP Ping** from the sidebar — checks reachability on the configured port (ms)
- Duplicate, edit, delete, export `.sh` script to reopen from terminal
- **Import** from: Remmina (`.remmina`), Remote Desktop Manager (`.rdm`/`.json`), PuTTY (`~/.putty/sessions/`), `~/.ssh/config`

### 🛠 Integrated tools

- **Graphical SSH tunnels** — start, stop, monitor background tunnels
- **Local FTP server** (pyftpdlib) — expose a local folder via FTP/FTPS in one click
- **Global variables** `{NAME}` — reusable in commands across all sessions
- **Wake-on-LAN** — sends magic packet before connecting
- **Audit log** — connection history with timestamp, duration, protocol, status; exportable to CSV
- **Dependency checker** — automatically checks which tools are installed

### 🌍 Internationalization

5 complete languages: 🇮🇹 Italiano · 🇬🇧 English · 🇩🇪 Deutsch · 🇫🇷 Français · 🇪🇸 Español  
Instant language change from settings without restart.

---

## Screenshots — GTK3 version (active development)

<table>
<tr>
<td><img src="immagini/pcm1.png" width="380"/><br><em>Main window: group sidebar, Recent section, quick connect</em></td>
<td><img src="immagini/pcm2.png" width="380"/><br><em>SSH session: host, port, integrated WoL, KeePassXC button</em></td>
</tr>
<tr>
<td><img src="immagini/pcm3.png" width="380"/><br><em>Advanced authentication: SSH keys, Jump Host, Agent Forwarding</em></td>
<td><img src="immagini/pcm4.png" width="380"/><br><em>Integrated SFTP dual-pane browser — WinSCP style</em></td>
</tr>
<tr>
<td><img src="immagini/pcm6.png" width="380"/><br><em>RDP session: multi-monitor, clipboard, selectable client</em></td>
<td><img src="immagini/pcm10.png" width="380"/><br><em>FTP/FTPS dual-pane browser with transfer queue</em></td>
</tr>
</table>

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

### Tools menu and import

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
cd Python_Connection_Manager
bash setup.sh
cd gtk3
python3 PCM.py
```

> The `setup.sh` script detects the distribution and installs system dependencies (GTK3, VTE, gtk-vnc) and Python packages (paramiko, cryptography, pyftpdlib). It also creates a `.desktop` launcher in the application menu.

```bash
# Check dependencies only, without installing:
bash setup.sh --check
```

### Manual install by distribution

<details>
<summary><b>Debian / Ubuntu / Linux Mint</b></summary>

```bash
sudo apt install \
    python3 python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-vte-2.91 gir1.2-gtkvnc-2.0 \
    openssh-client freerdp3-x11 tigervnc-viewer \
    xdotool xdg-utils wakeonlan

pip install --user cryptography paramiko pyftpdlib
```
</details>

<details>
<summary><b>Arch Linux</b></summary>

```bash
sudo pacman -Sy --needed \
    python python-gobject gtk3 vte3 gtk-vnc \
    openssh freerdp tigervnc xdotool xdg-utils wol \
    python-cryptography python-paramiko python-pyftpdlib
```
</details>

<details>
<summary><b>Fedora</b></summary>

```bash
sudo dnf install \
    python3-gobject gtk3 vte291 gtk-vnc2 \
    openssh-clients freerdp tigervnc xdotool xdg-utils

pip install --user cryptography paramiko pyftpdlib
```
</details>

<details>
<summary><b>openSUSE</b></summary>

```bash
sudo zypper install \
    python3-gobject typelib-1_0-Gtk-3_0 \
    typelib-1_0-Vte-2.91 typelib-1_0-GtkVnc-2_0 \
    openssh freerdp tigervnc xdotool xdg-utils

pip install --user cryptography paramiko pyftpdlib
```
</details>

<details>
<summary><b>FreeBSD</b></summary>

```bash
sudo pkg install \
    python3 py311-gobject gtk3 vte3 gtk-vnc \
    mosh freerdp3 tigervnc-viewer xdotool wakeonlan \
    py311-cryptography py311-paramiko py311-pyftpdlib
```
</details>

### PyQt6 install (maintenance)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/pyqt6
pip install PyQt6
python3 PCM.py
```

---

## Optional dependencies

| Package | Feature enabled |
|---|---|
| `gir1.2-gtkvnc-2.0` / `gtk-vnc` | Native embedded VNC (recommended) |
| `tigervnc-viewer` / `xtightvncviewer` | VNC via external client (fallback) |
| `freerdp3-x11` / `xfreerdp` | RDP |
| `mosh` | Mosh connections |
| `picocom` / `minicom` | Serial ports |
| `xdotool` | RDP in internal panel (requires XWayland) |
| `wakeonlan` / `wol` | Wake-on-LAN |
| `keepassxc` | KeePassXC integration |
| `pynacl` | KeePassXC Browser Protocol v2 encryption |

---

## Wayland notes

GTK3 + VTE work **natively on Wayland** without XWayland.

The only exception is the **RDP internal panel** mode (embedding xfreerdp via xdotool), which requires XWayland. For pure Wayland use, set RDP to **"External window"**.

The `gtk-vnc` VNC viewer works natively on Wayland.

---

## Configuration files

| File | Contents |
|---|---|
| `gtk3/connections.json` | Session profiles — human-readable JSON, editable by hand |
| `gtk3/pcm_settings.json` | Global settings, shortcuts, recent sessions |
| `gtk3/audit_log.json` | Connection audit log (metadata only, no credentials) |
| `/tmp/pcm_logs/` | Terminal output logs, path configurable |

---

## Support the project

If you find PCM useful and want to thank the developer, you can buy him a coffee via PayPal. Any contribution is greatly appreciated and helps keep the project alive!

[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

*Thank you so much!*

---

## Author

**Andres Zanzani** — license [EUPL-1.2](EUPL-1.2%20EN.txt)

[![GitHub](https://img.shields.io/badge/GitHub-buzzqw%2FPython__Connection__Manager-blue?logo=github)](https://github.com/buzzqw/Python_Connection_Manager)
