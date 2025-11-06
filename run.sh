#!/bin/bash
# Wrapper-Skript zum Ausführen des Agents

# Wechsle ins Skript-Verzeichnis
cd "$(dirname "$0")"

# Aktiviere Virtual Environment
source venv/bin/activate

# Führe Agent aus
python main.py "$@"
