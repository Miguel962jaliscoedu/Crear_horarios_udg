# utils.py

def clean_days(value):
    days_mapping = {
        "L": "Lunes", "M": "Martes", "I": "Miércoles", "J": "Jueves", "V": "Viernes", "S": "Sabado"
    }
    if isinstance(value, str):
        possible_days = list(value.strip())
        cleaned_days = [days_mapping.get(day, f"Desconocido({day})") for day in possible_days]
        return [day for day in cleaned_days if day and "Desconocido" not in day]
    return []