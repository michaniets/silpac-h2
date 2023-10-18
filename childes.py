#!/usr/bin/python3

__author__ = "Achim Stein"
__version__ = "1.3"
__email__ = "achim.stein@ling.uni-stuttgart.de"
__status__ = "7.10.23"
__license__ = "GPL"

import sys
import argparse, pickle, re
import os
import fileinput
import datetime
from xmlrpc.client import boolean
import subprocess   # for system commands, here: tree-tagger
from collections import defaultdict   #  make dictionaries with initialised keys (avoids KeyError)
import csv
# ADDED TR
from childes.tokenizers import Tokenizer

# global vars
age = child = speaker = utt = uttID = timeCode = splitUtt = pid = ''
sNr = age_days = 0
outRows = []
childData = {}
# ADDED TR
# Here are all the possible tokenizers
TOKENIZERS = ['ASTokenizer', 'FrenchTokenizer']
# Here we are initializing the variable tokenizer as a global
tokenizer = None
# END


def main(args):
  global age, age_days, child, childData, speaker, utt, uttID, pid, splitUtt, sNr, timeCode, outRows, tokenizer    # needed to modify global vars locally
  age = child = taggerInput = pid = ''
  age_days = 0
  childData = {}  # store age for a child
  with open(args.out_file, 'r', encoding="utf8") as file:  # , newline=''
    sys.stderr.write("Reading " + args.out_file +'\n')
    all = file.read()
    all = re.sub('@END', '*\n', all)  # insert delimiter at end of file
    sentences = all.split('\n*')   # split utterances at '*', e.g. *CHI:
  if len(sentences) <= 1:
    sys.stderr.write("No output sentences found. " + str(len(sentences)) + " Exiting.\n")
    sys.exit(0)
  else:
    sys.stderr.write("Processing " + str(len(sentences)) + ' utterances\n')
  with open('tagthis.tmp', 'w') as tagthis:  # initialise tagger output file
    pass
  for s in sentences:  # sentence = utterance
    # -------------------------------------------------------
    # parse file header
    # -------------------------------------------------------
    # use PID to identify header
    rePID = re.compile('@PID:.*/.*?0*(\d+)')
    if re.search(rePID, s):
      if re.search (r'@Comment:.*dummy file', s):
        continue
      m = re.search(rePID, s)
      pid = m.group(1)
      childData = {}  # empty childData bio dictionary
      # check for more than one Target_Child (French: only in Palasis)
      childNr = re.findall(r'@ID:\s+.*\|.*?\|[A-Z]+\|.*?\|.*Target_Child\|', s)
      if len(childNr) > 1:
        for c in childNr:
          m = re.search(r'@ID:\s+.*\|(.*?)\|([A-Z]+)\|(\d.*?)\|.*Target_Child\|', c)
          sys.stderr.write("----- reading header ID %s\n" % (c))
          project = m.group(1)
          key = m.group(2)  # use speaker abbrev as key for bio data
          age, age_days = parseAge(m.group(3))
          child = 'n=' + str(len(childNr)) + '_' + project[:3]
          childData[key] = (child, age, age_days)   # store bio data in dict
      else:
        # just one Target_Child  (TODO: redundant, include above)
        # example: @ID: fra|Paris|CHI|0;11.18|female|||Target_Child|||

        if re.search(r"CHI Target_Child , TAT Tata Babysitter", s):  # correct error in one file header
          s = re.sub("CHI Target_Child , TAT Tata Babysitter", "CHI Anne Target_Child , TAT Tata Babysitter", s)
        reMatch = re.compile('@ID:.*\|(.*?)\|[A-Z]+\|(\d.*?)\|.*Target_Child')
        if re.search(reMatch, s):
          m = re.search(reMatch, s)
          project = m.group(1)
          age, age_days = parseAge(m.group(2))
          # get the child's name, e.g. @Participants:	CHI Tim Target_Child, MOT Mother Mother...
          reMatch = re.compile('@Participants:.*CHI\s(.*?)\sTarget_Child')
          if re.search(reMatch, s):
            m = re.search(reMatch, s)
            child = m.group(1) + '_' + project[:3]  # disambiguate identical child names
            child = re.sub(r'[éè]', 'e', child)  # Anae is not spelt consistently
            child = re.sub(r'Ann_Yor', 'Anne_Yor', child)  # repair inconsistency
            childData['CHI'] = (child, age, age_days)   # store bio data in dict
      sys.stderr.write("PID: %s / CHILD: %s / AGE: %s = %s days\n" % (pid, child, age, str(age_days)))
      continue  # no output for the header
    if pid == '':       # verify if header was parsed
      sys.stderr.write('!!!!! ERROR: missing header info. Check the file header! Exiting at utterance:\n')
      sys.stderr.write(s)
      sys.exit(1)
    # -------------------------------------------------------
    # parse utterance
    # -------------------------------------------------------
    timeCode = utt = mor = speaker = ''
    tags = []
    sNr += 1
    uttID = pid + '_u' + str(sNr)     # args.out_file + '_u' + str(sNr)
    # general substitution
    s = re.sub(r'‹', '<', s)
    s = re.sub(r'›', '>', s)
    s = re.sub(r'\n\s+', ' ', s, re.DOTALL)  # append multi-line to first line
    # get utterance time? code (delimited by ^U)
    if re.search(r'(.*?)', s):
      m = re.search(r'(.*?)', s)
      timeCode = m.group(1)
    s = re.sub(r' ?.*?', '', s)
    # match the annotation line starting with %mor
    reMatch = re.compile('%mor:\s+(.*)')
    if re.search(reMatch, s):
      m = re.search(reMatch, s)
      mor = m.group(1)
    # match speaker and utterance -- TODO: handle Palasis corpus (no 'CHI', but several child name abbrevs)
    reMatch = re.compile('^([A-Z]+):\s+(.*?)\n')
    if re.search(reMatch, s):
      m = re.search(reMatch, s)
      speaker = m.group(1)
      utt = m.group(2)
    # ADDED TR: (re)initialize Tokenizer
    tokenizer = Tokenizer.create(args.tokenizer)
    # END
    splitUtt = tokenizer.cleanUtt(utt)  # clean copy for splitting in to words
    # concatenate utterances to build taggerInput. Use tag with uttID
    if args.parameters != '':
      with open('tagthis.tmp', 'a') as tagthis:  # for tagger output
        taggerLine = "<s_" + uttID + "> " + tokenizer.tokenise(splitUtt) + '\n'
        tagthis.write(taggerLine)

    # -------------------------------------------------------
    # split utterance into tokens
    # -------------------------------------------------------
    # list of table rows 
    if speaker != '':
      if args.parameters == '':
        outRows = wordPerLineChat(splitUtt, mor)
      else:
        outRows = wordPerLineTagger(splitUtt, mor)

  # ----------------------------------------
  # TreeTagger (option -p)
  # ----------------------------------------
  if args.parameters != '':
    sys.stderr.write('Running TreeTagger on taggerInput\n')
    with open('tagthis.tmp', 'r') as tagthis:
      taggerInput = tagthis.read()
    (itemWords, itemPOS, itemLemmas, itemTagged) = treeTagger(taggerInput)

  # ----------------------------------------
  # output
  # ----------------------------------------
  # write output table: DictWriter matches header and rows, regardless of the order of fields in row
  outHeader = ['utt_id', 'utt_nr', 'w_nr', 'speaker', 'child_project', 'age', 'age_days', 'time_code', 'word', 'lemma', 'pos', 'features', 'note', 'utterance', 'utt_clean', 'utt_tagged']
  with open(args.out_file + '.csv', 'w', newline='') as out:   # newline '' is needed: we have commas in items
    writer = csv.DictWriter(out, delimiter='\t', fieldnames=outHeader)
    writer.writeheader()
    writer.writerows(outRows)

  # add tagger output
  if args.parameters != '':
    sys.stderr.write('Adding tagger output for each utterance...\n')
    addTagging(args.out_file + '.csv', args.out_file + '.tagged.csv', outHeader, itemWords, itemPOS, itemLemmas, itemTagged)
    sys.stderr.write("\nOutput file: " + args.out_file + '.tagged.csv\n')
    sys.stderr.write("  you can delete the temporary file: " + args.out_file + '.csv\n')
    sys.stderr.write("  you can delete the temporary files: tag*.tmp")
  else:
    sys.stderr.write("output was written to: " + args.out_file + '.csv\n')
      
