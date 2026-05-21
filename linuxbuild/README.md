# PCM — Linux Build System (GTK3)

Questa cartella contiene gli strumenti per impacchettare PCM (variante GTK3) come archivio distribuibile per Linux.

> ℹ️ La variante **PyQt6** non viene pacchettizzata: usa PyInstaller che richiede Windows per la versione GTK3 non è applicabile. La variante GTK3 usa librerie di sistema (PyGObject, VTE, ecc.) che non possono essere bundlate in un singolo eseguibile — il pacchetto distribuisce quindi i sorgenti Python con un launcher e tutte le istruzioni di installazione.

---

## File presenti

| File | Descrizione |
|------|-------------|
| `build.sh` | Script principale — crea l'archivio `.tar.gz` distribuibile |
| `install_deps.sh` | Installa le dipendenze Python (`cryptography`, `paramiko`, `pyftpdlib`) e mostra i comandi per le dipendenze di sistema |
| `README.md` | Questo file |

---

## Uso rapido

```bash
# Rendi gli script eseguibili (solo la prima volta)
chmod +x linuxbuild/build.sh linuxbuild/install_deps.sh

# 1. Installa le dipendenze di build (una volta sola)
bash linuxbuild/install_deps.sh

# 2. Pacchettizza
bash linuxbuild/build.sh 1.0.0

# 2b. Con versione rilevata automaticamente (prompt interattivo)
bash linuxbuild/build.sh

# 2c. Produce anche un archivio .zip oltre al .tar.gz
bash linuxbuild/build.sh 1.0.0 --zip
```

L'archivio viene creato in `dist/`:

```
dist/
└── PCM_v1.0.0_Linux_GTK3.tar.gz
```

---

## Contenuto del pacchetto

Ogni archivio prodotto contiene:

| Percorso | Descrizione |
|----------|-------------|
| `*.py` | Tutti i moduli Python della variante GTK3 |
| `icons/` | Icone dell'applicazione |
| `immagini/` | Immagini aggiuntive dalla root del progetto |
| `*.html` | File di help integrato (IT + EN) |
| `pcm` | Script launcher bash (rende eseguibile `python3 PCM.py`) |
| `pcm.desktop` | File di integrazione con il desktop Linux |
| `connections.json.example` | Template configurazione sessioni |
| `pcm_settings.json.example` | Template impostazioni |
| `requirements.txt` | Elenco dipendenze Python |
| `INSTALL.txt` | Istruzioni installazione dettagliate per distro |
| `LEGGIMI_INSTALLAZIONE.txt` | Guida rapida all'avvio |
| `LICENSE` | Licenza EUPL v1.2 |

---

## Dipendenze del pacchetto distribuito

Le dipendenze **non** vengono bundlate — vanno installate sull'host di destinazione.

### Dipendenze di sistema (una volta sola)

**Debian / Ubuntu / Linux Mint:**
```bash
sudo apt install \
    python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-vte-2.91 \
    gir1.2-webkit2-4.1 gir1.2-gtk-vnc-2.0 \
    gir1.2-gdkpixbuf-2.0 \
    openssh-client freerdp3-x11 tigervnc-viewer \
    mosh xdotool xdg-utils wakeonlan
```

**Fedora / RHEL:**
```bash
sudo dnf install \
    python3-gobject gtk3 vte291 \
    webkit2gtk4.1 gtk-vnc2 \
    openssh-clients mosh freerdp tigervnc \
    xdotool xdg-utils wol
```

**Arch Linux:**
```bash
sudo pacman -Sy --needed \
    python-gobject gtk3 vte3 gtk-vnc webkit2gtk \
    openssh mosh freerdp tigervnc xdotool xdg-utils wol \
    python-cryptography python-paramiko python-pyftpdlib
```

**openSUSE:**
```bash
sudo zypper install \
    python3-gobject typelib-1_0-Gtk-3_0 \
    typelib-1_0-Vte-2.91 typelib-1_0-GtkVnc-2_0 \
    openssh freerdp tigervnc xdotool xdg-utils
pip install --user cryptography paramiko pyftpdlib
```

### Dipendenze Python

```bash
pip install --user cryptography paramiko pyftpdlib
```

---

## Installazione dal pacchetto

```bash
# Estrai
tar -xzf PCM_v1.0.0_Linux_GTK3.tar.gz -C ~/Applicazioni/

# Avvia
bash ~/Applicazioni/PCM_v1.0.0_Linux_GTK3/pcm

# Integrazione desktop (opzionale)
cp ~/Applicazioni/PCM_v1.0.0_Linux_GTK3/pcm.desktop \
   ~/.local/share/applications/
# Poi modifica la riga Exec= con il percorso assoluto
```

---

## Download pacchetti precompilati

> 💡 Non vuoi buildare da soli? Ad ogni commit il workflow CI produce automaticamente i pacchetti pronti all'uso.

### Ultima versione di sviluppo (ogni commit)

1. Vai su **[GitHub → Actions → Build PCM Linux GTK3](https://github.com/buzzqw/Python_Connection_Manager/actions/workflows/build.yml)**
2. Clicca sull'ultima run completata (segno di spunta verde ✅)
3. Scorri fino alla sezione **Artifacts** in fondo alla pagina
4. Scarica il file che ti serve:

| File | Descrizione |
|------|-------------|
| `PCM_v..._Linux_GTK3.tar.gz` | Archivio tar.gz — estrai e lancia |
| `PCM_v..._Linux_GTK3.zip` | Archivio zip — alternativa |
| `pcm_..._all.deb` | Pacchetto Debian/Ubuntu — installa con `sudo dpkg -i` |

### Release ufficiali (versioni taggate)

I pacchetti delle versioni stabili sono pubblicati nella pagina **[Releases](https://github.com/buzzqw/Python_Connection_Manager/releases)** con `tar.gz`, `zip` e `.deb` allegati direttamente a ogni release.

---

## GitHub Actions (CI/CD)

Il progetto include un workflow GitHub Actions in `.github/workflows/build.yml` che si attiva automaticamente a ogni commit.

### Cosa fa

| Trigger | Comportamento |
|---------|---------------|
| Ogni `push` (qualsiasi branch) | Build `tar.gz` + `zip` + `.deb`; artefatti scaricabili dalla scheda **Actions** |
| Ogni `push` di un tag `v*` (es. `v1.2.0`) | Come sopra, **più** creazione automatica di una GitHub Release con i tre file allegati |

### Versione usata nel build

- **Da tag** (`git tag v1.2.0 && git push --tags`): versione = `1.2.0`
- **Da commit** (senza tag): versione = `0.0.0-<short SHA>` (build di sviluppo)

### Come creare una release ufficiale

```bash
git tag v1.2.0
git push origin v1.2.0
```

Il job `release` si avvierà automaticamente e pubblicherà la release con `tar.gz`, `zip` e `.deb` allegati.

---

## Note tecniche

- **Nessun binary bundled**: a differenza di PyInstaller, il pacchetto distribuisce i sorgenti Python. Questo è necessario perché GTK3/VTE sono librerie di sistema non bundlabili.
- **Launcher**: lo script `pcm` entra nella directory del pacchetto prima di avviare Python, assicurando che gli import relativi funzionino correttamente.
- **Versione**: se non passata come argomento, `build.sh` tenta di rilevarla dal `README.md` della root; in caso contrario chiede un prompt interattivo.
- **Staging**: la cartella `dist/PCM_v<VERSION>_Linux_GTK3/` rimane dopo il build per ispezione o distribuzione diretta via rsync/scp.
