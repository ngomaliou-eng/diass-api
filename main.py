from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from dotenv import load_dotenv
import random, math, jwt, requests, os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────────
# CHARGEMENT DES VARIABLES D'ENVIRONNEMENT
# ─────────────────────────────────────────────
load_dotenv()

# ─────────────────────────────────────────────
# CONFIGURATION GÉNÉRALE
# ─────────────────────────────────────────────
SECRET_KEY            = os.getenv("SECRET_KEY", "diass-secret-cle")
ALGORITHM             = "HS256"
TOKEN_EXPIRE_MINUTES  = 480
NB_ONDULEURS          = 32
PUISSANCE_NOMINALE_MW = 23.0

# Mode de fonctionnement
# "meteo" → irradiance réelle Open-Meteo (cache 5 min)
# "http"  → données réelles via interface HTTP du SCADA
MODE = "meteo"

# Coordonnées GPS exactes de la centrale de Diass
# Commune de Diass, Département de Mbour, Région de Thiès
LAT_DIASS = 14.653090
LON_DIASS = -17.103332

# IP de l'équipement SCADA
IP_SCADA = "192.168.123.100"

UTILISATEURS = {
    "admin":   {"mot_de_passe": "diass2024",  "role": "admin"},
    "manager": {"mot_de_passe": "senelec123", "role": "viewer"},
}

# ─────────────────────────────────────────────
# CONFIGURATION EMAIL
# ─────────────────────────────────────────────
EMAIL_EXPEDITEUR   = os.getenv("EMAIL_EXPEDITEUR",   "aliou99ngom@gmail.com")
EMAIL_MOT_DE_PASSE = os.getenv("EMAIL_MOT_DE_PASSE", "nzxv jgkn aduh ujqc")
EMAIL_DESTINATAIRE = os.getenv("EMAIL_DESTINATAIRE", "aliou99ngom@gmail.com")
EMAIL_ACTIF        = True

# Anti-doublon avec délai minimum entre deux alertes
# Format : {cle: datetime_dernier_envoi}
alertes_envoyees = {}
DELAI_MIN_ALERTE = 300  # 5 minutes minimum entre deux alertes du même onduleur

# ─────────────────────────────────────────────
# CACHE IRRADIANCE — Évite les appels excessifs
# ─────────────────────────────────────────────
cache_irradiance = {"valeur": None, "heure": None}
CACHE_DUREE_SECONDES = 300  # 5 minutes

# ─────────────────────────────────────────────
# APPLICATION FASTAPI
# ─────────────────────────────────────────────
app = FastAPI(title="API Supervision Centrale PV DIASS")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ─────────────────────────────────────────────
# FONCTIONS JWT
# ─────────────────────────────────────────────
def creer_token(data):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verifier_token(token: str = Depends(oauth2_scheme)):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expire")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")


# ─────────────────────────────────────────────
# MODE MÉTÉO — Irradiance réelle Open-Meteo
# ─────────────────────────────────────────────
def get_irradiance_reelle():
    """
    Récupère l'irradiance solaire réelle instantanée (GHI)
    via l'API Open-Meteo — données actualisées toutes les 15 minutes.
    GHI = Global Horizontal Irradiance en W/m²
    Coordonnées GPS : 14.653090°N, 17.103332°O
    Commune de Diass, Département de Mbour, Région de Thiès
    Sans limite d'appels — gratuit et illimité.
    """
    global cache_irradiance
    now = datetime.now()

    # Utiliser le cache si moins de 5 minutes
    if cache_irradiance["heure"] and cache_irradiance["valeur"] is not None:
        delta = (now - cache_irradiance["heure"]).total_seconds()
        if delta < CACHE_DUREE_SECONDES:
            print(f"[CACHE] Irradiance : {cache_irradiance['valeur']} W/m2 "
                  f"(actualisation dans {int(CACHE_DUREE_SECONDES - delta)}s)")
            return cache_irradiance["valeur"]

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT_DIASS}&longitude={LON_DIASS}"
            "&current=shortwave_radiation"
            "&timezone=Africa/Dakar"
        )
        res  = requests.get(url, timeout=10)
        data = res.json()
        irradiance = data["current"]["shortwave_radiation"]

        cache_irradiance["valeur"] = round(float(irradiance), 1)
        cache_irradiance["heure"]  = now

        print(f"[METEO] Irradiance reelle Diass : {irradiance} W/m2")
        return cache_irradiance["valeur"]

    except Exception as e:
        print(f"[METEO] Erreur Open-Meteo : {e}")
        if cache_irradiance["valeur"] is not None:
            print(f"[CACHE] Utilisation derniere valeur : {cache_irradiance['valeur']} W/m2")
            return cache_irradiance["valeur"]
        return None