#-------------------------------------------------------
# functions
#-------------------------------------------------------
def parseAge(age):
  # parse the age string, correct errors, return age in days
  year = months = days = 0
  m = re.search(r'(\d+);', age)
  if m:
    year = m.group(1)
  m = re.search(r'\d+;(\d+)', age)
  if m:
    months = m.group(1)
  m = re.search(r'\d+;\d+\.(\d+)', age)
  if m:
    days = m.group(1)
  #age = year + ';' + months + '.' + days
  age_days = int(int(year) * 365 + int(months) * 30.4 + int(days))
  return(age, age_days)

def addTagging(inputFile, outputFile, outHeader, itemWords, itemPOS, itemLemmas, itemTagged):
  # read the csv output file and add information from TreeTagger output
  with open(inputFile, 'r') as csvfile:    # csv file with empty pos, lemma
    with open(outputFile, 'w') as csvout:  # csv with filled columns
      writer = csv.writer(csvout, delimiter = "\t")
      reader = csv.reader(csvfile, delimiter = "\t")
      data = list(reader)
      # Iterate through each row and modify a specific cell in each row
      for l, row in enumerate(data):
        reMatch = re.compile('(.*)_w(\d+)') # get utterance ID (=key) and word number...
        if re.search(reMatch, data[l][0]):  # ... from the first col of the row
          m = re.search(reMatch, data[l][0])
          uID = m.group(1)
          wID = m.group(2)
          lemma = itemLemmas[uID].split(' ')
          pos = itemPOS[uID].split(' ')
          annotation = []
          # get column indexes from header
          lemmaIndex = outHeader.index("lemma") if "lemma" in outHeader else None
          posIndex = outHeader.index("pos") if "pos" in outHeader else None
          featIndex = outHeader.index("features") if "features" in outHeader else None
          uttIndex = outHeader.index("utterance") if "utterance" in outHeader else None
          noteIndex = outHeader.index("note") if "note" in outHeader else None
          # insert new lemma (col 9), pos (10), note (11)
          try:
            data[l][lemmaIndex] = lemma[int(wID)-1]
          except IndexError:
            print('   INDEX ERROR inserting lemma: %s\n' % data[l])
          try:
            data[l][posIndex] = pos[int(wID)-1]
          except IndexError:
            print('   INDEX ERROR inserting pos: %s\n' % data[l])

          # ----------------------------------------
          # output options
          # ----------------------------------------
          # -m : parse tagged output
          if args.match_tagging != '':
            tagged = itemTagged[uID]
            try:
              if re.search(re.compile(args.match_tagging), pos[int(wID)-1]): # if tagger pos matches argument
                annotation = analyseTagging(tagged, lemma[int(wID)-1])
                data[l][noteIndex] = ','.join(annotation)
            except IndexError:
              print('   INDEX ERROR annotation index 12 of: %s\n' % data[l])
          # add a column with the tagger analysis 
          if args.tagger_output:
            index = outHeader.index("utt_tagged")
            data[l][index] = tagged  # add the annotation values
          # output option depending on tagger output
          if args.pos_utterance:
            uttIndex = outHeader.index("utterance") if "utterance" in outHeader else None
            reMatch = re.compile(args.pos_utterance)
            if posIndex <= len(data[l]) and not re.search(reMatch, data[l][posIndex]):
              data[l][uttIndex] = ''  # add the annotation values

          # output table row
          writer.writerow(row)
        else:
          # output header row
          writer.writerow(row)

