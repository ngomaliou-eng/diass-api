from pymodbus.client import ModbusTcpClient
import struct

def decode_le(reg1, reg2):
    raw = struct.pack('>HH', reg2, reg1)
    return struct.unpack('>f', raw)[0]

client = ModbusTcpClient("192.168.123.111", port=502)
client.connect()

# Lire les registres clés identifiés
registres_cles = {
    108:  "Tension AC (V)",
    122:  "Puissance nominale (kW)",
    300:  "Puissance onduleur 1 (W)",
    302:  "Puissance onduleur 2 (W)",
    306:  "Puissance totale (W)",
    348:  "Fréquence (Hz)",
    438:  "Énergie (Wh)",
    702:  "Température ambiante (°C)",
    812:  "Irradiance (W/m²)",
    1030: "Puissance onduleur (W)",
    1132: "Tension AC onduleur (V)",
}

print("=" * 50)
print("Registres clés — UC8112-1")
print("=" * 50)
for adresse, label in registres_cles.items():
    result = client.read_holding_registers(
        address=adresse, count=2, device_id=1
    )
    if not result.isError():
        val = decode_le(result.registers[0], result.registers[1])
        print(f"Reg {adresse:5d} | {val:10.2f} | {label}")

client.close()