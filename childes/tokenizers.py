import re, collections

class Tokenizer():
    """
    Parent class for the tokenization of utterances.
    
    Attributes:
    -----------
    
    Methods:
    --------
    
    cleanUtt(self, s):
        Parses CHILDES-specific annotation and returns a "clean" string.
    
    tokenise(self, s):
        Tokenises s, returning a string with white-space separating the
        tokens.
    """
    
    # Globals determine the behaviour of cleanUtt
    
    DEFAULT = 0
    STANDARD = 1
    
    def __init__(self):
        pass
    
    @classmethod
    def create(cls, tokenizer_type):
        """
        Creates an instance of tokenizer_type and returns it.
        """
        
        TOKENIZER_TYPE_TO_CLASS_MAP = {
          'Tokenizer':  Tokenizer,
          'ASTokenizer': ASTokenizer
        }
        if tokenizer_type not in TOKENIZER_TYPE_TO_CLASS_MAP:
              raise ValueError('Bad tokenizer type {}'.format(tokenizer_type))
        return TOKENIZER_TYPE_TO_CLASS_MAP[tokenizer_type]()
        
    def cleanUtt(self, s, form=DEFAULT):
        """
        Global method to parse CHILDES markup (pre-tokenization), no
        language-specific settings.
        
        Parameters:
            s           :  string to clean
            form (int)  :  constant determining how cleanUtt handles corrections
            
        Returns:
            cleanUtt(self, s, [form=DEFAULT]):
                A string with CHILDES markup removed.
        """
        
        # Step 1. First, deal with structures which may include whitespace
        # CORRECTIONS (of the kind vì [: qui ])
        m = re.match(r'([^\s]+)\s+\[:\s*([^\]]+)\s*\]', s) 
        if m and form == STANDARD:
            # Replace with the correction
            s = s[:m.start()] + ' ' + m.group(2).replace(' ', '-') + ' ' + s[m.end():]
        elif m:
            # Replace with the uttered word
            s = s[:m.start()] + ' ' + m.group(1) + ' ' + s[m.end():]
            
        # TODO: repetitions, other coding of corrections in French CHILDES
            
        # Step 2. Parse whitespace-delimited items
        s = re.sub(r'\s+', ' ', s)  # reduce spaces
        toks = []
        for tok in s.split('\s'):
            if form == STANDARD:
                # Where the most standard form of a token is sought.
                tok = re.sub(r'&[~\-+]', '', tok) # &- initials
                tok = re.sub(r'[()]', '', tok) # Remove all parentheses (corrections).
        
            # General replacements
            tok = re.sub(r'^\(\.+\)', '', tok) # Delete all pauses.
            tok = re.sub(r'@[^\s]+', '', tok) # @ tags: removed in all forms
            tok = re.sub(r'^0.*', '', tok) # Delete all 0s (they weren't realized)
            tok = re.sub(r'^&=.*', '', tok) # Delete all &= (events)
            tok = re.sub(r'^+.*[\.\?\!]$', '.', tok) # Replace all + events ending in a period or question with a period
            tok = re.sub(r'^+.*', '', tok) # Delete all other + events
            tok = re.sub(r'^\[[<>]\]$', '', tok) # Delete all overlap event markers
            tok = re.sub(r'[_=]', '\s', tok) # Replace all underscores and equals signs with spaces
            
            if tok: toks.append(tok)
            
        return ' '.join(toks)
        
    def tokenise(self, s):
        # Default method: does nothing
        return s
        
class ASTokenizer(Tokenizer):
    """
    Tokenizer developed by AS for the French CHILDES corpus
    """
    
    def cleanUtt(self, s):
        # delete specific CHILDES annotation not needed for pos tagging (WIP - TODO check CHILDES documentation)
        # input:  unprocessed utterance
        # output: utterance cleaned of special annotation
        s = re.sub(r'0faire ', 'faire ', s) # faire + Inf is transcribed as '0faire' in York
        s = re.sub(r'<[^>]+> \[//?\] ', '', s) # repetitions (not in %mor), e.g. mais <je t'avais dit que> [/] je t'avais dit que ...
        s = re.sub(r'\[\!\] ?', ' ', s) # repetitions (not in %mor), e.g. mais <je t'avais dit que> [/] je t'avais dit que ...
        s = re.sub(r'<([^>]+)>\s+\[%[^\]]+\]', '\1', s) # corrections: qui <va> [% sdi=vais] la raconter . > va
        s = re.sub(r'<(0|www|xxx|yyy)[^>]+> ?', '', s) # repetitions (not in %mor), e.g. mais <je t'avais dit que> [/] je t'avais dit que ...
        s = re.sub(r'\+[<,]? ?', '', s)  
        s = re.sub(r'(0|www|xxx|yyy)\s', '', s)  # xxx = incomprehensible – yyy = separate phonetic coding
        s = re.sub(r'\[.*?\] ?', '', s)  # no words
        s = re.sub(r'\(([A-Za-z])\)', r'\1', s)  # delete parentheses around chars
        s = re.sub(r' \+/+', ' ', s)  # annotations for pauses (?) e.g. +//.
        s = re.sub(r'[_=]', ' ', s)  # eliminate _ and = 
        s = re.sub(r'\s+', ' ', s)  # reduce spaces
        return(s)
        
    def tokenise(self, s):
        # tokenise sentence for TreeTagger  (WIP - TODO: add rules from tokenise.pl + add Italian rules)
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
        s = re.sub(r'\s+', ' ', s)  # reduce spaces
        return(s)
    