def get_courbe_open_meteo():
    """
    Récupère les données par 15 minutes de la journée depuis Open-Meteo.
    Utilise le paramètre minutely_15 pour avoir une courbe détaillée
    montrant les variations d'irradiance dues aux nuages.
    Un point toutes les 15 minutes = courbe réelle et précise.
    """
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT_DIASS}&longitude={LON_DIASS}"
            "&minutely_15=shortwave_radiation"
            "&timezone=Africa/Dakar"
            "&forecast_days=1"
        )
        res  = requests.get(url, timeout=10)
        data = res.json()

        heures  = data["minutely_15"]["time"]
        valeurs = data["minutely_15"]["shortwave_radiation"]

        now             = datetime.now()
        heure_actuelle  = now.hour
        minute_actuelle = now.minute
        courbe = []

        for i, h in enumerate(heures):
            heure_h  = int(h[11:13])
            minute_h = int(h[14:16])

            if heure_h < 6:
                continue
            if heure_h > heure_actuelle:
                break
            if heure_h == heure_actuelle and minute_h > minute_actuelle:
                break
            if heure_h > 19:
                break

            irradiance = max(0.0, round(float(valeurs[i]), 1))
            courbe.append({
                "heure":          f"{heure_h:02d}h{minute_h:02d}",
                "puissance_mw":   calculer_puissance(irradiance),
                "irradiance_wm2": irradiance
            })

        print(f"[COURBE] {len(courbe)} points (1/15min) depuis Open-Meteo")
        return courbe

    except Exception as e:
        print(f"[COURBE] Erreur Open-Meteo : {e} → fallback sinusoidal")
        return None


# ─────────────────────────────────────────────
# MODE HTTP — Données réelles via SCADA
# ─────────────────────────────────────────────
def get_donnees_http():
    """
    Récupère les données réelles via l'interface HTTP
    du RTAC SEL3530-4 ou du datalogger UC8112.
    IP équipement : 192.168.123.100
    À configurer après identification des endpoints HTTP.
    """
    try:
        print("[HTTP] Mode HTTP non encore configure")
        return None, None, None
    except Exception as e:
        print(f"[HTTP] Erreur : {e}")
        return None, None, None


def calculer_puissance(irradiance):
    """
    Calcule la puissance produite en MW depuis l'irradiance réelle.
    Formule : P = (G / Gref) × Pnom × η
    G    = irradiance GHI mesurée (W/m²)
    Gref = 1000 W/m² (conditions standard STC)
    Pnom = 23 MWc (puissance nominale installée)
    η    = rendement global 78% à 82%
    """
    return round((irradiance / 1000) * PUISSANCE_NOMINALE_MW
                 * random.uniform(0.78, 0.82), 2)


def simuler_onduleurs(puissance_totale):
    """
    Génère l'état des 32 onduleurs depuis la puissance totale réelle.
    pwk = (puissance_totale × 1000) / 32 onduleurs
    INV-05 : toujours hors_ligne (panne permanente)
    INV-12 : toujours en alerte (panne stable)
    Autres : ok avec variation ±8%
    """
    onduleurs = []
    pwk = (puissance_totale * 1000) / NB_ONDULEURS
    for i in range(1, NB_ONDULEURS + 1):
        if i == 5:
            o = {"id": f"INV-{i:02d}", "puissance_kw": 0.0,
                 "statut": "hors_ligne", "temperature_c": 0.0}
        elif i == 12:
            # Statut stable — pas aléatoire pour éviter les doublons email
            o = {"id": f"INV-{i:02d}",
                 "puissance_kw": round(pwk * random.uniform(0.3, 0.6), 1),
                 "statut": "alerte",
                 "temperature_c": round(random.uniform(65, 75), 1)}
        else:
            o = {"id": f"INV-{i:02d}",
                 "puissance_kw": round(pwk * random.uniform(0.92, 1.08), 1),
                 "statut": "ok",
                 "temperature_c": round(random.uniform(38, 52), 1)}
        onduleurs.append(o)
    return onduleurs


# ─────────────────────────────────────────────
# FONCTION PRINCIPALE — RÉCUPÉRER LES DONNÉES
# ─────────────────────────────────────────────
def get_donnees():
    """
    Récupère les données selon le MODE configuré.
    - meteo : irradiance réelle Open-Meteo (15 min, cache 5 min)
    - http  : données réelles via interface HTTP du SCADA
    Fallback automatique si Open-Meteo est indisponible.
    """
    heure = datetime.now().hour

    if MODE == "http":
        irradiance, puissance, onduleurs = get_donnees_http()
        if irradiance is not None:
            return irradiance, puissance, onduleurs
        print("[HTTP] Fallback vers mode meteo")

    irradiance = get_irradiance_reelle()

    if irradiance is None:
        if heure < 6 or heure > 19:
            irradiance = 0.0
            print("[INFO] Nuit — irradiance nulle")
        else:
            irradiance = round(
                950 * math.sin(math.pi * (heure - 6) / 13), 1
            )
            print(f"[FALLBACK] Irradiance estimee : {irradiance} W/m2")

    puissance = calculer_puissance(irradiance)
    onduleurs = simuler_onduleurs(puissance)
    return irradiance, puissance, onduleurs


