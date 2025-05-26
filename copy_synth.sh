#!/bin/bash

if [ -z "$1" ] || [ -z "$2" ]; then
    echo -e "\nCall '$0 <dataset-name> <timestamp>"
    exit 1
fi

EXPERIMENT=medonc-test
VIEW=medonc
DATASET_NAME=$1

# Get timestamps:
# ls ../medonc/data/view/medonc/metajson.json | tail -n 3
DATASET_TS=$2

IN_DIR=../medonc/data
OUT_DIR=experiments/$EXPERIMENT/data/$DATASET_NAME

rm -rf $OUT_DIR
mkdir -p $OUT_DIR

cp -f $IN_DIR/view/$VIEW/metajson.json/$DATASET_TS/metajson.json $OUT_DIR/meta.json
cp -f $IN_DIR/synth/$VIEW/mare/tables/lines.pq/$DATASET_TS/* $OUT_DIR
cp -f $IN_DIR/synth/$VIEW/mare/tables/medicine.pq/$DATASET_TS/* $OUT_DIR
cp -f $IN_DIR/synth/$VIEW/mare/tables/patients.pq/$DATASET_TS/* $OUT_DIR
cp -f $IN_DIR/synth/$VIEW/mare/tables/updates.pq/$DATASET_TS/* $OUT_DIR