def analyseTagging(tagged, lemma):
  # parse tagger output
  matchedLemma = ''
  annotation = []
  # example for verbal token regex word_tag=lemma: ( .*?_VER.*?=\w+)?
  reRefl = re.compile(' [^_]+_.*?=se [^_]+_VER.*?=(?P<lemma>\w+)')    # try lemma
# ( reRefl = re.compile(' [^_]+_.*?=se( [^_]+_AUX.*?=\w+)? [^_]+_VER.*?=(?P<lemma>\w+)')
#  reRefl = re.compile(' [^_]+_.*?=se( [^_]+_VER.*?=\w+) [^_]+_VER.*?=(?P<lemma>\w+)')
#  reRefl = re.compile(' se_[^ ]+( .*?_VER.*?=\w+) [^_]+_VER.*?=(?P<lemma>\w+)')
  if re.search(reRefl, tagged):
    m = re.search(reRefl, tagged)
    if m.group(1) is not None:
      matchedLemma = m.group('lemma')
    if(lemma == matchedLemma):  # annotate only rows where lemma is identical
      annotation.append('refl') # ('refl:'+matchedLemma)
  # 'dative' complements with à, au, lui
  #reDat = re.compile('[^_]+_VER.*?=(?P<lemma>\w+) [^_]+_.*?=à ')
  reDat = re.compile('[^_]+_VER.*?=(?P<lemma>\w+) (à|au|aux)_[^ ]+')
  if re.search(reDat, tagged):
    m = re.search(reDat, tagged)
    if m.group(1) is not None:
      matchedLemma = m.group('lemma')
    if(lemma == matchedLemma):  # annotate only rows where lemma is identical
      annotation.append('dat') # ('dat:'+matchedLemma)
  reDatCl = re.compile('(lui|leur)_[^ ]+ [^_]+_VER.*?=(?P<lemma>\w+)')
  if re.search(reDatCl, tagged):
    m = re.search(reDatCl, tagged)
    if m.group(1) is not None:
      matchedLemma = m.group('lemma')
    if(lemma == matchedLemma):  # annotate only rows where lemma is identical
      annotation.append('datclit') # ('dat:'+matchedLemma)
  return(annotation)

