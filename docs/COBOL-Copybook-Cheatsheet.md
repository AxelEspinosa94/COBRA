# COBOL Copybook Cheatsheet

How to write `.cpy` files for COBRA: defining fields, choosing data types, declaring valid values with level 88, and redefining storage with `REDEFINES`.

> Every rule marked ✅ / ❌ was verified against **GnuCOBOL 3.1.2** (the version used in this repo and in CI).

---

## Table of Contents

1. [Copybook Basics](#1-copybook-basics)
   - 1.1 [What a copybook is](#11-what-a-copybook-is)
   - 1.2 [Including a copybook](#12-including-a-copybook)
   - 1.3 [File conventions in this repo](#13-file-conventions-in-this-repo)
2. [Fixed Format Layout](#2-fixed-format-layout)
3. [Level Numbers](#3-level-numbers)
4. [Defining Fields](#4-defining-fields)
   - 4.1 [PICTURE symbols](#41-picture-symbols)
   - 4.2 [USAGE and storage size](#42-usage-and-storage-size)
   - 4.3 [Choosing the right type](#43-choosing-the-right-type)
   - 4.4 [Group items and FILLER](#44-group-items-and-filler)
   - 4.5 [Calculating record length](#45-calculating-record-length)
5. [Valid Values with Level 88](#5-valid-values-with-level-88)
   - 5.1 [Syntax](#51-syntax)
   - 5.2 [Using condition names](#52-using-condition-names)
   - 5.3 [Rules](#53-rules)
6. [Redefinition with REDEFINES](#6-redefinition-with-redefines)
   - 6.1 [What REDEFINES does](#61-what-redefines-does)
   - 6.2 [Rules](#62-rules)
   - 6.3 [Common patterns](#63-common-patterns)
   - 6.4 [Pitfalls](#64-pitfalls)
7. [Tables with OCCURS](#7-tables-with-occurs)
8. [Validation Toolkit](#8-validation-toolkit)
9. [Naming Conventions](#9-naming-conventions)
10. [Pre-commit Checklist](#10-pre-commit-checklist)
11. [Full Example](#11-full-example)

---

## 1. Copybook Basics

### 1.1 What a copybook is

A copybook is a fragment of COBOL source that is pasted into a program at compile time. It is the COBOL equivalent of a C header: it defines a **record layout once** so every program that reads or writes that record agrees on it byte for byte.

A copybook usually contains **only data definitions**: an `01` group with its fields. No `IDENTIFICATION DIVISION`, no `PROCEDURE DIVISION`.

### 1.2 Including a copybook

```cobol
       WORKING-STORAGE SECTION.
       COPY CUENTA.
```

The compiler looks for `CUENTA.cpy` in the include path. The Makefile passes `-I copybooks`.

The same copybook can go in any section:

| Section | Typical use |
|---------|-------------|
| `FILE SECTION` (under an `FD`) | Record layout of a file |
| `WORKING-STORAGE SECTION` | Working copy of a record |
| `LINKAGE SECTION` | Parameters received by a subprogram (`CALL ... USING`) |

`COPY ... REPLACING` lets you include the same layout twice with different prefixes:

```cobol
       COPY CUENTA REPLACING ==REG-CUENTA== BY ==REG-ORIG==
                             LEADING ==CTA-== BY ==ORIG-==.
```

This gives you `REG-ORIG` with fields `ORIG-NUMERO`, `ORIG-SALDO`, etc., alongside the original `REG-CUENTA`. Useful for "before / after" comparisons.

> ⚠️ Plain `REPLACING ==CTA-== BY ==ORIG-==` does **nothing**: it only matches whole words. Prefixes need `LEADING`. Rename the `01` too, or you get a duplicate `REG-CUENTA`.

### 1.3 File conventions in this repo

| Rule | Example |
|------|---------|
| Location | `copybooks/` |
| Extension | `.cpy` |
| File name = record name, uppercase | `CUENTA.cpy` → `01 REG-CUENTA` |
| One record per copybook | |
| Header comment with layout table | See [section 11](#11-full-example) |
| Must pass `make lint` | |

---

## 2. Fixed Format Layout

```
Column:  1      7 8   12                                                    72 73    80
         |------|-|---|------------------------------------------------------|-------|
         sequence  A   B (program text)                                       ignored
         indicator
```

| Columns | Area | Contents |
|---------|------|----------|
| 1–6 | Sequence | Spaces or digits |
| 7 | Indicator | ` ` code, `*` comment, `-` continuation, `/` page break, `D` debug |
| 8–11 | **Area A** | Levels `01` and `77`, `FD`, division and section headers |
| 12–72 | **Area B** | Levels `02`–`49`, `66`, `88`, and everything else |
| 73–80 | Identification | **Silently ignored by the compiler** |

> ⚠️ GnuCOBOL counts **bytes**, not characters. In UTF-8, `á`, `é`, `ñ` take 2 columns each. Avoid accents in code; keep them in comments only if needed.

---

## 3. Level Numbers

| Level | Meaning | Area |
|-------|---------|------|
| `01` | Record (top-level group) | A |
| `02`–`49` | Subordinate fields. Convention: step by 5 (`05`, `10`, `15`) to leave room for insertion | B |
| `66` | `RENAMES` (regroup existing fields; rarely used) | B |
| `77` | Standalone elementary item (not used in copybooks) | A |
| `88` | Condition name: a named value of the field above it | B |

```cobol
       01  REG-CUENTA.                         *> group (no PIC)
           05  CTA-NUMERO          PIC X(10).  *> elementary (has PIC)
           05  CTA-FECHA-ACT-G.                *> nested group
               10  CTA-AAAA        PIC 9(4).
```

- A **group** has no `PIC`. Its size is the sum of its children and it is always treated as alphanumeric.
- An **elementary item** has a `PIC` and holds the data.

---

## 4. Defining Fields

### 4.1 PICTURE symbols

| Symbol | Meaning | Example | Holds |
|--------|---------|---------|-------|
| `X` | Any character | `PIC X(10)` | `"ABC       "` |
| `A` | Letter or space | `PIC A(5)` | `"HELLO"` |
| `9` | Digit | `PIC 9(4)` | `0042` |
| `S` | Sign (no storage in COMP-3; overpunched in DISPLAY) | `PIC S9(4)` | `-42` |
| `V` | Implied decimal point (**takes no space**) | `PIC 9(3)V99` | `123.45` stored as `12345` |
| `(n)` | Repetition | `X(3)` = `XXX` | |

> Editing symbols (`Z`, `,`, `.`, `-`, `$`) are for **output formatting** only. Never use them in a record copybook.

### 4.2 USAGE and storage size

| USAGE | Storage | Size formula | Use for |
|-------|---------|--------------|---------|
| `DISPLAY` (default) | 1 char per digit | n bytes | Text files, IDs, dates |
| `COMP-3` / `PACKED-DECIMAL` | 2 digits per byte + sign nibble | `floor(n / 2) + 1` | **Money**, rates, any decimal arithmetic |
| `COMP` / `BINARY` | Binary integer | See table below | Counters, indexes, lengths |
| `COMP-5` | Native binary, full range | Same as `COMP` | Interop with C |

`n` = number of `9`s, including those after `V`.

**Verified sizes in GnuCOBOL 3.1.2:**

| Definition | Bytes |
|------------|-------|
| `PIC S9(11)V99 COMP-3` | 7 |
| `PIC 9V9(4) COMP-3` | 3 |
| `PIC 9(4) COMP-3` | 3 |
| `PIC 9(2) COMP` | 1 ⚠️ |
| `PIC 9(4) COMP` | 2 |
| `PIC 9(9) COMP` | 4 |
| `PIC 9(18) COMP` | 8 |

> ⚠️ **Portability:** GnuCOBOL's default packs `COMP` into 1, 2, 4 or 8 bytes. IBM mainframes use 2 bytes minimum (`9(1)`–`9(4)` = 2 bytes). For records shared with other systems, prefer `COMP-3` or `DISPLAY`.

> 💡 Give `COMP-3` fields an **odd** number of digits (`S9(11)V99` = 13). An even count wastes half a byte.

### 4.3 Choosing the right type

| Data | Recommended | Why |
|------|-------------|-----|
| Account number, ID, ZIP, phone | `PIC X(n)` | No arithmetic; keeps leading zeros; may contain letters later |
| Money | `PIC S9(n)V99 COMP-3` | Exact decimal arithmetic, signed |
| Interest rate | `PIC 9V9(4) COMP-3` | 4 decimals: `0.0850` = 8.5 % |
| Quantity, counter | `PIC 9(n) COMP-3` or `COMP` | Arithmetic |
| Date | `PIC 9(8)` as `YYYYMMDD` | Sortable and comparable as a number |
| Timestamp | `PIC 9(14)` as `YYYYMMDDHHMMSS` | Same |
| Code or status | `PIC X(1)` + level 88 | Compact, self-documenting |
| Flag (yes/no) | `PIC X(1)` + level 88 | `"S"`/`"N"` or `"Y"`/`"N"` |
| Free text | `PIC X(n)` | Space-padded on the right |

> ❌ **Never** use floating point (`COMP-1`, `COMP-2`) for money.

### 4.4 Group items and FILLER

`FILLER` reserves bytes without a name. Use it to:

- **Reserve room for growth** without changing the record length later.
- Skip fields you don't use in a given program.

```cobol
       01  REG-EJEMPLO.
           05  EJ-CLAVE            PIC X(10).
           05  EJ-DATOS            PIC X(60).
           05  FILLER              PIC X(10).  *> reserved
```

### 4.5 Calculating record length

Add the byte size of each **elementary** item. Do not count `88` levels or `REDEFINES`. They take no extra space.

Verify it with a throwaway program:

```cobol
           DISPLAY "LENGTH: " LENGTH OF REG-CUENTA
```

Document the result in the copybook header.

---

## 5. Valid Values with Level 88

### 5.1 Syntax

A level 88 gives a **name to one or more values** of the field directly above it.

```cobol
           05  CTA-ESTATUS             PIC X(1).
               88  CTA-ACTIVA                  VALUE "A".
               88  CTA-BLOQUEADA               VALUE "B".
               88  CTA-CERRADA                 VALUE "C".
               88  CTA-ESTATUS-VALIDO          VALUE "A" "B" "C".
```

| Form | Example |
|------|---------|
| Single value | `VALUE "A"` |
| List | `VALUE "A" "E" "I" "O" "U"` |
| Range | `VALUE 0 THRU 49` |
| Mixed | `VALUE "0" THRU "9" "X"` |
| With FALSE value | `VALUE "S" WHEN SET TO FALSE "N"` |

### 5.2 Using condition names

```cobol
      *> Test
           IF CTA-BLOQUEADA
               PERFORM RECHAZAR
           END-IF

      *> Validate
           IF NOT CTA-ESTATUS-VALIDO
               PERFORM RECHAZAR
           END-IF

      *> Assign (moves the first VALUE into the parent field)
           SET CTA-ACTIVA TO TRUE

      *> In EVALUATE
           EVALUATE TRUE
               WHEN CTA-ACTIVA     PERFORM PROCESAR
               WHEN CTA-BLOQUEADA  PERFORM RECHAZAR
               WHEN OTHER          PERFORM ERROR-ESTATUS
           END-EVALUATE
```

### 5.3 Rules

| Rule | |
|------|---|
| An 88 has **no `PIC`** and **takes no storage** | ❌ `88 X PIC X(10).` |
| It must sit directly under an elementary field (or a group) | |
| Its values must match the parent's type and fit its size | |
| `SET ... TO TRUE` uses the **first** value of the list | |
| `SET ... TO FALSE` requires a `WHEN SET TO FALSE` clause | ❌ compile error without it |
| Group the valid set in its own 88 (`...-VALIDO`) for validation | ✅ |

---

## 6. Redefinition with REDEFINES

### 6.1 What REDEFINES does

`REDEFINES` gives a **second view of the same bytes**. It does not copy, convert or validate anything.

```cobol
           05  CTA-FECHA-ACT           PIC 9(8).
           05  CTA-FECHA-ACT-R REDEFINES CTA-FECHA-ACT.
               10  CTA-FECHA-AAAA      PIC 9(4).
               10  CTA-FECHA-MM        PIC 9(2).
               10  CTA-FECHA-DD        PIC 9(2).
```

```
Bytes:            2  0  2  6  1  0  3  1
CTA-FECHA-ACT     └──────────────────────┘  20261031
CTA-FECHA-ACT-R   └────────┘ └──┘ └──┘
                     2026     10   31
```

Writing through one name changes what the other one sees, immediately.

### 6.2 Rules

| Rule | GnuCOBOL 3.1.2 |
|------|----------------|
| Same level number as the item it redefines | Required |
| Must come **immediately after** the original (or after another redefinition of it) | ❌ `REDEFINES must follow the original definition` |
| Several views of the same original are allowed | ✅ `B REDEFINES A`, `C REDEFINES A` |
| Cannot redefine a redefinition | ❌ `'B' is not the original definition` |
| Below level 01, the new view **cannot be larger** than the original | ❌ `size of 'B' larger than size of 'A'` |
| At level 01 a larger view is accepted | ✅ (avoid it anyway) |
| `VALUE` on a redefining item is ignored | ⚠️ warning `-Winitial-value` |
| Level 88 under a redefining item | ✅ allowed |
| Level 66 and 88 cannot use `REDEFINES` | ❌ |

### 6.3 Common patterns

**a) Break a field into parts**: dates, composite keys.

```cobol
           05  TRN-CLAVE               PIC X(16).
           05  TRN-CLAVE-R REDEFINES TRN-CLAVE.
               10  TRN-SUCURSAL        PIC X(4).
               10  TRN-FOLIO           PIC X(12).
```

**b) Validate numeric input that arrives as text.**

```cobol
           05  IN-IMPORTE-X            PIC X(10).
           05  IN-IMPORTE REDEFINES IN-IMPORTE-X
                                       PIC 9(8)V99.

           IF IN-IMPORTE IS NUMERIC
               MOVE IN-IMPORTE TO CTA-SALDO
           ELSE
               PERFORM RECHAZAR
           END-IF
```

**c) Variant records**: one layout per record type, chosen by a type code.

```cobol
       01  REG-MOVIMIENTO.
           05  MOV-TIPO                PIC X(1).
               88  MOV-DEPOSITO                VALUE "D".
               88  MOV-TRANSFERENCIA           VALUE "T".
           05  MOV-DETALLE             PIC X(40).
           05  MOV-DEPOSITO-R REDEFINES MOV-DETALLE.
               10  DEP-CUENTA          PIC X(10).
               10  DEP-IMPORTE         PIC S9(11)V99 COMP-3.
               10  FILLER              PIC X(23).
           05  MOV-TRANSFER-R REDEFINES MOV-DETALLE.
               10  TRF-ORIGEN          PIC X(10).
               10  TRF-DESTINO         PIC X(10).
               10  TRF-IMPORTE         PIC S9(11)V99 COMP-3.
               10  FILLER              PIC X(13).
```

Always check the type code before using a view:

```cobol
           EVALUATE TRUE
               WHEN MOV-DEPOSITO       ADD DEP-IMPORTE TO ...
               WHEN MOV-TRANSFERENCIA  ...
           END-EVALUATE
```

**d) Table with initial values**: load constants into an array.

```cobol
       01  TABLA-TIPOS.
           05  FILLER                  PIC X(6) VALUE "AABBCC".
       01  TABLA-TIPOS-R REDEFINES TABLA-TIPOS.
           05  TIPO-COD                PIC X(2) OCCURS 3 TIMES.
```

`TIPO-COD(2)` → `"BB"`.

### 6.4 Pitfalls

| Pitfall | Consequence |
|---------|-------------|
| Assuming `REDEFINES` validates | `20262031` is accepted; `MM` = `20`. Validate explicitly |
| Reading a numeric view of non-numeric bytes | Garbage or a runtime data exception. Test `IS NUMERIC` first |
| Viewing `COMP-3` bytes as `PIC X` or `PIC 9` | Raw packed bytes, not digits |
| Using the wrong variant view | Silent wrong data. Always branch on the type code |
| Variant views of different sizes | Pad the smaller ones with `FILLER` so every view matches the original |

---

## 7. Tables with OCCURS

```cobol
           05  CTA-MOVS-MES            PIC S9(9)V99 COMP-3
                                       OCCURS 12 TIMES
                                       INDEXED BY IX-MES.
```

- Subscripts start at **1**: `CTA-MOVS-MES(1)` to `CTA-MOVS-MES(12)`.
- Size = element size × occurrences.
- `OCCURS` is not allowed on level `01`, `66`, `77` or `88`.
- Avoid `OCCURS ... DEPENDING ON` in file records unless you need variable-length records.

---

## 8. Validation Toolkit

| Check | How |
|-------|-----|
| Value is in the allowed set | `IF NOT CTA-ESTATUS-VALIDO` |
| Value is in a range | 88 with `THRU`: `88 MES-VALIDO VALUE 1 THRU 12` |
| Text contains only digits | `IF campo IS NUMERIC` |
| Text contains only letters | `IF campo IS ALPHABETIC` |
| Field is empty | `IF campo = SPACES` |
| Valid date `YYYYMMDD` | `IF FUNCTION TEST-DATE-YYYYMMDD(campo) = 0` (handles leap years) |
| Amount is positive | `IF importe > ZERO` |

---

## 9. Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Record (01) | `REG-` + entity | `REG-CUENTA` |
| Fields | **Unique prefix per copybook** | `CTA-`, `TRN-`, `RCH-` |
| Redefinition | Original name + `-R` | `CTA-FECHA-ACT-R` |
| Valid-set 88 | Field + `-VALIDO` | `CTA-TIPO-VALIDO` |
| Raw text input | Field + `-X` | `IN-IMPORTE-X` |

> Why unique prefixes: a program that includes two copybooks with the same field name (`SALDO` in both) gets ambiguous-reference errors.

Current prefixes:

| Copybook | Prefix |
|----------|--------|
| `PARAMINT.cpy` | `PI-` |
| `CUENTA.cpy` | `CTA-` |

---

## 10. Pre-commit Checklist

- [ ] Header comment with purpose, key, and a field table (format, bytes, position)
- [ ] Record length documented and verified with `LENGTH OF`
- [ ] Unique field prefix, not used by any other copybook
- [ ] Money and rates in `COMP-3`; IDs in `PIC X`
- [ ] Every code or status field has its 88 values plus a `-VALIDO` set
- [ ] Every `REDEFINES` is the same size as its original (pad with `FILLER`)
- [ ] No `VALUE` clauses in file or linkage records
- [ ] No text beyond column 72; no tabs; no accents in code
- [ ] `make lint` and `make` pass

---

## 11. Full Example

`copybooks/CUENTA.cpy`, the account master record:

```cobol
      *> ---------------------------------------------------------------
      *> CUENTA - Registro del maestro de cuentas (archivo indexado)
      *>   Clave primaria : CTA-NUMERO
      *>   Longitud       : 80 bytes
      *>
      *>   Campo              Formato               Bytes  Posición
      *>   CTA-NUMERO         X(10)                    10    1-10
      *>   CTA-TITULAR        X(50)                    50   11-60
      *>   CTA-TIPO           X(1)                      1   61
      *>   CTA-SALDO          S9(11)V99 COMP-3          7   62-68
      *>   CTA-TASA-ANUAL     9V9(4)    COMP-3          3   69-71
      *>   CTA-ESTATUS        X(1)                      1   72
      *>   CTA-FECHA-ACT      9(8) AAAAMMDD             8   73-80
      *> ---------------------------------------------------------------
       01  REG-CUENTA.
           05  CTA-NUMERO              PIC X(10).
           05  CTA-TITULAR             PIC X(50).
           05  CTA-TIPO                PIC X(1).
               88  CTA-AHORRO                  VALUE "A".
               88  CTA-CHEQUES                 VALUE "C".
               88  CTA-TIPO-VALIDO             VALUE "A" "C".
           05  CTA-SALDO               PIC S9(11)V99 COMP-3.
           05  CTA-TASA-ANUAL          PIC 9V9(4)    COMP-3.
           05  CTA-ESTATUS             PIC X(1).
               88  CTA-ACTIVA                  VALUE "A".
               88  CTA-BLOQUEADA               VALUE "B".
               88  CTA-CERRADA                 VALUE "C".
               88  CTA-ESTATUS-VALIDO          VALUE "A" "B" "C".
           05  CTA-FECHA-ACT           PIC 9(8).
           05  CTA-FECHA-ACT-R REDEFINES CTA-FECHA-ACT.
               10  CTA-FECHA-AAAA      PIC 9(4).
               10  CTA-FECHA-MM        PIC 9(2).
               10  CTA-FECHA-DD        PIC 9(2).
```