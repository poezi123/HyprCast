# HyprCast

Beamer, HDMI und Fernseher unter Hyprland ohne Kopfzerbechen.

- **app/** – Oberfläche (Flutter/Dart). Startet das Backend selbst.
- **backend/** – Python, nur Standardbibliothek. Spricht mit Hyprland.

Alles, was die App einstellt, gilt nur, solange sie läuft. Beim Schließen
(oder wenn das Kabel abgezogen wird) lädt sie die Hyprland-Config neu und
schaltet den Präsentationsmodus aus. In die Hyprland-Config wird nichts
geschrieben; gemerkte Geräte liegen in `~/.config/hyprcast/profiles.json`.

## Voraussetzung für HDMI

Der HDMI-Anschluss hängt an der Nvidia-Karte. Hyprland muss beim Start beide
Karten bekommen (`AQ_DRM_DEVICES=<amd>:<nvidia>`), sonst sieht es den
Anschluss nicht. Das lässt sich zur Laufzeit nicht ändern.

## Kabellos (iiShare)

Laut iiyama kann iiShare Miracast, AirPlay, teils Chromecast und Webcast
(Teilen über eine URL). Eine Linux-App gibt es nicht. Die App bietet:
URL im Browser öffnen und Miracast/Chromecast über gnome-network-displays.
Was die Tafel in der Schule tatsächlich anbietet, ist noch zu prüfen.
### Fernseher usw. werden ganz normal angezeigt.