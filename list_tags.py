#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import pprint
import re
from collections import defaultdict
import csv

"""
Leverage Lesson 6 tags code to do the following:
enumerate all distinct tag keys in osm source file.
1. identify tag keys that follow common naming conventions (lower case, first/last chars alpha)
2. identify tag keys with namespace values that can potentially be structured (have ':')
3. identify tag keys with whitespace that may need correction
4. identify problematic tag keys that may need correction
5. other keys
6. export tag, value combinations for each primitive (node, relation, way)

ref: http://taginfo.openstreetmap.org/reports/characters_in_keys
"""

# keys in 'common' format
plain_keys = re.compile(r'^[a-z]([_a-z]*[a-z])*$')
keys_with_colon = re.compile(r'^[a-z]([_a-z]*[a-z])*(:[a-z]([_a-z]*[a-z])*)+$')
# look for keys with ascii upper and numeric
keys_with_uppercase_or_numeric_chars = re.compile(r'[A-Z0-9]')
# check key for whitespace - just looking for space & tab here - can replace with _
keys_with_whitespace = re.compile(r'[ \t]')
# look for problematic characters (space & tab found above)
keys_with_possibly_problematic_characters = re.compile(r'[=\+/&<>;\'"\?%#$@,\.\r\n]')


def key_type(topelem, tagelem, keys):
    k = tagelem.get('k', "")
    v = tagelem.get('v', "")
    if re.search(keys_with_possibly_problematic_characters, k):
        keys['problematic'][('problematic',topelem.tag, k)].add(v)
    elif re.search(keys_with_whitespace, k):
        keys['whitespace'][('whitespace',topelem.tag, k)].add(v)
    elif re.search(plain_keys, k):
        keys['plain'][('plain',topelem.tag, k)].add(v)
    elif re.search(keys_with_colon, k):
        keys['colon'][('colon',topelem.tag, k)].add(v)
    elif re.search(keys_with_uppercase_or_numeric_chars, k):
        keys['uppernum'][('uppernum',topelem.tag, k)].add(v)
    else:
        keys['rest'][('rest',topelem.tag, k)].add(v)
    return keys


def process_map(filename):
    keys = {"plain": defaultdict(set), "colon": defaultdict(set), "uppernum": defaultdict(set),
            "whitespace": defaultdict(set), "problematic": defaultdict(set), "rest": defaultdict(set)}
    for _, elem in ET.iterparse(filename, events=("start",)):
        if elem.tag in ['node', 'way', 'relation']:
            for t in elem.iter("tag"):
                keys = key_type(elem, t, keys)
    return keys


def test():
    keys = process_map('brevardcty.osm')
    for k, v in keys.items():
        print(k, len(v))
    with open('tagkeyval.csv', 'w', newline='', encoding="UTF-8") as csvfile:
        tagwriter = csv.writer(csvfile, delimiter=';',
                               quotechar='"', quoting=csv.QUOTE_MINIMAL)
        tagwriter.writerow(['category','primitive','tag','value'])
        for k, v in keys.items():
            for s, t in v.items():
                try:
                    for l in list(t):
                        tagwriter.writerow(list(s) + [l])
                except UnicodeEncodeError:
                    print(s, t)


if __name__ == "__main__":
    test()
