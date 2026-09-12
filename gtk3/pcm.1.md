% PCM(1) PCM User Manual
%
% 2026

# NAME

pcm — Python Connection Manager, multi-protocol remote session manager

# SYNOPSIS

**pcm** [*URI*]

**python3** /usr/lib/pcm/PCM.py [*URI*]

# DESCRIPTION

**PCM** (Python Connection Manager) is a GTK3 graphical application for
managing remote connections. It supports SSH, SFTP, FTP/FTPS, RDP, VNC,
Telnet, Mosh, Serial, local Exec, SSH tunnels, and plugin protocols such as
AWS SSM, kubectl exec, Docker exec, and SPICE, all within a single tabbed
window.

PCM uses the native VTE terminal emulator and runs natively on both X11
and Wayland (no XWayland required, except for RDP internal-panel mode).

When invoked with a URI argument and PCM is already running, the
connection is forwarded to the existing instance via D-Bus and opens as
a new tab — no duplicate windows.

# URI FORMAT

    proto://[user@]host[:port][?options]

**Supported schemes:**

`ssh://`, `sftp://`, `ftp://`, `ftps://`, `rdp://`, `vnc://`,
`telnet://`, `mosh://`

**Query string options** (ad-hoc connections only):

`mode=internal|external`
:   Force embedded tab or external window/client.

`terminal=xterm|kitty|...`
:   Specific external terminal emulator (SSH/Telnet with mode=external).

**Session lookup order** when a URI is given:

1. Session name matches URI host (case-insensitive)
2. Session hostname matches URI host, same protocol
3. Session hostname matches URI host, any protocol
4. No match → ad-hoc connection using URI parameters

When a saved session is found all its settings are used (password, key,
macros, etc.). User and port from the URI override the saved values.

# EXAMPLES

Open a saved session named "server1":

    pcm ssh://server1

Ad-hoc SSH connection:

    pcm ssh://admin@192.168.1.10:2222

RDP session embedded in a PCM tab:

    pcm 'rdp://administrator@winserver?mode=internal'

VNC with integrated gtk-vnc viewer:

    pcm 'vnc://192.168.1.60:5901?mode=internal'

SFTP browser:

    pcm sftp://backup@nas.lan

Shell alias for frequent hosts:

    alias jira='pcm ssh://jiraapp'
    pcm() { python3 ~/PCM/gtk3/PCM.py "ssh://$1"; }

# INTERFACE

The main window is divided into:

**Left panel**
:   Session list organised in groups. Use `/` in a group name to display
    nested groups, for example `Production/Linux`. Sessions with an open
    connection show a green dot (●) next to their name. The panel supports
    tags, live search, recent sessions, TCP reachability checks, and a
    right-click context menu.

**Toolbar**
:   New Session, Local Terminal, Tunnel Indicator (shows active SSH
    tunnel count; click for quick-stop popup), Settings, Split.

**Quick Connect bar**
:   Connect instantly without saving a profile: select protocol, type
    `user@host:port`, press Enter.

**Session templates**
:   Mark a profile as a template and select it when creating another
    profile. Template fields are inherited by the child profile, whose
    explicit values take precedence. Template chains are supported; cycles
    are detected and do not prevent startup.

**Tab area**
:   Each connection opens in a tab. Tabs can be reordered, split
    vertically or horizontally, and moved between panels.

# TOOLS

## External tools

External tools are configured in **Settings > Tools > Generic external tools**
and launched from a session's right-click menu. Each tool has a label,
command, arguments, and optional working directory. Arguments are parsed into
an argument vector and started with `shell=False`; PCM never concatenates them
into a shell command.

The following placeholders are supported, case-insensitively:

`{HOST}`, `{PORT}`, `{USER}`, `{DOMAIN}`, `{DESCRIPTION}`, `{GROUP}`, `{TAGS}`
:   Values from the selected profile.

`{NAME}`
:   The profile name when available.

`{VARIABLE}`
:   A global variable configured in **Tools > Global variables**. Tool-local
    variables can also be stored in the JSON definition.

