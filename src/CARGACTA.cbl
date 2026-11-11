      *> ---------------------------------------------------------------
      *> CARGACTA - Carga inicial del maestro de cuentas
      *>
      *>   Entrada : CUENTAS  secuencial, registros de 80 bytes (CUENTA)
      *>   Salida  : MAESTRO  indexado, clave primaria CTA-NUMERO
      *>
      *>   Los archivos se asignan por variable de entorno, como las DD
      *>   de un JCL:
      *>     DD_CUENTAS=data/entrada/cuentas.dat
      *>     DD_MAESTRO=data/salida/maestro.idx
      *>
      *>   El maestro se crea desde cero (OPEN OUTPUT): si ya existía,
      *>   se reemplaza. Ante una clave duplicada se conserva la primera
      *>   ocurrencia y las siguientes se rechazan.
      *>
      *>   RETURN-CODE   0  todos los registros se cargaron
      *>                 4  hubo rechazos (se listan en la salida)
      *>                12  error de E/S; la carga se detiene y el
      *>                    maestro queda incompleto. Corregir y volver
      *>                    a correr (OPEN OUTPUT lo recrea).
      *> ---------------------------------------------------------------
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CARGACTA.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUENTAS ASSIGN TO "CUENTAS"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS-CUENTAS.
           SELECT MAESTRO ASSIGN TO "MAESTRO"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS CTA-NUMERO
               FILE STATUS IS FS-MAESTRO.

       DATA DIVISION.
       FILE SECTION.
       FD  CUENTAS.
       01  REG-ENTRADA                 PIC X(80).

       FD  MAESTRO.
       COPY CUENTA.

       WORKING-STORAGE SECTION.
       01  FS-CUENTAS                  PIC XX.
           88  FS-CUENTAS-OK                   VALUE "00".
           88  FS-CUENTAS-FIN                  VALUE "10".
       01  FS-MAESTRO                  PIC XX.
           88  FS-MAESTRO-OK                   VALUE "00".
           88  FS-MAESTRO-DUPLICADA            VALUE "22".

       01  WS-CONTADORES.
           05  WS-LEIDOS               PIC 9(9) COMP-3 VALUE 0.
           05  WS-CARGADOS             PIC 9(9) COMP-3 VALUE 0.
           05  WS-RECHAZADOS           PIC 9(9) COMP-3 VALUE 0.

       01  WS-MOTIVO                   PIC X(30).
           88  WS-SIN-MOTIVO                   VALUE SPACES.

       01  WS-ERROR.
           05  WS-ERR-OPERACION        PIC X(8).
           05  WS-ERR-ARCHIVO          PIC X(8).
           05  WS-ERR-STATUS           PIC XX.

       01  WS-NUM-ED                   PIC ZZZ,ZZZ,ZZ9.

       PROCEDURE DIVISION.
       PRINCIPAL.
           DISPLAY "CARGACTA - Carga inicial del maestro de cuentas"
           PERFORM ABRIR-ARCHIVOS
           PERFORM LEER-CUENTA
           PERFORM UNTIL FS-CUENTAS-FIN
               ADD 1 TO WS-LEIDOS
               PERFORM VALIDAR-CUENTA
               IF WS-SIN-MOTIVO
                   PERFORM GRABAR-CUENTA
               ELSE
                   PERFORM RECHAZAR-CUENTA
               END-IF
               PERFORM LEER-CUENTA
           END-PERFORM
           PERFORM CERRAR-ARCHIVOS
           PERFORM MOSTRAR-TOTALES
           IF WS-RECHAZADOS > ZERO
               MOVE 4 TO RETURN-CODE
           ELSE
               MOVE 0 TO RETURN-CODE
           END-IF
           STOP RUN.

      *> ---------------------------------------------------------------
      *> E/S: cada operación verifica su FILE STATUS
      *> ---------------------------------------------------------------
       ABRIR-ARCHIVOS.
           OPEN INPUT CUENTAS
           IF NOT FS-CUENTAS-OK
               MOVE "OPEN"    TO WS-ERR-OPERACION
               MOVE "CUENTAS" TO WS-ERR-ARCHIVO
               MOVE FS-CUENTAS TO WS-ERR-STATUS
               PERFORM ERROR-FATAL
           END-IF
           OPEN OUTPUT MAESTRO
           IF NOT FS-MAESTRO-OK
               MOVE "OPEN"    TO WS-ERR-OPERACION
               MOVE "MAESTRO" TO WS-ERR-ARCHIVO
               MOVE FS-MAESTRO TO WS-ERR-STATUS
               PERFORM ERROR-FATAL
           END-IF.

       LEER-CUENTA.
           READ CUENTAS INTO REG-CUENTA
           IF NOT FS-CUENTAS-OK AND NOT FS-CUENTAS-FIN
               MOVE "READ"    TO WS-ERR-OPERACION
               MOVE "CUENTAS" TO WS-ERR-ARCHIVO
               MOVE FS-CUENTAS TO WS-ERR-STATUS
               PERFORM ERROR-FATAL
           END-IF.

       GRABAR-CUENTA.
           WRITE REG-CUENTA
           EVALUATE TRUE
               WHEN FS-MAESTRO-OK
                   ADD 1 TO WS-CARGADOS
               WHEN FS-MAESTRO-DUPLICADA
                   MOVE "CLAVE DUPLICADA" TO WS-MOTIVO
                   PERFORM RECHAZAR-CUENTA
               WHEN OTHER
                   MOVE "WRITE"   TO WS-ERR-OPERACION
                   MOVE "MAESTRO" TO WS-ERR-ARCHIVO
                   MOVE FS-MAESTRO TO WS-ERR-STATUS
                   PERFORM ERROR-FATAL
           END-EVALUATE.

       CERRAR-ARCHIVOS.
           CLOSE CUENTAS
           IF NOT FS-CUENTAS-OK
               MOVE "CLOSE"   TO WS-ERR-OPERACION
               MOVE "CUENTAS" TO WS-ERR-ARCHIVO
               MOVE FS-CUENTAS TO WS-ERR-STATUS
               PERFORM ERROR-FATAL
           END-IF
           CLOSE MAESTRO
           IF NOT FS-MAESTRO-OK
               MOVE "CLOSE"   TO WS-ERR-OPERACION
               MOVE "MAESTRO" TO WS-ERR-ARCHIVO
               MOVE FS-MAESTRO TO WS-ERR-STATUS
               PERFORM ERROR-FATAL
           END-IF.

      *> ---------------------------------------------------------------
      *> Validación: deja en WS-MOTIVO la primera falla encontrada
      *> ---------------------------------------------------------------
       VALIDAR-CUENTA.
           MOVE SPACES TO WS-MOTIVO
           EVALUATE TRUE
               WHEN CTA-NUMERO IS NOT NUMERIC
                   MOVE "NUMERO DE CUENTA INVALIDO" TO WS-MOTIVO
               WHEN NOT CTA-TIPO-VALIDO
                   MOVE "TIPO DE CUENTA INVALIDO" TO WS-MOTIVO
               WHEN NOT CTA-ESTATUS-VALIDO
                   MOVE "ESTATUS INVALIDO" TO WS-MOTIVO
               WHEN CTA-SALDO IS NOT NUMERIC
                   MOVE "SALDO NO NUMERICO" TO WS-MOTIVO
               WHEN CTA-TASA-ANUAL IS NOT NUMERIC
                   MOVE "TASA NO NUMERICA" TO WS-MOTIVO
               WHEN CTA-FECHA-ACT IS NOT NUMERIC
                   MOVE "FECHA INVALIDA" TO WS-MOTIVO
               WHEN FUNCTION TEST-DATE-YYYYMMDD(CTA-FECHA-ACT)
                       NOT = ZERO
                   MOVE "FECHA INVALIDA" TO WS-MOTIVO
           END-EVALUATE.

       RECHAZAR-CUENTA.
           ADD 1 TO WS-RECHAZADOS
           MOVE WS-LEIDOS TO WS-NUM-ED
           DISPLAY "  RECHAZO  registro " WS-NUM-ED
                   "  cuenta " CTA-NUMERO "  " FUNCTION TRIM(WS-MOTIVO).

       MOSTRAR-TOTALES.
           MOVE WS-LEIDOS TO WS-NUM-ED
           DISPLAY "  Leidos     : " WS-NUM-ED
           MOVE WS-CARGADOS TO WS-NUM-ED
           DISPLAY "  Cargados   : " WS-NUM-ED
           MOVE WS-RECHAZADOS TO WS-NUM-ED
           DISPLAY "  Rechazados : " WS-NUM-ED.

       ERROR-FATAL.
           DISPLAY "CARGACTA ERROR: " WS-ERR-OPERACION " "
                   WS-ERR-ARCHIVO " FILE STATUS " WS-ERR-STATUS
           MOVE WS-LEIDOS TO WS-NUM-ED
           DISPLAY "  Registros leidos antes del error: " WS-NUM-ED
           CLOSE CUENTAS MAESTRO
           MOVE 12 TO RETURN-CODE
           STOP RUN.
