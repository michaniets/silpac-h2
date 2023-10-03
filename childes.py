#!/usr/bin/python3

__author__ = "Achim Stein"
__version__ = "1.0"
__email__ = "achim.stein@ling.uni-stuttgart.de"
__status__ = "2.10.23"
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

# global vars
age = child = speaker = utt = uttID = timeCode = ''
sNr = age_days = 0
outRows = []

def main(args):
  global age, child, speaker, utt, uttID, sNr, timeCode    # needed to modify global vars locally
  taggerInput = ''
  with open(args.out_file, 'r', encoding="utf8") as file:  # , newline=''
    all = file.read()
    sys.stderr.write("Reading " + args.out_file +'\n')
    sentences = all.split('\n*')
  if len(sentences) <= 1:
    sys.stderr.write("No output sentences found. " + str(len(sentences)) + " Exiting.\n")
    sys.exit(0)
  else:
    sys.stderr.write("Processing " + str(len(sentences)) + ' utterances\n')

  for s in sentences:  # sentence = utterance
    # -------------------------------------------------------
    # file header with biographic data
    # -------------------------------------------------------
    # example: @ID: fra|Paris|CHI|0;11.18|female|||Target_Child|||
    reMatch = re.compile('@ID:.*\|CHI\|(\d+);(\d+)\.(\d+)\|.*Target_Child')
    if re.search(reMatch, s):
      m = re.search(reMatch, s)
      year = m.group(1)
      months = m.group(2)
      days = m.group(3)
      age = year + ';' + months + '.' + days
      age_days = int(int(year) * 365 + int(months) * 30.4 + int(days))
      # get the child's name, e.g. @Participants:	CHI Tim Target_Child, MOT Mother Mother...
      reMatch = re.compile('@Participants:.*CHI\s(.*?)\sTarget_Child')
      if re.search(reMatch, s):
        m = re.search(reMatch, s)
        child = m.group(1)
        sys.stderr.write("CHILD found in header: " + child + '\n')
      sys.stderr.write("AGE found in header: " + age + ' = ' + str(age_days) + 'days\n')
      continue  # no output for the header

    # -------------------------------------------------------
    # utterances
    # -------------------------------------------------------
    if age_days == 0:
      sys.stderr.write('Exiting because age could not be determined.\nCheck if file header contains this information and is parsed correctly!\n')
      sys.exit(1)
    timeCode = ''
    utt = ''
    mor = ''
    speaker = ''
    tags = []
    sNr += 1
    uttID = args.out_file + '_u' + str(sNr)
    # general substitution
    s = re.sub(r'‹', '<', s)
    s = re.sub(r'›', '>', s)
    s = re.sub(r'\n\s+', ' ', s, re.DOTALL)  # append multi-line to first line
    # get utterance code (delimited by ^U)
    if re.search(r'(.*?)', s):
      m = re.search(r'(.*?)', s)
      timeCode = m.group(1)
    s = re.sub(r' ?.*?', '', s)
    # match the annotation line starting with %mor
    reMatch = re.compile('%mor:\s+(.*)')
    if re.search(reMatch, s):
      m = re.search(reMatch, s)
      mor = m.group(1)
    # match speaker and utterance
    reMatch = re.compile('^([A-Z]+):\s+(.*?)\n')
    if re.search(reMatch, s):
      m = re.search(reMatch, s)
      speaker = m.group(1)
      utt = m.group(2)
      #sys.stdout.write('\n' + str(sNr) + ' ==== ' + timeCode + '\nSPE=' + speaker + '\nUTT=' + utt + '\nMOR=' + mor)
    splitUtt = cleanUtt(utt)  # clean copy for splitting in to words
    # concatenate utterances to build taggerInput
