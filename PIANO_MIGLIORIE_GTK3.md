# Piano di lavoro esteso — Python Connection Manager

> Documento operativo destinato a un modello AI che eseguirà le modifiche.
> Copre **tutti** i punti da toccare: rimozione della variante PyQt6, esperienza utente,
> difetti bloccanti, sicurezza, gestione risorse, qualità del codice, build e documentazione.

---

## Contesto

PCM è un gestore di connessioni (SSH, RDP, VNC, FTP/SFTP, Telnet, Mosh, seriale) scritto in
Python con PyGObject/GTK3 + VTE. Il repository contiene oggi due varianti: `gtk3/` (~22.000
righe, 34 moduli, 88 commit, ultimo 2026-07-27) e `pyqt6/` (~13.000 righe, 30 commit, ferma dal
2026-05-22). Non condividono codice: `config_manager.py`, `crypto_manager.py`,
`session_command.py`, `importer.py` e `translations.py` esistono in due copie divergenti.

Un'analisi completa del codice ha rilevato quattro classi di problemi:

1. **Funzioni che l'interfaccia promette e che non funzionano.** Le scorciatoie da tastiera sono
   configurabili nelle impostazioni e non vengono mai registrate; sei pannelli interi non passano
   dal sistema di traduzione; gli errori finiscono su stdout, invisibili a chi lancia l'app
   dall'icona del desktop.
2. **Cinque difetti bloccanti**, di cui tre rendono inutilizzabili pre-comando, Wake-on-LAN e
   jump host — fallendo in silenzio.
3. **Debiti di sicurezza**: password nella riga di comando, file di configurazione a 0664,
   nessun blocco automatico della cifratura, verifica delle identità disattivata per
   impostazione predefinita, interpolazione non quotata in stringhe shell.
4. **Perdite di risorse**: timer GLib mai cancellati, processi figli mai attesi, file temporanei
   con credenziali che sopravvivono alla chiusura.

**Esito atteso:** un repository a variante singola, in cui ogni comando visibile funziona
davvero, l'interfaccia è coerente nella lingua scelta, i fallimenti sono visibili all'utente, le
credenziali non sono esposte a utenti locali e le risorse vengono liberate.

---

## Decisioni già prese dal committente

| Decisione | Effetto sul piano |
|---|---|
| **`pyqt6/` va rimossa** | FASE 0. Il repository diventa a variante singola. Cade ogni ipotesi di package condiviso `pcm_core/`. |
| **L'esperienza utente ha la priorità** | FASE 1 precede bug, sicurezza e pulizia. |
| **Ambito UX: riparare + rifiniture mirate** | Nessuna funzione nuova (niente palette comandi, riordino schede con trascinamento, ricerca globale). |

**Non obiettivi**, da non fare in questa tornata anche se sembrano naturali:

- Spostare `gtk3/` nella radice del repository. Il lanciatore `pcm`, `setup.sh`, il marcatore
  `.pcm_installed` e `packaging/appimage/pcm.spec` puntano tutti a quel percorso: rinominare
  moltiplica il rischio senza alcun beneficio per l'utente. Valutabile in futuro, separatamente.
- Migrare a GTK4. Fuori scopo.
- Riscrivere `translations.py` con gettext prima di UX-2 (rifarebbe il lavoro due volte —
  vedi QUAL-5).

---

## Istruzioni per il modello esecutore

- **Una fase per volta, un task per volta.** Ogni task ha un criterio di accettazione
  verificabile: non passare al successivo finché non è soddisfatto.
- **I riferimenti `file:riga` valgono per il commit `1e4d2af`.** Dopo le prime modifiche le
  righe scalano: **localizza sempre il codice per contenuto, non per numero di riga.**
- **Non rifattorizzare oltre il perimetro del task.** In particolare non spezzare `PCM.py` in
  moduli: è previsto in QUAL-4 e solo come task esplicito e isolato.
- **Un ramo dedicato, un commit per task**, con l'identificativo nel messaggio
  (es. `fix(ux): registra le scorciatoie configurate — UX-1`).
- **Verifica dopo ogni fase** con la procedura in fondo al documento.
- **Stile:** commenti in italiano, chiavi i18n in inglese puntato (`cron.title`), coerenti con
  il codice esistente.
- Se un task risulta già fatto o non applicabile, annotalo e prosegui senza forzare.
- Dove il piano dice *"verificare prima di rimuovere"*, fermati e chiedi: sono punti in cui la
  cancellazione potrebbe nascondere una regressione anziché rimuovere codice obsoleto.

### Mappa dei moduli `gtk3/`

| Area | Moduli |
|---|---|
| Nucleo | `PCM.py` (3154), `config_manager.py` (521), `crypto_manager.py` (335), `protocols.py` (311), `session_command.py` (581) |
| Dialoghi | `session_dialog.py` (2224), `settings_dialog.py` (642), `cluster_dialog.py`, `quick_connect_dialog.py`, `variables_dialog.py`, `snippets_dialog.py`, `deps_dialog.py`, `crypto_manager_dialog.py` |
| Terminale | `terminal_widget.py` (787), `terminal_highlight.py`, `themes.py` |
| Protocolli grafici | `rdp_widget.py` (669), `vnc_widget.py` (658) |
| Trasferimento file | `winscp_widget.py` (2196), `sftp_browser.py` (1091), `sftp_editor.py`, `ftp_server_dialog.py` |
| Strumenti | `tunnel_manager.py` (607), `panel_monitor.py` (921), `sysmon_widget.py`, `cron_widget.py`, `log_viewer.py`, `password_tools.py`, `totp_manager.py`, `keepassxc_manager.py` |
| Trasversali | `translations.py` (1724), `importer.py` (876), `session_panel.py`, `welcome_widget.py`, `plugins/` |

---

# FASE 0 — Rimozione della variante PyQt6

Indipendente dal resto: **non tocca `gtk3/`**, può essere eseguita per prima senza alcun rischio
per le fasi successive. Elimina 1,8 MB di codice divergente e semplifica installazione e
documentazione.

Motivazione tecnica, oltre all'abbandono: la copia PyQt6 contiene **due difetti di sicurezza
reali** che la versione GTK3 ha già corretto. `pyqt6/config_manager.py:64` salva
`connections.json` con `open(..., "w")`, quindi con i permessi dell'umask (tipicamente 0644): il
file con le credenziali è leggibile da altri utenti. `pyqt6/crypto_manager.py:143-148` cifra la
costante `b"pcm-verify"` come token di verifica, esponendo la password principale a un attacco
offline a testo noto, mentre `gtk3/crypto_manager.py:143-152` usa un canary casuale. Continuare
a distribuirla significa consegnare quei difetti agli utenti.

---

### REM-1 — Eliminare la cartella e le sue tracce

