# tutorial round needs e1, e10 removed manually
python -m guessgame.creator --name 00_tutorial.json --pretty "Tutorial (10 patients)" --peek --samples 5

python -m guessgame.creator --name 01_experiment1.json --pretty "Experiment 1 (100 patients)" --samples 25
python -m guessgame.creator --name 01_experiment2.json --pretty "Experiment 2 (100 patients)" --samples 25
python -m guessgame.creator --name 01_experiment3.json --pretty "Experiment 3 (100 patients)" --samples 25