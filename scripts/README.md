# Lüfterregelung: die laufenden Skripte und ihre Startbefehle

Diese beiden Skripte laufen auf dem übergebenen System. Die Lüfterdokumentation
im Hauptverzeichnis erklärt, *warum* sie so gebaut sind; hier liegen sie, damit
sie eine Neuinstallation überstehen.

| Datei | Zweck |
|---|---|
| `t4-fan.py` | Die Regelung. Liest GPU-, CPU- und Plattentemperaturen, stellt beide Lüfterzonen über IPMI, Takt 10 s. |
| `t4-fan-waechter.sh` | Läuft minütlich per Cron, prüft Prozess **und** Herzschlag und startet die Regelung neu. |

Auf dem System liegen beide unter `/mnt/scripts`, einem eigenen ZFS-Dataset
(`boot-pool/scripts`). **Eine Neuinstallation von TrueNAS löscht den boot-pool
und damit auch diese Dateien.** Die acht Startbefehle allein nützen dann nichts:
Der achte startet `/mnt/scripts/t4-fan.py`, und der zeigt danach ins Leere.

Die Referenzfassung in Abschnitt 7 der Lüfterdokumentation ist eine gekürzte,
portable Variante. Hier liegt das, was tatsächlich läuft — mit Protokollierung
und Rotation, und der Wächter steht im Dokument überhaupt nicht.

## Wiederherstellen nach einer Neuinstallation

```bash
zfs create boot-pool/scripts          # Dataset anlegen, haengt unter /mnt/scripts
cp t4-fan.py t4-fan-waechter.sh /mnt/scripts/
chmod +x /mnt/scripts/t4-fan.py /mnt/scripts/t4-fan-waechter.sh
```

Danach die acht Einträge unten anlegen und den Cron-Auftrag eintragen.

## Die acht Startbefehle

In der Weboberfläche unter **System → Erweitert → Init/Shutdown Scripts**, alle
vom Typ `Command`, Zeitpunkt `POSTINIT`, alle aktiv.

| Nr | Befehl | Zweck | Timeout |
|---|---|---|---|
| 1 | `bash -c "echo 0 > /sys/bus/pci/devices/0000:08:00.0/d3cold_allowed; echo on > /sys/bus/pci/devices/0000:08:00.0/power/control"` | D3cold sperren, sonst fällt die Karte vom Bus | 30 |
| 2 | `ipmitool raw 0x30 0x45 0x01 0x01` | Lüftermodus auf Full | 30 |
| 3 | `ipmitool raw 0x30 0x70 0x66 0x01 0x00 0x64` | Zone 0 auf 100 % als Startsicherung | 30 |
| 4 | `ipmitool raw 0x30 0x70 0x66 0x01 0x01 0x3c` | Zone 1 auf 60 % | 30 |
| 5 | `bash -c "ipmitool sensor thresh CPU_FAN1 lower 0 100 200; ipmitool sensor thresh CPU_FAN2 lower 0 100 200; ipmitool sensor thresh SYS_FAN1 lower 0 100 200; ipmitool sensor thresh SYS_FAN2 lower 0 100 200; ipmitool sensor thresh SYS_FAN3 lower 0 100 200"` | Untere Lüfterschwellen entschärfen | 60 |
| 6 | `zfs mount boot-pool/scripts` | Skript-Dataset einhängen | 30 |
| 7 | `bash -c "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do nvidia-smi -pm 1 >/dev/null 2>&1 && exit 0; sleep 2; done; exit 1"` | Persistence Mode, wartet bis zu 60 s auf den Treiber | 120 |
| 8 | `setsid nohup /mnt/scripts/t4-fan.py >/dev/null 2>&1 </dev/null &` | Regelung starten | 30 |

Dazu ein Cron-Auftrag, minütlich (`* * * * *`), als `root`:
`/mnt/scripts/t4-fan-waechter.sh`

### Warum die Einträge 5 und 7 so umständlich aussehen

