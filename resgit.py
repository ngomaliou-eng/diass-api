from pymodbus.client import ModbusTcpClient
import struct

def decode_formats(reg1, reg2):
    """Teste tous les formats possibles"""
    # Format 1 : big-endian standard
    raw_be = struct.pack('>HH', reg1, reg2)
    f_be = struct.unpack('>f', raw_be)[0]
    # Format 2 : little-endian inversé (CDAB)
    raw_le = struct.pack('>HH', reg2, reg1)
    f_le = struct.unpack('>f', raw_le)[0]
    return f_be, f_le

client = ModbusTcpClient("192.168.123.111", port=502)
client.connect()

# Tester adresse 1000 qui avait des valeurs variées
result = client.read_holding_registers(address=1000, count=40, device_id=1)
regs = result.registers

print("=== Adresse 1000 — tous formats ===")
for i in range(0, len(regs)-1, 2):
    f_be, f_le = decode_formats(regs[i], regs[i+1])
    # Afficher seulement les valeurs plausibles (0-25000)
    if 0 <= abs(f_be) <= 25000 or 0 <= abs(f_le) <= 25000:
        print(f"Reg {1000+i}-{1000+i+1} | BE: {f_be:10.2f} | LE: {f_le:10.2f} | brut: {regs[i]},{regs[i+1]}")

client.close()