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
NB_PTR                = 8
NB_ONDULEURS_PAR_PTR  = 4
NB_ONDULEURS          = NB_PTR * NB_ONDULEURS_PAR_PTR  # 32 onduleurs
PUISSANCE_NOMINALE_MW = 23.040  # MWc réelle de la centrale
ETA                   = 0.795   # Rendement moyen annuel — Source : J492

# Mode de fonctionnement
# "meteo"  → irradiance réelle Open-Meteo (cache 5 min)
# "modbus" → données réelles via RTAC SEL-3530-4
MODE = "meteo"

# Coordonnées GPS exactes de la centrale de Diass
# Commune de Diass, Département de Mbour, Région de Thiès
LAT_DIASS = 14.653162
LON_DIASS = -17.103018

# IP du RTAC SEL-3530-4 (à confirmer sur le réseau industriel)
IP_RTAC = os.getenv("IP_RTAC", "192.168.123.135")

UTILISATEURS = {
    "admin":   {"mot_de_passe": "diass2024",  "role": "admin"},
    "manager": {"mot_de_passe": "senelec123", "role": "viewer"},
}

# ─────────────────────────────────────────────
# PUISSANCES NOMINALES RÉELLES PAR ONDULEUR (kWc)
# Source : Documentation technique J492, centrale PV de Diass
# Onduleurs Schneider Electric Conext Core XC
# ─────────────────────────────────────────────
PUISSANCES_NOMINALES = {
    "INV-1-1": 699.84, "INV-1-2": 777.60, "INV-1-3": 699.84, "INV-1-4": 816.48,
    "INV-2-1": 699.84, "INV-2-2": 777.60, "INV-2-3": 699.48, "INV-2-4": 816.48,
    "INV-3-1": 699.48, "INV-3-2": 777.60, "INV-3-3": 699.84, "INV-3-4": 816.48,
    "INV-4-1": 699.84, "INV-4-2": 797.04, "INV-4-3": 699.84, "INV-4-4": 816.48,
    "INV-5-1": 699.84, "INV-5-2": 797.04, "INV-5-3": 699.84, "INV-5-4": 816.48,
    "INV-6-1": 699.84, "INV-6-2": 656.10, "INV-6-3": 699.84, "INV-6-4": 699.84,
    "INV-7-1": 699.84, "INV-7-2": 656.10, "INV-7-3": 699.84, "INV-7-4": 583.20,
    "INV-8-1": 655.10, "INV-8-2": 583.20, "INV-8-3": 699.84, "INV-8-4": 699.84,
}

# ─────────────────────────────────────────────
# CONFIGURATION EMAIL
# ─────────────────────────────────────────────
EMAIL_EXPEDITEUR   = os.getenv("EMAIL_EXPEDITEUR",   "aliou99ngom@gmail.com")
EMAIL_MOT_DE_PASSE = os.getenv("EMAIL_MOT_DE_PASSE", "nzxv jgkn aduh ujqc")
EMAIL_DESTINATAIRE = os.getenv("EMAIL_DESTINATAIRE", "aliou99ngom@gmail.com")
EMAIL_ACTIF        = True

# Anti-doublon alertes — délai minimum 5 minutes
alertes_envoyees = {}
DELAI_MIN_ALERTE = 300

# ─────────────────────────────────────────────
# CACHE IRRADIANCE
# ─────────────────────────────────────────────
cache_irradiance = {"valeur": None, "heure": None}
CACHE_DUREE_SECONDES = 300

