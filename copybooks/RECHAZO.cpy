      *> ---------------------------------------------------------------
      *> RECHAZO - Transacción rechazada por la validación del batch
      *>   Archivo        : secuencial (salida del paso de validación)
      *>   Longitud       : 160 bytes
      *>
      *>   Campo              Formato               Bytes  Posición
      *>   RCH-TRANSACCION    X(80)  REG-TRANSACCION   80    1-80
      *>   RCH-CODIGO         X(3)   R01..R07           3   81-83
      *>   RCH-DESCRIPCION    X(50)                    50   84-133
      *>   RCH-FECHA-PROCESO  9(8)   AAAAMMDD           8  134-141
      *>   FILLER             X(19)  reservado         19  142-160
      *>
      *>   RCH-TRANSACCION guarda el registro original tal cual, byte a
      *>   byte. Para leer sus campos se mueve de regreso:
      *>       MOVE RCH-TRANSACCION TO REG-TRANSACCION
      *>   (requiere COPY TRANSACCION en el mismo programa)
      *> ---------------------------------------------------------------
       01  REG-RECHAZO.
           05  RCH-TRANSACCION         PIC X(80).
           05  RCH-CODIGO              PIC X(3).
               88  RCH-CTA-INEXISTENTE         VALUE "R01".
               88  RCH-CTA-NO-ACTIVA           VALUE "R02".
               88  RCH-IMPORTE-INVALIDO        VALUE "R03".
               88  RCH-SALDO-INSUFICIENTE      VALUE "R04".
               88  RCH-TIPO-INVALIDO           VALUE "R05".
               88  RCH-DESTINO-INVALIDO        VALUE "R06".
               88  RCH-FECHA-INVALIDA          VALUE "R07".
               88  RCH-CODIGO-VALIDO           VALUE "R01" THRU "R07".
           05  RCH-DESCRIPCION         PIC X(50).
           05  RCH-FECHA-PROCESO       PIC 9(8).
           05  FILLER                  PIC X(19).
