# silpac-h2
Utilities created in project H2 of the DFG research unit SILPAC (FOR 5157)

This repository contains mostly scripts that were created for a specific research task (linguistics, psycholinguistics). Beware that the author is not a programming export, scripts may not be well documented and often are in a work-in-progress state.
You are nevertheless welcome to use them, adapt them to your needs and give feedback on them.

## pb1-parse-qualtrics.py

Processes output csv files exported from the Qualtrics experiment website. This script was designed for a specific experiment. It converts the Qualtrics output to a table that can be analysed with R. It also analyses the Italian data using H. Schmid's (LMU, München) _TreeTagger_ with paramater for Italian created by A. Stein (U Stuttgart).

## childes.py

Convert CHILDES chat data to csv.  The output table will have one word per line, to facilitate e.g. studies of vocabulary progression.
Morphological annotation from '%mor' lines will be added, other annotation lines will be ignored.
Tested for some of the French CHILDES files (e.g. Paris).

Hints:

- Concatenate *.cha files of one project
- Run scripts on concatenated file.

