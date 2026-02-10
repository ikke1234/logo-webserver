from pymodbus.client import ModbusTcpClient
import threading
import time

# PAS AAN
PLC_IP = "192.168.1.181"
PLC_PORT = 502
UNIT_ID = 1

# kortere timeout zodat je server niet “hangt”
client = ModbusTcpClient(PLC_IP, port=PLC_PORT, timeout=2)

lock = threading.Lock()
_last_connect_fail_ts = 0


def connect() -> bool:
    """Return True als verbonden, anders False (geen crash)."""
    global _last_connect_fail_ts

    try:
        if client.connected:
            return True
        ok = client.connect()
        if not ok:
            _last_connect_fail_ts = time.time()
        return bool(ok)
    except Exception:
        _last_connect_fail_ts = time.time()
        return False


def _call_unit_or_slave(fn, *args):
    """
    pymodbus 2.x gebruikt unit=
    pymodbus 3.x gebruikt slave=
    Deze wrapper probeert beide.
    """
    try:
        return fn(*args, slave=UNIT_ID)
    except TypeError:
        return fn(*args, unit=UNIT_ID)


# ---------- READ wrappers ----------
def read_holding_registers(start: int, count: int):
    if not connect():
        raise ConnectionError("PLC Modbus connect failed")
    return _call_unit_or_slave(client.read_holding_registers, start, count)


def read_input_registers(start: int, count: int):
    if not connect():
        raise ConnectionError("PLC Modbus connect failed")
    return _call_unit_or_slave(client.read_input_registers, start, count)


def read_coils(start: int, count: int):
    if not connect():
        raise ConnectionError("PLC Modbus connect failed")
    return _call_unit_or_slave(client.read_coils, start, count)


def read_discrete_inputs(start: int, count: int):
    if not connect():
        raise ConnectionError("PLC Modbus connect failed")
    return _call_unit_or_slave(client.read_discrete_inputs, start, count)


# ---------- WRITE wrappers ----------
def write_register(addr: int, value: int):
    if not connect():
        raise ConnectionError("PLC Modbus connect failed")
    rq = _call_unit_or_slave(client.write_register, addr, value)
    if rq.isError():
        raise RuntimeError(f"Write register error addr={addr}: {rq}")


def write_coil(addr: int, value: bool):
    if not connect():
        raise ConnectionError("PLC Modbus connect failed")
    rq = _call_unit_or_slave(client.write_coil, addr, value)
    if rq.isError():
        raise RuntimeError(f"Write coil error addr={addr}: {rq}")