# ─────────────────────────────────────────────
# APPLICATION FASTAPI
# ─────────────────────────────────────────────
app = FastAPI(title="API Supervision Centrale PV DIASS — SENELEC")
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
    Récupère l'irradiance solaire réelle (GHI) via Open-Meteo.
    Coordonnées GPS : 14.653090°N, 17.103332°O
    Commune de Diass, Département de Mbour, Région de Thiès.
    Cache de 5 minutes pour limiter les appels API.
    """
    global cache_irradiance
    now = datetime.now()

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
        res       = requests.get(url, timeout=10)
        data      = res.json()
        irradiance = data["current"]["shortwave_radiation"]

        cache_irradiance["valeur"] = round(float(irradiance), 1)
        cache_irradiance["heure"]  = now
        print(f"[METEO] Irradiance reelle Diass : {irradiance} W/m2")
        return cache_irradiance["valeur"]

    except Exception as e:
        print(f"[METEO] Erreur Open-Meteo : {e}")
        if cache_irradiance["valeur"] is not None:
            return cache_irradiance["valeur"]
        return None


# ─────────────────────────────────────────────
# MODE MODBUS — Données réelles via RTAC SEL-3530-4
# ─────────────────────────────────────────────
def get_donnees_modbus():
    """
    Récupère les données réelles via Modbus TCP du RTAC SEL-3530-4.
    IP RTAC : à confirmer sur le réseau industriel de la centrale.
    À configurer après identification des registres Modbus.
    """
    try:
        print(f"[MODBUS] Connexion RTAC : {IP_RTAC}:502 — non encore configuré")
        return None, None
    except Exception as e:
        print(f"[MODBUS] Erreur : {e}")
        return None, None


# ─────────────────────────────────────────────
# CALCUL DE LA PUISSANCE D'UN ONDULEUR
# Formule : P = (G / Gref) × Pnom × η
# G    = irradiance mesurée (W/m²)
# Gref = 1000 W/m² (conditions standard STC)
# Pnom = puissance nominale réelle de l'onduleur (kWc) — Source J492
# η    = 79.5% (rendement moyen annuel) — Source J492
# ─────────────────────────────────────────────
def calculer_puissance_onduleur(inv_id, irradiance):
    pnom = PUISSANCES_NOMINALES.get(inv_id, 699.84)
    return round((irradiance / 1000) * pnom * ETA, 1)


# ─────────────────────────────────────────────
# CALCUL DU RATIO DE PERFORMANCE (PR)
# PR = (P_mesurée / P_nominale) / (G / Gref) × 100
# Norme IEC 61724-1:2021
# ─────────────────────────────────────────────
def calculer_pr(puissance_kw, pnom_kw, irradiance):
    if irradiance <= 0 or pnom_kw <= 0:
        return 0.0
    return round((puissance_kw / pnom_kw) / (irradiance / 1000) * 100, 1)


# ─────────────────────────────────────────────
# CALCUL DE L'ÉNERGIE D'UN ONDULEUR
# E = P × t (puissance × heures de production depuis 6h)
# ─────────────────────────────────────────────
def calculer_energie(puissance_kw, heure_actuelle):
    heures_production = max(0, heure_actuelle - 6)
    return round(puissance_kw * heures_production / 1000, 3)  # kW → MWh


# ─────────────────────────────────────────────
# SIMULATION DES ONDULEURS
# Pour chaque onduleur : calcul de P, E et PR individuels
# Nomenclature : INV-{NuméroPTR}-{NuméroOnduleur}
# 8 PTR × 4 onduleurs = 32 onduleurs
# INV-2-1 : hors_ligne (test) / INV-3-4 : alerte (test)
# ─────────────────────────────────────────────
def simuler_onduleurs(irradiance):
    onduleurs      = []
    heure_actuelle = datetime.now().hour

    for ptr in range(1, NB_PTR + 1):
        for num in range(1, NB_ONDULEURS_PAR_PTR + 1):
            inv_id = f"INV-{ptr}-{num}"
            pnom   = PUISSANCES_NOMINALES.get(inv_id, 699.84)

            if ptr == 2 and num == 1:
                # Onduleur hors ligne — test
                o = {
                    "id":           inv_id,
                    "ptr":          f"PTR{ptr}",
                    "pnom_kwc":     pnom,
                    "puissance_kw": 0.0,
                    "energie_mwh":  0.0,
                    "pr":           0.0,
                    "statut":       "hors_ligne"
                }
            elif ptr == 3 and num == 4:
                # Onduleur en alerte — fonctionnement dégradé (test)
                pkw = round(pnom * (irradiance / 1000) * random.uniform(0.35, 0.55), 1)
                o = {
                    "id":           inv_id,
                    "ptr":          f"PTR{ptr}",
                    "pnom_kwc":     pnom,
                    "puissance_kw": pkw,
                    "energie_mwh":  calculer_energie(pkw, heure_actuelle),
                    "pr":           calculer_pr(pkw, pnom, irradiance),
                    "statut":       "alerte"
                }
            else:
                # Onduleur en fonctionnement normal
                pkw = calculer_puissance_onduleur(inv_id, irradiance)
                o = {
                    "id":           inv_id,
                    "ptr":          f"PTR{ptr}",
                    "pnom_kwc":     pnom,
                    "puissance_kw": pkw,
                    "energie_mwh":  calculer_energie(pkw, heure_actuelle),
                    "pr":           calculer_pr(pkw, pnom, irradiance),
                    "statut":       "ok"
                }
            onduleurs.append(o)

    return onduleurs


# ─────────────────────────────────────────────
# FONCTION PRINCIPALE — Récupération des données
# ─────────────────────────────────────────────
def get_donnees():
    """
    Récupère l'irradiance selon le MODE configuré.
    Retourne : (irradiance, onduleurs)
    Les indicateurs globaux sont calculés dans les routes.
    """
    heure = datetime.now().hour

    if MODE == "modbus":
        irradiance, onduleurs = get_donnees_modbus()
        if irradiance is not None:
            return irradiance, onduleurs
        print("[MODBUS] Fallback vers mode meteo")

    irradiance = get_irradiance_reelle()

    if irradiance is None:
        if heure < 6 or heure > 19:
            irradiance = 0.0
            print("[INFO] Nuit — irradiance nulle")
        else:
            irradiance = round(950 * math.sin(math.pi * (heure - 6) / 13), 1)
            print(f"[FALLBACK] Irradiance estimee : {irradiance} W/m2")

    onduleurs = simuler_onduleurs(irradiance)
    return irradiance, onduleurs


# ─────────────────────────────────────────────
# FONCTION EMAIL — SMTP via SSL (port 465)
# ─────────────────────────────────────────────
def envoyer_alerte_email(onduleur_id, statut, puissance, pr):
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
ALERTE AUTOMATIQUE - Centrale Photovoltaique de Diass — SENELEC

Onduleur          : {onduleur_id}
Statut            : {statut.upper()}
Puissance         : {puissance} kW
Ratio Performance : {pr} %
Date/Heure        : {datetime.now().strftime("%d/%m/%Y a %H:%M:%S")}

Veuillez verifier l etat de cet onduleur des que possible.

Systeme de supervision automatique - Centrale PV de Diass - SENELEC
        """
        msg.attach(MIMEText(corps, "plain", "utf-8"))
        serveur = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
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
    irradiance, onduleurs = get_donnees()

    # Puissance totale = somme des puissances des 32 onduleurs (kW → MW)
    puissance_totale = round(
        sum(o["puissance_kw"] for o in onduleurs) / 1000, 3
    )

    # Énergie totale = somme des énergies des 32 onduleurs (MWh)
    energie_totale = round(
        sum(o["energie_mwh"] for o in onduleurs), 3
    )

    # PR global = moyenne des PR des onduleurs actifs uniquement
    onduleurs_actifs = [o for o in onduleurs if o["statut"] == "ok"]
    pr_global = round(
        sum(o["pr"] for o in onduleurs_actifs) / len(onduleurs_actifs), 1
    ) if onduleurs_actifs else 0.0

    # Gestion alertes email — anti-doublon 5 minutes
    now = datetime.now()
    for o in onduleurs:
        cle = f"{o['id']}_{o['statut']}"
        if o["statut"] in ("hors_ligne", "alerte"):
            if cle not in alertes_envoyees or \
               (now - alertes_envoyees[cle]).total_seconds() > DELAI_MIN_ALERTE:
                envoyer_alerte_email(o["id"], o["statut"],
                                     o["puissance_kw"], o["pr"])
                alertes_envoyees[cle] = now
        elif o["statut"] == "ok":
            alertes_envoyees.pop(f"{o['id']}_alerte", None)

    return {
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode":              MODE,
        "puissance_mw":      puissance_totale,
        "irradiance_wm2":    irradiance,
        "energie_jour_mwh":  energie_totale,
        "ratio_performance": pr_global,
        "onduleurs":         onduleurs
    }


