"""Pruebas del parser de copybooks, el codec y el generador.

Las pruebas de interoperabilidad compilan un programa COBOL que lee los
archivos generados por Python; se omiten si cobc no está instalado.
"""

import shutil
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cobra_data import codec, generador
from cobra_data import copybook as cb

RAIZ = Path(__file__).resolve().parents[2]
COPYBOOKS = RAIZ / "copybooks"


def reg(nombre):
    return cb.cargar(COPYBOOKS / f"{nombre}.cpy")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre,longitud", [
    ("CUENTA", 80), ("TRANSACCION", 80), ("RECHAZO", 160), ("PARAMINT", 19),
])
def test_longitud_de_copybooks(nombre, longitud):
    assert reg(nombre).longitud == longitud


def test_offsets_cuenta():
    r = reg("CUENTA")
    assert [(c.nombre, c.offset, c.longitud) for c in r.campos()] == [
        ("CTA-NUMERO", 0, 10), ("CTA-TITULAR", 10, 50), ("CTA-TIPO", 60, 1),
        ("CTA-SALDO", 61, 7), ("CTA-TASA-ANUAL", 68, 3), ("CTA-ESTATUS", 71, 1),
        ("CTA-FECHA-ACT", 72, 8),
    ]


def test_redefines_comparten_bytes():
    r = reg("TRANSACCION")
    assert r.campo("TRN-FECHA-MM").offset == 44
    assert r.campo("TRN-HORA-SS").offset == 52
    assert "TRN-FECHA" not in [c.nombre for c in r.campos()]


def test_niveles_88():
    c = reg("CUENTA").campo("CTA-ESTATUS")
    assert c.acepta("A") and c.acepta("C") and not c.acepta("Q")


def test_rechaza_redefines_mas_grande():
    fuente = (
        "       01  R.\n"
        "           05  A               PIC X(4).\n"
        "           05  B REDEFINES A   PIC X(6).\n"
    )
    with pytest.raises(cb.CopybookError, match="más que"):
        cb.parsear(fuente)


def test_rechaza_clausula_no_soportada():
    fuente = "       01  R.\n           05  A PIC X OCCURS 3 TIMES.\n"
    with pytest.raises(cb.CopybookError, match="OCCURS"):
        cb.parsear(fuente)


# ---------------------------------------------------------------------------
# Codec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n,digitos,signo,esperado", [
    (12345, 5, True, "12345C"),
    (-12345, 5, True, "12345D"),
    (850, 5, False, "00850F"),
    (0, 13, True, "00000000000000C"[-14:]),
    (-123456789, 13, True, "00000123456789D"[-14:]),
])
def test_comp3(n, digitos, signo, esperado):
    datos = codec.empacar_comp3(n, digitos, signo)
    assert datos.hex().upper() == esperado
    assert codec.desempacar_comp3(datos) == n


def test_roundtrip_registro():
    r = reg("CUENTA")
    valores = {
        "CTA-NUMERO": "0000000001", "CTA-TITULAR": "PEÑA NÚÑEZ", "CTA-TIPO": "A",
        "CTA-SALDO": "-1500.50", "CTA-TASA-ANUAL": "0.085", "CTA-ESTATUS": "B",
        "CTA-FECHA-ACT": "20261107",
    }
    datos = codec.codificar(r, valores)
    assert len(datos) == 80
    leido = codec.decodificar(r, datos)
    assert leido["CTA-TITULAR"] == "PENA NUNEZ"
    assert leido["CTA-SALDO"] == Decimal("-1500.50")
    assert leido["CTA-TASA-ANUAL"] == Decimal("0.0850")


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("CTA-SALDO", "1.234", "decimales"),
    ("CTA-SALDO", "999999999999", "no cabe"),
    ("CTA-TASA-ANUAL", "-0.01", "negativo"),
    ("CTA-NUMERO", "12345678901", "máximo"),
    ("CTA-SALDO", "abc", "no es un número"),
])
def test_valores_invalidos(campo, valor, mensaje):
    with pytest.raises(codec.ValorInvalido, match=mensaje):
        codec.codificar(reg("CUENTA"), {campo: valor})


# ---------------------------------------------------------------------------
# Generador
# ---------------------------------------------------------------------------

def _generar(semilla=7):
    return generador.generar(80, 2000, semilla, 15, date(2026, 11, 7))


def test_generador_determinista():
    a, b = _generar(), _generar()
    assert a.cuentas == b.cuentas and a.transacciones == b.transacciones


def test_generador_cubre_todos_los_rechazos():
    codigos = {e["CODIGO-ESPERADO"] for e in _generar().esperados}
    assert set(generador.INVALIDAS) <= codigos


