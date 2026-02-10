# LOGO mapping volgens jouw tabel
# Q: coil 8193-8212 (Q1..Q20)
# M: coil 8257-8320 (M1..M64)
# V bits: coil 1-6808 (V0.0..V850.7)
# AI: input register 1-8
# VW: holding register 1-425 (VW0..VW850) -> VW is byte-offset: VW0, VW2, VW4 ... => reg = VW/2 + 1
# AQ: holding register 513-520
# AM: holding register 529-592

def translate(resource: str, index: str):
    r = resource.upper().strip()

    # Q1..Q20
    if r == "Q":
        n = int(index)
        if not (1 <= n <= 20): raise ValueError("Q range 1..20")
        return {"modbus_kind": "coil", "address": 8193 + (n - 1)}

    # M1..M64
    if r == "M":
        n = int(index)
        if not (1 <= n <= 64): raise ValueError("M range 1..64")
        return {"modbus_kind": "coil", "address": 8257 + (n - 1)}

    # AI1..AI8
    if r == "AI":
        n = int(index)
        if not (1 <= n <= 8): raise ValueError("AI range 1..8")
        return {"modbus_kind": "input", "address": n}  # input register

    # AQ1..AQ8
    if r == "AQ":
        n = int(index)
        if not (1 <= n <= 8): raise ValueError("AQ range 1..8")
        return {"modbus_kind": "holding", "address": 513 + (n - 1)}

    # AM1..AM64
    if r == "AM":
        n = int(index)
        if not (1 <= n <= 64): raise ValueError("AM range 1..64")
        return {"modbus_kind": "holding", "address": 529 + (n - 1)}

    # VW0..VW850 (even nummers!)
    if r == "VW":
        n = int(index)
        if not (0 <= n <= 850): raise ValueError("VW range 0..850")
        if (n % 2) != 0:
            raise ValueError("VW moet even zijn (VW0, VW2, VW4, ...)")
        # register 1..425
        addr = (n // 2) + 1
        if not (1 <= addr <= 425): raise ValueError("VW mapping buiten 1..425")
        return {"modbus_kind": "holding", "address": addr}

    raise ValueError("Onbekend resource (Q/M/AI/AQ/AM/VW)")
