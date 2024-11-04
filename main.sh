#!/bin/bash

# Spostati nella directory principale del progetto
cd "$(dirname "$0")"

# Attiva l'ambiente virtuale
source .venv/bin/activate

# Aggiungi la directory principale al PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Avvia il file main.py dentro cartella1
python3 chain_analisys/main.py --config "../config" --log-level "INFO"
