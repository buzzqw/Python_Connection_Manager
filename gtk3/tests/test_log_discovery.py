"""Test del parser della discovery sorgenti log (log_viewer.py)."""
import shlex

from log_viewer import parse_sorgenti_log


def test_sezioni_vuote():
    g = parse_sorgenti_log("")
    assert g == {"files": [], "systemd": [], "docker": []}


def test_file_con_dimensione_e_spazi_nel_path():
    out = "===FILES\n12K\t/var/log/syslog\n4.0K\t/var/log/my app/error.log\n"
    g = parse_sorgenti_log(out)
    assert len(g["files"]) == 2
    cmd, label = g["files"][1]
    assert label == "error.log (4.0K)"
    assert cmd == f"tail -f -n 200 {shlex.quote('/var/log/my app/error.log')}"


def test_file_senza_dimensione():
    out = "===FILES\n/var/log/nginx/access.log\n"
    g = parse_sorgenti_log(out)
    cmd, label = g["files"][0]
    assert label == "access.log"
    assert cmd == "tail -f -n 200 /var/log/nginx/access.log"


def test_file_con_path_non_assoluto_ignorato():
    out = "===FILES\n12K\trelativo.log\n"
    assert parse_sorgenti_log(out)["files"] == []


def test_systemd_strip_service():
    out = "===SYSTEMD\nssh.service\nnginx.service\n"
    g = parse_sorgenti_log(out)
    assert [lbl for _, lbl in g["systemd"]] == ["ssh", "nginx"]
    assert g["systemd"][0][0] == "journalctl -f -n 200 -u ssh.service"


def test_docker():
    out = "===DOCKER\nweb\npostgres-1\n"
    g = parse_sorgenti_log(out)
    assert [lbl for _, lbl in g["docker"]] == ["web", "postgres-1"]
    assert g["docker"][0][0] == "docker logs -f --tail 200 web"


def test_sezioni_mancanti():
    out = "===SYSTEMD\nssh.service\n"
    g = parse_sorgenti_log(out)
    assert g["files"] == []
    assert g["docker"] == []
    assert len(g["systemd"]) == 1


def test_output_sporco_ignorato():
    # Righe fuori sezione (es. banner di login) non devono finire nei risultati
    out = "Last login: today\n===FILES\n12K\t/var/log/syslog\n"
    g = parse_sorgenti_log(out)
    assert len(g["files"]) == 1
    assert g["systemd"] == []