#    taggerInput = taggerInput + " <s_" + str(sNr) + "> " + tokenise(splitUtt)  # prepend tag with sNr
    taggerInput = taggerInput + " <s_" + uttID + "> " + tokenise(splitUtt)  # prepend tag with sNr

    # -------------------------------------------------------
    # split utterance into tokens
    # -------------------------------------------------------
    # list of table rows 
    if speaker != '': #len(splitUtt.split(' ')) > 1:
      if args.parameters == '':
        outRows = wordPerLineChat(splitUtt, mor)
      else:
        outRows = wordPerLineTagger(splitUtt, mor)

  # ----------------------------------------
  # TreeTagger (option -p)
  # ----------------------------------------
  if args.parameters != '':
    sys.stderr.write('Running TreeTagger on taggerInput\n')
#    sys.stderr.write('Running TreeTagger on taggerInput:\n' + taggerInput + '\n')
    (itemWords, itemPOS, itemLemmas, itemTagged) = treeTagger(taggerInput)
#    sys.stderr.write('>>>>>>>>< TreeTagger output:\n' + str(itemTagged) + '\n')

  # ----------------------------------------
  # output
  # ----------------------------------------
  # write output table: DictWriter matches header and rows, regardless of the order of fields in row
  outHeader = ['utt_id', 'utt_nr', 'w_nr', 'speaker', 'child', 'age', 'age_days', 'time_code', 'word', 'lemma', 'pos', 'features', 'note', 'utterance']
  with open(args.out_file + '.csv', 'w', newline='') as out:   # newline '' is needed: we have commas in items
    writer = csv.DictWriter(out, delimiter='\t', fieldnames=outHeader)
    writer.writeheader()
    writer.writerows(outRows)

  sys.stderr.write("output was written to: " + args.out_file + '.csv\n')
  # add tagger output
  if args.parameters != '':
    sys.stderr.write('Adding tagger output for each utterance...\n')
    addTagging(args.out_file + '.csv', args.out_file + '.tagged.csv', outHeader, itemWords, itemPOS, itemLemmas)
#-------------------------------------------------------
# functions
#-------------------------------------------------------
def addTagging(inputFile, outputFile, outHeader, itemWords, itemPOS, itemLemmas):
  # read the csv output file and add information from TreeTagger
  with open(inputFile, 'r') as csvfile:
    with open(outputFile, 'w') as csvout:
      csvout.write('\t'.join(outHeader)+'\n')  # write header
      reader = csv.reader(csvfile)
      lemmaIndex = outHeader.index("lemma") if "lemma" in outHeader else None
      posIndex = outHeader.index("pos") if "pos" in outHeader else None
      featIndex = outHeader.index("features") if "features" in outHeader else None
      next(reader, None) # skip header
      for row in reader:
        col = row[0].split('\t')
        reMatch = re.compile('(.*)_w(\d+)') # get utterance ID (= key) and word number
        if re.search(reMatch, col[0]):
          m = re.search(reMatch, col[0])
          uID = m.group(1)
          wID = m.group(2)
          lemma = itemLemmas[uID].split(' ')
          pos = itemPOS[uID].split(' ')
          # update column values
          col = insertAtIndex(lemma[int(wID)-1], col, lemmaIndex)  # update column
          col = insertAtIndex(pos[int(wID)-1], col, posIndex)  # update column
          csvout.write('\t'.join(col)+'\n')
        else:
          print('NO UTTERANCE ID FOUND IN '+col[0])

def insertAtIndex(add, list, index):
  # insert 'add' in list at index
  if len(list) < index+1:
    sys.stderr.write('INDEX ERROR FOR LIST of len=' + str(len(list)) + '>>' + str(list) + '\n')
  else:
    list[index] = add
  return(list)

def wordPerLineTagger(splitUtt, mor):
  # for TreeTagger annotation: build one line (table row) for each token in utterance
  tags = ''
  words = tokenise(splitUtt).split(' ')
  wNr = 0
  thisRow = {}
  for w in words:
    wNr += 1
    t = l = f = ''  # will be filled by TreeTagger output
    w = re.sub(r'@.*', '', w)
    # build output line for word
    thisRow = {
      'utt_id': uttID + '_w' + str(wNr),
      'utt_nr': sNr,
      'w_nr': wNr,
      'speaker': speaker,
      'child' : child,
      'age': age,
      'age_days': age_days,
      'time_code': timeCode,
      'word': w,
      'pos': t,
      'lemma': l,
      'features': f,
      'note': '',
      'utterance': utt
      }
    outRows.append(thisRow)   # append dictionary for this row to list of rows
  return(outRows)