1. `git rm -r pyqt6/`.
2. Rimuovere i riferimenti residui nei commenti di `gtk3/`, che citano PyQt6 come "originale" e
   dopo la rimozione diventano indicazioni verso codice inesistente:
   - `gtk3/rdp_widget.py:4` — *"Stessa strategia dell'originale PyQt6 (xdotool reparent)"*
   - `gtk3/rdp_widget.py:321` — *"Timeout 180s (360 × 500ms) — come PyQt6"*
   - `gtk3/session_dialog.py:5` — *"Corrisponde 1:1 all'originale PyQt6"*
   - `gtk3/translations.py:1048` — intestazione di sezione *"variables_dialog (PyQt6)"*

   Riformulare in modo autonomo (es. *"Riposizionamento finestra via xdotool: xfreerdp non
   supporta XEmbed"*), non limitarsi a cancellare la parola.
3. **Conservare** `packaging/appimage/pcm.spec:141`
   (`excludes=['tkinter', 'PyQt5', 'PyQt6', ...]`): è un'esclusione di PyInstaller che impedisce
   a Qt di finire nel pacchetto, corretta e da mantenere.

**Accettazione.** `grep -rniI "pyqt" --exclude-dir=.git .` restituisce solo `pcm.spec:141`.

---

### REM-2 — Semplificare `setup.sh`

`setup.sh` contiene un intero meccanismo di scelta della variante, ora privo di senso.

1. Rimuovere il menu di selezione (`setup.sh:85-104`): niente più domanda *"Quale versione di PCM
   vuoi installare?"*.
2. Rimuovere il ramo PyQt6 (`setup.sh:145-173`): messaggio di avvertimento, `PIP_PACKAGES` con
   `PyQt6`/`PyQt6-WebEngine`, i tre `SYS_PKGS` per Arch/BSD/altri, `VARIANT_DIR`, `CHECK_CMD_PY`,
   `CHECK_LABEL`.
3. Rimuovere il commento d'intestazione `setup.sh:10`.
4. Sostituire la variabile `VARIANT` con il valore fisso `gtk3`, oppure eliminarla e usare il
   percorso diretto. Punti coinvolti: `:98`, `:107`, `:111`, `:116`, `:140`, `:224`, `:261`,
   `:330`, `:333`.
5. **Gestire la migrazione delle installazioni esistenti**: il marcatore `.pcm_installed`
   (letto a `setup.sh:107`, scritto a `:330`) può contenere la stringa `pyqt6` su una macchina
   già installata. Alla lettura, trattare qualunque valore diverso da `gtk3` come `gtk3` e
   informare l'utente che la variante PyQt6 non è più distribuita e che l'installazione passerà
   a GTK3. **Non fallire in silenzio né interrompersi.**
6. Verificare che il lanciatore generato (`setup.sh:224`) e la voce desktop (`:249`) puntino
   correttamente a `gtk3/PCM.py`.

**Accettazione.** `bash -n setup.sh` pulito. Un'installazione a partire da `.pcm_installed`
contenente `pyqt6` completa senza errori e produce un'installazione GTK3. Il menu di scelta non
compare più.

---

### REM-3 — Aggiornare la documentazione

`README.md` è bilingue (sezione inglese e sezione italiana): **entrambe** vanno aggiornate.

- Righe `23` e `483` — la riga PyQt6 nella tabella delle varianti: rimuoverla, e con essa la
  colonna "variante" se resta una sola riga.
- Righe `25` e `485` — la nota *"la cartella `pyqt6/` contiene la versione legacy"*.
- Righe `399-401` e `857-859` — le sezioni *"PyQt6 — versione legacy"* con il collegamento a
  `pyqt6/README.md`, che diventerà un collegamento rotto.
- `linuxbuild/README.md:5` — la nota *"La variante PyQt6 non viene pacchettizzata"*: ora è
  l'unica variante, la frase va riscritta.
- Aggiungere alle note di rilascio una riga esplicita: la variante PyQt6 è stata rimossa, gli
  utenti che la usavano devono passare a GTK3; i file `connections.json` e `pcm_settings.json`
  sono compatibili **in lettura** (GTK3 legge il formato PyQt6), ma non il contrario.

**Nota di compatibilità da verificare e documentare.** I due formati del token di verifica della
cifratura non sono interoperabili: `gtk3/crypto_manager.py:176-188` legge sia il formato con
canary sia quello vecchio, quindi la migrazione PyQt6 → GTK3 funziona. Il percorso inverso no,
ma non serve più. Confermare sperimentalmente prima di scriverlo nelle note.

**Accettazione.** Nessun collegamento rotto nel README (verificare i percorsi relativi). Nessuna
menzione di PyQt6 come opzione installabile.

---

# FASE 1 — Esperienza utente

Obiettivo: l'utente non incontra più comandi che non fanno nulla, testo nella lingua sbagliata,
o fallimenti silenziosi.

---

### UX-1 — Le scorciatoie da tastiera non funzionano affatto

**Priorità: massima.** È la funzione rotta più visibile.

**Problema.** `gtk3/settings_dialog.py:520-545` costruisce una scheda "Scorciatoie" con otto
combinazioni configurabili, salvate in `pcm_settings.json` da `settings_dialog.py:622`
(`s["shortcuts"][key] = ...`). I default sono in `gtk3/config_manager.py:248-257`:

```python
"shortcuts": {
    "new_terminal": "Ctrl+Alt+T",   "close_tab":      "Ctrl+Alt+Q",
    "prev_tab":     "Ctrl+Alt+Left","next_tab":       "Ctrl+Alt+Right",
    "new_session":  "Ctrl+Shift+N", "toggle_sidebar": "Ctrl+Shift+B",
    "find":         "Ctrl+Shift+F", "fullscreen":     "F11",
}
```

Ma `gtk3/PCM.py:532-539` — `_setup_accels()` — registra **un solo** acceleratore, `Ctrl+Shift+G`
per le variabili globali, che non è nemmeno tra gli otto configurabili. Nessuna delle otto è
collegata: l'utente le configura, salva, e non accade nulla.

**Intervento.**

1. Riscrivere `_setup_accels()` perché legga `config_manager.load_settings().get("shortcuts", {})`
   e registri un acceleratore per ciascuna voce presente, mantenendo `Ctrl+Shift+G` come voce
   fissa aggiuntiva.
2. Aggiungere un helper `_accel_to_gtk(s: str) -> str` che converta la notazione salvata
   (`"Ctrl+Alt+T"`) nel formato GTK (`"<Primary><Alt>t"`): `Ctrl`→`<Primary>`, `Shift`→`<Shift>`,
   `Alt`→`<Alt>`, `Super`/`Meta`→`<Super>`; l'ultimo segmento è il tasto. Validare con
   `Gtk.accelerator_parse()`: se restituisce `(0, 0)`, saltare la voce e registrare un avviso
   (UX-3) **senza interrompere le altre**.
3. Collegare le azioni. Handler già esistenti da riusare:
   - `new_terminal` → `self._on_terminale_locale()` (`PCM.py:1838`)
   - `new_session` → `self._on_nuova_sessione()` (`PCM.py:1822`)
   - `close_tab` → `self._chiudi_tab_corrente()` (`PCM.py:1720`)
   - `prev_tab` / `next_tab` → `self._notebook.prev_page()` / `.next_page()`
   - `find` → sulla pagina attiva, attivare la barra di ricerca del terminale, già implementata
     in `terminal_widget.py:136-168` e commutata dal metodo a `terminal_widget.py:629-632`.
     Verificarne il nome esatto ed esporlo come metodo pubblico se necessario. Se la pagina
     attiva non è un terminale, non fare nulla.
   - `toggle_sidebar` e `fullscreen` → **handler assenti, da creare**:
     - `_toggle_sidebar()`: alterna la visibilità del pannello laterale nel `Gtk.Paned` principale
       (`PCM.py:325`) e persiste in `settings["display"]["sidebar_visible"]`, chiave già prevista
       in `config_manager.py:242` **e oggi mai usata**.
     - `_toggle_fullscreen()`: alterna `self.fullscreen()` / `self.unfullscreen()` su un flag di
       istanza.
4. Ogni callback deve restituire `True`: gli acceleratori GTK richiedono un valore veritiero per
   considerare l'evento gestito.
5. Rendere le scorciatoie riapplicabili **senza riavvio**: conservare il gruppo in
   `self._accel_group`; al salvataggio delle impostazioni rimuoverlo con `remove_accel_group()`
   e richiamare `_setup_accels()`.
6. Gestire il conflitto con VTE: `Ctrl+Shift+F` e simili possono essere intercettati dal
   terminale. Verificare che la ricerca funzioni con un terminale attivo; se l'acceleratore non
   arriva, gestirlo in `key-press-event` sulla finestra prima dell'inoltro al widget.

**Accettazione.** Con i default: `Ctrl+Alt+T` apre un terminale locale; `Ctrl+Shift+N` il dialogo
nuova sessione; `Ctrl+Alt+Q` chiude la scheda; `Ctrl+Alt+Left/Right` cambia scheda;
`Ctrl+Shift+B` mostra/nasconde la barra laterale e lo stato sopravvive al riavvio; `F11` va a
schermo intero; `Ctrl+Shift+F` apre la ricerca in un terminale. Modificando una combinazione e
salvando, la nuova ha effetto senza riavviare. Una combinazione non valida non impedisce alle
altre di funzionare.

---

### UX-2 — Sei pannelli non sono tradotti

**Problema.** Verificato contando le chiamate reali a `t()`:

| Modulo | righe | importa `translations` | chiamate a `t()` |
|---|---|---|---|
| `gtk3/cron_widget.py` | 531 | **no** | **0** |
| `gtk3/log_viewer.py` | 337 | sì | **0** |
| `gtk3/sysmon_widget.py` | 389 | **no** | **0** |
| `gtk3/sftp_editor.py` | 374 | **no** | **0** |
| `gtk3/snippets_dialog.py` | 208 | **no** | **0** |
| `gtk3/password_tools.py` | 160 | **no** | **0** |

`log_viewer.py` importa il modulo di traduzione e non lo usa mai. Un utente con lingua inglese
apre Cron, Log, Monitor di sistema, l'editor SFTP o gli snippet e trova un'interfaccia
interamente in italiano.

Stringhe hardcoded anche in moduli altrimenti tradotti — le più gravi:

- `PCM.py:272` — avviso *"Il file connections.json contiene credenziali cifrate (ENC:…) ma il
  file impostazioni non ha la chiave"*: messaggio critico, solo in italiano.
- `PCM.py:1203` — *"⚠ Credenziali non complete nel profilo sessione…"*
- `PCM.py:1239` — `Gtk.CheckButton("Salva nel profilo sessione")`
- `PCM.py:1377` — `Gtk.Label("In attesa della connessione VNC…")`
- `session_dialog.py:249` — tooltip *"Genera password casuale"*
- `session_dialog.py:254` — tooltip *"Mostra/Nascondi password"*
- `session_dialog.py:722` — `Gtk.Label("Keepalive (s):")`
- `session_dialog.py:2004-2010` — *"⚠ nessun client seriale trovato…"*, *"(comando exec vuoto)"*,
  *"(inserire host)"*
- `settings_dialog.py:462,469` — placeholder *"UltraVNC, AnyDesk…"*, *"/usr/bin/vncviewer"*
- `sftp_browser.py:269,273` — *"Utente SSH:"*, *"Password SSH:"*
- `panel_monitor.py:486-517` — italiano e inglese mescolati nello stesso pannello
  (*"Scheda di rete"* accanto a *"Usage history"*)
- `snippets_dialog.py:101-103`, `cron_widget.py:213,288-294,345,522`,
  `log_viewer.py:84,90,104,108,136`, `sftp_editor.py:184,191,210,226`, `sysmon_widget.py:244`,
  `winscp_widget.py:1913-1927`, `keepassxc_manager.py:443,448`, `password_tools.py:140-146`,
  `quick_connect_dialog.py:70,118,146,164`, `tunnel_manager.py:226,231`
- `PCM.py:43,57,68` — messaggi di dipendenza mancante (PyGObject/GTK/VTE assenti).
  **Eccezione consapevole:** girano prima che le traduzioni siano inizializzabili. Lasciarli in
  italiano ma aggiungere la versione inglese sulla stessa riga.

**Intervento.** Modulo per modulo, dal più grande al più piccolo:

1. Aggiungere `from translations import t` in testa.
2. Sostituire ogni stringa letterale rivolta all'utente — etichette, titoli, pulsanti, tooltip,
   placeholder, messaggi di dialogo, intestazioni di colonna — con `t("<chiave>")`.
   **Non** tradurre: comandi shell, chiavi di configurazione, percorsi, formati di data, testo di
   debug.
3. Registrare ogni nuova chiave in `gtk3/translations.py` **per tutte e cinque le lingue**
   (it, en, de, fr, es). Prefisso per modulo: `cron.`, `logview.`, `sysmon.`, `sftpedit.`,
   `snip.`, `pwtools.`.
4. Per le stringhe con valori interpolati usare i segnaposto già supportati da `t(key, **kwargs)`
   (`translations.py:19-60`), non la concatenazione.
5. Attenzione al fallback: `t()` restituisce **la chiave grezza** se manca (`translations.py:19-60`),
   quindi un refuso produce `cron.titl` a schermo invece di un errore. Dopo ogni modulo,
   eseguire il controllo di coerenza di `tests/test_translations.py`.

**Nota sul volume.** `translations.py` è già a 1724 righe e 1157 chiavi × 5 lingue; questo task
ne aggiunge diverse centinaia. Accettabile per ora: la migrazione a gettext è QUAL-5 e **non va
anticipata**.

**Accettazione.** Con lingua English e riavvio, nessuna stringa italiana visibile in: pannello
Cron, visualizzatore Log, Monitor di sistema, editor SFTP, dialogo Snippet, strumenti password, e
nei punti elencati di `PCM.py`/`session_dialog.py`. Controllo a campione su Deutsch.

---

### UX-3 — Gli errori sono invisibili all'utente

**Problema.** Il modulo `logging` non è **mai** importato in tutto il progetto: 57 chiamate
`print()` scrivono su stdout, invisibili a chi lancia PCM da un'icona. In parallelo esistono
**95 blocchi `except ...: pass`** che sopprimono del tutto l'errore (i più densi:
`winscp_widget.py` 20, `vnc_widget.py` 14, `session_dialog.py` 9, `rdp_widget.py` 8, `PCM.py` 7).

