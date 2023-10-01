#!/usr/bin/env python3
__author__ = "SILPAC H2"
__version__ = "1.3"
__email__ = "(alessia.cassara|achim.stein)@ling.uni-stuttgart.de"
__status__ = "tested with test items"
__license__ = "GPL"

import sys
import argparse, pickle, re
import pandas as pd   # a package for tables
import numpy as np    # not sure if we need this
import os
import datetime
from xmlrpc.client import boolean
import subprocess   # for system commands, here: tree-tagger
from collections import defaultdict   #  make dictionaries with initialised keys (avoids KeyError)
from geopy.geocoders import Nominatim   # get region from gps coordinates
import csv

# ----------------------------------------------------------------------
# set global variables
# ----------------------------------------------------------------------
errors = {} # store error analysis
warnings = defaultdict(int) # store warnings
geolocator = Nominatim(user_agent="geoapiExercises")

# The order of verbs is defined in the Qualtrics input file
# Exp #1 Nov 2022
targetVerbOrder = ['rompere', 'rompere', 'rompere', 'bruciare', 'bruciare', 'bruciare', 'fermare', 'fermare', 'fermare', 'illuminare', 'illuminare', 'illuminare', 'affondare', 'affondare', 'affondare', 'aumentare', 'aumentare', 'aumentare', 'sciogliere', 'sciogliere', 'sciogliere', 'bagnare', 'bagnare', 'bagnare', 'curare', 'curare', 'curare', 'diminuire', 'diminuire', 'diminuire', 'aprire', 'aprire', 'aprire', 'bollire', 'bollire', 'bollire']
# Exp #2 June 2023
targetVerbOrder = ['fermare', 'fermare', 'fermare', 'affondare', 'affondare', 'affondare', 'rompere', 'rompere', 'rompere', 'curare', 'curare',
'curare', 'bruciare', 'bruciare', 'bruciare', 'bollire', 'bollire',
'bollire', 'bagnare', 'bagnare', 'bagnare', 'sciogliere',
'sciogliere', 'sciogliere', 'illuminare', 'illuminare', 'illuminare',
'aprire', 'aprire', 'aprire', 'diminuire', 'diminuire', 'diminuire',
'aumentare', 'aumentare', 'aumentare']
# reduce list to types
testedVerbs = set(targetVerbOrder)
# build a regex to match the verb roots in target items
testedVerbroots = list(map(lambda x: re.sub(r'.re', '', x), testedVerbs))   #  cut the suffix. map() applies the function to each item of the list
testedVerbsRegex = '|'.join(testedVerbroots)
print("===> target Items:", len(targetVerbOrder))
print("===> tested Verbs:", len(testedVerbs), testedVerbs)
print("===> regex for tested Verbs:", testedVerbsRegex)


# ----------------------------------------------------------------------
# command line options
# ----------------------------------------------------------------------

def get_arguments():
    parser = argparse.ArgumentParser(
        description = ( "Convert results from Qualtrics experiment for R input." ),
        formatter_class = argparse.ArgumentDefaultsHelpFormatter)  # show default values in help text
    parser.add_argument(
        "file_name",
        help = "input data, table with tab delimiters")
    parser.add_argument(
        '-o', '--output', default = "", type = str,
        help='Write output to file')
    parser.add_argument(
        '-q', '--quest', default = "", type = str,
        help='Write questionnaire (participant data) to file')
    args = parser.parse_args()
    return args

# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    args = get_arguments()   # get command line options
    if args.quest != '':
        with open(args.quest, 'w') as quest:
            quest.write("")
            quest.close()
    itemNumbers = {}     # dictionary to associate header with Pri_Tar number
    args = get_arguments()   # get command line options
    print("===> Reading input file: ", args.file_name)
    df = pd.read_csv(args.file_name, sep='\t', dtype=str, header=0)   # define panda object, take first row as column headers

    # SECOND ROW: row 1 is header, row 2 has index 0
    # we need the item number Argument_structure_prime
    # B_Pri_Tar_26=T
    for colHead, value in df.iloc[0, 0:].items():    # in row 2 iterate through columns and store item numbers
        try:
            re.search(r"_Pri_Tar_(\d+)", value)
        except:
            print(colHead)
            print(value)
            raise
        if re.search(r"_Pri_Tar_(\d+)", value):     # only in Prime-Target columns...
            itemNr = re.search(r"_Pri_Tar_(\d+)", value).group(1)   # assign the number to a variable
            itemNumbers[colHead] = itemNr     # store in dict: '435_Prime-List3 ': '1', '435_Target-List3': '1', etc
            #print("    col:", colHead, "item:", itemNr, "value:", value)   # check
            continue
        else:
            itemNumbers[colHead] = 0     # zero if not in a Prime-Target column
    print(f"===> Column headers parsed: {len(itemNumbers.keys())} item numbers stored.\n")

    # FOLLOWING ROWS: row 3 has index 1 in df
    # TODO clear conditions for calling the functions depending on the type of column
    outRows = []   # define list of rows (each row is a dictionary)
    outRowNr = 0   # output row numbering
    for rowNr, row in df[1:].iterrows():    # iterate through rows 3- using commands of the Pandas library
        thisQuest = {}    # stores the questionnaire
        readQuest = True    # True if the questionnaire has been stored
        # verify some selection criteria
        if row.Finished == "False":
            warnings["not finished (skipped)"] += 1   # TODO better collect row numbers
            continue
        # verify some selection criteria
        if not re.search ("italian", str(row.Languages_1), re.IGNORECASE):
            warnings["not Italian L1 (skipped)"] += 1   # TODO better collect row numbers
            row.ResponseId = row.ResponseId + "_reject:Language1"
            # continue    # uncomment to skip
        print("\n----ROW number", rowNr, "\n", row)    # display an overview of the row
        taggerInput = ""     # will hold the concatenated input items: <s_A1> sentence <s_A2> sentence ....
        items = {}     # dictionary colHead:item
        primeItem = defaultdict(str)
        for colHead, value in row.items():    # iterate through columns
            listID = "0"
            value = str(value)    # we need a string
            # 1) match columns containing participant data
            if readQuest:
                thisQuest[colHead] = value
            if re.search(r"End of questionnaire", colHead):
                readQuest = False
            # 2) match columns containing target items
            if re.search(r"Target-List", colHead) and value != "nan":  # for target items with non-empty cells
                match = re.search(r'Target-List([\d])', colHead).group(1)    # get the list number (1-3)....
                listID = "ABC"[int(match)-1]      # get the corresponding letter, to match Argument_structure_prime
                itemID = listID + str(itemNumbers[colHead])     # add the item number to create a unique code
                if itemNumbers[colHead] != 0:  # only for targets (not primes): append sentence
                    items[itemID] = value   # store the original input in dictionary
                    taggerInput = taggerInput + " <s_" + itemID + "> " + value
            # 3) match column 699: content collected by Qualtrics plugin
            if colHead == "Argument_structure_prime":
                primeType = getPrimeValues(value)  # get the dictionary relating itemID to type of prime
            # 4) match column 700: content collected by Qualtrics plugin
            if colHead == "Content_prime":
                primeItem = getPrimeValues(value)
            if colHead == "Animacy_prime":
                primeAnimacy = getPrimeValues(value)

        # end of column processing. Launch TreeTagger
        (itemWords, itemPOS, itemTagged) = treeTagger(taggerInput)     # dictionary containing the tagged target items
        if args.quest != '':
            outputQuestionnaire(rowNr, thisQuest)    # output participant data
        if args.output != '':
            debugTarget = 0   # reset the counter for calls of getTargetAS
            for key in itemTagged.keys():            # output each item in a separate row (v1.1: using DictWriter)
                (targetType, targetDebug) = getTargetAS(itemPOS[key], itemTagged[key])     # rules for analysing the annotated sentence
                m = re.search(r'([A-Z])(\d+)', key)   # separate list and item ID
                listID=m.group(1)
                itemNr=m.group(2)
                outRowNr += 1
                thisRow = {
                    'outRowNr': outRowNr,
                    'ResponseId': row.ResponseId,
                    'listID': listID,
                    'itemNr': itemNr,
                    'verb': targetVerbOrder[int(itemNr)-1],
                    'primeType': primeType[key],
                    'primeAnimacy': primeAnimacy[key],
                    'primeItem': primeItem[key],
                    'targetGuess': targetType,
                    'targetType': targetType + '?',
                    'targetDebug': targetDebug,
                    'targetItem': items[key],
                    'targetWords': itemWords[key],
                    'targetPOS': itemPOS[key],
                    'targetTagged': itemTagged[key] }
                outRows.append(thisRow)   # append dictionary for this row to list of rows
    # end of processing input lines / end of file
    # write output table: DictWriter matches header and rows, regardless of the order of fields in row