def test_validas_nunca_sobregiran():
    """Aplica las transacciones válidas en orden: ningún saldo queda negativo."""
    res = _generar()
    saldo = {c["CTA-NUMERO"]: c["CTA-SALDO"] for c in res.cuentas}
    for trn, esp in zip(res.transacciones, res.esperados):
        if esp["CODIGO-ESPERADO"]:
            continue
        cta, imp = trn["TRN-CUENTA"], trn["TRN-IMPORTE"]
        assert imp > 0
        if trn["TRN-TIPO"] == "D":
            saldo[cta] += imp
        else:
            saldo[cta] -= imp
            assert saldo[cta] >= 0, trn
            if trn["TRN-TIPO"] == "T":
                saldo[trn["TRN-CTA-DESTINO"]] += imp


def test_todo_se_codifica():
    res = _generar()
    for r, filas in ((reg("CUENTA"), res.cuentas), (reg("TRANSACCION"), res.transacciones)):
        for f in filas:
            assert len(codec.codificar(r, f)) == r.longitud


# ---------------------------------------------------------------------------
# Interoperabilidad con GnuCOBOL
# ---------------------------------------------------------------------------

LECTOR = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LECTOR.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUENTAS ASSIGN TO "CUENTAS"
               ORGANIZATION IS SEQUENTIAL.
           SELECT MOVS ASSIGN TO "MOVS"
               ORGANIZATION IS SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  CUENTAS.
       COPY CUENTA.
       FD  MOVS.
       COPY TRANSACCION.
       WORKING-STORAGE SECTION.
       01  WS-FIN                  PIC X VALUE "N".
       01  WS-SALDO                PIC -9(11).99.
       01  WS-TASA                 PIC 9.9999.
       PROCEDURE DIVISION.
       PRINCIPAL.
           OPEN INPUT CUENTAS
           PERFORM UNTIL WS-FIN = "S"
               READ CUENTAS
                   AT END MOVE "S" TO WS-FIN
                   NOT AT END
                       MOVE CTA-SALDO TO WS-SALDO
                       MOVE CTA-TASA-ANUAL TO WS-TASA
                       DISPLAY "C|" CTA-NUMERO "|" CTA-TIPO "|"
                           WS-SALDO "|" WS-TASA "|" CTA-ESTATUS "|"
                           CTA-FECHA-ACT
               END-READ
           END-PERFORM
           CLOSE CUENTAS
           MOVE "N" TO WS-FIN
           OPEN INPUT MOVS
           PERFORM UNTIL WS-FIN = "S"
               READ MOVS
                   AT END MOVE "S" TO WS-FIN
                   NOT AT END
                       MOVE TRN-IMPORTE TO WS-SALDO
                       DISPLAY "T|" TRN-ID "|" TRN-CUENTA "|" TRN-TIPO
                           "|" WS-SALDO "|" TRN-FECHA-MM "|"
                           TRN-HORA-SS
               END-READ
           END-PERFORM
           CLOSE MOVS
           STOP RUN.
"""


@pytest.mark.skipif(shutil.which("cobc") is None, reason="cobc no instalado")
def test_cobol_lee_lo_que_escribe_python(tmp_path):
    res = _generar()
    rc, rt = reg("CUENTA"), reg("TRANSACCION")
    (tmp_path / "cuentas.dat").write_bytes(b"".join(codec.codificar(rc, f) for f in res.cuentas))
    (tmp_path / "movs.dat").write_bytes(b"".join(codec.codificar(rt, f) for f in res.transacciones))

    fuente = tmp_path / "LECTOR.cbl"
    fuente.write_text(LECTOR)
    subprocess.run(
        ["cobc", "-x", "-I", str(COPYBOOKS), "-o", str(tmp_path / "lector"), str(fuente)],
        check=True, capture_output=True,
    )
    salida = subprocess.run(
        [str(tmp_path / "lector")], check=True, capture_output=True, text=True,
        env={"DD_CUENTAS": str(tmp_path / "cuentas.dat"), "DD_MOVS": str(tmp_path / "movs.dat")},
    ).stdout.splitlines()

    cuentas = [l.split("|") for l in salida if l.startswith("C|")]
    movs = [l.split("|") for l in salida if l.startswith("T|")]
    assert len(cuentas) == len(res.cuentas)
    assert len(movs) == len(res.transacciones)

    for (_, num, tipo, saldo, tasa, est, fecha), esp in zip(cuentas, res.cuentas):
        assert num == esp["CTA-NUMERO"]
        assert tipo == esp["CTA-TIPO"]
        assert Decimal(saldo) == esp["CTA-SALDO"]
        assert Decimal(tasa) == esp["CTA-TASA-ANUAL"]
        assert est == esp["CTA-ESTATUS"]
        assert fecha == esp["CTA-FECHA-ACT"]

    for (_, tid, cta, tipo, imp, mm, ss), esp in zip(movs, res.transacciones):
        assert tid == esp["TRN-ID"]
        assert cta == esp["TRN-CUENTA"]
        assert tipo == esp["TRN-TIPO"]
        assert Decimal(imp) == esp["TRN-IMPORTE"]
        assert mm == esp["TRN-FECHA-HORA"][4:6]
        assert ss == esp["TRN-FECHA-HORA"][12:14]
