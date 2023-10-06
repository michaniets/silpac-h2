# silpac-h2
Utilities created in project H2 of the DFG research unit [SILPAC](https://silpac.uni-mannheim.de) (FOR 5157)

This repository contains mostly scripts that were created for a specific research task (linguistics, psycholinguistics). Note that the author is not a programmer, scripts may not be well documented and are often in a work-in-progress state.
You are welcome to use them, adapt them to your needs and give feedback on them.

## pb1-parse-qualtrics.py

Processes output csv files exported from the Qualtrics experiment website. This script was designed for a specific experiment. It converts the Qualtrics output to a table that can be analysed with R. It also analyses the Italian data using H. Schmid's (LMU, München) _TreeTagger_ with paramater for Italian created by A. Stein (U Stuttgart).

## childes.py

Convert CHILDES chat data to csv where utterances are split into one word per line format.
The script was built to facilitate studies of vocabulary progression.

- Without -p option: Morphological annotation from '%mor' lines will be used, other annotation lines will be ignored.
- Option -p <parameters>: Selects a file with TreeTagger parameters.  Tokenises for TreeTagger and uses tagger annotation instead of the original '%mor' line.) All the annotation lines will be ignored.

(Looking for a better written script? J. Kodner has one, [here](https://github.com/jkodner05/method.git).)

Tested for some of the French CHILDES files (e.g. Paris).

Hints:

1. Concatenate *.cha files of one project
2. Run script on concatenated file.
3. Use -p <parameters> for TreeTagger analysis

Example: concatenated French CHILDES projects, tagged with parameters for spoken French

> childes.py -m VER --pos_utterance VER -p perceo-spoken-french-utf.par CHILDES-French-SILPAC.cha


Bugs:

- Some utterances are not processed correctly because not all the specifics of the CHAT annotation were implemented.  Watch out for 'INDEX ERROR' messages while processing.


