#!/usr/bin/env bash
# t4-fan-waechter.sh - Waechter fuer t4-fan.py, laeuft minuetlich per Cron.
#
# Warum es ihn braucht: Der BMC steht auf Fan Mode Full und die unteren
# Drehzahlschwellen sind entschaerft. Stirbt die Regelung, friert der zuletzt
# geschriebene Duty-Wert ein und niemand zieht die Luefter wieder hoch - anders
# als am iDX6011, wo der EC eine Mindestdrehzahl erzwingt. Uebrig bliebe nur die
# Karte selbst mit ihrer Drosselung bei 93 C.
#
# Der Waechter prueft zweierlei: laeuft der Prozess, und ist sein Herzschlag
# frisch. Ein haengender Prozess ist genauso schlimm wie ein toter.

SKRIPT=/mnt/scripts/t4-fan.py
HEARTBEAT=/tmp/t4-fan.heartbeat
MAX_ALTER=90          # Sekunden, Takt ist 10 s
LOG=/mnt/scripts/t4-fan-waechter.log

melde() { echo "$(date '+%F %T')  $*" >> "$LOG"; }

vollast() {
  ipmitool raw 0x30 0x45 0x01 0x01 >/dev/null 2>&1; sleep 1
  ipmitool raw 0x30 0x70 0x66 0x01 0x00 0x64 >/dev/null 2>&1; sleep 1
  ipmitool raw 0x30 0x70 0x66 0x01 0x01 0x64 >/dev/null 2>&1
  melde "Sicherheitshalber beide Zonen auf 100 Prozent"
}

starte() {
  setsid nohup "$SKRIPT" >/dev/null 2>&1 </dev/null &
  sleep 5
  if ps -eo cmd | grep -q "[t]4-fan.py"; then
    melde "Regelung neu gestartet"
    midclt call mail.send "{\"subject\": \"[X13SAE] Luefterregelung neu gestartet\", \"text\": \"Der Waechter hat t4-fan.py tot oder haengend vorgefunden und um $(date '+%F %T') neu gestartet. Die Luefter liefen zwischenzeitlich auf 100 Prozent.\"}" >/dev/null 2>&1 || true
  else
    melde "NEUSTART FEHLGESCHLAGEN - Luefter bleiben auf 100 Prozent"
    midclt call mail.send "{\"subject\": \"[X13SAE] Luefterregelung laesst sich nicht starten\", \"text\": \"Der Waechter konnte t4-fan.py um $(date '+%F %T') nicht starten. Die Luefter laufen auf 100 Prozent. Bitte pruefen.\"}" >/dev/null 2>&1 || true
  fi
}

# Das Dataset wird beim Boot nicht automatisch eingehaengt. Ohne das Skript
# ist hier ohnehin nichts zu regeln.
if [ ! -x "$SKRIPT" ]; then
  zfs mount boot-pool/scripts >/dev/null 2>&1
  if [ ! -x "$SKRIPT" ]; then
    melde "FEHLER: $SKRIPT nicht gefunden, auch nach zfs mount nicht"
    vollast
    exit 1
  fi
  melde "Dataset war nicht eingehaengt, nachgeholt"
fi

laeuft=0
ps -eo cmd | grep -q "[t]4-fan.py" && laeuft=1

frisch=0
if [ -f "$HEARTBEAT" ]; then
  alter=$(( $(date +%s) - $(stat -c %Y "$HEARTBEAT") ))
  [ "$alter" -le "$MAX_ALTER" ] && frisch=1
fi

if [ "$laeuft" -eq 1 ] && [ "$frisch" -eq 1 ]; then
  exit 0
fi

if [ "$laeuft" -eq 1 ]; then
  melde "Prozess laeuft, Herzschlag aber aelter als ${MAX_ALTER}s - beende ihn"
  pkill -TERM -f "[t]4-fan.py" >/dev/null 2>&1
  sleep 5
  pkill -KILL -f "[t]4-fan.py" >/dev/null 2>&1
  sleep 1
else
  melde "Regelung laeuft nicht"
fi

vollast
starte
exit 0
