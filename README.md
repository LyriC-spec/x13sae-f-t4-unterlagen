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

## [Kühlung der Tesla T4 (PDF, 20 Seiten)](../../releases/latest/download/T4-Luefterregelung-X13SAE-F.pdf)

Die Grafikkarte ist eine Serverkarte ohne eigenen Lüfter und wird hier von
einem Radiallüfter gekühlt, den eine eigene Regelung steuert. Das Dokument
beschreibt, wie diese Regelung aufgebaut ist und welche drei Eigenheiten der
Hardware man kennen muss, damit die Karte überhaupt zuverlässig läuft.

Enthalten sind sämtliche Messwerte, die Begründung jeder Entwurfsentscheidung
und eine lauffähige Referenzfassung der Regelung — geschrieben so, dass sie
sich unter jedem Linux nachbauen lässt, nicht nur unter dem installierten
Betriebssystem.

---

Stand: 28. August 2026, vollständig. Die erweiterten Selbsttests der vier
Festplatten sind abgeschlossen und im Bericht eingetragen.

---

## Berichtigung vom 18. September 2026

In der Lüfterdokumentation ist der Pfad der Lebenszeichendatei mit
`/run/t4-fan.heartbeat` angegeben — in der Referenzfassung, im Wächter und in den
Prüfbefehlen in Abschnitt 10. **Auf dem System liegt die Datei unter
`/tmp/t4-fan.heartbeat`.** Regelung und Wächter verwenden dort übereinstimmend
diesen Pfad, es ist also nichts fehlerhaft eingerichtet; wer aber Abschnitt 10
abarbeitet, bekommt `No such file or directory` und hält den Wächter für tot.

Der richtige Prüfbefehl lautet:

```
stat -c %y /tmp/t4-fan.heartbeat
```

Das `noexec` auf `/tmp` steht dem nicht entgegen — es verhindert das Ausführen
von Dateien, nicht das Schreiben.

## Nachprüfung vom 18. September 2026

Das System wurde vor der Übergabe noch einmal unter Last geprüft. Leerlauf
`Enabled, P8, 405 MHz, 9,6 W, 42 °C`; unter Volllast 69 W, die Regelung zog der
Kennlinie folgend von 30 auf 100 % nach und fiel danach in Fünferschritten bis
auf die Untergrenze von 30 % zurück (Blower wieder 3220 U/min). Abweichend von
den Augustwerten lag die Karte bei Vollast auf 74 bis 75 °C statt 72 °C, bei
weiterhin zehn Grad Abstand zur Betriebsgrenze von 85 °C.
