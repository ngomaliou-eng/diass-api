py -c "
import requests
r = requests.get(
    'https://api.open-meteo.com/v1/forecast'
    '?latitude=14.653090&longitude=-17.103332'
    '&current=shortwave_radiation,temperature_2m,cloud_cover,wind_speed_10m'
    '&timezone=Africa/Dakar'
)
data = r.json()
current = data['current']
print('Heure         :', current['time'])
print('Irradiance    :', current['shortwave_radiation'], 'W/m2')
print('Temperature   :', current['temperature_2m'], 'C')
print('Couverture    :', current['cloud_cover'], '%')
print('Vent          :', current['wind_speed_10m'], 'km/h')
