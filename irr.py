import requests
import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.express as px

# =========================
# CONFIGURATION SOLCAST
# =========================
API_KEY = "rvJ-YbdPt9zJ_NoSXyJolUtlJ7AV9VUS"

LATITUDE = 14.73      # Diass
LONGITUDE = -17.07

# =========================
# FONCTION DE RECUPERATION
# =========================
def get_irradiance_data():

    url = (
        f"https://api.solcast.com.au/radiation/live?"
        f"latitude={LATITUDE}"
        f"&longitude={LONGITUDE}"
        f"&api_key={API_KEY}"
        f"&format=json"
    )

    response = requests.get(url)

    if response.status_code != 200:
        return pd.DataFrame()

    data = response.json()

    records = []

    for item in data["estimated_actuals"]:
        records.append({
            "time": item["period_end"],
            "ghi": item["ghi"]
        })

    df = pd.DataFrame(records)

    if not df.empty:
        df["time"] = pd.to_datetime(df["time"])

    return df


# =========================
# APPLICATION DASH
# =========================
app = Dash(__name__)

app.layout = html.Div([

    html.H2(
        "Irradiance Solaire Temps Réel",
        style={"textAlign": "center"}
    ),

    dcc.Graph(id="irradiance-graph"),

    dcc.Interval(
        id="update",
        interval=5 * 60 * 1000,   # 5 minutes
        n_intervals=0
    )

])


# =========================
# CALLBACK
# =========================
@app.callback(
    Output("irradiance-graph", "figure"),
    Input("update", "n_intervals")
)
def update_graph(n):

    df = get_irradiance_data()

    if df.empty:
        return {}

    fig = px.line(
        df,
        x="time",
        y="ghi",
        title="Courbe d'Irradiance (GHI)"
    )

    fig.update_layout(
        xaxis_title="Heure",
        yaxis_title="Irradiance (W/m²)",
        template="plotly_white"
    )

    return fig


# =========================
# EXECUTION
# =========================
if __name__ == "__main__":
    app.run(debug=True)