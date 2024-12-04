import os
import datetime

# Establecer el rango de fechas
start_date = datetime.date(2024, 11, 28)
end_date = datetime.date(2024, 11, 29)

# Inicializar contadores
success_count = 0
error_count = 0

# Iterar sobre los archivos de registro
while start_date <= end_date:
    log_filename = f"log_{start_date.strftime('%d_%m_%Y')}.log"
    if os.path.exists(log_filename):
        with open(log_filename, "r") as log_file:
            for line in log_file:
                if "Exito en Ejecucion" in line:
                    success_count += 1
                elif "Error en Ejecucion" in line:
                    error_count += 1
    start_date += datetime.timedelta(days=1)

print(f"Éxitos: {success_count}")
print(f"Errores: {error_count}")