#    outLine = "(c) SILPAC " + str(today)  # put a date in first cell of header row
    outHeader = ['outRowNr', 'ResponseId', 'listID', 'itemNr', 'verb', 'primeType', 'primeAnimacy', 'primeItem', 'targetGuess', 'targetType', 'targetDebug', 'targetItem', 'targetWords', 'targetPOS', 'targetTagged']
    if args.output != '':   # initialise the ouput files
        print ("\n--- Writing items to file " + args.output)
        with open(args.output, 'w', newline='') as out:   # newline '' is needed: we have commas in items
            writer = csv.DictWriter(out, delimiter='\t', fieldnames=outHeader)
            writer.writeheader()
            writer.writerows(outRows)
    print ("\n============== TAGGING ERRORS ==============")
    for key in errors.keys():
        print ("\n===>ERROR:", key)
        for sentence in errors[key].split("@ERR@"):    #  split concatenated error items
            print ("\t", sentence)
    print ("\n============== WARNINGS ==============")
    for key in warnings.keys():
        print (warnings[key], " warning(s) for: ", key, sep="")
    quit()


#----------------------------------------------------------------------
# Below: functions for the different cell types
#----------------------------------------------------------------------
def storeTargetNr(value):     #  (maybe not needed: we did this in main)
    # TODO... make dictionary
    return()

def parseInput(value):     # parse what participants typed in the textbox
    # TODO...... code Alessia's conditions
    return()

def treeTagger(str):
    # input:  concatenated target items
    # output: tagged items stored in dictionaries with item IDs as key
    itemTagged = {}  # this dict stores tagged items in the format  Word_POS_Lemma ...
    itemPOS = {}  # this dict stores POS tags only
    itemWords = {}  # this dict stores words only
    taggerBin = os.path.expanduser('~/Nextcloud/H2-shared/cmd/tree-tagger')     # TreeTagger binary
    paramFile = os.path.expanduser('~/Nextcloud/H2-shared/experiments/unacc-it/italian-utf.par')    # TreeTagger parameters
    if not os.path.exists(taggerBin):   # verify if tagger files exist
        print("tree-tagger binary not found:", taggerBin, " - trying current working directory...")
        taggerBin = os.path.expanduser('./tree-tagger')     # TreeTagger binary
        if not os.path.exists(taggerBin):   # verify if tagger files exist
            print("tree-tagger binary not found:", taggerBin, " - quitting.")
            quit()
    if not os.path.exists(paramFile):
        print("Parameter file not found:", paramFile, " -  trying current working directory...")
        paramFile = os.path.expanduser('./italian-utf.par')    # TreeTagger parameters
        if not os.path.exists(paramFile):
            print("Parameter file not found:", paramFile, " - quitting.")
            quit()
    str = re.sub(r'([\'\´\`])', r'\1 ', str)        # quick & dirty tokenization
    str = re.sub(r'([\"\.\!,;:])', r' \1 ', str)
    str = re.sub(r' +', r'\n', str)      # 1 word per line
    # system call for TreeTagger: echo + output to pipe: echo "bla"|tree-tagger parameters options
    #    next line takes pipe output as input
    #    check_output() returns output as a byte string that needs to be decoded using decode()
    p1 = subprocess.Popen(["echo", str], stdout=subprocess.PIPE)
    tagged = subprocess.check_output([taggerBin, paramFile, '-token', '-lemma', '-sgml'], stdin=p1.stdout)
    tagged = tagged.decode('utf8')
    tagged = re.sub(r'\t([A-Za-z:]+)\t', r'_\1=', tagged)         # format annotation format: word_pos=lemma ...
    tagged = re.sub(r'\n', r' ', tagged)                          # put everything on one line
    for sentence in tagged.split("<s_"): #taggedItems:    # split the concatenated items
        if sentence == "":   # first element is empty: ignore
            continue
        # pos tagging: improve / correct errors
        sentence = re.sub(r'uno_ADJ', r'uno_DET:def', sentence)  # correct uno_ADJ everywhere
        if(re.search(r'_VER:[a-z]+=(essere|avere|fare|stare) [^ ]+_VER:(pper|infi|geru)=', sentence)):   # VER>AUX
            sentence = re.sub(r'_VER:[a-z]+=(essere|avere|fare|stare) ([^ ]+_VER:(pper|infi|geru)=)', r'_AUX:pres=\1 \2', sentence)
        if(not re.search(r'_VER', sentence)):    # missing verb: correct tagging error
            sentence = re.sub(r'ferma_ADJ=fermo', r'ferma_VER:pres=fermare', sentence)
            sentence = re.sub(r'bolle_NOM=bolla', r'bolle_VER:pres=bollire', sentence)
            sentence = re.sub(r'cura_NOM=cura', r'cura_VER:pres=curare', sentence)
            sentence = re.sub(r'_ADJ=veterinario', r'_NOM=veterinario', sentence)
            sentence = re.sub(r'zuppa_ADJ', r'zuppa_NOM', sentence)

        if re.search(r'^[A-Z]\d+>', sentence):     # get the item number from the rest of code, e.g. (<s_)A23
            matches = re.search(r'^([A-Z])(\d+)> *(.*?) ?$', sentence)
        else:
            print("Error: no item number found in item:", sentence)
            quit()
        # generate output fields from each item
        key = matches.group(1) + matches.group(2)
        itemTagged[key] = matches.group(3)     #   dict   itemNr : sentence {A1:Il vaso si rompe}
        posTags = re.findall(r'_(.*?)=', sentence)   # gets the list of tags...
        posWords = re.findall(r' (.*?)_', sentence)   # gets the list of words...
        itemPOS[key] = ' '.join(posTags)     #  ... and stores it in dictionary
        itemWords[key] = ' '.join(posWords)     #  ... and stores it in dictionary
    return(itemWords, itemPOS, itemTagged)

