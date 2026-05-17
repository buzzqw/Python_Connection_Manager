# PCM — Python Connection Manager

[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](../EUPL-1.2%20EN.txt)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GTK3](https://img.shields.io/badge/UI-GTK3-green.svg)](https://docs.gtk.org/gtk3/)
[![Wayland](https://img.shields.io/badge/Wayland-nativo-purple.svg)](#note-wayland)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20FreeBSD-lightgrey.svg)](#installazione)

> **L'alternativa Linux a MobaXterm** — tutto in una finestra: SSH, RDP, VNC, SFTP, FTP, Telnet, Mosh, Seriale.  
> Scritto in Python con GTK3 e terminale VTE nativo. Funziona su **X11 e Wayland** senza XWayland.

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

## Screenshot

<table>
<tr>
<td><img src="../immagini/pcm1.png" width="380"/><br><em>Finestra principale: sidebar gruppi, sezione Recenti, quick connect</em></td>
<td><img src="../immagini/pcm2.png" width="380"/><br><em>Sessione SSH: host, porta, WoL integrato, pulsante KeePassXC</em></td>
</tr>
<tr>
<td><img src="../immagini/pcm3.png" width="380"/><br><em>Autenticazione avanzata: chiavi SSH, Jump Host, Agent Forwarding</em></td>
<td><img src="../immagini/pcm4.png" width="380"/><br><em>Browser SFTP dual-pane integrato — stile WinSCP</em></td>
</tr>
<tr>
<td><img src="../immagini/pcm6.png" width="380"/><br><em>Sessione RDP: multi-monitor, clipboard, client selezionabile</em></td>
<td><img src="../immagini/pcm10.png" width="380"/><br><em>Browser FTP/FTPS dual-pane con coda trasferimenti</em></td>
</tr>
</table>

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
- **Chiavi SSH**: genera, copia sul server, visualizza la chiave pubblica.
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

## Installazione

### Automatica — raccomandato

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

### Manuale

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

---

## Avvio rapido

```bash
cd Python_Connection_Manager/gtk3
python3 PCM.py
```

Al primo avvio PCM crea `connections.json` con sessioni di esempio e propone di abilitare la cifratura AES-256 delle credenziali.

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

## Autore

**Andres Zanzani** — licenza [EUPL-1.2](../EUPL-1.2%20EN.txt)

[GitHub](https://github.com/buzzqw/Python_Connection_Manager) · Segnala bug e richieste su [Issues](https://github.com/buzzqw/Python_Connection_Manager/issues)