def insertAtIndex(add, list, index):
  # insert 'add' in list at index
  #if len(list) < index+1:
  if index < len(list):
    list[index] = add
  else:
    sys.stderr.write('INDEX ERROR FOR LIST of len=' + str(len(list)) + ' index='+ str(index) + ' >>' + str(list) + '\n')
  return(list)

def wordPerLineTagger(splitUtt, mor):
  # for TreeTagger annotation: build one line (table row) for each token in utterance
  age = tags = ''
  age_days = wNr = 0
  thisRow = {}
  words = tokenizer.tokenise(splitUtt).split(' ')
  for w in words:
    if w == '':
      continue
    wNr += 1
    t = l = f = ''  # will be filled by TreeTagger output
    w = re.sub(r'@.*', '', w)
    # control if utterance is printed
    splitUttPrint = ''
    if args.tagger_input:
      splitUttPrint = splitUtt
    uttPrint = utt
    if args.first_utterance and wNr > 1:
      uttPrint = splitUttPrint = ''
    # read bio data for this speaker
    if childData.get(speaker) != None:
      age = childData[speaker][1]
      age_days = childData[speaker][2]
    # build output line for word
    thisRow = {
      'utt_id': uttID + '_w' + str(wNr),
      'utt_nr': sNr,
      'w_nr': wNr,
      'speaker': speaker,
      'child_project' : child,
      'age': age,
      'age_days': age_days,
      'time_code': timeCode,
      'word': w,
      'pos': t,
      'lemma': l,
      'features': f,
      'note': '',
      'utterance': uttPrint,
      'utt_clean': splitUttPrint
      }
    outRows.append(thisRow)   # append dictionary for this row to list of rows
  return(outRows)

def wordPerLineChat(splitUtt, mor):
  # for CHAT format: build one line (table row) for each token in utterance
  age = tags = ''
  age_days = wNr = 0
  thisRow = {}
  words = splitUtt.split(' ')
  if mor != '':
    tags = mor.split(' ')
  if len(words) == len(tags):
    equal = 'YES'
  else:
    equal = 'NO '
  wNr = 0
  thisRow = {}
  for w in words:
    wNr += 1
    t = l = f = ''  # tag (CHILDES)
    w = re.sub(r'@.*', '', w)
    if len(tags) >= wNr:
      # parse morphological annotation (%mor line)
      if mor != '':
        t = tags[wNr-1]
        if re.search(r'(.*)\|(.*)', t):
          m = re.search(r'(.*)\|(.*)', t)  # split tag and lemma
          t = m.group(1)
          l = m.group(2)
          if re.search(r'(.*?)[-&](.*)', l):
            m = re.search(r'(.*?)[-&](.*)', l)  # split lemma and morphology (lemma-INF, lemma$PRES...)
            l = m.group(1)
            f = m.group(2)
    # read bio data for this speaker
    if childData.get(speaker) != None:
      age = childData[speaker][1]
      age_days = childData[speaker][2]
    # build output line for word
    thisRow = {
      'utt_id': uttID + '_w' + str(wNr),
      'utt_nr': sNr,
      'w_nr': wNr,
      'speaker': speaker,
      'child_project' : child,
      'age': age,
      'age_days': age_days,
      'time_code': timeCode,
      'word': w,
      'pos': t,
      'lemma': l,
      'features': f,
      'note': equal,
      'utterance': utt
      }
    outRows.append(thisRow)   # append dictionary for this row to list of rows
#    return(w,t,l,f)
  return(outRows)