Distribuzione dei `print()`: `importer.py` 21, `PCM.py` 10, `plugins/plugin_manager.py` 8,
`config_manager.py` 8, `rdp_widget.py` 4, `terminal_widget.py` 2, `protocols.py` 2,
`totp_manager.py` 1.

I casi che danneggiano direttamente l'utente:

1. **`PCM.py:1367-1368` — `_salva_password_vnc()`**: l'intero blocco che carica i profili, scrive
   la password e chiama `save_profiles()` è in `try/except Exception: pass`. Se il salvataggio
   fallisce (disco pieno, permessi, cifratura bloccata) l'utente ha cliccato "salva password",
   crede che sia salvata, e non lo è. **Perdita silenziosa di dato.**
2. **`config_manager.py:49`** — `except (json.JSONDecodeError, Exception) as e:` (tupla
   ridondante: `JSONDecodeError` è già sottoclasse di `Exception`). Su un `connections.json`
   corrotto restituisce `{}`: l'utente vede **zero sessioni**, come se le avesse perse.
3. **`session_dialog.py:1543-1577` — `_on_template_changed()`**: 34 righe che applicano un
   modello di sessione, chiuse da `except Exception: pass`. Con un modello malformato l'utente
   vede campi compilati a metà senza capire perché.
4. **`keepassxc_manager.py:65-70` — `_save_assoc()`**: il salvataggio delle chiavi di
   associazione è silenziato; se fallisce, l'utente deve riassociare a ogni avvio senza motivo
   apparente.
5. **`winscp_widget.py:1540-1546` — `_rmdir_ricorsivo()`**: `delete()` e `rmd()` falliscono in
   silenzio; una cancellazione remota può fallire a metà e riportare comunque "fatto".
6. **`winscp_widget.py:1373-1411`** — i tre fallback di listing FTP (MLSD→LIST→NLST) sono tutti
   `except: pass`: se falliscono tutti si mostra una cartella vuota, indistinguibile da una
   cartella realmente vuota.
7. **`translations.py:69-75` — `init_from_settings()`**: se la lettura delle impostazioni
   fallisce, l'app resta in italiano senza traccia.
8. **`PCM.py:690-695`** — `except ImportError: pass` sul controllo di cifratura nel percorso di
   apertura da URI: se `cryptography` manca, il flusso prosegue **senza sblocco** e usa come
   password la stringa cifrata `ENC:…`. Vedi anche SEC-8.
9. **`sftp_editor.py:362-363`** — `os.unlink` del file temporaneo silenziato: file con contenuti
   remoti restano su disco. Vedi RES-3.

**Intervento.**

1. Creare `gtk3/pcm_logging.py`: configura il modulo `logging` standard con due destinazioni —
   `RotatingFileHandler` su `~/.local/share/pcm/pcm.log` (cartella creata con `mode=0o700`,
   ~1 MB × 3 file) e `StreamHandler` su stderr. Livello da `settings["general"]["log_level"]`,
   default `INFO`, con override da variabile d'ambiente `PCM_LOG_LEVEL`. Esporre `get_logger(name)`.
2. Aggiungere `general.log_level` a `DEFAULT_SETTINGS` e la voce corrispondente nelle
   impostazioni, con un pulsante *"Apri cartella dei log"*.
3. Inizializzare il logging per primo in `PCM.py`, prima di ogni altro import di moduli PCM.
4. Sostituire tutti i `print()` non-CLI con la chiamata di logging appropriata. **Conservare come
   `print()`**: il blocco `__main__` di `importer.py:820-876` (è una vera interfaccia a riga di
   comando) e i messaggi di dipendenza mancante di `PCM.py:43-89` (girano prima della
   configurazione del logging).
5. Sui nove punti elencati, sostituire `except Exception: pass` con un `except` che registra a
   livello `warning`/`error` **e**, quando l'operazione era stata richiesta esplicitamente
   dall'utente (casi 1, 3, 5), gliela segnala tramite `_warn()` (`PCM.py:2674`) o l'equivalente
   nel widget.
   - Caso 1: se `save_profiles()` restituisce `False` o solleva, mostrare *"Impossibile salvare
     la password: <motivo>"*. **Non** dire all'utente che è stata salvata.
   - Caso 2: distinguere "file assente" (normale al primo avvio) da "file illeggibile o
     corrotto". Nel secondo caso mostrare all'avvio un dialogo con il percorso del file e
     l'avviso che le sessioni non sono state caricate, **senza sovrascriverlo**. Vedi SEC-1
     punto 2, che elimina la causa più probabile della corruzione.
   - Caso 6: se tutti e tre i tentativi di listing falliscono, errore esplicito invece di
     cartella vuota.
6. Per i restanti ~86 `except: pass`, **non** modificarli tutti ora: aggiungere `logger.debug(...)`
   dove l'eccezione è realmente attesa e benigna, e annotare il resto come debito residuo.

**Accettazione.** Un fallimento di salvataggio password produce un messaggio visibile e una riga
in `~/.local/share/pcm/pcm.log`. Un `connections.json` deliberatamente corrotto produce un avviso
esplicito all'avvio, non una lista vuota silenziosa. `PCM_LOG_LEVEL=DEBUG` aumenta il dettaglio
senza modificare il codice.

---

### UX-4 — L'interfaccia si congela durante la connessione a un cluster

**Problema.** `PCM.py:1124-1143` — `_connect_to_cluster_plan()` è invocato dal thread principale
GTK e chiama `time.sleep(delay)` dentro il ciclo sugli host. Doppio difetto:

- La finestra si blocca per `delay × numero_host` secondi, senza cursore di attesa né indicazione
  di avanzamento: l'app sembra bloccata.
- Le `GLib.idle_add()` accodate durante lo `sleep` vengono eseguite **tutte insieme alla fine**:
  lo scaglionamento configurato dall'utente non produce alcun effetto reale.

**Intervento.** Sostituire il ciclo bloccante con una catena `GLib.timeout_add()`: appiattire il
piano in una lista di `(label, dati)`, poi consumarla un elemento alla volta con un callback che
apre la connessione e riarma il timer a `delay * 1000` ms, restituendo `GLib.SOURCE_REMOVE` alla
fine. Conservare l'id in un attributo di istanza e cancellarlo alla chiusura (coerente con RES-1).

**Rifinitura.** Mostrare l'avanzamento nella barra di stato (*"Connessione cluster: 3/12 —
host…"*) e offrire un modo per annullare le connessioni rimanenti.

**Accettazione.** Con un cluster da 5 host e ritardo 2 s: la finestra resta reattiva, le schede si
aprono una ogni ~2 secondi (non tutte insieme dopo 10 s), la barra di stato mostra l'avanzamento,
l'annullamento interrompe le rimanenti.

---

### UX-5 — Rifiniture mirate

Interventi contenuti e indipendenti fra loro.

1. **Nessun riscontro durante l'apertura di una connessione.** Tra il doppio clic e la comparsa
   del terminale possono passare secondi (DNS, handshake, jump host) senza alcun segnale.
   Mostrare *"Connessione a <host>…"* nella barra di stato all'avvio del tentativo e pulirla al
   successo o all'errore. Agganci: `_on_connetti()` (`PCM.py:557`) e il thread `_bg` corretto in
   BUG-1.
2. **La scheda RDP incorporata non segnala mai la disconnessione.** `RdpEmbedWidget` dichiara il
   segnale `processo-terminato` (`rdp_widget.py:58-60`) e lo emette (`rdp_widget.py:521`), ma
   `_apri_rdp` in modalità interna **non lo collega** (`PCM.py:1306-1318`), a differenza di tutti
   gli altri protocolli (confronta `PCM.py:1341`). Conseguenza: quando la sessione cade, la
   scheda non viene marcata `✖` e la riconnessione automatica non parte mai. Collegare il segnale.
3. **Il parametro `?mode=external` degli URI da riga di comando è ignorato.** `PCM.py:712` lo
   analizza in `mode_ext = qs.get("mode", [""])[0].lower() == "external"` e la variabile non viene
   mai usata. **Implementarlo** (forza la modalità di apertura del profilo) — è una riga — oppure
   rimuoverlo insieme alla documentazione corrispondente.
4. **Il contatore di sessione si congela dopo una riconnessione automatica.** Il timer di
   keepalive è creato una sola volta in `terminal_widget.py:72` e rimosso in `_on_child_exited`
   (`terminal_widget.py:454`), ma `avvia()` (`terminal_widget.py:189`) non lo ricrea. Dopo una
   riconnessione, durata, byte trasferiti e indicatore `●○○` restano fermi per sempre. Ricrearlo
   in `avvia()` se assente.
5. **Un pulsante è creato e mai mostrato.** `session_dialog.py:1331` costruisce `btn_manuale`, mai
   aggiunto a un contenitore: è invisibile. **Verificare prima di rimuovere**: stabilire se andava
   mostrato.
6. **Testo dell'interfaccia che consiglia una scelta insicura.** `translations.py:433` recita
   *"StrictHostKeyChecking (consigliato: disabilitato per lab)"*. Riformulare: la verifica della
   chiave host è la scelta corretta, la disattivazione è un'eccezione per laboratori isolati.
   Aggiornare in tutte e cinque le lingue. Collegato a SEC-4.
7. **Impostazione fantasma.** `config_manager.py:235` definisce `ssh.strict_host_check`, che
   **non viene letta da nessuna parte**: `session_command.py:181` e `:296` leggono solo il campo
   per profilo `strict_host`, e così `sftp_browser.py:213`. O si implementa come default globale
   per i nuovi profili, o si rimuove la chiave. Da decidere insieme a SEC-4.
8. **`display.sidebar_visible` non è mai usata.** Definita in `config_manager.py:242`, nessun
   lettore. Viene risolta da UX-1 punto 3.

**Accettazione.** Ogni punto verificato singolarmente nell'app in esecuzione.

---

# FASE 2 — Difetti bloccanti

Cinque bug che rendono inutilizzabili funzioni esistenti.

---

### BUG-1 — Pre-comando, Wake-on-LAN e jump host non funzionano (`UnboundLocalError`)

**Gravità: critica.** Tre funzioni pubblicizzate sono completamente inoperanti.

**Problema.** In `PCM.py:568-590`, la funzione annidata `_bg()`:

```python
def _bg():
    if pre_cmd:
        timeout = dati.get("pre_cmd_timeout", 15)                  # riga 570
        ...
    if wol_mac:
        err = self._invia_wol(wol_mac, dati.get("wol_wait", 20))   # riga 578
        ...
    if use_gateway:
        local_port, gw_proc = self._start_ssh_gateway(dati)        # riga 583
        ...
        dati = dict(dati)                                          # riga 587  ← causa
```

