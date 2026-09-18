#!/usr/bin/env python3
"""
t4-fan.py - Luefterregelung fuer das Supermicro X13SAE-F mit Tesla T4

Zone 0 = CPU_FAN1 + CPU_FAN2. Am CPU_FAN2 haengt der Blower der T4.
         Stellwert ist das Maximum aus GPU- und CPU-Bedarf, jeweils aus
         einer eigenen Kurve. Nicht das Maximum der Temperaturen - 43 C
         CPU und 72 C GPU sind keine vergleichbaren Zahlen.
Zone 1 = SYS_FAN1-3, Gehaeuse. Fuehrungsgroesse sind die Plattentemperaturen,
         die CPU kommt nur als Untergrenze dazu.

Gelesen wird ueber sysfs (coretemp, drivetemp) und nvidia-smi. IPMI wird nur
zum Schreiben benutzt, und nur wenn sich der Wert aendert oder die
Wiederholfrist abgelaufen ist - der KCS-Kanal dieses BMC liefert bei schnellem
Pollen Muellwerte.

Messgrundlage (23.08.2026, siehe Wiki runbooks/x13sae-tesla-t4.md):
  - Unter Volllast (68 W) liegt die Karte selbst bei 100 % Duty auf 72 C,
    bei 70 % auf 79 C, bei 50 % nach einer Minute auf 84 C.
    Darum muss die GPU-Kurve bis 72 C auf 100 % sein.
  - Im Leerlauf zieht die Karte mit Persistence Mode 10 W und liegt bei
    38-42 C. Darum darf die Kurve unten weit herunter.
  - Zone 1 darf nicht unter 25 %: dort faellt SYS_FAN1 unter die
    Lower-Critical-Schwelle von 140 RPM, der BMC erklaert einen
    Luefterausfall und zwingt alle Zonen auf 100 %. Untergrenze hier 30 %.
  - Thermische Zeitkonstante 5-6 Minuten, darum reichen 10 s Takt.
"""
import os
import subprocess
import sys
import signal
import time
import logging
from collections import deque
from logging.handlers import RotatingFileHandler

INTERVAL = 10          # Sekunden je Regelschritt
SMOOTH_N = 6           # gleitender Mittelwert ueber 6 Messungen = 60 s
HYST = 4               # erst ab 4 Punkten Differenz herunterschalten (Skala 0-100)
DOWN_STEP = 5          # und dann hoechstens 5 Punkte je Schritt
REASSERT_S = 30        # Duty spaetestens alle 30 s erneut schreiben
HEARTBEAT = "/tmp/t4-fan.heartbeat"
LOGFILE = "/mnt/scripts/t4-fan.log"

ZONE0_MIN, ZONE0_MAX = 30, 100
ZONE1_MIN, ZONE1_MAX = 30, 100   # 25 % waere die Fan-Fault-Grenze

# (Temperatur C, Duty Prozent) - dazwischen wird linear interpoliert
CURVE_GPU = [(45, 30), (55, 50), (62, 70), (68, 90), (72, 100)]
CURVE_CPU = [(55, 30), (70, 45), (80, 65), (88, 85), (95, 100)]
CURVE_DISK = [(40, 30), (45, 50), (50, 70), (55, 90), (58, 100)]

EMERG_GPU, EMERG_CPU, EMERG_DISK = 80, 92, 58

log = logging.getLogger("t4-fan")
log.setLevel(logging.INFO)
_h = RotatingFileHandler(LOGFILE, maxBytes=512 * 1024, backupCount=2)
_h.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
log.addHandler(_h)


