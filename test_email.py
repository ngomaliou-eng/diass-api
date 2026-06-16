import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_EXPEDITEUR   = "aliou99ngom@gmail.com"
EMAIL_MOT_DE_PASSE = "urwu tvpf vocm fxpi"
EMAIL_DESTINATAIRE = "seye84laminel@gmail.com"

try:
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_EXPEDITEUR
    msg["To"]      = EMAIL_DESTINATAIRE
    msg["Subject"] = "TEST — Système d'alerte Centrale PV Diass"
    
    corps = """
Bonjour,

Ceci est un message de test du système d'alerte automatique.

Centrale Photovoltaïque de Diass — SENELEC
Système de supervision développé par Aliou Ngom
    """
    msg.attach(MIMEText(corps, "plain", "utf-8"))
    
    serveur = smtplib.SMTP("smtp.gmail.com", 587)
    serveur.starttls()
    serveur.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
    serveur.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
    serveur.quit()
    print("✅ Email envoyé avec succès !")
    
except Exception as e:
    print(f"✗ Erreur : {e}")