L'assegnamento a riga 587 rende `dati` **variabile locale per tutto `_bg`**, perché manca
`nonlocal`. Ogni lettura precedente (righe 570, 578, 583) solleva quindi `UnboundLocalError`. Il
percorso `_bg` viene imboccato ogni volta che il profilo ha un pre-comando, Wake-on-LAN o un jump
host — cioè **sempre, per tutte e tre le funzioni**. L'eccezione muore silenziosamente nel thread
daemon (`PCM.py:591`): la sessione non si apre e nessun errore compare.

**Intervento.** Rinominare la variabile locale invece di riassegnare quella catturata:

```python
def _bg():
    dati_loc = dict(dati)          # copia esplicita, subito
    if pre_cmd:
        timeout = dati_loc.get("pre_cmd_timeout", 15)
        ...
    if wol_mac:
        err = self._invia_wol(wol_mac, dati_loc.get("wol_wait", 20))
        ...
    if use_gateway:
        local_port, gw_proc = self._start_ssh_gateway(dati_loc)
        ...
        dati_loc["_gateway_tunnel"] = gw_proc
        dati_loc["_gateway_local_port"] = str(local_port)
    GLib.idle_add(self._apri_protocollo, proto, nome, dati_loc)
```

Avvolgere l'intero corpo di `_bg` in un `try/except` che registra l'eccezione (UX-3) e avvisa
l'utente via `GLib.idle_add(self._warn, ...)`: **un thread daemon non deve mai fallire in
silenzio.** Applicare la stessa protezione agli altri thread di `PCM.py` (`:1415`, `:1506`,
`:2171`).

**Accettazione.** Tre profili di prova — pre-comando (`echo test`), Wake-on-LAN, jump host — si
connettono correttamente. Un pre-comando che fallisce (`false`) produce un messaggio visibile.

---

### BUG-2 — Il wrapper della password VNC è sintatticamente rotto

**Problema.** `session_command.py:367-373` (`_passwd_wrap`) e la variante a `:414-421` costruiscono
una stringa `bash -c '...'` in cui le virgolette di `printf '%s'` **chiudono** la stringa quotata
esterna. Verificato eseguendo `shlex.split()` sull'output reale con password `S3cr et`:

```
RAW:    bash -c 'TMP=$(mktemp); printf '%s' 'S3cr et' | vncpasswd -f > "$TMP"; ... rm -f '$TMP''
TOKENS: ['bash', '-c', 'TMP=$(mktemp); printf %s S3cr', 'et | vncpasswd -f > "$TMP"; ...; rm -f $TMP']
```

Tre conseguenze:

1. Una password contenente uno **spazio** spezza il comando in due argomenti: la connessione
   fallisce senza spiegazione.
2. La password finisce **non quotata** nello script interno: se contiene `;`, `` ` ``, `$(...)` o
   `|` viene **eseguita come comando**. Rilevante perché le password possono arrivare da
   KeePassXC o da profili importati.
3. `rm -f $TMP` finisce fuori dalle virgolette: `$TMP` viene espanso dalla shell chiamante, dove è
   vuoto. Il comando diventa `rm -f` senza argomenti e **il file temporaneo con la password VNC
   non viene mai cancellato**, restando in `/tmp`.

**Intervento.** Non riparare il quoting a mano. Smettere di generare uno script shell e allinearsi
all'approccio già corretto di `vnc_widget.py:520-566`: creare il file password in Python con
`tempfile.mkstemp()`, scriverci il contenuto, passare al client solo il **percorso**. File creato
con 0600 e cancellato in un `finally`/`atexit` (vedi RES-3, che completa il ciclo di vita).

Se per ragioni di architettura la funzione deve restituire una stringa di comando, generarla con
`shlex.quote()` su **ogni** valore interpolato e aggiungere un test che verifichi il numero di
token prodotti da `shlex.split()`.

**Accettazione.** Un profilo VNC con password `a b;c$(id)` si connette, non esegue `id`, e non
lascia file in `/tmp` dopo la chiusura. Test automatico che lo dimostri (QUAL-2).

---

### BUG-3 — L'opzione keepalive SSH non ha alcun effetto

**Problema.** `session_command.py:182` costruisce sempre gli argomenti di base:

```python
args = [f"-p {_esc(port)}", f"-o StrictHostKeyChecking={strict}",
        "-o ServerAliveInterval=15", "-o ServerAliveCountMax=3"]
```

e poi, a `:189-190`:

```python
if p.get("keepalive"):
    args.append("-o ServerAliveInterval=60")
```

`ssh` applica la **prima** occorrenza di ogni opzione e ignora le successive: `ServerAliveInterval`
resta quindi sempre 15, e la casella "keepalive" del profilo non produce alcun effetto. Peggio, il
valore configurabile `ssh.keepalive_interval` di `config_manager.py:234` (default 60) non viene
letto da nessuna parte.

**Intervento.** Calcolare l'intervallo **prima** di costruire la lista e inserirlo una volta sola:
se `keepalive` è attivo usare `settings["ssh"]["keepalive_interval"]`, altrimenti 15. Verificare
lo stesso schema di duplicazione sulle altre opzioni `-o` della funzione.

**Accettazione.** Con keepalive attivo e `keepalive_interval` a 90, il comando generato contiene
esattamente un `ServerAliveInterval=90`. Test unitario che lo verifichi.

---

### BUG-4 — `_wrap_pre` costruisce un doppio livello di quoting fragile

**Problema.** `session_command.py:126-142` avvolge il comando in `bash -c '...'` applicando solo
`_esc()` (escaping dei soli apici singoli) sia al pre-comando sia al comando principale. Due
difetti:

- Il testo finisce dentro un `echo ">>> ..."` a virgolette doppie: un pre-comando contenente `"`,
  `$` o backtick rompe la stringa o subisce espansione dalla shell.
- `cmd_esc` contiene già la password per RDP/FTP/VNC (SEC-2), quindi il difetto di quoting si
  somma a quello di BUG-2.

Il pre-comando è per definizione fornito dall'utente, quindi non è un'escalation di privilegi; è
però un difetto di correttezza che rende inaffidabile una funzione documentata.

**Intervento.** Ricostruire con `shlex.quote()` su ogni parte interpolata, o meglio evitare del
tutto la shell annidata: eseguire il pre-comando con `subprocess.run` in Python (come già fa
`PCM.py:573`) e lanciare il comando principale solo se il primo è andato a buon fine. Questo
elimina un intero livello di quoting.

**Accettazione.** Un pre-comando `echo "ciao $USER"` viene eseguito correttamente e il comando
principale parte. Test unitario con apici, virgolette e `$`.

---

### BUG-5 — Codice morto e valori mai usati

Pulizia mirata, a basso rischio.

1. **`PCM.py:1067` e `PCM.py:1101` definiscono entrambi `_apri_cluster`.** La seconda sovrascrive
   la prima: 17 righe irraggiungibili. Di conseguenza anche `_connect_to_cluster` (`PCM.py:1156`),
   chiamato solo dalla versione morta, è irraggiungibile.
   **Verificare prima di rimuovere**: se la versione morta contiene logica assente nella viva, si
   tratta di una regressione da recuperare, non di codice obsoleto. Annotare la scelta.
2. **`PCM.py:128`** — `pcm_context_actions as _plugin_context_actions` importato e mai usato: una
   funzione dei plugin ("azioni contestuali") è dichiarata e mai collegata all'interfaccia.
   **Verificare prima di rimuovere**: potrebbe essere una funzione incompleta da completare.
3. **`config_manager.py:40`** — `if first_run := not os.path.exists(SESSIONS_FILE):` — il nome
   `first_run` non viene mai riletto: sostituire con un `if` semplice.
4. **`session_command.py:177`** — `pwd = p.get("password", "")` in `_build_ssh()`: assegnata e mai
   usata (residuo di un tentativo `sshpass` rimosso). Eliminare.
5. **Import inutilizzati confermati**, da rimuovere:
   `config_manager.py:8` (`secrets`) · `session_command.py:9` (`subprocess`) ·
   `session_command.py:12-13` (`MODE_PANEL`, `MODE_RDP_EMBED`, `MODE_EMBED`) ·
   `PCM.py:99` (`Gdk`, `GObject`), `:107` (`TERMINAL_THEMES`), `:113` (`check_dipendenze`),
   `:855` (`shutil as _sh`) · `session_dialog.py:19` (`installed_tools`), `:1619`
   (`check_password_strength`) · `session_panel.py:17` (`Gdk`) · `tunnel_manager.py:17`
   (`Gdk`, `Pango`) · `terminal_highlight.py:11` (`Gtk`) · `terminal_widget.py:18` (`subprocess`) ·
   `deps_dialog.py:3` (`GObject`) · `vnc_widget.py:413` (`GdkPixbuf`) · `winscp_widget.py:28`
   (`GdkPixbuf`) · `plugins/plugin_base.py:11-12` (`os`, `Any`) · `plugins/plugin_manager.py:18`
   (`pcm_list_plugins`) · `plugins/builtins/spice_client/__init__.py:6` (`shlex`) ·
   nei test: `tests/test_session_command.py:3,4,8`, `tests/test_cluster.py:8`,
   `tests/test_new_features.py:5,12,20`.
6. **Variabili assegnate e mai lette**, da eliminare: `PCM.py:499` (`p_icon`), `PCM.py:3035` (`p`),
   `deps_dialog.py:64` (`detected`), `rdp_widget.py:472-473` (`w`, `h`), `settings_dialog.py:499`
   (`model`), `winscp_widget.py:266` (`col`), `winscp_widget.py:895` (`n`).
7. **`crypto_manager.py:106, 167, 297`** — `Fernet, InvalidToken, PBKDF2HMAC, hashes = _get_fernet()`
   con parte dei nomi inutilizzati. Il caso di `:297` non è cosmetico: `InvalidToken` è importato
   e **non usato**, quindi un dato corrotto non viene distinto da un errore generico. Vedi SEC-5.
8. **Blocchi `__main__` di debug** spediti nel pacchetto: `importer.py:434-438` (`_test_stampa`) e
   `:820-876`, `config_manager.py:517-521`, `protocols.py:208-212`. Quello di `importer.py:820-876`
   è una vera interfaccia a riga di comando: **conservarlo**. Valutare la rimozione degli altri due.

**Accettazione.** L'applicazione si avvia e tutte le funzioni restano operative;
`python3 -m py_compile` pulito; nessuna rimozione cambia il comportamento osservabile.

---

# FASE 3 — Sicurezza

---

