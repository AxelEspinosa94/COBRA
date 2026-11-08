#!/usr/bin/env python3
"""Datos de prueba para COBRA.

El layout de cada archivo se lee directamente de copybooks/*.cpy, así que si
cambia un copybook este script se adapta sin tocar código.

Comandos:

  generar   Crea cuentas y transacciones aleatorias, incluyendo casos
            inválidos a propósito, y un manifiesto con el rechazo esperado.

      python3 scripts/generar_datos.py generar --cuentas 100 --transacciones 1000 --semilla 42

  cargar    Convierte un CSV (texto legible) al formato binario que lee COBOL.
            El encabezado del CSV usa los nombres de campo del copybook, con o
            sin prefijo y con '-' o '_':  CTA-SALDO, cta_saldo o saldo.

      python3 scripts/generar_datos.py cargar CUENTA data/entrada/cuentas.csv

  ver       Decodifica un archivo binario y lo muestra como tabla o CSV.

      python3 scripts/generar_datos.py ver CUENTA data/entrada/cuentas.dat
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from cobra_data import codec
from cobra_data import copybook as cb
from cobra_data import generador

RAIZ = Path(__file__).resolve().parent.parent
COPYBOOKS = RAIZ / "copybooks"
SALIDA_DEFAULT = RAIZ / "data" / "entrada"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def registro_de(nombre: str) -> cb.Registro:
    ruta = Path(nombre)
    if not ruta.suffix:
        ruta = COPYBOOKS / f"{nombre.upper()}.cpy"
    if not ruta.exists():
        disponibles = ", ".join(sorted(p.stem for p in COPYBOOKS.glob("*.cpy")))
        sys.exit(f"error: no existe el copybook {ruta}. Disponibles: {disponibles}")
    return cb.cargar(ruta)


def texto(valor) -> str:
    if isinstance(valor, Decimal):
        return format(valor, "f")
    return "" if valor is None else str(valor)


def escribir_dat(registro: cb.Registro, filas: list[dict], ruta: Path):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "wb") as f:
        for fila in filas:
            f.write(codec.codificar(registro, fila))


def escribir_csv(columnas: list[str], filas: list[dict], ruta: Path):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        w.writeheader()
        for fila in filas:
            w.writerow({k: texto(fila.get(k)) for k in columnas})


def mapear_encabezados(registro: cb.Registro, encabezados: list[str]) -> dict[str, str]:
    """Relaciona cada columna del CSV con un campo del copybook.

    Acepta el nombre completo (CTA-SALDO), con guion bajo (cta_saldo) o sin
    prefijo (saldo) siempre que no sea ambiguo.
    """
    campos = [c.nombre for c in registro.campos() if not c.es_filler]
    mapa, errores = {}, []
    for col in encabezados:
        clave = col.strip().upper().replace("_", "-")
        if clave in campos:
            mapa[col] = clave
            continue
        sufijo = [c for c in campos if c.endswith("-" + clave)]
        if len(sufijo) == 1:
            mapa[col] = sufijo[0]
        elif sufijo:
            errores.append(f"columna '{col}' es ambigua: {', '.join(sufijo)}")
        else:
            errores.append(f"columna '{col}' no existe en {registro.nombre}")
    duplicados = {v for v in mapa.values() if list(mapa.values()).count(v) > 1}
    if duplicados:
        errores.append(f"columnas repetidas para: {', '.join(sorted(duplicados))}")
    if errores:
        sys.exit("error:\n  " + "\n  ".join(errores) + f"\n  campos válidos: {', '.join(campos)}")
    return mapa


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_generar(args):
    fecha = datetime.strptime(args.fecha_proceso, "%Y%m%d").date() if args.fecha_proceso else date.today()
    try:
        res = generador.generar(args.cuentas, args.transacciones, args.semilla, args.pct_invalidas, fecha)
    except ValueError as e:
        sys.exit(f"error: {e}")

    cuenta = registro_de("CUENTA")
    trn = registro_de("TRANSACCION")
    salida = Path(args.salida)

    escribir_dat(cuenta, res.cuentas, salida / "cuentas.dat")
    escribir_dat(trn, res.transacciones, salida / "transacciones.dat")
    escribir_csv(["TRN-ID", "CODIGO-ESPERADO", "CAUSA"], res.esperados, salida / "esperados.csv")

    if args.csv:
        escribir_csv([c.nombre for c in cuenta.campos() if not c.es_filler], res.cuentas, salida / "cuentas.csv")
        escribir_csv([c.nombre for c in trn.campos() if not c.es_filler], res.transacciones, salida / "transacciones.csv")

    invalidas = sum(1 for e in res.esperados if e["CODIGO-ESPERADO"])
    por_codigo = {}
    for e in res.esperados:
        if e["CODIGO-ESPERADO"]:
            por_codigo[e["CODIGO-ESPERADO"]] = por_codigo.get(e["CODIGO-ESPERADO"], 0) + 1

    print(f"Fecha de proceso : {fecha:%Y-%m-%d}   semilla: {args.semilla}")
    print(f"Cuentas          : {len(res.cuentas):>6}  -> {salida / 'cuentas.dat'}")
    print(f"Transacciones    : {len(res.transacciones):>6}  -> {salida / 'transacciones.dat'}")
    print(f"  inválidas      : {invalidas:>6}  " + "  ".join(f"{k}={v}" for k, v in sorted(por_codigo.items())))
    print(f"Esperados        : {salida / 'esperados.csv'}")


def cmd_cargar(args):
    registro = registro_de(args.copybook)
    entrada = Path(args.entrada)
    destino = Path(args.salida) if args.salida else entrada.with_suffix(".dat")

    with open(entrada, newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f, delimiter=args.separador)
        if not lector.fieldnames:
            sys.exit(f"error: {entrada} está vacío o no tiene encabezado")
        mapa = mapear_encabezados(registro, lector.fieldnames)
        filas_csv = list(lector)

    registros, errores, avisos = [], [], []
    for n, fila in enumerate(filas_csv, start=2):  # línea 1 = encabezado
        valores = {mapa[col]: val for col, val in fila.items() if col in mapa}
        for c in registro.campos():
            if c.condiciones and c.nombre in valores:
                try:
                    v = codec.valor_para_88(c, valores[c.nombre])
                except codec.ValorInvalido:
                    continue  # el error de formato se reporta abajo
                if not c.acepta(v):
                    nombres = ", ".join(x.nombre for x in c.condiciones)
                    avisos.append(f"línea {n}: {c.nombre}='{valores[c.nombre]}' no coincide con ningún 88 ({nombres})")
        try:
            registros.append(codec.codificar(registro, valores))
        except codec.ValorInvalido as e:
            errores.append(f"línea {n}: {e}")

    for a in avisos:
        print(f"aviso: {a}", file=sys.stderr)
    if args.estricto and avisos:
        errores += ["--estricto: hay valores fuera de los 88 (ver avisos)"]
    if errores:
        print("\n".join(f"error: {e}" for e in errores), file=sys.stderr)
        sys.exit(f"No se escribió {destino}: {len(errores)} error(es).")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(b"".join(registros))
    print(f"{len(registros)} registro(s) de {registro.nombre} ({registro.longitud} bytes c/u) -> {destino}")


def cmd_ver(args):
    registro = registro_de(args.copybook)
    try:
        filas = codec.leer_archivo(registro, args.archivo, args.redefines)
    except (ValueError, codec.ValorInvalido) as e:
        sys.exit(f"error: {e}")
    if args.limite:
        filas = filas[: args.limite]
    campos = [c for c in registro.campos(args.redefines) if not c.es_filler]
    columnas = [c.nombre for c in campos]

    # Enteros DISPLAY con sus ceros a la izquierda, como los ve COBOL (07, no 7)
    for f in filas:
        for c in campos:
            if c.tipo == cb.ZONED and c.escala == 0:
                f[c.nombre] = format(f[c.nombre], "f").zfill(c.digitos)

    if args.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=columnas, lineterminator="\n")
        w.writeheader()
        for f in filas:
            w.writerow({k: texto(f[k]) for k in columnas})
        return

    anchos = {c: max([len(c)] + [len(texto(f[c])) for f in filas]) for c in columnas}
    print("  ".join(c.ljust(anchos[c]) for c in columnas))
    print("  ".join("-" * anchos[c] for c in columnas))
    for f in filas:
        print("  ".join(texto(f[c]).ljust(anchos[c]) for c in columnas))
    print(f"\n{len(filas)} registro(s)")


# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(
        description="Datos de prueba para COBRA (layouts leídos de copybooks/).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="comando", required=True)

    g = sub.add_parser("generar", help="genera cuentas y transacciones aleatorias")
    g.add_argument("--cuentas", type=int, default=100, help="número de cuentas (default 100)")
    g.add_argument("--transacciones", type=int, default=1000, help="número de transacciones (default 1000)")
    g.add_argument("--semilla", type=int, default=42, help="semilla para reproducibilidad (default 42)")
    g.add_argument("--pct-invalidas", type=float, default=10, help="porcentaje de transacciones inválidas (default 10)")
    g.add_argument("--fecha-proceso", help="AAAAMMDD (default: hoy)")
    g.add_argument("--salida", default=str(SALIDA_DEFAULT), help="carpeta de salida (default data/entrada)")
    g.add_argument("--csv", action="store_true", help="escribe también cuentas.csv y transacciones.csv")
    g.set_defaults(func=cmd_generar)

    c = sub.add_parser("cargar", help="convierte un CSV al formato binario de COBOL")
    c.add_argument("copybook", help="nombre (CUENTA) o ruta a un .cpy")
    c.add_argument("entrada", help="archivo CSV con encabezado")
    c.add_argument("-o", "--salida", help="archivo .dat (default: mismo nombre que la entrada)")
    c.add_argument("--separador", default=",", help="separador del CSV (default ',')")
    c.add_argument("--estricto", action="store_true", help="falla si un valor no coincide con sus niveles 88")
    c.set_defaults(func=cmd_cargar)

    v = sub.add_parser("ver", help="muestra el contenido de un archivo binario")
    v.add_argument("copybook", help="nombre (CUENTA) o ruta a un .cpy")
    v.add_argument("archivo", help="archivo .dat")
    v.add_argument("-n", "--limite", type=int, help="muestra solo los primeros N registros")
    v.add_argument("--csv", action="store_true", help="salida en CSV")
    v.add_argument("--redefines", action="store_true", help="incluye también las vistas REDEFINES")
    v.set_defaults(func=cmd_ver)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except cb.CopybookError as e:
        sys.exit(f"error en copybook: {e}")


if __name__ == "__main__":
    main()