def verifyTagging(value):
    verdict = ""   # output
    if re.search(r'_VER:pres=(essere|avere).*_VER:pper=', value):
        inf = re.search(r'_VER:pres=(essere|avere).*_VER:pper=(.*)', value).group(1)
        verdict = "auxiliary"
    elif re.search(r'_VER.*_VER', value):
        verdict = "too many verbs"
    elif not re.search(r'_VER', value):
        verdict = "no verb"
    else:
        verdict = "OK"
    if not verdict == "OK":
        if verdict in errors:
            errors[verdict] = errors[verdict] + "@ERR@" + value    # store errors in list
        else:
            errors[verdict] = value    # store errors
    return(verdict)

def getPrimeValues(value):
    #d = {}
    d = defaultdict(str)   # this definition of the dictionary avoids KeyErrors if value for key is missing
    pairs = value.split("/")
    for pair in pairs:
        if not pair:
            d
            continue
        m = re.search(r"_Pri_Tar_(\d+)", pair)
        itemNr = m.group(1) if m else ""
        m = re.search(r"([ABC])_Pri_Tar_", pair)
        listID = m.group(1) if m else ""
        #m = re.search(r"_Pri_Tar_\d+=([TEA])", pair)
        m = re.search(r"_Pri_Tar_\d+=(.*)", pair)    # TODO: check if this works for both primeType and primeItem
        primeType = m.group(1) if m else ""
        if itemNr:
            #print(pair, itemNr, listID, primeType)
            d[listID + itemNr] = primeType
        #print(d)
    return(d)

