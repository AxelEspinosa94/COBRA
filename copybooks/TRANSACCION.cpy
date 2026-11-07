      *> ---------------------------------------------------------------
      *> TRANSACCION - Movimiento a aplicar sobre una cuenta
      *>   Archivo        : secuencial (entrada del batch diario)
      *>   Identificador  : TRN-ID (único por transacción)
      *>   Longitud       : 80 bytes
      *>
      *>   Campo              Formato               Bytes  Posición
      *>   TRN-ID             X(12)                    12    1-12
      *>   TRN-CUENTA         X(10)                    10   13-22
      *>   TRN-TIPO           X(1)                      1   23
      *>   TRN-IMPORTE        S9(11)V99 COMP-3          7   24-30
      *>   TRN-CTA-DESTINO    X(10)                    10   31-40
      *>   TRN-FECHA-HORA     9(14) AAAAMMDDHHMMSS     14   41-54
      *>   FILLER             X(26)  reservado         26   55-80
      *>
      *>   TRN-CTA-DESTINO solo aplica a transferencias; en los demás
      *>   tipos va en espacios.
      *> ---------------------------------------------------------------
       01  REG-TRANSACCION.
           05  TRN-ID                  PIC X(12).
           05  TRN-CUENTA              PIC X(10).
           05  TRN-TIPO                PIC X(1).
               88  TRN-DEPOSITO                VALUE "D".
               88  TRN-RETIRO                  VALUE "R".
               88  TRN-TRANSFERENCIA           VALUE "T".
               88  TRN-COMISION                VALUE "C".
               88  TRN-TIPO-VALIDO             VALUE "D" "R" "T" "C".
           05  TRN-IMPORTE             PIC S9(11)V99 COMP-3.
           05  TRN-CTA-DESTINO         PIC X(10).
           05  TRN-FECHA-HORA          PIC 9(14).
           05  TRN-FECHA-HORA-R REDEFINES TRN-FECHA-HORA.
               10  TRN-FECHA           PIC 9(8).
               10  TRN-FECHA-R REDEFINES TRN-FECHA.
                   15  TRN-FECHA-AAAA  PIC 9(4).
                   15  TRN-FECHA-MM    PIC 9(2).
                   15  TRN-FECHA-DD    PIC 9(2).
               10  TRN-HORA            PIC 9(6).
               10  TRN-HORA-R REDEFINES TRN-HORA.
                   15  TRN-HORA-HH     PIC 9(2).
                   15  TRN-HORA-MI     PIC 9(2).
                   15  TRN-HORA-SS     PIC 9(2).
           05  FILLER                  PIC X(26).
