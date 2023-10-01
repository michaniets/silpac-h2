#!/usr/bin/python3

__author__ = "Achim Stein"
__version__ = "1.0"
__email__ = "achim.stein@ling.uni-stuttgart.de"
__status__ = "1.10.23"
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

def main(args):
  sNr = 0
  outRows = []   # define list of rows (each row is a dictionary)
  age_days = 0
  with open(args.out_file, 'r', encoding="utf8") as file:  # , newline=''
    all = file.read()
    sys.stderr.write("Reading " + args.out_file +'\n')
    sentences = all.split('\n*')
  if len(sentences) <= 1:
    sys.stderr.write("No output sentences found. " + str(len(sentences)) + " Exiting.\n")
    sys.exit(0)
  else:
    sys.stderr.write("Processing " + str(len(sentences)) + ' utterances\n')
  for s in sentences:

    # process file header with biographic data
    # example: @ID: fra|Paris|CHI|0;11.18|female|||Target_Child|||
    reMatch = re.compile('@ID:.*\|CHI\|(\d+);(\d+)\.(\d+)\|.*Target_Child')
    if re.search(reMatch, s):
      m = re.search(reMatch, s)
      year = m.group(1)
      months = m.group(2)
      days = m.group(3)
      age = year + ';' + months + '.' + days
      age_days = int(int(year) * 365 + int(months) * 30.4 + int(days))
      continue

    # process utterances
    if age_days == 0:
      sys.stderr.write('Exiting because age could not be determined.\nCheck if file header contains this information and is parsed correctly!\n')
      sys.exit(1)
    timeCode = ''
    utt = ''
    mor = ''
    speaker = ''
    tags = []
    sNr += 1
    if sNr % 100 == 0:  # display progress
        percent = int(sNr / len(sentences) * 100)
        sys.stderr.write(" processed: " + str(percent) + '%' + '\r')
    # general substitution
    s = re.sub(r'‹', '<', s)
    s = re.sub(r'›', '>', s)
    s = re.sub(r'\n\s+', ' ', s, re.DOTALL)  # append multi-line to first line
    # get utterance code
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
      sys.stdout.write('\n' + str(sNr) + ' ==== ' + timeCode + '\nSPE=' + speaker + '\nUTT=' + utt + '\nMOR=' + mor)
    # split into words
    splitUtt = re.sub(r'\+< ', '', utt)  # use a clean copy of utt
    splitUtt = re.sub(r'(0|www|xxx|yyy)\s', '', splitUtt)  # xxx = incomprehensible – yyy = separate phonetic coding
    splitUtt = re.sub(r'\[.*?\] ?', '', splitUtt)  # no words
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
      t = ''  # tag (CHILDES)
      l = ''  # lemma
      f = ''  # features
      w = re.sub(r'@.*', '', w)
      sys.stdout.write('\n\t' + equal + ' ' + w)
      if len(tags) >= wNr:
        if mor == '':
          sys.stdout.write('\tNA')
        # parse morphological annotation (%mor line)
        else:
          t = tags[wNr-1]
          sys.stdout.write('\t' + t)
          if re.search(r'(.*)\|(.*)', t):
            m = re.search(r'(.*)\|(.*)', t)  # split tag and lemma
            t = m.group(1)
            l = m.group(2)
            if re.search(r'(.*?)[-&](.*)', l):
              m = re.search(r'(.*?)[-&](.*)', l)  # split lemma and morphology (lemma-INF, lemma$PRES...)
              l = m.group(1)
              f = m.group(2)
      
      thisRow = {
        'utt_id': args.out_file + '_' + str(sNr),
        'utt_nr': sNr,
        'w_nr': wNr,
        'speaker': speaker,
        'age': age,
        'age_days': age_days,
        'time_code': timeCode,
        'word': w,
        'pos': t,
        'lemma': l,
        'features': f,
        'words=tags': equal,
        'utterance': utt
        }
      outRows.append(thisRow)   # append dictionary for this row to list of rows

  # ----------------------------------------
  # output
  # ----------------------------------------
  # write output rows
  # write output table: DictWriter matches header and rows, regardless of the order of fields in row
  outHeader = ['utt_id', 'utt_nr', 'w_nr', 'speaker', 'age', 'age_days', 'time_code', 'word', 'lemma', 'pos', 'features', 'words=tags', 'utterance']
  with open(args.out_file + '.csv', 'w', newline='') as out:   # newline '' is needed: we have commas in items
    writer = csv.DictWriter(out, delimiter='\t', fieldnames=outHeader)
    writer.writeheader()
    writer.writerows(outRows)

#-------------------------------------------------------
# functions
#-------------------------------------------------------

# replace @ in amalgamated forms, e.g. el (< en+le) coded as e@ @l
def parseHeader(s):
    sys.stdout.write("---------- HEADER -------------")
#    s = re.sub(r'@([@\)])', r'+\1', s)   # e@ before ')' or added annotation ('@')
#    s = re.sub(r'(\n| )@', r'\1+', s)   # @l at beginning of word
    return(s)

###########################################################################
# main function
###########################################################################

if __name__ == "__main__":
   parser = argparse.ArgumentParser(
       description='''
Converts childes CHAT format data into one word per line table.
- Aligns words with matching information from annotation in %mor.
- Discards other annotation types (%sit etc).
''', formatter_class = argparse.RawTextHelpFormatter   # allows triple quoting for multiple-line text
       )
   parser.add_argument('out_file', type=str,  help='output file')
   args = parser.parse_args()
   main(args)