@app.get("/donnees/courbe")
def get_courbe(u=Depends(verifier_token)):
    """
    Retourne l'historique de la journée (1 point / 15 min).
    La puissance de chaque point = somme des puissances des 32 onduleurs.
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

        heures          = data["minutely_15"]["time"]
        valeurs         = data["minutely_15"]["shortwave_radiation"]
        now             = datetime.now()
        heure_actuelle  = now.hour
        minute_actuelle = now.minute
        courbe          = []

        for i, h in enumerate(heures):
            heure_h  = int(h[11:13])
            minute_h = int(h[14:16])

            if heure_h < 6:                                              continue
            if heure_h > heure_actuelle:                                 break
            if heure_h == heure_actuelle and minute_h > minute_actuelle: break
            if heure_h > 19:                                             break

            irradiance       = max(0.0, round(float(valeurs[i]), 1))
            onduleurs_courbe = simuler_onduleurs(irradiance)

            # Puissance = somme des puissances des 32 onduleurs
            puissance_mw = round(
                sum(o["puissance_kw"] for o in onduleurs_courbe) / 1000, 3
            )
            courbe.append({
                "heure":          f"{heure_h:02d}h{minute_h:02d}",
                "puissance_mw":   puissance_mw,
                "irradiance_wm2": irradiance
            })

        print(f"[COURBE] {len(courbe)} points depuis Open-Meteo")
        return courbe

    except Exception as e:
        print(f"[COURBE] Erreur Open-Meteo : {e} — fallback sinusoidal")
        heure_actuelle = datetime.now().hour
        courbe = []
        for h in range(6, min(heure_actuelle + 1, 20)):
            irradiance       = round(950 * math.sin(math.pi * (h - 6) / 13), 1)
            onduleurs_courbe = simuler_onduleurs(irradiance)
            puissance_mw     = round(
                sum(o["puissance_kw"] for o in onduleurs_courbe) / 1000, 3
            )
            courbe.append({
                "heure":          f"{h:02d}h00",
                "puissance_mw":   puissance_mw,
                "irradiance_wm2": irradiance
            })
        return courbe


@app.get("/donnees/par-ptr")
def get_par_ptr(u=Depends(verifier_token)):
    """
    Retourne les données agrégées par PTR.
    8 PTR × 4 onduleurs = 32 onduleurs.
    """
    irradiance, onduleurs = get_donnees()

    ptrs = {}
    for o in onduleurs:
        ptr = o["ptr"]
        if ptr not in ptrs:
            ptrs[ptr] = {
                "ptr":           ptr,
                "puissance_kw":  0.0,
                "energie_mwh":   0.0,
                "pnom_kwc":      0.0,
                "pr_moyen":      0.0,
                "nb_ok":         0,
                "nb_alerte":     0,
                "nb_hors_ligne": 0,
                "onduleurs":     []
            }
        ptrs[ptr]["onduleurs"].append(o)
        ptrs[ptr]["puissance_kw"] += o["puissance_kw"]
        ptrs[ptr]["energie_mwh"]  += o["energie_mwh"]
        ptrs[ptr]["pnom_kwc"]     += o["pnom_kwc"]
        if o["statut"] == "ok":       ptrs[ptr]["nb_ok"]         += 1
        elif o["statut"] == "alerte": ptrs[ptr]["nb_alerte"]     += 1
        else:                         ptrs[ptr]["nb_hors_ligne"]  += 1

    # PR moyen par PTR = moyenne des PR des onduleurs actifs du PTR
    for ptr in ptrs:
        ptrs[ptr]["puissance_kw"] = round(ptrs[ptr]["puissance_kw"], 1)
        ptrs[ptr]["energie_mwh"]  = round(ptrs[ptr]["energie_mwh"], 3)
        ptrs[ptr]["pnom_kwc"]     = round(ptrs[ptr]["pnom_kwc"], 2)
        actifs = [o for o in ptrs[ptr]["onduleurs"] if o["statut"] == "ok"]
        ptrs[ptr]["pr_moyen"] = round(
            sum(o["pr"] for o in actifs) / len(actifs), 1
        ) if actifs else 0.0

    return list(ptrs.values())


@app.get("/sante")
def sante():
    return {
        "statut":                 "ok",
        "mode":                   MODE,
        "heure":                  datetime.now().strftime("%H:%M:%S"),
        "centrale":               "PV Diass — SENELEC",
        "puissance_nominale_mwc": PUISSANCE_NOMINALE_MW,
        "eta":                    ETA
    }