def ipmi(args, timeout=15):
    try:
        r = subprocess.run(["ipmitool"] + args, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode == 0, r.stdout
    except Exception:
        return False, ""


def set_duty(zone, duty):
    """Duty setzen, bis zu drei Versuche mit Pause - KCS ist empfindlich."""
    for _ in range(3):
        ok, _out = ipmi(["raw", "0x30", "0x70", "0x66", "0x01",
                         "0x%02x" % zone, "0x%02x" % duty])
        if ok:
            return True
        time.sleep(2)
    log.warning("Zone %d: Duty %d konnte nicht gesetzt werden", zone, duty)
    return False


def fan_mode_full():
    """Ohne Full-Modus regelt der BMC die geschriebenen Werte wieder weg.

    Nur setzen, wenn er nicht ohnehin schon steht: Der Wechsel nach Full
    laesst den BMC zunaechst alle Luefter auf Vollast gehen. Beim Start des
    Dienstes steht der Modus normalerweise bereits (PostInit 2), ein blindes
    Setzen erzeugte also jedes Mal einen unnoetigen Vollast-Sprung.
    """
    ok, out = ipmi(["raw", "0x30", "0x45", "0x00"])
    if ok and out.replace(" ", "").strip() == "01":
        return False
    ipmi(["raw", "0x30", "0x45", "0x01", "0x01"])
    log.info("BMC-Lueftermodus auf Full gesetzt")
    time.sleep(3)
    return True


def _hwmon_max(name):
    best = -1
    base = "/sys/class/hwmon"
    try:
        geraete = os.listdir(base)
    except OSError:
        return best
    for d in geraete:
        pfad = os.path.join(base, d)
        try:
            with open(os.path.join(pfad, "name")) as fh:
                if fh.read().strip() != name:
                    continue
            for f in os.listdir(pfad):
                if f.startswith("temp") and f.endswith("_input"):
                    with open(os.path.join(pfad, f)) as fh:
                        v = int(fh.read().strip()) // 1000
                    if 0 < v < 150:
                        best = max(best, v)
        except (OSError, ValueError):
            continue
    return best


def cpu_temp():
    return _hwmon_max("coretemp")


def disk_temp():
    return _hwmon_max("drivetemp")


def gpu_temp():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        werte = [int(x) for x in r.stdout.split() if x.strip().isdigit()]
        return max(werte) if werte else -1
    except Exception:
        return -1


def curve(punkte, temp):
    """Lineare Interpolation. None, wenn kein Messwert vorliegt."""
    if temp is None or temp < 0:
        return None
    if temp <= punkte[0][0]:
        return punkte[0][1]
    if temp >= punkte[-1][0]:
        return punkte[-1][1]
    for (t0, d0), (t1, d1) in zip(punkte, punkte[1:]):
        if t0 <= temp <= t1:
            spanne = t1 - t0
            return int(d0 + (d1 - d0) * (temp - t0) / spanne) if spanne else d1
    return punkte[-1][1]


class Glaetter:
    def __init__(self, n):
        self.buf = deque(maxlen=n)

    def add(self, v):
        if v is not None and v >= 0:
            self.buf.append(v)
        return self.mittel()

    def mittel(self):
        return sum(self.buf) / len(self.buf) if self.buf else None


def naechster_duty(aktuell, ziel, minimum):
    """Nach oben sofort, nach unten gebremst.

    Die Hysterese haengt am Duty-Wert, nicht an einer gespeicherten
    Temperatur. Genau daran ist die Vorgaengerversion gescheitert: Sie
    verglich gegen die Temperatur der Vorminute, die bei langsamer Abkuehlung
    mitwanderte, sodass nie heruntergeschaltet wurde.
    """
    if aktuell is None:
        return ziel
    if ziel > aktuell:
        return ziel
    if aktuell - ziel < HYST:
        return aktuell
    return max(ziel, aktuell - DOWN_STEP, minimum)


def vollast(grund):
    log.warning("Vollast: %s", grund)
    fan_mode_full()
    time.sleep(1)
    set_duty(0, 100)
    time.sleep(1)
    set_duty(1, 100)


def beenden(signum=None, frame=None):
    vollast("Dienst wird beendet")
    sys.exit(0)


signal.signal(signal.SIGTERM, beenden)
signal.signal(signal.SIGINT, beenden)


def main():
    log.info("gestartet (Takt %ss, Mittelwert ueber %s Messungen, Hysterese %s)",
             INTERVAL, SMOOTH_N, HYST)
    fan_mode_full()
    glatt = {k: Glaetter(SMOOTH_N) for k in ("cpu", "disk", "gpu")}
    duty0 = duty1 = None
    letzte_schreibung = 0.0

    while True:
        roh = {"cpu": cpu_temp(), "disk": disk_temp(), "gpu": gpu_temp()}
        mittel = {k: glatt[k].add(v) for k, v in roh.items()}

        def bedarf(punkte, schluessel):
            """Nach oben auf den Rohwert reagieren, nach unten auf den
            geglaetteten - ein einzelner Ausreisser hebt die Stufe, aber
            senkt sie nicht."""
            a = curve(punkte, mittel[schluessel])
            r = curve(punkte, roh[schluessel])
            werte = [x for x in (a, r) if x is not None]
            return max(werte) if werte else None

        # Zone 0: Maximum der Stellwerte, nicht der Temperaturen
        b_gpu = bedarf(CURVE_GPU, "gpu")
        b_cpu = bedarf(CURVE_CPU, "cpu")
        if roh["gpu"] < 0:
            # Karte antwortet nicht - nie leise bei unbekanntem Zustand
            ziel0 = ZONE0_MAX
        else:
            kandidaten = [x for x in (b_gpu, b_cpu) if x is not None]
            ziel0 = max(kandidaten) if kandidaten else ZONE0_MAX

        # Zone 1: Platten fuehren, CPU nur als Untergrenze
        b_disk = bedarf(CURVE_DISK, "disk")
        kandidaten1 = [x for x in (b_disk, b_cpu) if x is not None]
        ziel1 = max(kandidaten1) if kandidaten1 else ZONE1_MAX

        notfall = []
        if roh["gpu"] >= EMERG_GPU:
            notfall.append("GPU %d C" % roh["gpu"])
        if roh["cpu"] >= EMERG_CPU:
            notfall.append("CPU %d C" % roh["cpu"])
        if roh["disk"] >= EMERG_DISK:
            notfall.append("Platten %d C" % roh["disk"])

        if notfall:
            neu0 = neu1 = 100
            log.warning("NOTFALL (%s) -> beide Zonen Vollast", ", ".join(notfall))
        else:
            ziel0 = max(ZONE0_MIN, min(ZONE0_MAX, ziel0))
            ziel1 = max(ZONE1_MIN, min(ZONE1_MAX, ziel1))
            neu0 = naechster_duty(duty0, ziel0, ZONE0_MIN)
            neu1 = naechster_duty(duty1, ziel1, ZONE1_MIN)

        jetzt = time.time()
        faellig = (jetzt - letzte_schreibung) >= REASSERT_S
        if neu0 != duty0 or faellig:
            set_duty(0, neu0)
            time.sleep(1)
        if neu1 != duty1 or faellig:
            set_duty(1, neu1)
        if faellig:
            letzte_schreibung = jetzt

        if neu0 != duty0 or neu1 != duty1:
            log.info("GPU %s C  CPU %s C  Platten %s C  ->  Zone0 %s%%  Zone1 %s%%",
                     roh["gpu"], roh["cpu"], roh["disk"], neu0, neu1)
        duty0, duty1 = neu0, neu1

        try:
            with open(HEARTBEAT, "w") as fh:
                fh.write("%d %d %d\n" % (int(jetzt), neu0, neu1))
        except OSError:
            pass

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log.exception("Unerwarteter Fehler: %s", e)
        vollast("Dienst abgestuerzt")
        sys.exit(1)
