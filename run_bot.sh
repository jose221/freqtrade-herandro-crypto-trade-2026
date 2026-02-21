#!/bin/bash
cd /Users/joseangelalvaradogonzalez/freqtrade-herandro-crypto-trade-2026
source myvenv/bin/activate
python -m freqtrade trade --config config.json --dry-run --strategy SampleStrategy
