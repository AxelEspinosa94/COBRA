      *> ---------------------------------------------------------------
      *> CALCINT - Subprograma: interés diario, convención 360 días
      *>   interes = saldo * tasa_anual / 360, redondeado a 2 decimales
      *> Se compila como módulo (cobc -m) y se invoca con CALL.
      *> ---------------------------------------------------------------
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALCINT.

       DATA DIVISION.
       LINKAGE SECTION.
       COPY PARAMINT.

       PROCEDURE DIVISION USING PARAM-INTERES.
       PRINCIPAL.
           IF PI-SALDO NOT > ZERO
               MOVE ZERO TO PI-INTERES
               SET PI-SALDO-NO-POSITIVO TO TRUE
           ELSE
               COMPUTE PI-INTERES ROUNDED =
                   PI-SALDO * PI-TASA-ANUAL / 360
               SET PI-OK TO TRUE
           END-IF
           GOBACK.
