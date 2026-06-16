from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.123.111", port=502)
client.connect()
print("✓ Connexion UC8112-1 réussie !")

# Lire 50 registres à partir de différentes adresses
for adresse in [0, 50, 100, 200, 500, 1000]:
    result = client.read_holding_registers(
        address=adresse, 
        count=20, 
        device_id=1
    )
    if not result.isError():
        print(f"\nAdresse {adresse} → {result.registers}")
    else:
        print(f"\nAdresse {adresse} → pas de données")

client.close()