def treeTagger(str):
    # input:  concatenated target items
    # output: tagged items stored in dictionaries with item IDs as key
    itemTagged = {}  # this dict stores tagged items in the format  Word_POS_Lemma ...
    itemLemmas = {}  # this dict stores POS tags only
    itemPOS = {}  # this dict stores POS tags only
    itemWords = {}  # this dict stores words only
    taggerBin = os.path.expanduser('./tree-tagger')     # TreeTagger binary
    #paramFile = os.path.expanduser('./perceo-spoken-french-utf.par')    # TreeTagger parameters
    paramFile = os.path.expanduser(args.parameters)    # TreeTagger parameters
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
    str = re.sub(r' +', r'\n', str)      # 1 word per line
    with open('tagged.tmp', 'w') as tmp:
      tmp.write(str)  # write header
    # system call for TreeTagger: cat <tmp file>|tree-tagger parameters options
    #    next line takes pipe output as input
    #    check_output() returns output as a byte string that needs to be decoded using decode()
    p1 = subprocess.Popen(["cat", 'tagged.tmp'], stdout=subprocess.PIPE)
    tagged = subprocess.check_output([taggerBin, paramFile, '-token', '-lemma', '-sgml'], stdin=p1.stdout)
    tagged = tagged.decode('utf8')
    tagged = re.sub(r'\t([A-Za-z:]+)\t', r'_\1=', tagged)         # annotation format: word_pos=lemma ...
    tagged = re.sub(r'\n', ' ', tagged)                          # put everything on one line
    # Tagger corrections (TODO improve)
    tagged = re.sub(r'([,\?])_NAM=<unknown>', r'\1_PON=,', tagged)
    for sentence in tagged.split("<s_"): #taggedItems:    # split the concatenated items
        if sentence == "":   # first element is empty: ignore
            continue
        reItem = re.compile('^([^>]+)> (.*)') # e.g.: <s_paris-julie.cha_u18342>
        if re.search(reItem, sentence):  # get the item number from the rest of code, e.g. (<s_)A23
            m = re.search(reItem, sentence)
            sentence = re.sub(r'^([^>]+)> ', ' ', sentence)  # leave a initial space for word matching
        else:
            print("Error: no item number found in item:", sentence)
            quit()
        # generate output fields from each item
        key = m.group(1)
        itemTagged[key] = m.group(2)     #   dict   itemNr : sentence {A1:Il vaso si rompe}
        posLemmas = re.findall(r'=(.*?)[ $]', sentence)   # gets the list of lemmas...
        posTags   = re.findall(r'_(.*?)=', sentence)   # gets the list of tags...
        posWords  = re.findall(r' (.*?)_', sentence)   # gets the list of words...
        itemLemmas[key] = ' '.join(posLemmas)     #  ... and stores it in dictionary, 
        itemPOS[key] = ' '.join(posTags)     #  ... and stores it in dictionary
        itemWords[key] = ' '.join(posWords)     #  ... and stores it in dictionary
    return(itemWords, itemPOS, itemLemmas, itemTagged)


###########################################################################
# main function
###########################################################################

if __name__ == "__main__":
   parser = argparse.ArgumentParser(
       description='''
Converts childes CHAT format data into one word per line table.
- Aligns words with matching information from annotation in %mor.
- Discards other annotation lines (%sit etc).
''', formatter_class = argparse.RawTextHelpFormatter   # allows triple quoting for multiple-line text
       )
   parser.add_argument('out_file', type=str,  help='output file')
   parser.add_argument(
        '-F', '--first_utterance', action='store_true',
        help='print utterance only for first token')
   parser.add_argument(
       '-m', '--match_tagging', default = "", type = str,
       help='match the tagger output against this regex')
   parser.add_argument(
       '-p', '--parameters', default = "", type = str,
       help='run TreeTagger with this parameter file')
   parser.add_argument(
       '--pos_utterance', default = "", type = str,
       help='print utterance only if pos matches this regex')
   parser.add_argument(
       '--tagger_input', action='store_true',
       help='print utterance as converted for tagger')
   parser.add_argument(
       '--tagger_output', action='store_true',
       help='print utterance as converted for tagger')
   # ADDED TR
   parser.add_argument('--tokenizer', choices=TOKENIZERS, default='ASTokenizer',
        help='Select tokenizer:\n   - ASTokenizer: Original tokenizer by AS (default)' + \
        '\n    - FrenchTokenizer: Tokenizer for French'
   )
   # END
   args = parser.parse_args()
   main(args)
