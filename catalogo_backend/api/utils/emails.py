# pyrefly: ignore [missing-import]
from django.core.mail import EmailMultiAlternatives
# pyrefly: ignore [missing-import]
from django.utils.html import strip_tags
# pyrefly: ignore [missing-import]
from django.conf import settings
# pyrefly: ignore [missing-import]
from django.contrib.staticfiles import finders
from email.mime.image import MIMEImage
from datetime import date

def send_bukis_email(recipient_name, recipient_email, mail_subject, html_body):
    greeting = f"<h2>Hola, {recipient_name}.</h2>"

    full_mail = (
        f"{greeting}"
        f"{html_body}"
        f'<p style="font-size: 1.3em;">Muchas gracias por su atención.</p>'
        f'<img src="cid:logo_bukis" width="180" height="auto">'
        f'<p style="font-size: 1.1em;">Copyright &copy; {date.today().year} Importaciones Los Bukis.Todos los derechos reservados.<br>Blvd. Solidaridad 118 A, Raquet Club II, 83200 Hermosillo, Sonora, México.</p>'
    )

    body = strip_tags(full_mail)

    msg = EmailMultiAlternatives(
        subject=mail_subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )
    
    msg.attach_alternative(full_mail, "text/html")
    logo_path = finders.find("img/logo.png")

    if logo_path:
        try:
            with open(logo_path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<logo_bukis>')
                img.add_header('Content-Disposition', 'inline', filename='logo.png')
                msg.attach(img)
        except Exception as e:
            print(f"No se pudo adjuntar el logo: {e}")
    else:
        print("Advertencia: No se encontró img/logo.png en los estáticos.")

    msg.send(fail_silently=False)