"""Pruebas de CARGACTA: carga del maestro indexado de cuentas.

Python arma el archivo de entrada con el codec, CARGACTA lo carga, y un
lector COBOL recorre el maestro indexado por clave para verificar qué quedó.
"""

import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from cobra_data import codec
from cobra_data import copybook as cb

pytestmark = pytest.mark.skipif(shutil.which("cobc") is None, reason="cobc no instalado")

RAIZ = Path(__file__).resolve().parents[2]
COPYBOOKS = RAIZ / "copybooks"

LECTOR_MAESTRO = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEEMAE.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MAESTRO ASSIGN TO "MAESTRO"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS SEQUENTIAL
               RECORD KEY IS CTA-NUMERO
               FILE STATUS IS FS.
       DATA DIVISION.
       FILE SECTION.
       FD  MAESTRO.
       COPY CUENTA.
       WORKING-STORAGE SECTION.
       01  FS                      PIC XX.
       01  WS-SALDO                PIC -9(11).99.
       PROCEDURE DIVISION.
       PRINCIPAL.
           OPEN INPUT MAESTRO
           READ MAESTRO NEXT
           PERFORM UNTIL FS NOT = "00"
               MOVE CTA-SALDO TO WS-SALDO
               DISPLAY CTA-NUMERO "|" WS-SALDO
               READ MAESTRO NEXT
           END-PERFORM
           CLOSE MAESTRO
           STOP RUN.
"""


def _compilar(fuente: Path, salida: Path):
    r = subprocess.run(
        ["cobc", "-x", "-I", str(COPYBOOKS), "-o", str(salida), str(fuente)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


@pytest.fixture(scope="module")
def binarios(tmp_path_factory):
    d = tmp_path_factory.mktemp("bin")
    _compilar(RAIZ / "src" / "CARGACTA.cbl", d / "cargacta")
    (d / "LEEMAE.cbl").write_text(LECTOR_MAESTRO)
    _compilar(d / "LEEMAE.cbl", d / "leemae")
    return d


def _cuenta(numero, saldo="100.00", tipo="A", estatus="A", fecha="20261101"):
    return {
        "CTA-NUMERO": numero, "CTA-TITULAR": f"TITULAR {numero}",
        "CTA-TIPO": tipo, "CTA-SALDO": saldo,
        "CTA-TASA-ANUAL": "0.05" if tipo == "A" else "0",
        "CTA-ESTATUS": estatus, "CTA-FECHA-ACT": fecha,
    }


def _cargar(binarios, tmp_path, registros: list[bytes]):
    entrada = tmp_path / "cuentas.dat"
    maestro = tmp_path / "maestro.idx"
    entrada.write_bytes(b"".join(registros))
    env = {**os.environ, "DD_CUENTAS": str(entrada), "DD_MAESTRO": str(maestro)}
    r = subprocess.run([str(binarios / "cargacta")], capture_output=True, text=True, env=env)
    return r, maestro


def _leer_maestro(binarios, maestro) -> list[tuple[str, Decimal]]:
    env = {**os.environ, "DD_MAESTRO": str(maestro)}
    r = subprocess.run([str(binarios / "leemae")], capture_output=True, text=True, env=env, check=True)
    filas = [l.split("|") for l in r.stdout.splitlines()]
    return [(n, Decimal(s)) for n, s in filas]


def _totales(salida: str) -> dict[str, int]:
    t = {}
    for linea in salida.splitlines():
        for etiqueta in ("Leidos", "Cargados", "Rechazados"):
            if linea.strip().startswith(etiqueta):
                t[etiqueta] = int(linea.split(":")[1].replace(",", ""))
    return t


R = cb.cargar(COPYBOOKS / "CUENTA.cpy")


def test_carga_limpia(binarios, tmp_path):
    regs = [codec.codificar(R, _cuenta(f"{n:010d}", f"{n}.50")) for n in (30, 10, 20)]
    r, maestro = _cargar(binarios, tmp_path, regs)
    assert r.returncode == 0, r.stdout
    assert _totales(r.stdout) == {"Leidos": 3, "Cargados": 3, "Rechazados": 0}
    # El maestro queda ordenado por clave aunque la entrada no lo esté
    assert _leer_maestro(binarios, maestro) == [
        ("0000000010", Decimal("10.50")),
        ("0000000020", Decimal("20.50")),
        ("0000000030", Decimal("30.50")),
    ]


def test_rechazos_sin_abortar(binarios, tmp_path):
    corrupto = bytearray(codec.codificar(R, _cuenta("0000000007")))
    saldo = R.campo("CTA-SALDO")
    corrupto[saldo.offset : saldo.offset + saldo.longitud] = b"\xff" * saldo.longitud

    regs = [
        codec.codificar(R, _cuenta("0000000001", "100.00")),
        codec.codificar(R, _cuenta("0000000001", "999.00")),        # duplicada
        codec.codificar(R, _cuenta("0000000002", tipo="X")),        # tipo
        codec.codificar(R, _cuenta("0000000003", estatus="Q")),     # estatus
        codec.codificar(R, _cuenta("0000000004", fecha="20260230")),  # fecha
        codec.codificar(R, _cuenta("00000ABC05")),                  # número
        bytes(corrupto),                                            # COMP-3
        codec.codificar(R, _cuenta("0000000008", "-50.00", tipo="C")),
    ]
    r, maestro = _cargar(binarios, tmp_path, regs)

    assert r.returncode == 4, r.stdout
    assert _totales(r.stdout) == {"Leidos": 8, "Cargados": 2, "Rechazados": 6}
    for motivo in ("CLAVE DUPLICADA", "TIPO DE CUENTA INVALIDO", "ESTATUS INVALIDO",
                   "FECHA INVALIDA", "NUMERO DE CUENTA INVALIDO", "SALDO NO NUMERICO"):
        assert motivo in r.stdout, motivo

    # La primera ocurrencia de la clave duplicada es la que se conserva
    assert _leer_maestro(binarios, maestro) == [
        ("0000000001", Decimal("100.00")),
        ("0000000008", Decimal("-50.00")),
    ]


def test_entrada_inexistente(binarios, tmp_path):
    env = {**os.environ, "DD_CUENTAS": str(tmp_path / "no-existe.dat"),
           "DD_MAESTRO": str(tmp_path / "maestro.idx")}
    r = subprocess.run([str(binarios / "cargacta")], capture_output=True, text=True, env=env)
    assert r.returncode == 12
    assert "OPEN" in r.stdout and "CUENTAS" in r.stdout and "35" in r.stdout


def test_archivo_truncado_es_error_fatal(binarios, tmp_path):
    """Un archivo cuyo tamaño no es múltiplo de 80 está corrupto: RC 12."""
    reg = codec.codificar(R, _cuenta("0000000001"))
    r, _ = _cargar(binarios, tmp_path, [reg, reg[:50]])
    assert r.returncode == 12
    assert "READ" in r.stdout and "FILE STATUS 04" in r.stdout


def test_entrada_vacia(binarios, tmp_path):
    r, maestro = _cargar(binarios, tmp_path, [])
    assert r.returncode == 0
    assert _totales(r.stdout) == {"Leidos": 0, "Cargados": 0, "Rechazados": 0}
    assert _leer_maestro(binarios, maestro) == []