### SEC-1 — I file di configurazione sono leggibili da altri utenti

**Problema.** `config_manager.py:278-283` — `_write_json_secure()` usa
`os.open(path, O_WRONLY|O_CREAT|O_TRUNC, 0o600)`. Il parametro `mode` di `os.open` **si applica
solo alla creazione**: sui file preesistenti i permessi non vengono corretti. Stato reale
osservato sul disco:

```
-rw-rw-r--  connections.json      (0664)
-rw-rw-r--  pcm_settings.json     (0664)
```

`connections.json` contiene le password **in chiaro** se la cifratura non è attiva.
`pcm_settings.json` contiene `crypto.salt`, `crypto.canary`, `crypto.verify` e i
`credential_profiles`. Il token `verify` leggibile consente un **attacco a dizionario offline**
sulla password principale (mitigato solo dalle 480.000 iterazioni PBKDF2).

**Intervento.**
1. In `_write_json_secure()`, aggiungere `os.chmod(path, 0o600)` **dopo** la scrittura, così da
   correggere anche i file esistenti.
2. Scrivere in modo **atomico**: file temporaneo nella stessa cartella, `chmod 0600`, poi
   `os.replace()`. Elimina anche il rischio di corruzione da terminazione a metà scrittura, che è
   la causa più probabile dello scenario descritto in UX-3 punto 2.
3. All'avvio, verificare i permessi di `connections.json`, `pcm_settings.json` e `audit_log.json`;
   se più permissivi di 0600, correggerli e registrare un avviso.
4. Applicare lo stesso trattamento alla cartella di configurazione (0700), inclusa quella creata
   da `_resolve_config_dir()` per AppImage (`config_manager.py:22-29`), che oggi usa
   `os.makedirs(d, exist_ok=True)` senza `mode`.

**Accettazione.** Dopo un avvio, tutti e tre i file sono 0600. Impostandone uno a 0644 a mano e
riavviando, viene riportato a 0600 con una riga di log.

---

### SEC-2 — Password esposte nella riga di comando

**Problema.** Le password compaiono in `/proc/<pid>/cmdline`, leggibile da qualunque utente locale
con `ps aux` (`hidepid=0` è il default su gran parte delle distribuzioni). Tutte le stringhe
prodotte da `session_command.py` vengono eseguite da `terminal_widget.py:207`
(`argv = ["/bin/sh", "-c", comando]`), quindi la password compare **sia** nella riga di comando
del client **sia** in quella della shell padre.

| Punto | Esposizione |
|---|---|
| `session_command.py:328` | RDP: `/p:'<password>'` |
| `session_command.py:263, 268, 308` | FTP/SFTP via `lftp` e `ftp`: credenziali nell'URI |
| `session_command.py:370, 417` | VNC (vedi BUG-2) |
| `rdp_widget.py:210, 287, 650, 665` | `/p:<pwd>` e `-p<pwd>` |

`rdp_widget.py:214-216` e `PCM.py:1328-1330` mascherano `/p:` in `****` **solo nell'etichetta
mostrata a schermo**; l'`argv` reale resta in chiaro. È un mascheramento cosmetico, da non
scambiare per una mitigazione.

Nel progetto esiste già l'approccio corretto da riusare: `tunnel_manager.py:489-490` usa
`sshpass -e` con la password nell'ambiente (`SSHPASS`), che non compare in `ps`. Anche
`PCM.py:838-849` (script askpass) è ben realizzato: la password arriva dall'ambiente, non dal
file.

**Intervento, per protocollo, in ordine di preferenza:**

- **RDP/FreeRDP:** usare `/from-stdin`, oppure la variabile d'ambiente `FREERDP_PASSWORD` dove
  supportata. Verificare quale sia disponibile nella versione installata di `xfreerdp3`/`xfreerdp`
  prima di scegliere.
- **VNC:** già risolto da BUG-2 (file password 0600, solo il percorso in `argv`).
- **FTP/SFTP via lftp:** passare le credenziali su stdin invece che nell'URI in `argv`.
- Dove nessuna alternativa esiste, documentarlo nel README e **avvisare nell'interfaccia** al
  salvataggio di una password per quel protocollo.

**Nota.** L'ambiente (`/proc/<pid>/environ`) è leggibile solo dallo stesso UID: netto
miglioramento rispetto ad `argv`, non protezione assoluta. Preferire comunque lo stdin.

**Accettazione.** Con una sessione RDP e una FTP attive, `ps aux | grep -i <password>` non
restituisce nulla.

---

### SEC-3 — I log di sessione finiscono in `/tmp` con permessi aperti

**Problema.** `terminal_widget.py:201-206` registra la sessione con `script(1)`:

```python
os.makedirs(self._log_dir, exist_ok=True)
log_file = os.path.join(self._log_dir, f"pcm_{ts}.log")
argv = ["/bin/sh", "-c", f"script -q -c {_shell_quote(comando)} {_shell_quote(log_file)}"]
```

Quattro problemi:
1. Il default di `log_dir` è **`/tmp/pcm_logs`** (`session_dialog.py:626` e `:1897`) — cartella
   condivisa e prevedibile. Da notare che `config_manager.py:229` usa già il default corretto
   (`~/.local/share/pcm/logs`): **i due valori sono incoerenti fra loro.**
2. `os.makedirs(..., exist_ok=True)` senza `mode` → 0755; il file creato da `script` eredita
   l'umask → 0644. **Qualunque utente locale può leggere il transcript completo della sessione.**
3. `exist_ok=True` su un percorso prevedibile in `/tmp` consente a un altro utente di pre-creare
   `/tmp/pcm_logs` di sua proprietà e leggerne il contenuto (o piazzarvi un collegamento
   simbolico).
4. La stringa `comando` passata a `script -c` contiene la password in chiaro per RDP/FTP/SFTP/VNC
   (SEC-2), quindi la password compare anche nella riga di comando di `script`.

**Intervento.**
1. Allineare il default di `session_dialog.py:626` e `:1897` a quello di `config_manager.py:229`.
   Migrare i valori `/tmp/pcm_logs` già salvati nelle impostazioni degli utenti.
2. `os.makedirs(self._log_dir, mode=0o700, exist_ok=True)`; se la cartella esiste già, verificare
   che il proprietario sia l'utente corrente e che non sia scrivibile da altri — altrimenti
   rifiutare di scrivere e avvisare.
3. Creare il file di log con 0600 **prima** di passarlo a `script`.
4. Se `log_dir` punta a una cartella scrivibile da tutti, mostrare un avviso nelle impostazioni.

**Accettazione.** I log sono in `~/.local/share/pcm/logs`, cartella 0700 e file 0600. Con `log_dir`
impostato a una cartella di proprietà altrui, la registrazione viene rifiutata con un messaggio.

---

### SEC-4 — Verifica delle identità disattivata per impostazione predefinita

**Problema.** Tre incoerenze che riducono le garanzie sul canale su cui viaggia la password.

1. **Politica host key incoerente fra i pannelli.** `sftp_browser.py:212-217` usa
   `paramiko.AutoAddPolicy()` quando `strict_host` è falso — e il default è falso ovunque
   (`session_dialog.py:1827`, `config_manager.py:235`). È **accettazione cieca della chiave host**
   su un canale dove subito dopo viene inviata la password (`sftp_browser.py:222`). Gli altri
   moduli che usano paramiko sullo stesso profilo sono invece sicuri: `winscp_widget.py:787,801`
   usa `RejectPolicy()` esplicito, e `sysmon_widget.py:264`, `log_viewer.py:190`,
   `cron_widget.py:370`, `panel_monitor.py:768` ereditano il `RejectPolicy` predefinito.
   **A parità di profilo, il comportamento cambia a seconda del pannello che si apre.**
2. **FTPS senza validazione del certificato.** `sftp_browser.py:767-770` e
   `winscp_widget.py:1646-1650` istanziano `ftplib.FTP_TLS()` senza passare un `context`: in quel
   caso la libreria standard usa `ssl._create_stdlib_context()`, con `verify_mode=CERT_NONE` e
   `check_hostname=False`. Il TLS diventa cifratura opportunistica, senza difesa da un
   intermediario attivo. In `winscp_widget.py:1649` il `login()` avviene per giunta **prima** di
   `prot_p()`.
3. **`/cert:ignore` fisso nel codice** per RDP in tre punti (`session_command.py:329`,
   `rdp_widget.py:200`, `rdp_widget.py:658`), senza possibilità di configurazione.

Da notare anche `PCM.py:628`: il tunnel verso il jump host forza
`StrictHostKeyChecking=accept-new` **ignorando** il `strict_host` del profilo, mentre
`tunnel_manager.py:564` usa `yes`. Terza incoerenza sullo stesso concetto.

**Intervento.**
1. Uniformare la politica host key: `sftp_browser.py` deve comportarsi come gli altri moduli.
   Sostituire `AutoAddPolicy` con una politica che, davanti a una chiave sconosciuta, **chiede
   conferma all'utente** mostrando l'impronta digitale, e la registra in `known_hosts` solo su
   accettazione esplicita. È il comportamento che l'utente si aspetta da un client SSH.
2. FTPS: costruire un `ssl.create_default_context()` (verifica catena e nome host) e passarlo a
   `FTP_TLS`. Prevedere un'opzione per profilo *"accetta certificato non verificabile"*,
   disattivata per impostazione predefinita, per i server con certificato autofirmato. In
   `winscp_widget.py` invertire l'ordine: `prot_p()` prima del `login()`.
3. RDP: rendere `/cert:ignore` un'opzione di profilo, disattivata per impostazione predefinita.
4. Far rispettare `strict_host` anche al tunnel gateway (`PCM.py:628`).
5. Aggiornare il testo di `translations.py:433` (UX-5 punto 6) e decidere il destino di
   `ssh.strict_host_check` (UX-5 punto 7).

**Compatibilità.** Sono modifiche che possono interrompere connessioni oggi funzionanti verso
apparati con certificati autofirmati. Per questo ogni punto prevede una deroga esplicita e per
profilo. Segnalarlo nelle note di rilascio.

**Accettazione.** Un server SSH sconosciuto aperto dal browser SFTP mostra l'impronta e chiede
conferma. Un server FTPS con certificato non valido viene rifiutato salvo deroga esplicita.

---

### SEC-5 — La chiave di cifratura resta in memoria per sempre

