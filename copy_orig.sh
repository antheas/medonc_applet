#!/bin/bash

EXPERIMENT=medonc-test
VIEW=medonc
DATASET_NAME=orig

rm -rf experiments/$EXPERIMENT/data/$DATASET_NAME
mkdir -p experiments/$EXPERIMENT/data/$DATASET_NAME

cp -f ../medonc/data/view/$VIEW/tables/* experiments/$EXPERIMENT/data/$DATASET_NAME