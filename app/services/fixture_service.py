import random

# devuelve una lista de fechas, cada fecha es una lista de (local_id, visitante_id)
def generate_fixture(club_ids: list[int], seed: int | None = None) -> list[list[tuple[int, int]]]:
    rng = random.Random(seed) # generador de numeros aleatorios
    ids = sorted(club_ids) # ordenamos la lista
    rng.shuffle(ids) # Mezclamos la lista para sortear los partidos
    
    if len(ids) % 2 != 0:
        ids.append(None)

    fechas = []

    n = len(ids)
    
    for _ in range(n - 1): # _: no se usa en el loop
        fecha = []
        j = n - 1
        i = 0
        while j > i:
            
            if ids[i] is not None and ids[j] is not None:
                # calculamos local y visitante
                if rng.random() < 0.5:
                    fecha.append((ids[i], ids[j]))
                else:
                    fecha.append((ids[j], ids[i]))
            
            i = i + 1
            j = j - 1

        fechas.append(fecha)

        # rotamos los clubes para la siguiente fecha      
        fijo = ids[0]
        resto = ids[1:]
        resto = resto[-1:] + resto[:-1]   # el último pasa adelante, los demás se corren
        ids = [fijo] + resto

    return fechas