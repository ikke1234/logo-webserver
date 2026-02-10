from pymodbus.client import ModbusTcpClient

PLC_IP="192.168.1.181"
c = ModbusTcpClient(PLC_IP, port=502)
c.connect()

addr = 8279

print("Try holding:")
print(c.read_holding_registers(addr, 1))

print("Try coils:")
print(c.read_coils(addr, 1))

c.close()
