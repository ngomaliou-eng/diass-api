py -c "
import smtplib
try:
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login('votre_email@gmail.com', 'votre_mot_de_passe_app')
    print('Connexion Gmail OK !')
    s.quit()
except Exception as e:
    print('Erreur :', e)
"