**Problema.** `crypto_manager.py:198-202` definisce `lock()`, che azzera la chiave derivata. Una
ricerca su tutto il repository non trova **nessun chiamante**: gli unici riferimenti sono la
definizione e la sua menzione nella docstring a `crypto_manager.py:31`. Non esiste blocco
automatico, nessuna chiave `auto_lock` in `DEFAULT_SETTINGS`, nessuna voce di menu "Blocca". Dopo
lo sblocco iniziale (`PCM.py:301`) la chiave resta in memoria per tutta la durata del processo,
anche a schermo bloccato o dopo ore di inattività.

Due difetti correlati nello stesso modulo, **più gravi del primo** perché comportano perdita di
dati:

- **`crypto_manager.py:271-274`** — `encrypt_field()` restituisce il valore **in chiaro** se la
  chiave è assente, senza segnalarlo. Un salvataggio effettuato ad applicazione bloccata riscrive
  le password in chiaro su `connections.json`.
- **`crypto_manager.py:288-292`** — `decrypt_field()` restituisce `""` sia quando la chiave manca
  sia quando il token è corrotto: un errore di decifratura è indistinguibile da "password vuota"
  e, combinato con `save_profiles()`, può **sovrascrivere silenziosamente le credenziali con
  stringhe vuote**. È il rischio di perdita dati più serio del progetto.

**Intervento.**
1. Aggiungere `general.auto_lock_minutes` a `DEFAULT_SETTINGS` (default 15, `0` = disattivato) e
   la relativa impostazione nell'interfaccia.
2. Implementare il blocco per inattività: azzerare un timer sull'attività di tastiera/mouse della
   finestra; alla scadenza chiamare `crypto_manager.lock()` e mostrare il dialogo di sblocco.
   Aggiungere una voce di menu "Blocca ora". Il timer va registrato e cancellato secondo RES-1.
3. `encrypt_field()`: sollevare un'eccezione invece di restituire il valore in chiaro quando la
   cifratura è attiva ma la chiave è assente. `save_profiles()` deve intercettarla, **rifiutare la
   scrittura** e avvisare l'utente.
4. `decrypt_field()`: distinguere `InvalidToken` (dato corrotto) da chiave assente e propagare
   l'informazione al chiamante. `save_profiles()` non deve **mai** sovrascrivere un campo non
   decifrato correttamente: in quel caso conservare il valore cifrato originale. `InvalidToken` è
   già importato e inutilizzato a `crypto_manager.py:297` (vedi BUG-5 punto 7).
5. Valutare un limite di tentativi o un ritardo progressivo sul dialogo di sblocco
   (`PCM.py:296-315`), che oggi non ne ha. Priorità bassa: l'attacco offline sul file resta la via
   più economica, ed è SEC-1 a mitigarlo.

**Accettazione.** Con `auto_lock_minutes=1`, dopo un minuto di inattività l'app chiede la
password. Ad app bloccata, un salvataggio profilo viene rifiutato con messaggio, non esegue una
scrittura in chiaro, e le credenziali cifrate restano intatte. Test automatico che verifichi che
un token corrotto non produce sovrascrittura con stringa vuota.

---

### SEC-6 — Interpolazione non quotata in stringhe shell

**Problema.** Oltre a BUG-2, dati provenienti dal profilo finiscono non quotati in stringhe
eseguite da `/bin/sh -c`:

- `session_command.py:371, 382-383, 399-400, 404, 407, 409-421` — `host` e `port` VNC **mai**
  quotati (`{host}::{port}`, `vnc://{host}:{port}`).
- `session_command.py:268` — `host`/`port` FTP dentro `printf "open {host} {port}..."` in contesto
  a virgolette doppie: `$(...)` e i backtick vengono espansi.
- `session_dialog.py:1348-1362` — `cmd_str = f"ssh-copy-id -i '{pub_path}' -p {port} {target}"`,
  poi eseguito con `bash -c`: `target` e `port` non sono quotati e `pub_path` è racchiuso in apici
  singoli senza escaping.

Il vettore realistico è un **profilo importato o condiviso**: `importer.py` legge Remmina, RDM,
PuTTY, MobaXterm e `ssh_config`, quindi un campo `host` malevolo esegue comandi arbitrari
all'apertura.

**Intervento.**
1. Applicare `_q()` (già presente, `session_command.py:482-484`, è `shlex.quote`) a **ogni** valore
   interpolato nei punti elencati. Il helper `_esc()` (`session_command.py:477-479`) fa solo
   l'escaping degli apici singoli e presuppone un contesto di quoting che spesso non è quello
   reale: **preferire sempre `_q()`**, e usare `_esc()` solo dove il contesto è dimostrabilmente a
   singoli apici.
2. Come difesa aggiuntiva, validare `host` e `port` in `protocols.py::validate_profiles` (già
   invocata da `config_manager.py:57`): rifiutare host con spazi o metacaratteri di shell, e porte
   non numeriche. Applicare la validazione **anche in `importer.py`**, al momento
   dell'importazione, così che un profilo malevolo venga segnalato subito e non alla prima
   apertura.

**Accettazione.** Un profilo con `host = "x; touch /tmp/pwned; #"` non crea `/tmp/pwned` per
nessun protocollo, e l'importazione di un file che lo contiene produce un avviso. Test automatici
che coprano i casi (QUAL-2).

---

### SEC-7 — Il segreto TOTP non viene cifrato

**Problema.** `crypto_manager.py:69` definisce `_FIELDS_TO_ENCRYPT = ("user", "password")`. Il
segreto TOTP salvato nel profilo **non è incluso**: resta in chiaro in `connections.json` anche
con la cifratura attiva — su un file che oggi è per giunta 0664 (SEC-1). Chi lo legge può generare
codici a due fattori validi in perpetuo.

**Intervento.** Aggiungere il campo del segreto TOTP (verificarne il nome esatto in
`session_dialog.py` e `totp_manager.py`) a `_FIELDS_TO_ENCRYPT`. Prevedere la migrazione dei
profili esistenti: al primo salvataggio con cifratura attiva il campo viene cifrato in modo
trasparente, poiché `encrypt_field()` ignora i valori già prefissati `ENC:`
(`crypto_manager.py:272`). Verificare che `decrypt_profile()` lo gestisca simmetricamente e che
nessun percorso di lettura assuma il testo in chiaro.

**Accettazione.** Con cifratura attiva, `grep` del segreto TOTP in `connections.json` non trova
nulla; il codice TOTP continua a essere generato correttamente.

---

### SEC-8 — La password del profilo viene inviata ai prompt di secondo fattore

**Problema.** `terminal_widget.py:285-292` — `imposta_auto_password()` usa un'espressione regolare
che intercetta, oltre ai prompt di password, anche:

```
|[Pp]asscode:\s*$
|[Vv]erification [Cc]ode:\s*$
```

La **password del profilo** viene quindi digitata automaticamente anche in un prompt di codice a
due fattori. Conseguenze: il secondo fattore fallisce (con `max_trigger: 3`, fino a tre tentativi
errati, con rischio di blocco dell'account), e la password viene inviata a un campo che il server
potrebbe registrare in chiaro nei log, dato che non è un prompt di password.

Problema correlato: `PCM.py:690-695` — `except ImportError: pass` sul controllo di cifratura nel
percorso di apertura da URI. Se `cryptography` manca, il flusso prosegue senza sblocco e invia
come password la stringa cifrata `ENC:…`, che verrà digitata sul prompt remoto.

**Intervento.**
1. Rimuovere `[Pp]asscode:` e `[Vv]erification [Cc]ode:` dall'espressione della password. Se
   l'obiettivo era supportare il secondo fattore, va gestito da `totp_manager.py` come regola
   `expect` distinta, con il codice TOTP e non con la password.
2. Rendere l'insieme dei prompt riconosciuti configurabile per profilo, così che un caso
   particolare non richieda di modificare il codice.
3. `PCM.py:690-695`: se `cryptography` manca ma il profilo contiene valori `ENC:`, **interrompere**
   con un messaggio esplicito invece di inviare il testo cifrato.

**Accettazione.** Su un server con secondo fattore, la password non viene inviata al prompt del
codice. Con `cryptography` disinstallato e un profilo cifrato, l'apertura da URI si ferma con un
errore comprensibile.

---

### SEC-9 — KeePassXC: nessun rifiuto esplicito senza PyNaCl

**Problema.** `keepassxc_manager.py:87-91` imposta `self._priv = self._pub = None` quando PyNaCl
manca, ma `_send_encrypted` (`:127`) fallirebbe con `AttributeError` invece di rifiutare
esplicitamente una connessione non cifrata. Il resto del modulo è realizzato correttamente:
trasporto via `keepassxc-proxy` con framing binario, nessun segreto in `argv` o nell'ambiente,
chiave privata effimera per istanza, `client_id` da `secrets.token_bytes(24)`.

Difetto minore: `close()` (`:248-256`) è invocato solo da `do_destroy()` (`:389`); se il dialogo
non viene distrutto, il processo proxy resta vivo.

**Intervento.** Aggiungere un controllo esplicito all'ingresso di `_send_encrypted` (e del metodo
di connessione) che sollevi un errore chiaro se le chiavi non sono disponibili. Assicurare la
chiusura del proxy anche sui percorsi che non passano da `do_destroy` (`try/finally`). Vedi anche
QUAL-3: `pynacl` non è dichiarato fra le dipendenze.

**Accettazione.** Con PyNaCl disinstallato, l'uso di KeePassXC produce un messaggio comprensibile
e nessun `AttributeError`; il processo proxy non resta in esecuzione dopo la chiusura del dialogo.

---

# FASE 4 — Risorse: timer, processi, file temporanei

Nessuno di questi problemi è visibile subito; si manifestano dopo ore di uso come consumo di
memoria, processi zombie e finestre fantasma.

---

### RES-1 — Timer GLib mai cancellati

Ogni `GLib.timeout_add`/`io_add_watch` il cui identificatore non viene conservato continua a
essere eseguito dopo la distruzione del widget, agendo su oggetti deallocati.

