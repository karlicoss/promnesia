#!/usr/bin/env bash

cd "$(dirname "$0")"

cd user_data/
mkdir source1
cd source1
echo "i like https://github.com/karlicoss/promnesia." >> my_notes.txt
git clone https://github.com/karlicoss/exobrain
git clone https://github.com/koo5/notes