# rules for analysing the annotated sentence
# pos: string of POS POS ...
# full: string of  word_POS=lemma word_POS=lemma ...
def getTargetAS(pos, full):
    # take an item as input (as POS string and the complete annotated item)
    # return the AS type (T = transitive, A = unaccusative, R = reflexive, P = passive)
    global debugTarget   # use global variable
    asType = 'NA'    # default return value
    append = ''
    posL = pos.split(" ")   # create a list version for both input strings
    fullL = full.split(" ")
    # 1) improve unanalysable cases: if more than 1 verb, find the relevant verb using the lemma (testedVerbs)
    if re.search(r' VER.* VER', pos):    # more than 1 verb
        r = re.compile("VER:[a-z]+=(" + testedVerbsRegex + ").*" + "VER:[a-z]+=(" + testedVerbsRegex + ")")
        if re.search(r, full):
            append = "_err:tooManyVerbs"    # append error message. Undecidable: two verbs match the list of tested verbs
        else:
            # we match the testedVerbs (as regex) against the *list* of pos
            r = re.compile(".*VER:[a-z]+=("+ testedVerbsRegex + ").*")   # regex must expand to the complete item
            matches = list(filter(r.match, fullL)) # we retrieve the matching element
            if len(matches) == 1:                  # if only one element matches...
                wordNr = fullL.index(matches[0])   # ...determine the position of the matched word in the list
                posL[wordNr] = re.sub("VER", "VOK", posL[wordNr])  # temporarily rename VER > VOK for this element
                append = "_check:verbSelected"    # append a warning so we can verify this decision
                pos = " ".join(posL)              # rebuild the pos as string
                pos = re.sub("VER", "VRB", pos)   # and rename the 'good' verb as VER and the bad verb(s) as VRB
                pos = re.sub("VOK", "VER", pos)
        if re.search(r'.*? VRB.*? (PON|CON|ADV) (.*VER.*)', pos):
            pos = re.sub(r'.* VRB.*? (PON|CON|ADV) (.*VER.*)', r'\2', pos)   # cut off initial subordinate clause with bad verb
            append = append + "_cutSubordL"
        if re.search(r'(.*VER.*) (PON|CON|ADV) .*? VRB.*?', pos):
            pos = re.sub(r'(.*VER.*) (PON|CON|ADV) .*? VRB.*', r'\1', pos)   # cut off final subordinate clause with bad verb
            append = append + "_check:cutSubordR"
    # 2) adverbials: PRE+NOM > ADVP
    if re.search(r" VER.* PRE NOM", pos):
        pos = re.sub(r'( VER.*?) PRE NOM', r'\1', pos)    # delete adverbials
        append = append + "_check:deletedPRE+NOM"
    # 3) cut off after the first post-verbal preposition
    if re.search(r" VER.* PRE", pos):    # if there is a PRE after the verb...
        pos = re.sub(r'( VER.*?) PRE.*', r'\1', pos)   # ... cut off
        append = append + "_check:cutPRE..."
    # 4) delete auxiliary
    if re.search(r"AUX.*? VER", pos):    # ignore auxiliary
        pos = re.sub(r'AUX.*? VER', r'VER', pos)
        append = append + "_check:deleteAUX..."
    # 5) apply rules: the longest expression is matched first
    if re.search(r"NOM.* VER.*? ADV DET.*? NOM", pos):    # DET:def NOM VER:pres ADV DET:def NOM   (...aumenta sotto il sole)
        asType = "A"
        append = append + "_check:ADV>PRE?"
    elif re.search(r"NOM.* PRO:(pers|refl) VER", pos):
        asType = "R"
        append = append + "_rule:NOM-PRO:(pers|refl)-VER"
    elif re.search(r"NOM.* VER.* NOM", pos):
        asType = "T"
        append = append + "_rule:NOM-VER-NOM"
    elif re.search(r"NOM.* VER", pos):
        asType = "A"
    elif re.search(r"^PRO:(pers|refl) VER", pos):
        asType = "R"
    elif re.search(r"VER", pos):
        asType = "A"
    else:
        asType = "NA"
        append = append + "_err:noMatchingPattern"
#    return(asType +'\t'+ append)
    return(asType, append)


def processLocation(Latitude, Longitude):
    location = geolocator.reverse(Latitude+","+Longitude)
    if location is None:
        return('NA')
    address = location.raw['address']
    city = address.get('city', '')
    zipcode = address.get('postcode')
    country = address.get('country', '')
    return(city + ", " + str(zipcode) + ", " + country)

def outputQuestionnaire(rowNr, thisQuest):
    thisQuest["addAddress"] = "dummy"
    thisQuest["addAddress"] = processLocation(thisQuest["LocationLatitude"], thisQuest["LocationLongitude"])
    #print(thisQuest)
    args = get_arguments()   # get command line options
    if args.quest != '':
        print ("\n--- Writing participants data to file " + args.quest)
        with open(args.quest, 'a') as out:   #### TODO: this stores only the last line
            if rowNr == 1:      # if first line, write keys as table header
                today = datetime.date.today()
                outLine = "(c) SILPAC " + str(today)  # put a date in first cell of header row
                outLine = outLine + '\t' + '\t'.join(thisQuest.keys())   # add the concatenated dictionary keys
                out.write(outLine + '\n')
            outLine = str(rowNr) + '\t' + '\t'.join(thisQuest.values())   # add the concatenated dictionary values
            out.write(outLine + '\n')
    return()

def outputItems(rowNr, itemTagged):
    thisQuest["addAddress"] = "dummy"
    thisQuest["addAddress"] = processLocation(thisQuest["LocationLatitude"], thisQuest["LocationLongitude"])
    #print(thisQuest)
    args = get_arguments()   # get command line options
    if args.output != '':
        with open(args.output, 'a') as quest:   #### TODO: this stores only the last line
            if rowNr == 1:      # if first line, write keys as table header
                today = datetime.date.today()
                outLine = "(c) SILPAC " + str(today)  # put a date in first cell of header row
                outLine = outLine + '\t' + '\t'.join(thisQuest.keys())   # add the concatenated dictionary keys
                quest.write(outLine + '\n')
            outLine = str(rowNr) + '\t' + '\t'.join(thisQuest.values())   # add the concatenated dictionary values
            quest.write(outLine + '\n')
    return()

# don't delete the call of main
if __name__ == "__main__":
    main()


