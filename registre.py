from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.123.xx", port=502)
client.connect()

# Lire 10 registres à partir de l'adresse 0
# slave=1 signifie onduleur numéro 1
result = client.read_holding_registers(
    address=0,    # adresse de départ
    count=10,     # nombre de registres à lire
    slave=1       # identifiant de l'onduleur
)

if not result.isError():
    print("Registres lus :", result.registers)
else:
    print("Erreur de lecture")

client.close()