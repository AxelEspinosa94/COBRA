      *> ---------------------------------------------------------------
      *> DEMO - Programa mínimo para validar el Makefile
      *>   - Resuelve un copybook (-I copybooks)
      *>   - Llama a un subprograma compilado como módulo (CALCINT)
      *>   - Usa aritmética decimal exacta (COMP-3) y salida editada
      *> ---------------------------------------------------------------
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY PARAMINT.
       01  WS-EDITADOS.
           05  WS-SALDO-ED         PIC ZZZ,ZZZ,ZZ9.99-.
           05  WS-TASA-ED          PIC 9.9999.
           05  WS-INTERES-ED       PIC ZZZ,ZZZ,ZZ9.99-.

       PROCEDURE DIVISION.
       PRINCIPAL.
           MOVE 10000.00 TO PI-SALDO
           MOVE 0.0850   TO PI-TASA-ANUAL

           CALL "CALCINT" USING PARAM-INTERES
               ON EXCEPTION
                   DISPLAY "ERROR: no se encontró el módulo CALCINT"
                   MOVE 8 TO RETURN-CODE
                   STOP RUN
           END-CALL

           IF NOT PI-OK
               DISPLAY "ERROR: CALCINT regresó " PI-RETORNO
               MOVE 4 TO RETURN-CODE
               STOP RUN
           END-IF

           MOVE PI-SALDO      TO WS-SALDO-ED
           MOVE PI-TASA-ANUAL TO WS-TASA-ED
           MOVE PI-INTERES    TO WS-INTERES-ED

           DISPLAY "COBRA - prueba de compilación"
           DISPLAY "Saldo        : " WS-SALDO-ED
           DISPLAY "Tasa anual   : " WS-TASA-ED
           DISPLAY "Interés día  : " WS-INTERES-ED

           STOP RUN.
