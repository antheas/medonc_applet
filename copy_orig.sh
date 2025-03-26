#!/bin/bash

EXPERIMENT=medonc-v2
DATASET_NAME=orig

rm -rf experiments/$EXPERIMENT/data/$DATASET_NAME
mkdir -p experiments/$EXPERIMENT/data/$DATASET_NAME

cp -f ../medonc/data/view/medonc/tables/* experiments/$EXPERIMENT/data/$DATASET_NAME