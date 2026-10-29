      *> ---------------------------------------------------------------
      *> PARAMINT - Parámetros del cálculo de interés diario
      *> Compartido entre el llamador y el subprograma CALCINT.
      *> ---------------------------------------------------------------
       01  PARAM-INTERES.
           05  PI-SALDO            PIC S9(11)V99 COMP-3.
           05  PI-TASA-ANUAL       PIC 9V9(4)    COMP-3.
           05  PI-INTERES          PIC S9(11)V99 COMP-3.
           05  PI-RETORNO          PIC 99.
               88  PI-OK                         VALUE 00.
               88  PI-SALDO-NO-POSITIVO          VALUE 10.
