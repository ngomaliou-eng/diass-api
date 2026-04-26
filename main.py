from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
import random, math, jwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────────
# CONFIGURATION GÉNÉRALE
# ─────────────────────────────────────────────
SECRET_KEY = "diass-secret-cle"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60
NB_ONDULEURS = 32
PUISSANCE_NOMINALE_MW = 23.0  # MWc

UTILISATEURS = {
    "admin":   {"mot_de_passe": "diass2024",  "role": "admin"},
    "manager": {"mot_de_passe": "senelec123", "role": "viewer"},
}

# ─────────────────────────────────────────────
# CONFIGURATION EMAIL
# Remplacez par vos vraies informations Gmail
# ─────────────────────────────────────────────
EMAIL_EXPEDITEUR    = "seye84laminel@gmail.com"
EMAIL_MOT_DE_PASSE  = "qviy iiqu rgwv zlxx"   # mot de passe d'application Gmail
EMAIL_DESTINATAIRE  = "aliou99ngom@gmail.com"  # email qui reçoit les alertes
EMAIL_ACTIF         = True  # Mettre True quand vous avez configuré Gmail

# Mémorise les alertes déjà envoyées pour éviter les doublons
alertes_envoyees = set()

# ─────────────────────────────────────────────
# APPLICATION FASTAPI
# ─────────────────────────────────────────────
app = FastAPI(title="API Supervision Centrale PV DIASS")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ─────────────────────────────────────────────
# FONCTIONS D'AUTHENTIFICATION JWT
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
# FONCTIONS DE SIMULATION SCADA
# ─────────────────────────────────────────────
def simuler_ensoleillement(heure):
    if heure < 6 or heure > 19:
        return 0.0
    return max(0.0, round(950 * math.sin(math.pi * (heure - 6) / 13)
                          + random.uniform(-30, 30), 1))

def simuler_puissance(enso):
    return round((enso / 1000) * 20.0 * random.uniform(0.78, 0.82), 2)

def simuler_onduleurs(puissance_totale):
    onduleurs = []
    pwk = (puissance_totale * 1000) / NB_ONDULEURS
    for i in range(1, NB_ONDULEURS + 1):
        if i == 5:
            o = {"id": f"INV-{i:02d}", "puissance_kw": 0.0,
                 "statut": "hors_ligne", "temperature_c": 0.0}
        elif i == 12 and random.random() < 0.4:
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
@app.get("/donnees/instantanees")
def get_instantanees(u=Depends(verifier_token)):
    heure = datetime.now().hour
    enso  = simuler_ensoleillement(heure)
    pw    = simuler_puissance(enso)
    onduleurs = simuler_onduleurs(pw)

    # Calcul du ratio de performance
    puissance_nominale = 23.0  # MWc
    if enso > 0:
        pr = round((pw / puissance_nominale) / (enso / 1000) * 100, 1)
    else:
        pr = 0.0

    # ... reste du code email ...


    return {
        "timestamp":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "puissance_mw":       pw,
        "ensoleillement_wm2": enso,
        "energie_jour_mwh":   round(pw * max(0, heure - 6) * 0.85, 1),
        "ratio_performance":  pr,
        "onduleurs":          onduleurs
}



# ─────────────────────────────────────────────
# FONCTION D'ENVOI D'EMAIL
# ─────────────────────────────────────────────
def envoyer_alerte_email(onduleur_id: str, statut: str,
                         puissance: float, temperature: float):
    """
    Envoie un email d'alerte quand un onduleur est hors ligne ou en alerte.
    Ne s'exécute que si EMAIL_ACTIF = True.
    """
    if not EMAIL_ACTIF:
        print(f"[EMAIL DÉSACTIVÉ] Alerte {onduleur_id} — {statut}")
        return False

    try:
        # Icône selon le statut
        icone = "🔴" if statut == "hors_ligne" else "🟠"

        # Construction du message
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_EXPEDITEUR
        msg["To"]      = EMAIL_DESTINATAIRE
        msg["Subject"] = f"{icone} ALERTE Centrale Diass — {onduleur_id} ({statut.upper()})"

        corps = f"""
ALERTE AUTOMATIQUE — Centrale Photovoltaïque de Diass
══════════════════════════════════════════════════════

Onduleur     : {onduleur_id}
Statut       : {statut.upper()}
Puissance    : {puissance} kW
Température  : {temperature} °C
Date/Heure   : {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")}

──────────────────────────────────────────────────────
Veuillez vérifier l'état de cet onduleur dès que possible.
──────────────────────────────────────────────────────

Système de supervision automatique
Centrale PV de Diass — Senelec
        """

        msg.attach(MIMEText(corps, "plain", "utf-8"))

        # Envoi via Gmail
        serveur = smtplib.SMTP("smtp.gmail.com", 587)
        serveur.starttls()
        serveur.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        serveur.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
        serveur.quit()

        print(f"[EMAIL ENVOYÉ] Alerte {onduleur_id} — {statut}")
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
    enso  = simuler_ensoleillement(heure)
    pw    = simuler_puissance(enso)
    onduleurs = simuler_onduleurs(pw)

    # Vérification des alertes et envoi d'emails si nécessaire
    for o in onduleurs:
        cle = f"{o['id']}_{o['statut']}"
        if o["statut"] in ("hors_ligne", "alerte") and cle not in alertes_envoyees:
            envoyer_alerte_email(
                o["id"], o["statut"],
                o["puissance_kw"], o["temperature_c"]
            )
            alertes_envoyees.add(cle)
        # Réinitialiser si l'onduleur revient en ligne
        elif o["statut"] == "ok":
            alertes_envoyees.discard(f"{o['id']}_hors_ligne")
            alertes_envoyees.discard(f"{o['id']}_alerte")

    return {
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "puissance_mw":      pw,
        "ensoleillement_wm2": enso,
        "energie_jour_mwh":  round(pw * max(0, heure - 6) * 0.85, 1),
        "onduleurs":         onduleurs
    }


@app.get("/donnees/courbe")
def get_courbe(u=Depends(verifier_token)):
    heure_actuelle = datetime.now().hour
    courbe = []
    for h in range(6, min(heure_actuelle + 1, 20)):
        enso = simuler_ensoleillement(h)
        courbe.append({
            "heure":             f"{h:02d}h00",
            "puissance_mw":      simuler_puissance(enso),
            "ensoleillement_wm2": enso
        })
    return courbe


@app.get("/sante")
def sante():
    return {"statut": "ok", "heure": datetime.now().strftime("%H:%M:%S")}