# ─────────────────────────────────────────────
# FONCTION EMAIL
# ─────────────────────────────────────────────
def envoyer_alerte_email(onduleur_id, statut, puissance, temperature):
    if not EMAIL_ACTIF:
        print(f"[EMAIL DESACTIVE] Alerte {onduleur_id} - {statut}")
        return False
    try:
        icone = "PANNE" if statut == "hors_ligne" else "ALERTE"
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_EXPEDITEUR
        msg["To"]      = EMAIL_DESTINATAIRE
        msg["Subject"] = f"{icone} Centrale Diass - {onduleur_id} ({statut.upper()})"
        corps = f"""
ALERTE AUTOMATIQUE - Centrale Photovoltaique de Diass

Onduleur     : {onduleur_id}
Statut       : {statut.upper()}
Puissance    : {puissance} kW
Temperature  : {temperature} C
Date/Heure   : {datetime.now().strftime("%d/%m/%Y a %H:%M:%S")}

Veuillez verifier l etat de cet onduleur des que possible.

Systeme de supervision automatique - Centrale PV de Diass - SENELEC
        """
        msg.attach(MIMEText(corps, "plain", "utf-8"))
        serveur = smtplib.SMTP("smtp.gmail.com", 587)
        serveur.starttls()
        serveur.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        serveur.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
        serveur.quit()
        print(f"[EMAIL ENVOYE] {onduleur_id} - {statut}")
        return True
    except Exception as e:
        print(f"[ERREUR EMAIL] {e}")
        return False


# ─────────────────────────────────────────────
# ROUTES DE L'API
# ─────────────────────────────────────────────

@app.post("/token")
def connexion(form: OAuth2PasswordRequestForm = Depends()):
    user = UTILISATEURS.get(form.username)
    if not user or user["mot_de_passe"] != form.password:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    return {"access_token": creer_token({"sub": form.username}),
            "token_type": "bearer"}


@app.get("/donnees/instantanees")
def get_instantanees(u=Depends(verifier_token)):
    heure = datetime.now().hour
    irradiance, puissance, onduleurs = get_donnees()

    if irradiance > 0:
        pr = round((puissance / PUISSANCE_NOMINALE_MW)
                   / (irradiance / 1000) * 100, 1)
    else:
        pr = 0.0

    # Gestion alertes email — anti-doublon avec délai 5 minutes
    now = datetime.now()
    for o in onduleurs:
        cle = f"{o['id']}_{o['statut']}"
        if o["statut"] in ("hors_ligne", "alerte"):
            # Envoyer seulement si pas d'alerte récente (< 5 minutes)
            if cle not in alertes_envoyees or \
               (now - alertes_envoyees[cle]).total_seconds() > DELAI_MIN_ALERTE:
                envoyer_alerte_email(o["id"], o["statut"],
                                     o["puissance_kw"], o["temperature_c"])
                alertes_envoyees[cle] = now
                print(f"[ALERTE] {o['id']} - {o['statut']} enregistree")
        elif o["statut"] == "ok":
            # Supprimer seulement alerte — hors_ligne reste bloqué
            alertes_envoyees.pop(f"{o['id']}_alerte", None)

    return {
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode":              MODE,
        "puissance_mw":      puissance,
        "irradiance_wm2":    irradiance,
        "irradiation_kwhm2": round(irradiance * max(0, heure - 6) / 1000, 2),
        "energie_jour_mwh":  round(puissance * max(0, heure - 6) * 0.85, 1),
        "ratio_performance": pr,
        "onduleurs":         onduleurs
    }


@app.get("/donnees/courbe")
def get_courbe(u=Depends(verifier_token)):
    """
    Retourne l'historique de la journée avec un point toutes les 15 minutes.
    Utilise minutely_15 d'Open-Meteo pour capturer les variations
    d'irradiance dues aux passages nuageux.
    """
    courbe = get_courbe_open_meteo()

    if courbe is None:
        heure_actuelle = datetime.now().hour
        courbe = []
        for h in range(6, min(heure_actuelle + 1, 20)):
            irradiance = round(950 * math.sin(math.pi * (h - 6) / 13), 1)
            courbe.append({
                "heure":          f"{h:02d}h00",
                "puissance_mw":   calculer_puissance(irradiance),
                "irradiance_wm2": irradiance
            })

    return courbe


@app.get("/sante")
def sante():
    return {
        "statut": "ok",
        "mode":   MODE,
        "heure":  datetime.now().strftime("%H:%M:%S")
    }