from itertools import combinations
import random

# devuelve una lista de (local_id, visitante_id)
def generate_fixture(club_ids: list[int], seed: int | None = None) -> list[tuple[int, int]]:
    rng = random.Random(seed) # generador de numeros aleatorios
    pares = list(combinations(sorted(club_ids), 2)) # todas las combinaciones entre pares de clubes sin repetir
    rng.shuffle(pares) # Mezclamos la lista para sortear los partidos

    resultado = []
    
    # el primero de la tupla es el local
    for a, b in pares:
        # decidir quién va primero
        if rng.random() < 0.5:
            resultado.append((a, b))
        else:
            resultado.append((b, a))
        
    return resultado
