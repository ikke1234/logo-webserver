from .modbus import (
    read_holding_registers,
    read_input_registers,
    read_coils,
    read_discrete_inputs,
)

MAX_HOLDING_BLOCK = 80
MAX_COIL_BLOCK = 200

_last_plc_error = None


def get_plc_status():
    return {"ok": _last_plc_error is None, "error": _last_plc_error}


def _group_blocks(addresses, max_block):
    if not addresses:
        return []
    addrs = sorted(set(addresses))
    blocks = []
    start = prev = addrs[0]
    for a in addrs[1:]:
        if a == prev + 1 and (a - start + 1) <= max_block:
            prev = a
        else:
            blocks.append((start, prev - start + 1))
            start = prev = a
    blocks.append((start, prev - start + 1))
    return blocks


def read_points(points):
    """
    points: [{"id","modbus_kind","address","scale","default"}]
    return: dict(widget_id -> value) (nooit crash)
    """
    global _last_plc_error
    _last_plc_error = None

    holding_addrs = [p["address"] for p in points if p["modbus_kind"] == "holding"]
    input_addrs = [p["address"] for p in points if p["modbus_kind"] == "input"]
    coil_addrs = [p["address"] for p in points if p["modbus_kind"] == "coil"]
    di_addrs = [p["address"] for p in points if p["modbus_kind"] == "di"]

    values_h = {}
    values_i = {}
    values_c = {}
    values_d = {}

    try:
        for start, count in _group_blocks(holding_addrs, MAX_HOLDING_BLOCK):
            rr = read_holding_registers(start, count)
            if rr and not rr.isError():
                for i, v in enumerate(rr.registers):
                    values_h[start + i] = v

        for start, count in _group_blocks(input_addrs, MAX_HOLDING_BLOCK):
            rr = read_input_registers(start, count)
            if rr and not rr.isError():
                for i, v in enumerate(rr.registers):
                    values_i[start + i] = v

        for start, count in _group_blocks(coil_addrs, MAX_COIL_BLOCK):
            rr = read_coils(start, count)
            if rr and not rr.isError():
                for i, b in enumerate(rr.bits):
                    values_c[start + i] = bool(b)

        for start, count in _group_blocks(di_addrs, MAX_COIL_BLOCK):
            rr = read_discrete_inputs(start, count)
            if rr and not rr.isError():
                for i, b in enumerate(rr.bits):
                    values_d[start + i] = bool(b)

    except Exception as e:
        _last_plc_error = str(e)

    out = {}
    for p in points:
        wid = p["id"]
        addr = p["address"]
        kind = p["modbus_kind"]
        scale = float(p.get("scale") or 1.0)
        default = p.get("default")

        if kind == "holding":
            raw = values_h.get(addr, default)
            out[wid] = (raw * scale) if raw is not None else default
        elif kind == "input":
            raw = values_i.get(addr, default)
            out[wid] = (raw * scale) if raw is not None else default
        elif kind == "coil":
            out[wid] = values_c.get(addr, default)
        elif kind == "di":
            out[wid] = values_d.get(addr, default)

    return out
