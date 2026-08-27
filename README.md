# Supermicro X13SAE-F mit NVIDIA Tesla T4 — Unterlagen zum Verkauf

Zwei Dokumente zum Herunterladen. Alle Zahlen wurden auf dem laufenden Gerät
gemessen, nicht aus Datenblättern übernommen.

## [SMART-Bericht aller 16 Datenträger (PDF, 55 Seiten)](../../releases/latest/download/SMART-Bericht-X13SAE-F.pdf)

Zustand jedes einzelnen Datenträgers: zehn SAS-SSDs, vier Festplatten,
zwei SATA-SSDs. Vorn eine Zusammenfassung mit allen Kennwerten, dahinter die
ungekürzten Rohausgaben von `smartctl`, damit sich jede Angabe nachprüfen
lässt.

Auf jedem Datenträger lief vorher ein Selbsttest. **Zwei Auffälligkeiten sind
offengelegt** und im Bericht erklärt — beide betreffen die Anbindung, nicht das
Medium; auf allen sechzehn stehen sämtliche Zähler für Medienschäden auf null.

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

Stand: 28. August 2026. Erweiterte Selbsttests der vier Festplatten laufen
noch; die Ergebnisse werden hier nachgetragen.
