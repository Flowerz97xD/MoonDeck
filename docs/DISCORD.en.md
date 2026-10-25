# Connecting MoonDeck to Discord

The **Discord** widget shows the voice channel you are in and who is there (whoever is talking lights up). From it you can mute, deafen, leave the channel and change each person's volume just for you.

Discord only lets **registered applications** control voice, so you need to create your own application on the Discord website. It's free, you only do it **once**, and it takes about 3 minutes.

> **Did a friend give you MoonDeck and invite you as a *tester* of their application?**
> Accept the invitation (you get it on Discord or by email), then in the connect window leave the **Client Secret empty** and press **Connect**. You can skip the rest of this guide.

## 1. Create your Discord application

1. Open **[discord.com/developers/applications](https://discord.com/developers/applications)** and log in with your Discord account.
2. Press **New Application** (top right).
3. Give it a name (for example `MoonDeck`), accept the terms and press **Create**.

## 2. Copy the Client ID and the Client Secret

1. In the left menu, open **OAuth2**.
2. Copy the **Client ID** (*Copy* button).
3. Under **Client Secret**, press **Reset Secret**, confirm and **copy** the code that appears. It is only shown once; if you lose it, press *Reset Secret* again.

> The Client Secret is like a password for your application: don't share it.

## 3. Add the Redirect

On the same **OAuth2** page, under **Redirects**:

1. Press **Add Redirect**.
2. Type exactly: `http://localhost`
3. Press **Save Changes** (at the bottom).

## 4. Connect MoonDeck

1. Open Discord (the desktop app, not the website).
2. In MoonDeck, on the **Discord** widget, press **Connect to Discord…** (or right-click the widget > *Change Client ID / Secret…*).
3. Paste the **Client ID** and the **Client Secret** and press **Connect**.
4. Discord will show a window asking you to **Authorize** your application: press **Authorize**.

Done. From now on MoonDeck connects by itself every time you open Discord.

## Want your friends to use your application?

On **discord.com/developers** > your application > **App Testers**, add their Discord username. Each of them has to **accept the invitation**. Then you can give them your Client ID and Client Secret, or a MoonDeck build prepared with `construir.sh` (see the README).

## Troubleshooting

| What the widget says | What to do |
|---|---|
| *Discord is not open.* | Open the Discord desktop app (the website doesn't work). |
| *Discord doesn't recognize that Client ID.* | Check that you copied the Client ID correctly (OAuth2 > Client ID). |
| *Discord has not authorized…* | You pressed *Cancel* in Discord's window, or you are not the owner or a tester of that application. Connect again and press *Authorize*. |
| *Discord rejected the authorization: invalid_client* | The Client Secret is wrong (or you regenerated it). Press *Reset Secret* again and paste the new one. |
| *… redirect_uri …* | The `http://localhost` Redirect is missing in OAuth2 > Redirects (with *Save Changes*). |

Your data (Client ID, Client Secret and the authorization) is only stored on your computer, in `~/.config/MoonDeck/discord.json` (Linux) or `%APPDATA%\MoonDeck\discord.json` (Windows). To delete it: right-click the widget > *Disconnect from Discord*.