TrueNAS reicht den hinterlegten Befehl durch eine zusätzliche Kommandozeilen-Ebene.
Alles mit einem Dollarzeichen wird aufgelöst, **bevor** der Befehl ausgeführt wird.
Schleifen über Variablen und Befehlsersetzungen scheitern dabei lautlos — weder im
Startprotokoll noch in der Weboberfläche steht etwas, nur
`/var/log/middlewared.log` zeigt es (`grep InitShutdownScriptService`). Auf diesem
System hatte Eintrag 5 deshalb monatelang nie funktioniert, ohne dass es auffiel.
Deshalb sind 5 und 7 ausgeschrieben statt als Schleife. **Wer sie umschreibt, darf
kein `$` verwenden.**

## Prüfen, ob nach einem Neustart alles greift

```bash
nvidia-smi --query-gpu=persistence_mode,pstate,clocks.mem,power.draw,temperature.gpu --format=csv,noheader
# gesund im Leerlauf: Enabled, P8, 405 MHz, ~10 W, 38-45 C

ps -eo cmd | grep "[t]4-fan.py"       # laeuft die Regelung?
stat -c %y /tmp/t4-fan.heartbeat      # Herzschlag frisch?
ipmitool raw 0x30 0x45 0x00           # Antwort 01 = Fan Mode Full
ipmitool sensor thresh CPU_FAN1       # dort muss lcr 140 stehen
```

## Wenn die Lüfter dauerhaft laut laufen

Das ist der wahrscheinlichste Fehlerfall, und er hat zwei ganz verschiedene
Ursachen. Die erste Datei, in die man schaut, ist das Protokoll des Wächters:

```bash
tail -20 /mnt/scripts/t4-fan-waechter.log
tail -20 /mnt/scripts/t4-fan.log          # die Regelung selbst
```

### Ursache 1: der Wächter hat eingegriffen

Er lässt die Lüfter bewusst auf 100 % stehen, statt sie in einem unbekannten
Zustand zu lassen — im Zweifel laut statt heiß. Was im Protokoll stehen kann:

| Zeile | Bedeutung |
|---|---|
| `Regelung laeuft nicht` … `Regelung neu gestartet` | Normalfall, hat sich selbst geheilt. Danach regelt sie wieder. |
| `Prozess laeuft, Herzschlag aber aelter als 90s - beende ihn` | Die Regelung hing. Sie wurde beendet und neu gestartet. |
| `Dataset war nicht eingehaengt, nachgeholt` | PostInit-Eintrag 6 hat nicht gegriffen. Nachsehen, ob er noch existiert und aktiv ist. |
| `FEHLER: /mnt/scripts/t4-fan.py nicht gefunden, auch nach zfs mount nicht` | Das Skript ist weg — etwa nach einer Neuinstallation. Aus diesem Verzeichnis zurückspielen, siehe oben. |
| `NEUSTART FEHLGESCHLAGEN - Luefter bleiben auf 100 Prozent` | Die Regelung lässt sich nicht starten. Von Hand aufrufen und die Fehlermeldung ansehen: `/mnt/scripts/t4-fan.py` |

Bleibt das Protokoll dagegen stumm und ist der letzte Eintrag alt, war es der
Wächter **nicht**.

### Ursache 2: der BMC erzwingt Vollast

Dann ist die Regelung machtlos, weil der Fernwartungsbaustein jeden gesetzten
Stellwert überschreibt. Zwei Prüfungen:

```bash
ipmitool sensor thresh CPU_FAN1     # muss lcr 140 zeigen
ipmitool raw 0x30 0x45 0x00         # muss 01 (Full) antworten
```

Steht bei der unteren Schwelle ein höherer Wert, hält der BMC einen langsam
drehenden Lüfter für ausgefallen und zwingt **alle** Zonen auf Vollast. Das
passiert vor allem nach einem Zurücksetzen des Fernwartungsbausteins auf
Werkseinstellungen: Die entschärften Schwellen liegen in seinem eigenen Speicher,
nicht in der TrueNAS-Konfiguration. Abhilfe ist PostInit-Eintrag 5, von Hand
ausgeführt.

### Und wenn alles stimmt

Dann ist es kein Fehler. Unter Dauerlast auf der Grafikkarte geht der
Radiallüfter auf Vollast, und das ist so gewollt — die Karte liegt dabei rund
13 Grad unter ihrer Betriebsgrenze. Leise wird das System nicht mehr, solange
gerechnet wird.
