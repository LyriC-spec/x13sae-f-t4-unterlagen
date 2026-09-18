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