def wordPerLineChat(splitUtt, mor):
  # for CHAT format: build one line (table row) for each token in utterance
  tags = ''
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
    # build output line for word
    thisRow = {
      'utt_id': uttID + '_w' + str(wNr),
      'utt_nr': sNr,
      'w_nr': wNr,
      'speaker': speaker,
      'child' : child,
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

def cleanUtt(s):
    # delete specific CHILDES annotation not needed for pos tagging (WIP - TODO check CHILDES documentation)
    # input:  unprocessed utterance
    # output: utterance cleaned of special annotation
    s = re.sub(r'<[^>]+> \[//?\] ', '', s) # repetitions (not in %mor), e.g. mais <je t'avais dit que> [/] je t'avais dit que ...
    s = re.sub(r'<(0|www|xxx|yyy)[^>]+> ?', '', s) # repetitions (not in %mor), e.g. mais <je t'avais dit que> [/] je t'avais dit que ...
    s = re.sub(r'\+< ', '', s)  # use a clean copy of utt
    s = re.sub(r'(0|www|xxx|yyy)\s', '', s)  # xxx = incomprehensible – yyy = separate phonetic coding
    s = re.sub(r'\[.*?\] ?', '', s)  # no words
    s = re.sub(r'\(([A-Za-z])\)', r'\1', s)  # delete parentheses around chars
    s = re.sub(r' \+/+', ' ', s)  # annotations for pauses (?) e.g. +//.
    s = re.sub(r'\s+', r' ', s)  # reduce spaces
    return(s)

def tokenise(s):
    # tokenise sentence for TreeTagger  (WIP - TODO: add rules from tokenise.pl)
    # input:  unprocessed sentence
    # output: sentence tokenised for TreeTagger
    # 1) define cutoff characters and strings at beginning and end of tokens
    reBeginChar = re.compile('(\[\|\{\(\/\'\´\`"»«°)') 
    reEndChar = re.compile('(\]\|\}\/\'\`\"\),;:\!\?\%»«)') 
    reBeginString = re.compile('([dcjlmnstDCJLNMST]\'|[Qq]u\'|[Jj]usqu\'|[Ll]orsqu\')') 
    reEndString = re.compile('(-t-elles?|-t-ils?|-t-on|-ce|-elles?|-ils?|-je|-la|-les?|-leur|-lui|-mêmes?|-m\'|-moi|-nous|-on|-toi|-tu|-t\'|-vous|-en|-y|-ci|-là)') 
    # 2) cut
    s = re.sub(reBeginChar, r'\1 ', s)
    s = re.sub(reBeginString, r'\1 ', s)
    s = re.sub(reEndChar, r' \1', s)
    s = re.sub(reEndString, r' \1', s)
    s = re.sub(r'\s+', r' ', s)  # reduce spaces
    return(s)

def treeTagger(str):
    # input:  concatenated target items
    # output: tagged items stored in dictionaries with item IDs as key
    itemTagged = {}  # this dict stores tagged items in the format  Word_POS_Lemma ...
    itemLemmas = {}  # this dict stores POS tags only
    itemPOS = {}  # this dict stores POS tags only
    itemWords = {}  # this dict stores words only
    taggerBin = os.path.expanduser('./tree-tagger')     # TreeTagger binary
    paramFile = os.path.expanduser('./perceo-spoken-french-utf.par')    # TreeTagger parameters
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
#    str = re.sub(r'([\'\´\`])', r'\1 ', str)        # quick & dirty tokenization
#    str = re.sub(r'([\"\.\!,;:])', r' \1 ', str)
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
        reItem = re.compile('^([^>]+)> (.*)') # e.g.: <s_paris-julie.cha_18342>
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
       '-p', '--parameters', default = "", type = str,
       help='run TreeTagger with this parameter file')
   args = parser.parse_args()
   main(args)