| Punto | Problema |
|---|---|
| `PCM.py:1811` | Timer di riconnessione automatica: id non salvato. Chiudendo la scheda entro il ritardo, `_do_reconnect` (`PCM.py:936-949`) riavvia comunque un processo SSH che non appartiene più ad alcuna scheda e resta invisibile all'utente. `_chiudi_tab` (`PCM.py:1731-1795`) non lo annulla. **Il più grave.** |
| `rdp_widget.py:415-489` | Catena `_step1…_step5` di riposizionamento finestra, nessun id salvato. `chiudi_processo` (`:556-562`) rimuove solo `_poll_source` e `_monitor_source`: i passi successivi continuano a invocare `xdotool` su una finestra morta e a scrivere su `self._info` di un widget distrutto. |
| `rdp_widget.py:243` | `GLib.io_add_watch` su un descrittore nudo, mai rimosso. Il `Popen` viene deallocato, il descrittore chiuso, e il kernel può riassegnarlo: il watch resta agganciato e `_on_rdp_output` (`:586-598`) scrive su un widget distrutto. |
| `tunnel_manager.py:510` | Stesso schema; `_on_destroy` (`:596-598`) rimuove solo `_poll_source`. `_scrivi_log` (`:523`) tocca il buffer di un dialogo distrutto. |
| `vnc_widget.py:265` | Riconnessione senza controllo del flag `_closed`: chiudendo entro 800 ms si agisce su un display già chiuso. |
| `vnc_widget.py:545-553` | `_check_proc`: id non salvato, mentre l'equivalente `rdp_widget.py:495-522` lo salva. Incoerenza fra i due moduli. |
| `PCM.py:208, 447` | Due timer di finestra a 3 s, mai rimossi in `_on_close` (`PCM.py:2504`). |
| `terminal_widget.py:356-359` | Timer di antirimbalzo e connessione `contents-changed` non disconnessi in `chiudi_processo`. |
| `PCM.py:849` | Timer di pulizia dello script askpass: vedi RES-3. |

Da verificare inoltre le callback che raggiungono widget già distrutti: `PCM.py:2168-2171`
(`_test_connettivita`, probe a 5 s mentre il dialogo può essere già chiuso da `:2157-2158`),
`PCM.py:1397-1399` e `:1502-1504` (closure che catturano `paned` e `placeholder` durante un probe
a 3 s).

**Intervento.** Regola uniforme: **ogni** `timeout_add`/`io_add_watch` salva il proprio id in un
attributo di istanza, e ogni `chiudi_processo`/`destroy` li rimuove tutti con `GLib.source_remove`.
Introdurre un piccolo aiuto condiviso (lista `self._sources` con metodo `_clear_sources()`) e
adottarlo in tutti i widget elencati. Aggiungere un flag `_closed` controllato all'inizio di ogni
callback, sul modello già presente in `vnc_widget.py`.

**Accettazione.** Aprendo e chiudendo 20 schede RDP/VNC/SSH in successione rapida, nessun errore in
console e nessuna crescita del numero di sorgenti GLib attive.

---

### RES-2 — Processi figli mai attesi e non terminati all'uscita

**Problema.** Non esistono nel progetto né gestore di `SIGCHLD`, né `GLib.child_watch_add`, né
`waitpid`: ogni `Popen` non atteso lascia uno zombie fino alla chiusura di PCM.

- `rdp_widget.py:541, 548` — `Popen(["xdotool", "windowfocus", ...])` **a ogni clic e a ogni
  cambio di focus**: uno zombie per clic. È la sorgente più prolifica del codice.
- `PCM.py:645` (gateway SSH) — `_chiudi_tab` (`PCM.py:1782`) chiama `.terminate()` **senza**
  `.wait()`.
- `PCM.py:876` (terminale esterno), `PCM.py:2437` (`xdg-open`), `tunnel_manager.py:493`
  (`killpg` senza `wait`), `vnc_widget.py:510`.

Fanno eccezione, correttamente: `rdp_widget.py:563-580` e `vnc_widget.py:592-598`.

**Alla chiusura dell'applicazione i processi non vengono terminati.** `PCM.py:2583-2586`:

```python
for i in range(self._notebook.get_n_pages()):
    page = self._notebook.get_nth_page(i)
    if page and hasattr(page, "chiudi_processo"):
        page.chiudi_processo()
```

Tre difetti cumulativi:
1. **`self._notebook2` è ignorato**: tutte le schede spostate nel pannello affiancato
   (`PCM.py:1600`) non vengono chiuse.
2. **I contenitori `Gtk.Paned` non hanno `chiudi_processo`**: ogni scheda con browser SFTP
   laterale (`PCM.py:1275`, `:891-899`) fallisce il test `hasattr` e i suoi figli non ricevono mai
   la chiamata. `_chiudi_tab` (`PCM.py:1786-1791`) la discesa nei figli la fa correttamente: qui no.
3. **I tunnel gateway non vengono terminati**: `_dati["_gateway_tunnel"]` è gestito solo in
   `_chiudi_tab`.

Risultato: uscendo dall'applicazione restano orfani `xfreerdp`, `vncviewer` e i tunnel `ssh -N`,
che sopravvivono anche grazie a `preexec_fn=os.setsid` (`rdp_widget.py:236`,
`tunnel_manager.py:495`).

**Intervento.**
1. Introdurre un helper condiviso `termina_processo(proc, timeout=2)` che esegua `terminate()` →
   `wait(timeout)` → `kill()` → `wait()`. Il modello corretto esiste già in `rdp_widget.py:563-580`
   e `vnc_widget.py:592-598`: estrarlo e riusarlo ovunque.
2. Per `xdotool` (`rdp_widget.py:541,548`) usare `subprocess.run(..., timeout=…)`, che attende già,
   invece di `Popen`.
3. Riscrivere la chiusura in `_on_close` come funzione ricorsiva che percorra **entrambi** i
   notebook e discenda nei contenitori, riusando la logica corretta di `_chiudi_tab:1786-1791`.
   Terminare anche i tunnel gateway.
4. Definire un contratto esplicito per il ciclo di vita dei widget: una classe base astratta (o
   almeno un `Protocol`) con `chiudi_processo()`, implementata da `TerminalWidget`,
   `RdpEmbedWidget`, le tre classi VNC (`vnc_widget.py:57, 448, 612`), `SysMonitorWidget`,
   `CronWidget`, `InfoPanelWidget`. È il contratto implicito basato su `hasattr` a causare il
   difetto 2: con un'interfaccia esplicita un `Gtk.Paned` non può più passare inosservato.
5. Uniformare la semantica di terminazione: RDP usa `preexec_fn=os.setsid` + `killpg` (uccide il
   gruppo di processi), VNC no. Decidere quale sia corretta per ciascun caso e documentarlo.

**Accettazione.** Dopo apertura e chiusura di 10 sessioni miste e uscita dall'applicazione,
`ps aux | grep -E 'xfreerdp|vncviewer|ssh -N'` non restituisce nulla e non restano processi in
stato `Z`.

---

### RES-3 — File temporanei con credenziali che sopravvivono

| Punto | Problema |
|---|---|
| `vnc_widget.py:556-566` | `_avvia_client` può essere richiamato più volte (pulsante Riconnetti, `:482`) e **sovrascrive `self._passwd_file`** ogni volta; `chiudi_processo` (`:601-605`) cancella solo l'ultimo. **Ogni riconnessione lascia un file password in `/tmp`.** Nessuna pulizia in caso di arresto anomalo. |
| `session_command.py:369-372, 414-421` | Il `rm -f` non funziona affatto (BUG-2). |
| `PCM.py:838-849` | Script askpass cancellato da un timer a 5 s: se l'app esce prima, resta. Il contenuto **non** è sensibile (la password arriva dall'ambiente), quindi impatto basso. È il percorso meglio realizzato del progetto. |
| `sftp_editor.py:259` | File remoti scaricati per la modifica; `os.unlink` silenziato a `:362-363`. Possono contenere dati riservati. |

Nota su `vnc_widget.py:558-561`: l'"offuscamento" è uno XOR con la chiave costante
`[23,82,107,6,35,78,88,7]` — la chiave DES fissa dello standard VNC. **Non è cifratura** ed è
banalmente reversibile. Va trattato come testo in chiaro: le uniche difese reali sono i permessi
0600 e la cancellazione affidabile. Non "migliorarlo" con un altro schema fatto in casa.

**Intervento.** Registrare ogni file temporaneo contenente segreti in una lista di istanza;
cancellare **tutti** gli elementi in `chiudi_processo`; installare un gestore `atexit` come rete di
sicurezza; creare sempre con `mkstemp` seguito da `os.chmod(0o600)` esplicito. Valutare `/run/user/<uid>`
(tmpfs privata, 0700) al posto di `/tmp` dove disponibile.

**Accettazione.** Dopo cinque riconnessioni VNC e la chiusura dell'app, `ls /tmp/pcm_vnc_*` non
restituisce nulla.

---

# FASE 5 — Qualità del codice

---

### QUAL-1 — I test non vengono mai eseguiti

**Stato.** `gtk3/tests/` contiene 5 file, 814 righe, ~60 test:

| File | Copre | Test |
|---|---|---|
| `test_config_manager.py` | profili, impostazioni, variabili, recenti, audit | 17 |
| `test_session_command.py` | `build_command`, `_wrap_pre`, `_esc` | 12 |
| `test_translations.py` | coerenza delle chiavi i18n | 6 |
| `test_cluster.py` | `cluster_dialog` e selezione sessioni | 12 |
| `test_new_features.py` | plugin, ereditarietà modelli, TOTP | 20 |

Ma:
- Non esiste `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini` né `conftest.py` in tutto il
  repository. Ogni file replica a mano `sys.path.insert` (`test_config_manager.py:7`,
  `test_session_command.py:6`).
- **La CI non li esegue**: `.github/workflows/build.yml:47-49` esegue solo
  `bash linuxbuild/build.sh`. `grep pytest` su tutti i workflow, `linuxbuild/`, `setup.sh` e
  `packaging/`: zero occorrenze.
- `pytest` non compare in `requirements.txt`.

**Intervento.** Aggiungere `gtk3/conftest.py` che sistemi `sys.path` una volta sola; aggiungere
`pyproject.toml` con la configurazione di pytest; creare `requirements-dev.txt` con `pytest`;
aggiungere un passo alla CI che esegua la suite **prima** della build. Rimuovere i `sys.path.insert`
duplicati. Verificare che i test girino senza display grafico (i moduli che importano GTK vanno
isolati o marcati).

---

### QUAL-2 — Test mancanti sui moduli critici

- **`crypto_manager.py` — zero test.** Nessun file di test lo importa. È il modulo che gestisce
  PBKDF2, Fernet, il canary di verifica e lock/unlock.
- **`importer.py` (876 righe) — zero test.** È il codice più esposto a input esterno malformato
  (Remmina, RDM, PuTTY, `ssh_config`, MobaXterm). Ha solo una modalità di prova manuale
  (`importer.py:434`).
- **`session_command.py` — copertura parziale**: testati ssh/telnet/rdp/mosh/serial/exec; non
  testati `_build_sftp`, `_build_ftp`, `_build_vnc`, `_build_rdp` con credenziali, il tunnel SSH,
  `check_dipendenze`. **Nessun test di iniezione shell**, benché il modulo interpoli dati di
  profilo in stringhe `bash -c`.
