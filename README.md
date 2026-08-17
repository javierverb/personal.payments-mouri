# payments-mouri

Genera el PDF de factura del último período de pago ya cerrado, según `fechas-de-pagos.txt` y `_config_params.py`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Config

Editar [`_config_params.py`](_config_params.py):

- `TO_NAME` / `TO_ADDRESS` / `FROM_NAME` / `RATE` / `CURRENCY` / `EMAIL`
- `INVOICE_NO`: número de la próxima factura (se incrementa solo después de generar)
- `OUTPUT_PATH`: carpeta de salida del PDF

Los períodos están en [`fechas-de-pagos.txt`](fechas-de-pagos.txt). El script usa el último período cuya fecha de fin sea `<= hoy`.

## Uso

```bash
source .venv/bin/activate
python generate_invoice.py
```

Ejemplo: si hoy es 17/08/2026, genera el período `07/29/2026 - 08/11/2026` (el de `08/25/2026` todavía no cerró).
