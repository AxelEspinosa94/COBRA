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
