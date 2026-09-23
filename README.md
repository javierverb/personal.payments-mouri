# payments-mouri

Genera el PDF de factura del último período de pago ya cerrado, según `fechas-de-pagos.txt` y `_config_params.py`.

## Setup

```bash
cd /home/javier/projects/personal/payments-mouri
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./install_cron.sh
```

## Config

Editar [`_config_params.py`](_config_params.py):

- `TO_NAME` / `TO_ADDRESS` / `FROM_NAME` / `RATE` / `CURRENCY` / `EMAIL`
- `INVOICE_NO`: número de la próxima factura (se incrementa solo después de generar + abrir correo)
- `OUTPUT_PATH`: carpeta de salida del PDF
- `OPEN_THUNDERBIRD`: si es `True`, abre Thunderbird con el PDF adjunto
- `EMAIL_TO`: destinatario del correo
- `CRON_EVERY_MINUTES`: cada cuántos minutos revisa el cron (default 30)

Los períodos están en [`fechas-de-pagos.txt`](fechas-de-pagos.txt) (`inicio - fin | due-date`). El script usa el último período cuya fecha de fin sea `<= hoy`. En el PDF/email, **Invoice Due** usa la tercera columna (due-date).

## Uso manual

Desde el proyecto:

```bash
cd /home/javier/projects/personal/payments-mouri
source .venv/bin/activate
```

**Forzar** generación + Thunderbird (ignora si el período ya fue enviado):

```bash
python generate_invoice.py
```

**Igual que el cron** (solo si el período cerrado aún no está en `sent_periods.json`):

```bash
python generate_invoice.py --if-needed
# o:
./run_cron.sh
```

## Cron

**Estado:** instalado en el crontab del usuario.

```cron
*/30 * * * * /home/javier/projects/personal/payments-mouri/run_cron.sh >> .../logs/cron.log 2>&1
```

- Corre **cada 30 minutos**
- Si el período ya está en `sent_periods.json` → skip
- Si no → genera PDF, abre Thunderbird y marca el período

Verificar / reinstalar:

```bash
crontab -l
./install_cron.sh
```

Logs: `logs/cron.log`

Ejemplo: si hoy es 17/08/2026, genera el período `07/29/2026 - 08/11/2026` (el de `08/25/2026` todavía no cerró).
