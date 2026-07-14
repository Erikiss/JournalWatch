# JournalWatch

Tägliche Abfrage der größten Wissenschaftsjournale nach neuen **AI- und
Computing-Publikationen** – für die Verlage **Nature Portfolio (nature.com)**,
**Science / AAAS (science.org)** und **MDPI (mdpi.com)**.

## Wie es funktioniert

- `journalwatch.py` fragt die [Crossref-API](https://api.crossref.org) (kostenlos,
  kein API-Key) für jedes in `journals.json` konfigurierte Journal nach Artikeln
  der letzten Tage ab.
- Breit aufgestellte Journale (Nature, Science, Scientific Reports, Applied
  Sciences, …) werden per Keyword-Filter auf AI-/Computing-Themen eingegrenzt
  (Machine Learning, LLMs, Quantum Computing, Kryptographie, Turing/Komplexität,
  Neuromorphic, Robotics, …). Spezialisierte Journale (Nature Machine
  Intelligence, Science Robotics, MDPI *AI*, …) werden komplett übernommen.
- Bereits gemeldete DOIs werden in `data/seen_dois.json` gemerkt – kein Artikel
  taucht doppelt auf.
- Das Ergebnis ist ein nach Verlag gruppierter Markdown-Report:
  `reports/YYYY-MM-DD.md` (Archiv) und `reports/latest.md` (immer der neueste).

## Tägliche Ausführung

Der GitHub-Actions-Workflow [`journalwatch.yml`](.github/workflows/journalwatch.yml)
läuft **täglich um 06:00 UTC** (08:00 MESZ), führt die Abfrage aus und committet
den neuen Report direkt ins Repository. Über den Tab *Actions →
JournalWatch Daily → Run workflow* lässt er sich auch manuell starten.

Optional: Als Repository-Variable `CROSSREF_MAILTO` eine E-Mail-Adresse
hinterlegen – damit landet die Abfrage im schnelleren „polite pool" von Crossref.

## Lokal ausführen

Es wird nur Python ≥ 3.10 benötigt (keine Abhängigkeiten):

```bash
python journalwatch.py             # Lookback: 2 Tage
python journalwatch.py --days 7    # Lookback: 7 Tage
python journalwatch.py --no-dedupe # seen_dois.json ignorieren
```

## Journale anpassen

Journale und Keywords werden in [`journals.json`](journals.json) gepflegt:

```json
{ "publisher": "MDPI (mdpi.com)", "name": "Sensors", "issn": "1424-8220", "filter": true }
```

- `issn` – ISSN (Online-Ausgabe) des Journals bei Crossref
- `filter: true` – nur Artikel, die ein AI-/Computing-Keyword treffen
- `filter: false` – alle neuen Artikel des Journals übernehmen

### Abgedeckte Journale

| Verlag | Journale |
| --- | --- |
| Nature Portfolio | Nature, Nature Machine Intelligence, Nature Computational Science, Nature Electronics, Nature Communications, Scientific Reports |
| Science / AAAS | Science, Science Advances, Science Robotics |
| MDPI | AI, Machine Learning and Knowledge Extraction, Big Data and Cognitive Computing, Algorithms, Computers, Electronics, Applied Sciences, Sensors |
