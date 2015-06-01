import xml.etree.cElementTree as ET
from collections import defaultdict
import re
import pprint
import csv
import json

# munge osm file to json with edits for address
# json structure for primitives:

# { "primitive": ('node' | 'relation' | 'way'),
#   "attrib": dictionary of key value pairs of primitive attributes
#   "tag": dictionary of tag key value pairs (per audit key values within a primitive are unique in this dataset)
#   "nd": list of nd ref values
#   "member": list of dictionary of member key value pairs

OSMFILE = "brevardcty.osm"
JSONFILE = "brevardcty.json"
# street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

# street re pattern used to create a list of street name elements
#  ^(direction prefix)?(street name)(street type)(direction suffix)?


street_type_re = re.compile(
    r'^(N\s+|S\s+|E\s+|W\s+|NE\s+|SE\s+|SW\s+|NW\s+|North\s+|South\s+|East\s+|West\s+|Northeast\s+|Southeast\s+|Southwest\s+|Northwest\s+)?' +
    r'(\S+|\S+\s+\S+|\S+\s+\S+\s+\S+)' +
    r'\s+(\S+)' +
    r'(\s+N|\s+S|\s+E|\s+W|\s+NE|\s+SE|\s+SW|\s+NW|\s+North|\s+South|\s+East|\s+West|\s+Northeast|\s+Southeast|\s+Southwest|\s+Northwest)?$',
    re.IGNORECASE)

expected_type = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road",
                 "Trail", "Parkway", "Commons", "Circle", "Cove", "Creek", "Highway", "Causeway", "Lake",
                 "Loop", "Manor", "Park", "Plaza", "Run", "Terrace", "Way", "Trace"]
expected_dir = ["North", "South", "East", "West", "Northeast", "Southeast", "Southwest", "Northwest"]

# dictionary used to translate parsed type value to long names
# developed iteratively using the audit process to identify abbreviations and typos in the xml source
# that need translation

map_type = {"St": "Street", "St.": "Street", "Ave": "Avenue", "Ave.": "Avenue",
            "Avenuen": "Avenue", "Aveue": "Avenue", "Av": "Avenue", "Rd.": "Road",
            "Rd": "Road", "Blvd": "Boulevard", "Causway": "Causeway", "Cir": "Circle",
            "Cswy": "Causeway", "Ct": "Court", "Dr": "Drive", "Ln": "Lane",
            "Pky": "Parkway", "Pl": "Place", "Ter": "Terrace", "Terr": "Terrace",
            "Tr": "Trail", "Trl": "Trail", "Trls": "Trails", "ave": "Avenue",
            "court": "Court", "ln": "Lane", "Cv": "Cove", "Brg": "Bridge",
            "Aly": "Alley", "Plz": "Plaza", "Hwy": "Highway", "Trce": "Trace",
            "Sq": "Square", "Hts": "Heights", "BLVD": "Boulevard", "Raod": "Road", "Kn": "Lane"
            }
map_dir = {
    "N": "North", "S": "South", "E": "East", "W": "West",
    "NE": "Northeast", "SE": "Southeast", "SW": "Southwest", "NW": "Northwest"
}

# translation maps for state and postcode developed through audit

map_state = {
    "Florida": "FL",
    "Fl": "FL"
}

map_postcode = {
    "FL 32904": "32904"
}


def clean_street(street_addr):
    m = street_type_re.search(street_addr)
    address = street_addr

    if m:
        dir_prefix, street_name, street_type, dir_suffix = m.groups()
        if dir_prefix is not None:
            dir_prefix = dir_prefix.strip()
        else:
            dir_prefix = ""
        if dir_suffix is not None:
            dir_suffix = dir_suffix.strip()
        else:
            dir_suffix = ""
        if street_type is None:
            street_type = ""
        address = " ".join(
            [map_dir.get(dir_prefix, dir_prefix), street_name, map_type.get(street_type, street_type),
             map_dir.get(dir_suffix, dir_suffix)]).strip()

    return address


def clean_state(state):
    return map_state.get(state, state)


def clean_postcode(postcode):
    return map_postcode.get(postcode, postcode)


def is_tag(elem, key):
    return elem.attrib['k'] == key


def get_keyval(elem, key):
    return [t.attrib['v'] for t in elem.iter("tag") if t.attrib['k'] == key]


# apply edits to osm file and translate to json format

def clean(osmfile, jsonfile):
    osm_file = open(osmfile, "r", encoding="UTF-8")
    with open(jsonfile, 'w', newline='', encoding="UTF-8") as json_file:
        for _, elem in ET.iterparse(osm_file, events=("start",)):
            if elem.tag in ['node', 'way', 'relation']:
                primitive = {"primitive": elem.tag}

                # store all the primitives attributes in a dictionary
                # translate lat, lon attributes to GeoJSON structure
                attrib = {}
                for ak, av in elem.attrib.items():
                    if ak in ['lat', 'lon']:
                        pos = attrib.get("pos", {"type": "Point", "coordinates": [0, 0]})
                        pos["coordinates"][0 if ak == 'lon' else 1] = float(av)
                        attrib['pos'] = pos
                    else:
                        attrib[ak] = av
                primitive["attrib"] = attrib

                # store all tags for a primitive in a dictionary
                # audit of tag keys confirmed there are no instances of the same key appearing more than once
                #     otherwise, logic would need to support one to many mapping
                tagdict = {}
                for tag in elem.iter("tag"):
                    # parse addr tag into dictionary of address parts
                    if tag.attrib['k'].startswith("addr:"):
                        addr = tagdict.get("addr", {})
                        part = tag.attrib['k'].split(":")[1]
                        if part == "state":
                            addr["state"] = clean_state(tag.attrib['v'])
                        elif part == "postcode":
                            addr["postcode"] = clean_postcode(tag.attrib['v'])
                        elif part == "street":
                            addr["street"] = clean_street(tag.attrib['v'])
                        else:
                            addr[part] = tag.attrib['v']
                        tagdict["addr"] = addr
                    elif elem.tag == "way" and tag.attrib['k'] in ['name', 'old_name', 'alt_name', 'name_1', 'name_2',
                                                                   'name_3']:
                        tagdict[tag.attrib['k']] = clean_street(tag.attrib['v'])
                    else:
                        tagdict[tag.attrib['k']] = tag.attrib['v']
                if len(tagdict) > 0:
                    primitive['tag'] = tagdict

                # for the nd tag, create list of node reference values
                if elem.tag == 'way':
                    nd = []
                    for tag in elem.iter("nd"):
                        nd.append(tag.get('ref'))
                    if len(nd) > 0:
                        primitive["nd"] = nd
                # for the member tags, create list of dictionaries with key value pairs
                if elem.tag == 'relation':
                    member = []
                    for tag in elem.iter("member"):
                        member.append(tag.attrib)
                    if len(member) > 0:
                        primitive["member"] = member
                json.dump(primitive, json_file)
                json_file.write("\n")


if __name__ == '__main__':
    clean(OSMFILE, JSONFILE)