Passwords and secrets are deliberately rejected as placeholders.

## Port scan and discovery

Open **Tools > Port scan and discovery** to scan an inclusive IPv4 or IPv6
range. Enter comma-separated ports and ranges such as `22,80,443` or
`5900-5902`, then choose the protocol to assign when importing results.

The scanner limits a run to 4096 hosts, 256 ports, and 65536 TCP checks. The
timeout must be between 0 and 30 seconds. Select the discovered rows and use
**Import selected** to create profiles in the `Port scan` group. Only TCP
reachability is detected; the selected protocol is an import choice, not a
protocol fingerprint.

Only scan networks you own or are explicitly authorised to test.

# CONFIGURATION

## Backups

PCM can create a private backup before replacing `connections.json` or
`pcm_settings.json`. Configure this in **Settings > General**:

- enable or disable automatic backups;
- choose the maximum number of copies to retain;
- optionally choose a backup directory.

The default directory is `backups/` beside the configuration files. The
directory is forced to mode 0700 and backup files to mode 0600. Backups retain
the on-disk representation, including encryption if credential encryption is
enabled.

# FILES

`connections.json`
:   Session profiles in JSON format. Permissions 0600. In a writable source
    checkout this is beside the GTK3 modules; for an AppImage or read-only
    installation it is in `${XDG_CONFIG_HOME:-~/.config}/pcm/`.

`pcm_settings.json`
:   Global settings, shortcuts, recent sessions, external tools, and backup
    policy. Permissions 0600. It uses the same configuration directory as
    `connections.json`.

`audit_log.json`
:   Connection audit log with SHA-256 hash chaining. Permissions 0600. It
    uses the same configuration directory as `connections.json`.

`backups/`
:   Rotating pre-edit backups of the two JSON configuration files, unless a
    custom backup directory is configured.

`~/.local/share/pcm/logs/`
:   Terminal session output logs (path configurable per session).

`~/.cache/pcm/`
:   Temporary SSH_ASKPASS helper scripts (directory 0700, files deleted
    after 5 seconds).

`~/.local/share/applications/pcm.desktop`
:   Desktop launcher created by setup.sh.

# ENVIRONMENT

`PCM_ASKPASS_PASSWORD`
:   Used internally to pass the session password to the SSH_ASKPASS
    helper. Never set this variable manually.

`SSH_AUTH_SOCK`
:   If set, PCM uses the running ssh-agent for authentication.

# SECURITY

- Passwords are **never** placed on the command line. PCM types the
  password directly into the terminal via the VTE feed-child mechanism,
  or uses SSH_ASKPASS_REQUIRE=force for OpenSSH ≥ 8.4.
- All profile parameters are sanitised with **shlex.quote()** before
  shell use. Pre-commands run with shell=False.
- Credential files are written with permissions **0600**.
- SSH connections use **StrictHostKeyChecking=yes**.
- Optional AES-128 encryption (Fernet + PBKDF2-SHA256, 480 k iterations)
  of usernames and passwords with a master password.

# DEPENDENCIES

**Required:**
python3 (≥ 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-vte-2.91,
python3-paramiko, python3-cryptography, python3-pyftpdlib

**Recommended:**
gir1.2-gtk-vnc-2.0 (native VNC), openssh-client, freerdp3-x11,
tigervnc-viewer, mosh, xdotool, wakeonlan

# SEE ALSO

**ssh**(1), **sftp**(1), **xfreerdp**(1), **mosh**(1), **vncviewer**(1),
**minicom**(1), **picocom**(1)

Full documentation: use **Help > PCM Guide** inside PCM or consult this
manual and the project README.

Project page: https://github.com/buzzqw/Python_Connection_Manager

# BUGS

Report bugs at: https://github.com/buzzqw/Python_Connection_Manager/issues

# AUTHOR

Andres Zanzani <azanzani@gmail.com>

# LICENSE

European Union Public Licence (EUPL) v1.2
