"""Test del parser GPU di panel_monitor.py (nvidia-smi --format=csv)."""
import pytest

from panel_monitor import parse_gpu_line


def test_riga_completa():
    g = parse_gpu_line("0, NVIDIA GeForce RTX 4090, 42, 8123, 24564, 61, 187.42")
    assert g["idx"] == 0
    assert g["nome"] == "NVIDIA GeForce RTX 4090"
    assert g["gpu_util"] == 42.0
    assert g["mem_used_mib"] == 8123.0
    assert g["mem_total_mib"] == 24564.0
    assert g["temp_c"] == 61.0
    assert g["power_w"] == pytest.approx(187.42)


def test_power_draw_na_non_scarta_la_gpu():
    # Su molte GPU/VM power.draw è [N/A]: la card deve restare visibile
    g = parse_gpu_line("1, Tesla T4, 0, 512, 15360, 45, [N/A]")
    assert g is not None
    assert g["power_w"] is None
    assert g["temp_c"] == 45.0
    assert g["mem_total_mib"] == 15360.0


def test_temperatura_na():
    g = parse_gpu_line("0, GPU, 10, 100, 1000, N/A, 30")
    assert g["temp_c"] is None
    assert g["power_w"] == 30.0


def test_utilizzo_na_diventa_zero():
    g = parse_gpu_line("0, GPU, [N/A], 100, 1000, 50, 20")
    assert g["gpu_util"] == 0.0


def test_riga_troppo_corta():
    assert parse_gpu_line("0, GPU, 10") is None


def test_indice_non_numerico():
    assert parse_gpu_line("abc, GPU, 10, 1, 2, 3, 4") is None


def test_riga_vuota():
    assert parse_gpu_line("") is None
