# Conectar MoonDeck con Discord

El widget **Discord** muestra el canal de voz en el que estás y quién hay dentro (se ilumina quien habla). Desde él puedes silenciarte, ensordecerte, salir del canal y cambiar el volumen de cada persona solo para ti.

Discord solo deja controlar la voz a **aplicaciones registradas**, así que hay que crear una aplicación tuya en la web de Discord. Es gratis, se hace **una sola vez** y lleva unos 3 minutos.

> **¿Te ha pasado MoonDeck un amigo y te ha invitado como *tester* de su aplicación?**
> Acepta la invitación (te llega por Discord o por correo), y en la ventana de conexión deja el **Client Secret vacío** y pulsa **Conectar**. Te puedes saltar el resto de esta guía.

## 1. Crea tu aplicación de Discord

1. Abre **[discord.com/developers/applications](https://discord.com/developers/applications)** e inicia sesión con tu cuenta de Discord.
2. Pulsa **New Application** (arriba a la derecha).
3. Ponle un nombre (por ejemplo `MoonDeck`), acepta las condiciones y pulsa **Create**.

## 2. Copia el Client ID y el Client Secret

1. En el menú de la izquierda, entra en **OAuth2**.
2. Copia el **Client ID** (botón *Copy*).
3. En **Client Secret**, pulsa **Reset Secret**, confirma y **copia** el código que aparece. Solo se muestra una vez; si lo pierdes, vuelve a pulsar *Reset Secret*.

> El Client Secret es como una contraseña de tu aplicación: no lo compartas.

## 3. Añade el Redirect

En la misma página de **OAuth2**, en **Redirects**:

1. Pulsa **Add Redirect**.
2. Escribe exactamente: `http://localhost`
3. Pulsa **Save Changes** (abajo).

## 4. Conecta MoonDeck

1. Abre Discord (la aplicación de escritorio, no la web).
2. En MoonDeck, en el widget **Discord**, pulsa **Conectar con Discord…** (o clic derecho en el widget > *Cambiar Client ID / Secret…*).
3. Pega el **Client ID** y el **Client Secret** y pulsa **Conectar**.
4. En Discord aparecerá una ventana pidiendo **Autorizar** a tu aplicación: pulsa **Autorizar**.

Listo. A partir de ahora MoonDeck se conecta solo cada vez que abres Discord.

## ¿Quieres que tus amigos usen tu aplicación?

En **discord.com/developers** > tu aplicación > **App Testers**, añade su nombre de usuario de Discord. Cada uno tiene que **aceptar la invitación**. Después les puedes pasar tu Client ID y tu Client Secret, o un MoonDeck preparado con `construir.sh` (ver el README).

## Problemas frecuentes

| Lo que pone el widget | Qué hacer |
|---|---|
| *Discord no está abierto.* | Abre la aplicación de escritorio de Discord (la web no sirve). |
| *Discord no reconoce ese Client ID.* | Revisa que copiaste bien el Client ID (OAuth2 > Client ID). |
| *Discord no ha autorizado…* | Pulsaste *Cancelar* en la ventana de Discord, o no eres dueño ni tester de esa aplicación. Vuelve a conectar y pulsa *Autorizar*. |
| *Discord rechazó la autorización: invalid_client* | El Client Secret no es correcto (o lo regeneraste). Pulsa *Reset Secret* otra vez y pega el nuevo. |
| *… redirect_uri …* | Falta el Redirect `http://localhost` en OAuth2 > Redirects (con *Save Changes*). |

Tus datos (Client ID, Client Secret y la autorización) se guardan solo en tu equipo, en `~/.config/MoonDeck/discord.json` (Linux) o `%APPDATA%\MoonDeck\discord.json` (Windows). Para borrarlos: clic derecho en el widget > *Desconectar de Discord*.
