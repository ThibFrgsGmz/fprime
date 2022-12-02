#!/usr/bin/env python

# Convert output from Google's cpplint.py to the cppcheck XML format for
# consumption by the Jenkins cppcheck plugin.

# Reads from stdin and writes to stderr (to mimic cppcheck)

# https://stackoverflow.com/questions/14172232/how-to-make-cpplint-work-with-jenkins-warnings-plugin
# https://gist.github.com/esutton/c19606e6962bfe535b1d80d672afb82b

import sys
import re
import xml.sax.saxutils

def cpplint_score_to_cppcheck_severity(score):
    # I'm making this up
    if score in [1, 2]:
        return 'style'
    elif score in [3, 4]:
        return 'warning'
    elif score == 5:
        return 'error'

def parse():
    # TODO: do this properly, using the xml module.
    # Write header
    sys.stderr.write('''<?xml version="1.0" encoding="UTF-8"?>\n''')
    sys.stderr.write('''<results version="2">\n''')
    sys.stderr.write('''<cppcheck version="1.90"/>\n''')
    sys.stderr.write('''<errors>\n''')

    # Do line-by-line conversion
    r = re.compile('([^:]*):([0-9]*):  ([^\[]*)\[([^\]]*)\] \[([0-9]*)\].*')

    for l in sys.stdin.readlines():
        m = r.match(l.strip())
        if not m:
            continue
        g = m.groups()
        if len(g) != 5:
            continue
        fname, lineno, rawmsg, label, score = g
        # Protect Jenkins from bad XML, which makes it barf
        msg = xml.sax.saxutils.escape(rawmsg)
        # A "[google] prefix to make easy to distinguish ccplint warning from cppcheck messages
        label = f"{label}"
        # prepare data to be used as an attribute value
        msg = xml.sax.saxutils.quoteattr(msg)
        severity = cpplint_score_to_cppcheck_severity(int(score))
        if severity in ['warning', 'error']:
            sys.stderr.write(f'''<error id="{label}" severity="{severity}" msg={msg} verbose="">\n''')
            sys.stderr.write(f'''<location file="{fname}" line="{lineno}" column="0"/>\n''')
            sys.stderr.write('''</error>\n''')

    sys.stderr.write('''</errors>\n''')
    sys.stderr.write('''</results>\n''')


if __name__ == '__main__':
    parse()