- Senza alcun test: `tunnel_manager.py`, `keepassxc_manager.py`, `protocols.py`, `themes.py`,
  `password_tools.py`, `terminal_highlight.py`, tutti i widget.
- `tests/test_translations.py:18-20` esamina solo i file di primo livello: la cartella `plugins/`
  è esclusa dal controllo i18n.

**Intervento, in quest'ordine.**
1. **Test di iniezione per `session_command.py`**: per ogni protocollo, un profilo con
   `host`/`user`/`password` contenenti `; touch /tmp/pwned`, spazi, apici, `$(...)`, backtick.
   Verificare con `shlex.split()` che i metacaratteri finiscano in un unico token. Questi test
   proteggono BUG-2 e SEC-6 dalle regressioni: **scriverli contestualmente a quelle correzioni.**
2. **Test per `crypto_manager.py`**: ciclo setup/unlock/lock, password errata, cambio password,
   disattivazione, e soprattutto **token corrotto che non deve produrre sovrascrittura con stringa
   vuota** (SEC-5), più il campo TOTP cifrato (SEC-7).
3. **Test per `importer.py`**: un file di esempio per formato, più input troncati e malformati,
   incluso un profilo con `host` malevolo (SEC-6 punto 2).
4. **Test per `session_command.py`** sull'intervallo di keepalive (BUG-3) e su `_wrap_pre` (BUG-4).
5. Estendere `test_translations.py` a `plugins/` e aggiungere un controllo che rilevi stringhe
   letterali passate a costruttori di widget al di fuori di `t()` — protegge UX-2 dalle regressioni.

---

### QUAL-3 — Dipendenze dichiarate in modo incompleto

`gtk3/requirements.txt` dichiara `cryptography>=41.0`, `paramiko>=3.0`, `pyftpdlib>=1.5` — tutte
effettivamente usate. **Mancano:**

- **`pynacl`** — richiesto da `keepassxc_manager.py:31-32` per l'intero protocollo KeePassXC
  Browser. Non è in `requirements.txt` né in `setup.sh`; compare solo in
  `packaging/appimage/pcm.spec:31` come import nascosto di PyInstaller. Chi segue
  `requirements.txt` non ottiene mai la funzione e vede solo l'avviso di
  `keepassxc_manager.py:443`. Aggiungerlo, e aggiungerlo anche a `setup.sh` fra i pacchetti
  installati. Collegato a SEC-9.
- **`pytest`** — necessario per i test, non dichiarato da nessuna parte (QUAL-1).

Valutare inoltre un limite superiore o un pinning per le dipendenze critiche: oggi sono tutte
`>=` senza lock file.

---

### QUAL-4 — `PCM.py` è un monolite

`PCM.py:161` — la classe `MainWindow` è **2538 righe e 90 metodi**, l'80% del file, con almeno
nove responsabilità distinte: costruzione dell'interfaccia, gestione schede e affiancamento,
creazione dei protocolli, rete di basso livello (socket, `Popen`), credenziali e cifratura,
analisi degli URI da riga di comando, importazione configurazioni, orchestrazione dei cluster,
persistenza sessioni.

Metodi oltre le 80 righe: `_apri_vnc` (172, `:1344`), `_apri_terminale` (140, `:815`),
`_on_importa_sessioni` (137, `:1970`), `apri_da_cli` (118, `:663`), `_on_broadcast` (98, `:2195`),
`_build_headerbar` (89, `:392`), `_on_close` (84, `:2504`), `_chiedi_credenziali_rdp` (82, `:1178`),
`_on_audit_log` (81, `:2298`). Poco sotto soglia: `_build_ui` (70, `:321`), `_chiudi_tab` (68,
`:1731`), `_check_crypto_unlock` (65, `:226`).

**Intervento — solo se le fasi 0-4 sono complete e verificate.** Estrazione incrementale, un modulo
per volta, verificando l'applicazione a ogni passo:

1. `pcm_uri.py` ← `apri_da_cli` (118 righe di analisi pura, **nessuna dipendenza da GTK**: diventa
   immediatamente testabile).
2. `pcm_credentials.py` ← `_resolve_credentials`, `_chiedi_credenziali_rdp`,
   `_salva_credenziali_sessione`, `_check_crypto_unlock`.
3. `pcm_protocols.py` ← la famiglia `_apri_*`, che oggi ripete cinque volte lo stesso schema
   (`PCM.py:995-1030`).
4. `pcm_tabs.py` ← gestione schede e affiancamento (`PCM.py:1563-1729`).

**Non affrontare questo task insieme ad altri.** Va fatto isolato, con la suite di QUAL-2 già in
funzione.

Nota collaterale: `_startup_chain` (`PCM.py:192-209`) concatena cinque passi con ritardi fissi
(200/300/500/500 ms) — accoppiamento temporale fragile, da sostituire con callback di completamento.

Duplicazione da sanare nella stessa occasione: `rdp_widget.py:200-212` e `:658-668`
(`_build_freerdp_cmd`) ripetono la stessa sequenza di flag FreeRDP con due percorsi di manutenzione
separati; `rdp_widget.py` e `vnc_widget.py` implementano due scheletri paralleli e divergenti per
lo stesso ciclo di vita (processo esterno, `Gtk.Socket`, polling, etichetta di stato, chiusura).

---

### QUAL-5 — Migrazione di `translations.py` a gettext

**Solo dopo UX-2.** `translations.py` è un file da 1724 righe con 1157 chiavi × 5 lingue in
dizionari letterali: aggiungere una lingua significa modificare 1157 voci, e non esiste alcuno
strumento di traduzione utilizzabile. Dopo UX-2 il file sarà ancora più grande.

Valutare la migrazione a gettext (`.po`/`.mo`), che darebbe accesso agli strumenti standard
(Poedit, Weblate) e permetterebbe contributi di traduzione esterni senza toccare il codice.
Comporta: estrazione delle stringhe con `xgettext`, un file `.po` per lingua, compilazione in fase
di build (`linuxbuild/build.sh` e `packaging/appimage/pcm.spec` vanno aggiornati per includere i
`.mo`), e sostituzione di `t()` con un wrapper su `gettext.translation()`.

**Da valutare, non da eseguire in automatico**: è un lavoro consistente il cui beneficio dipende
dall'intenzione di accettare traduzioni dall'esterno. Chiedere conferma prima di iniziare.

---

## Procedura di verifica

Dopo **ogni fase**:

```bash
cd /home/azanzani/Python_Connection_Manager/gtk3
python3 -m py_compile *.py plugins/*.py plugins/builtins/*/*.py   # nessun errore
python3 -m pytest tests/ -v                                        # dopo QUAL-1
python3 PCM.py                                                     # avvio manuale
bash -n ../setup.sh                                                # dopo FASE 0
```

**Prova manuale minima** (richiede un ambiente grafico X11/Wayland):

1. Avvio senza errori in console, barra laterale e sessioni di esempio visibili.
2. Apertura di una sessione SSH verso `localhost`; digitazione nel terminale; chiusura scheda.
3. Le otto scorciatoie predefinite rispondono (UX-1).
4. Cambio lingua in English → riavvio → apertura di Cron, Log, Monitor, editor SFTP: nessuna
   stringa italiana (UX-2).
5. Profilo con pre-comando `echo ciao`: si connette e il comando viene eseguito (BUG-1).
6. Profilo VNC con password contenente uno spazio: si connette (BUG-2).
7. Chiusura dell'applicazione → `ps aux | grep -E 'xfreerdp|vncviewer|ssh -N'` vuoto (RES-2).
8. `ls -l connections.json pcm_settings.json` → entrambi `-rw-------` (SEC-1).
9. `ls /tmp/pcm_vnc_* /tmp/pcm_logs` → nulla (RES-3, SEC-3).
10. Installazione da zero con `bash setup.sh` su una macchina pulita: nessuna domanda sulla
    variante, installazione GTK3 completa (REM-2).

---

## Ordine di esecuzione consigliato

```
FASE 0  REM-1 → REM-2 → REM-3                                    ← indipendente, eseguibile subito
FASE 1  UX-1 → UX-3 → UX-2 → UX-4 → UX-5                         ← priorità del committente
FASE 2  BUG-1 → BUG-2 → BUG-3 → BUG-4 → BUG-5
FASE 3  SEC-1 → SEC-5 → SEC-8 → SEC-7 → SEC-2 → SEC-3 → SEC-6 → SEC-9 → SEC-4
FASE 4  RES-2 → RES-1 → RES-3
FASE 5  QUAL-1 → QUAL-2 → QUAL-3 → QUAL-4 → QUAL-5
```

Motivi dell'ordine interno:

- **FASE 0 per prima** perché non tocca `gtk3/` e riduce la superficie di tutto il resto.
- **UX-3 prima di UX-2** perché il sistema di logging serve a diagnosticare il lavoro successivo.
- **BUG-1 subito dopo la FASE 1** perché tre funzioni sono completamente inoperanti.
- **SEC-1, SEC-5, SEC-8 e SEC-7 per primi** nella sicurezza: proteggono da perdita di dati e da
  invio di credenziali al destinatario sbagliato, non solo da divulgazione passiva.
- **SEC-4 per ultimo** perché può interrompere connessioni oggi funzionanti e richiede le opzioni
  di deroga.
- **QUAL-2 va scritto insieme a BUG-2, BUG-3, BUG-4 e SEC-6**, non dopo: sono i test che
  impediscono a quelle correzioni di regredire.
- **QUAL-4 per ultimo in assoluto**: la ristrutturazione di `PCM.py` è sicura solo con i test già
  attivi.

---

## Punti che richiedono una decisione prima di procedere

1. **BUG-5 punto 1** — se la versione morta di `_apri_cluster` (`PCM.py:1067`) contiene logica
   assente in quella viva, si tratta di una regressione da recuperare, non di codice obsoleto da
   cancellare.
2. **BUG-5 punto 2** — `pcm_context_actions` è importato e mai collegato: funzione dei plugin
   incompleta da completare, o residuo da rimuovere?
3. **UX-5 punto 5** — `btn_manuale` (`session_dialog.py:1331`) è creato e mai mostrato: andava
   visualizzato o va rimosso?
4. **UX-5 punto 7** — `ssh.strict_host_check` non è letta da nessuna parte: implementarla come
   default globale per i nuovi profili, o rimuovere la chiave?
5. **SEC-4** — le correzioni su host key e certificati possono interrompere connessioni oggi
   funzionanti verso apparati con certificati autofirmati. Confermare che le deroghe per profilo
   siano una mitigazione accettabile.
6. **QUAL-5** — migrare a gettext è un lavoro consistente: ha senso solo se si intende accettare
   traduzioni dall'esterno.
