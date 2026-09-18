# Supermicro X13SAE-F mit NVIDIA Tesla T4 — Unterlagen zum Verkauf

Zwei Dokumente zum Herunterladen. Alle Zahlen wurden auf dem laufenden Gerät
gemessen, nicht aus Datenblättern übernommen.

## [SMART-Bericht aller 16 Datenträger (PDF, 55 Seiten)](../../releases/latest/download/SMART-Bericht-X13SAE-F.pdf)

Zustand jedes einzelnen Datenträgers: zehn SAS-SSDs, vier Festplatten,
zwei SATA-SSDs. Vorn eine Zusammenfassung mit allen Kennwerten, dahinter die
ungekürzten Rohausgaben von `smartctl`, damit sich jede Angabe nachprüfen
lässt.

Auf jedem Datenträger lief ein Selbsttest, auf den vier Festplatten zusätzlich
ein **erweiterter Test, der die vollständige Oberfläche liest** — alle vier ohne
einen einzigen Lesefehler. **Zwei Auffälligkeiten sind offengelegt** und im
Bericht erklärt; beide betreffen die Anbindung, nicht das Medium, und auf allen
sechzehn Datenträgern stehen sämtliche Zähler für Medienschäden auf null.

Kurzfassung: Die zehn SAS-SSDs haben 143 bis 375 Betriebsstunden bei 0 %
Abnutzung.

## [Kühlung der Tesla T4 (PDF, 21 Seiten)](../../releases/latest/download/T4-Luefterregelung-X13SAE-F.pdf)

Die Grafikkarte ist eine Serverkarte ohne eigenen Lüfter und wird hier von
einem Radiallüfter gekühlt, den eine eigene Regelung steuert. Das Dokument
beschreibt, wie diese Regelung aufgebaut ist und welche drei Eigenheiten der
Hardware man kennen muss, damit die Karte überhaupt zuverlässig läuft.

Enthalten sind sämtliche Messwerte, die Begründung jeder Entwurfsentscheidung
und eine lauffähige Referenzfassung der Regelung — geschrieben so, dass sie
sich unter jedem Linux nachbauen lässt, nicht nur unter dem installierten
Betriebssystem.

## [Die laufenden Skripte und ihre Startbefehle](scripts/)

Die Regelung `t4-fan.py` und der Wächter `t4-fan-waechter.sh`, wie sie auf dem
System laufen, dazu die acht PostInit-Einträge im Wortlaut.

Auf dem Gerät liegen die Skripte in einem ZFS-Dataset auf dem boot-pool. **Eine
Neuinstallation von TrueNAS löscht sie**, und die Startbefehle allein nützen dann
nichts — der achte startet eine Datei, die es nicht mehr gibt. Deshalb liegen sie
hier.

---

Stand: 28. August 2026, vollständig. Die erweiterten Selbsttests der vier
Festplatten sind abgeschlossen und im Bericht eingetragen.

---

## Berichtigung vom 18. September 2026

Die Lüfterdokumentation nannte die Lebenszeichendatei der Regelung an vier
Stellen mit `/run/t4-fan.heartbeat` — in der Referenzfassung, im Wächter und im
Prüfbefehl in Abschnitt 10. **Auf dem System liegt die Datei unter
`/tmp/t4-fan.heartbeat`.** Eingerichtet war nichts fehlerhaft: Regelung und
Wächter verwenden dort übereinstimmend denselben Pfad. Wer aber den Prüfbefehl
abtippte, bekam `No such file or directory` und hielt den Wächter für tot.

**Die PDF ist berichtigt.** Alle vier Fundstellen sind angeglichen, und am Ende
steht ein Berichtigungsblatt, das die Änderung und die Nachprüfung festhält.

## Nachprüfung vom 18. September 2026

Das System wurde vor der Übergabe noch einmal unter Last geprüft. Leerlauf
`Enabled, P8, 405 MHz, 9,6 W, 42 °C`; unter Volllast 69 W, die Regelung zog der
Kennlinie folgend von 30 auf 100 % nach und fiel danach in Fünferschritten bis
auf die Untergrenze von 30 % zurück (Blower wieder 3220 U/min). Abweichend von
den Augustwerten lag die Karte bei Vollast auf 74 bis 75 °C statt 72 °C, bei
weiterhin zehn Grad Abstand zur Betriebsgrenze von 85 °C.
