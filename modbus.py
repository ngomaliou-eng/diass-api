from pymodbus.client import ModbusTcpClient

# Remplacez par l'IP réelle du RTAC ou du datalogger
client = ModbusTcpClient("192.168.123.xx", port=502)

if client.connect():
    print("✓ Connexion Modbus réussie !")
    client.close()
else:
    print("✗ Connexion échouée")