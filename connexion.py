from pymodbus.client import ModbusTcpClient

# Connexion au RTAC
client = ModbusTcpClient("192.168.123.200" \
"")  
client.connect()

result = client.read_holding_registers(address=100, count=10)
print(result.registers)

client.close()