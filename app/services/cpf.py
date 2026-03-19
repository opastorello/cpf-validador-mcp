import re


def calcular_digitos(cpf9: str) -> str:
    digits = [int(c) for c in cpf9]

    soma = sum(digits[i] * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto

    digits.append(d1)
    soma = sum(digits[i] * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto

    return f"{d1}{d2}"


def is_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    if len(set(cpf)) == 1:
        return False
    return calcular_digitos(cpf[:9]) == cpf[9:]


def formatar(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def validate_cpf(cpf: str) -> dict:
    numeros = re.sub(r"\D", "", cpf)
    valido = is_valido(numeros)
    return {
        "valido": valido,
        "cpf_formatado": formatar(numeros) if len(numeros) == 11 else None,
        "cpf_numeros": numeros,
        "mensagem": "CPF válido." if valido else "CPF inválido.",
    }


def gerar_cpfs_de_mascara(mascara: str) -> list[str]:
    """Gera todos os CPFs válidos a partir de uma máscara com * nos dígitos desconhecidos.
    Ex: '***.587.570-**' → lista com todos os CPFs válidos com miolo 587570.
    Os dígitos verificadores (posições 10-11) são sempre recalculados.
    """
    # Extrai sequência de dígitos e wildcards (ignora pontos, traços, espaços)
    chars = [c for c in mascara if c.isdigit() or c == "*"]
    if len(chars) != 11:
        raise ValueError(f"Máscara deve ter 11 posições (dígitos ou *), recebeu {len(chars)}: '{mascara}'")

    # Posições 0-8 são a base; posições 9-10 são os verificadores (sempre recalculados)
    base_template = chars[:9]

    # Descobre quais posições da base são wildcards
    wildcard_positions = [i for i, c in enumerate(base_template) if c == "*"]

    candidates = []
    for combo in _product("0123456789", repeat=len(wildcard_positions)):
        base = list(base_template)
        for pos, digit in zip(wildcard_positions, combo):
            base[pos] = digit
        base9 = "".join(base)
        cpf11 = base9 + calcular_digitos(base9)
        if is_valido(cpf11):
            candidates.append(cpf11)

    return candidates


def _product(iterable, repeat=1):
    """itertools.product reimplementado para evitar import extra."""
    import itertools
    return itertools.product(iterable, repeat=repeat)


def generate_valid_variations(cpf: str) -> dict:
    numeros = re.sub(r"\D", "", cpf)
    if len(numeros) != 11:
        return {"error": f"CPF deve ter 11 dígitos, recebido {len(numeros)}", "variations": []}
    original_valido = is_valido(numeros)

    seen = set()
    variations = []

    def add(candidate: str):
        if candidate not in seen and is_valido(candidate):
            seen.add(candidate)
            variations.append({"cpf_numeros": candidate, "cpf_formatado": formatar(candidate)})

    # original
    add(numeros)

    # recalculate check digits
    if len(numeros) >= 9:
        recalc = numeros[:9] + calcular_digitos(numeros[:9])
        add(recalc)

    # swap one digit (positions 0-8 only to keep base, recalc check digits)
    for i in range(9):
        for d in "0123456789":
            if d != numeros[i]:
                candidate_base = numeros[:i] + d + numeros[i + 1:9]
                candidate = candidate_base + calcular_digitos(candidate_base)
                add(candidate)

    # transpose adjacent digits
    for i in range(10):
        lst = list(numeros)
        lst[i], lst[i + 1] = lst[i + 1], lst[i]
        candidate = "".join(lst)
        add(candidate)

    return {
        "original": numeros,
        "original_valido": original_valido,
        "total_variacoes": len(variations),
        "variations": variations,
    }
