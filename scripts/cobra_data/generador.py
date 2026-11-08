"""Generación de cuentas y transacciones de prueba.

Las transacciones se generan en orden cronológico simulando los saldos, igual
que los aplicará PROCTRAN: una transacción válida nunca deja una cuenta en
negativo, y cada transacción inválida tiene exactamente UNA causa de rechazo,
la que queda registrada en el manifiesto de esperados.

Todo depende de la semilla: la misma semilla produce los mismos bytes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

NOMBRES = [
    "MARIA", "JOSE", "GUADALUPE", "JUAN", "FERNANDA", "LUIS", "ANA", "CARLOS",
    "SOFIA", "MIGUEL", "VALERIA", "JORGE", "XIMENA", "RICARDO", "DANIELA",
    "ALEJANDRO", "PAOLA", "FRANCISCO", "ANDREA", "EDUARDO", "LUCIA", "PEDRO",
]
APELLIDOS = [
    "HERNANDEZ", "GARCIA", "MARTINEZ", "LOPEZ", "GONZALEZ", "PEREZ",
    "RODRIGUEZ", "SANCHEZ", "RAMIREZ", "CRUZ", "FLORES", "GOMEZ", "MORALES",
    "VAZQUEZ", "REYES", "JIMENEZ", "TORRES", "DIAZ", "GUTIERREZ", "RUIZ",
    "MENDOZA", "AGUILAR", "ORTIZ", "CASTILLO", "PENA", "NUNEZ",
]

# Causas de rechazo que el generador sabe provocar (ver RECHAZO.cpy)
INVALIDAS = {
    "R01": "cuenta inexistente",
    "R02": "cuenta bloqueada o cerrada",
    "R03": "importe cero o negativo",
    "R04": "saldo insuficiente",
    "R05": "tipo de transaccion no reconocido",
    "R06": "cuenta destino invalida",
    "R07": "fecha invalida",
}

CENTAVO = Decimal("0.01")


@dataclass
class Resultado:
    cuentas: list[dict]
    transacciones: list[dict]
    esperados: list[dict]   # TRN-ID, codigo esperado ("" = debe aplicarse), causa


def _importe(rng: random.Random, minimo: float, maximo: float) -> Decimal:
    return Decimal(str(round(rng.uniform(minimo, maximo), 2))).quantize(CENTAVO)


def generar_cuentas(rng: random.Random, n: int, fecha_proceso: date) -> list[dict]:
    numeros = rng.sample(range(1, 10**10), n)
    cuentas = []
    for numero in numeros:
        ahorro = rng.random() < 0.6
        estatus = rng.choices(["A", "B", "C"], weights=[85, 10, 5])[0]
        nombre = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
        fecha_act = fecha_proceso - timedelta(days=rng.randint(1, 365))
        cuentas.append({
            "CTA-NUMERO": f"{numero:010d}",
            "CTA-TITULAR": nombre,
            "CTA-TIPO": "A" if ahorro else "C",
            "CTA-SALDO": _importe(rng, 0, 250_000),
            "CTA-TASA-ANUAL": Decimal(rng.randint(200, 1000)) / 10000 if ahorro else Decimal(0),
            "CTA-ESTATUS": estatus,
            "CTA-FECHA-ACT": fecha_act.strftime("%Y%m%d"),
        })
    return cuentas


def generar(
    n_cuentas: int,
    n_transacciones: int,
    semilla: int,
    pct_invalidas: float,
    fecha_proceso: date,
) -> Resultado:
    if n_cuentas < 2:
        raise ValueError("se necesitan al menos 2 cuentas (para transferencias)")
    if not 0 <= pct_invalidas <= 100:
        raise ValueError("el porcentaje de inválidas debe estar entre 0 y 100")

    rng = random.Random(semilla)
    cuentas = generar_cuentas(rng, n_cuentas, fecha_proceso)

    activas = [c["CTA-NUMERO"] for c in cuentas if c["CTA-ESTATUS"] == "A"]
    no_activas = [c["CTA-NUMERO"] for c in cuentas if c["CTA-ESTATUS"] != "A"]
    existentes = {c["CTA-NUMERO"] for c in cuentas}
    saldo = {c["CTA-NUMERO"]: c["CTA-SALDO"] for c in cuentas}

    if len(activas) < 2:
        raise ValueError("la semilla produjo menos de 2 cuentas activas; usa más cuentas")

    def inexistente() -> str:
        while True:
            n = f"{rng.randrange(1, 10**10):010d}"
            if n not in existentes:
                return n

    # Horas del día de proceso, en orden cronológico
    inicio = datetime.combine(fecha_proceso, datetime.min.time())
    segundos = sorted(rng.randrange(0, 86_400) for _ in range(n_transacciones))

    transacciones, esperados = [], []
    for i, seg in enumerate(segundos, start=1):
        trn = {
            "TRN-ID": f"T{i:011d}",
            "TRN-CTA-DESTINO": "",
            "TRN-FECHA-HORA": (inicio + timedelta(seconds=seg)).strftime("%Y%m%d%H%M%S"),
        }
        codigo = ""
        if rng.random() * 100 < pct_invalidas:
            codigo = rng.choice(sorted(INVALIDAS))
            if codigo == "R02" and not no_activas:
                codigo = "R01"

        # Base válida: cuenta activa, tipo e importe coherentes con su saldo.
        # R06 necesita saldo para que la única falla sea el destino.
        candidatas = activas
        if codigo == "R06":
            candidatas = [c for c in activas if saldo[c] >= 1] or activas
            if candidatas is activas:
                codigo = "R01"
        origen = rng.choice(candidatas)
        tipo = rng.choices("DRTC", weights=[40, 30, 20, 10])[0]
        if tipo != "D" and saldo[origen] < 1:
            tipo = "D"
        if tipo == "D":
            importe = _importe(rng, 100, 20_000)
        elif tipo == "C":
            importe = min(Decimal(rng.choice([35, 50, 99, 150])), saldo[origen])
        else:
            importe = _importe(rng, 1, float(min(saldo[origen], Decimal(30_000))))
        trn.update({"TRN-CUENTA": origen, "TRN-TIPO": tipo, "TRN-IMPORTE": importe})
        if tipo == "T":
            trn["TRN-CTA-DESTINO"] = rng.choice([c for c in activas if c != origen])

        # Se introduce exactamente una causa de rechazo
        if codigo == "R01":
            trn["TRN-CUENTA"] = inexistente()
        elif codigo == "R02":
            trn["TRN-CUENTA"] = rng.choice(no_activas)
        elif codigo == "R03":
            trn["TRN-IMPORTE"] = rng.choice([Decimal(0), -_importe(rng, 1, 5_000)])
        elif codigo == "R04":
            trn["TRN-TIPO"] = "R"
            trn["TRN-CTA-DESTINO"] = ""
            trn["TRN-IMPORTE"] = saldo[origen] + _importe(rng, 1, 10_000)
        elif codigo == "R05":
            trn["TRN-TIPO"] = rng.choice("XZ9")
            trn["TRN-CTA-DESTINO"] = ""
        elif codigo == "R06":
            trn["TRN-TIPO"] = "T"
            trn["TRN-IMPORTE"] = _importe(rng, 1, float(saldo[origen]))
            trn["TRN-CTA-DESTINO"] = rng.choice([origen, inexistente()])
        elif codigo == "R07":
            hora = trn["TRN-FECHA-HORA"][8:]
            trn["TRN-FECHA-HORA"] = rng.choice(["20261332", "20260230", "20261100", "20260431"]) + hora

        # Solo las válidas mueven saldos
        if not codigo:
            if tipo == "D":
                saldo[origen] += importe
            else:
                saldo[origen] -= importe
                if tipo == "T":
                    saldo[trn["TRN-CTA-DESTINO"]] += importe

        transacciones.append(trn)
        esperados.append({
            "TRN-ID": trn["TRN-ID"],
            "CODIGO-ESPERADO": codigo,
            "CAUSA": INVALIDAS.get(codigo, ""),
        })

    return Resultado(cuentas, transacciones, esperados)
