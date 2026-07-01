#!/usr/bin/env bash
# Double-click me in Finder (macOS) to launch the ovb dashboard.
cd "$(dirname "$0")"
./run.sh || { echo; echo "run.sh exited ($?)"; read -n 1 -s -r -p "Press any key to close…"; }
