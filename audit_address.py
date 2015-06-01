import xml.etree.cElementTree as ET
from collections import defaultdict
import re
import pprint
import csv

OSMFILE = "brevardcty.osm"
# street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

# street re pattern  ^(direction prefix)?(street name)(street type)(direction suffix)?
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


def audit_street(audit_dict, street_addr, tiger):
    m = street_type_re.search(street_addr)
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
        corrected_address = " ".join(
            [map_dir.get(dir_prefix, dir_prefix), street_name, map_type.get(street_type, street_type),
             map_dir.get(dir_suffix, dir_suffix)]).strip()
        if dir_prefix and dir_prefix not in expected_dir:
            audit_dict[('prefix', dir_prefix)].add((street_addr, corrected_address))
        if dir_suffix and dir_suffix not in expected_dir:
            # Special case to ignore "Avenue E", "Avenue N", etc.
            if street_name != "Avenue":
                audit_dict[("suffix", dir_suffix)].add((street_addr, corrected_address))
        if street_type not in expected_type:
            audit_dict[('type', street_type)].add((street_addr, corrected_address))
        if tiger:
            val_base, val_type = tiger
            if val_base and street_name != val_base[0]:
                audit_dict[("tiger:base", val_base[0] + "-" + street_name)].add((street_addr, ''))
            if val_type and map_type.get(street_type, street_type) != map_type.get(val_type[0], val_type[0]):
                audit_dict[("tiger:type", val_type[0] + "-" + street_type)].add((street_addr, ''))
    else:
        audit_dict[("nomatch", "nomatch")].add((street_addr, street_addr))
    return audit_dict


def is_tag(elem, key):
    return elem.attrib['k'] == key


def get_keyval(elem, key):
    return [t.attrib['v'] for t in elem.iter("tag") if t.attrib['k'] == key]


def get_tiger_validation(elem):
    return {"name": (get_keyval(elem, "tiger:name_base"),
                     get_keyval(elem, "tiger:name_type")),
            "name_1": (get_keyval(elem, "tiger:name_base_1"),
                       get_keyval(elem, "tiger:name_type_1")),
            "alt_name": (get_keyval(elem, "tiger:name_base_1"),
                         get_keyval(elem, "tiger:name_type_1")),
            "name_2": (),
            "name_3": (),
            "old_name":(get_keyval(elem, "tiger:name_base"),
                     get_keyval(elem, "tiger:name_type"))
            }


def audit(osmfile):
    osm_file = open(osmfile, "r", encoding="UTF-8")
    audit_dict = defaultdict(set)
    for _, elem in ET.iterparse(osm_file, events=("start",)):
        if elem.tag == "node" or elem.tag == "way":

            t=defaultdict(int)
            tiger = get_tiger_validation(elem)
            for tag in elem.iter("tag"):
                t[tag.attrib['k']]+=1
                if is_tag(tag, "addr:street"):
                    # No TIGER cross validation available for addr:street
                    audit_street(audit_dict, tag.attrib['v'], None)
                if elem.tag == "way" and tag.attrib['k'] in ['name', 'old_name', 'alt_name', 'name_1', 'name_2', 'name_3']:
                    audit_street(audit_dict, tag.attrib['v'], tiger[tag.attrib['k']])
            # data check to see if a given node or way can have more than one tag with the same key value
            # if not, tag key values will be structured as a simple dictionary in json
            if any([v > 1 for k,v in t.items()]):
                pprint.pprint(t)
    return audit_dict


def test():
    audit_dict = audit(OSMFILE)
    with open('addrval.csv', 'w', newline='', encoding="UTF-8") as csvfile:
        tagwriter = csv.writer(csvfile, delimiter=';',
                               quotechar='"', quoting=csv.QUOTE_MINIMAL)
        tagwriter.writerow(['audit', 'value', 'address', 'corrected_address'])
        for k, v in audit_dict.items():
            try:
                for l in list(v):
                    tagwriter.writerow(list(k) + list(l))
            except UnicodeEncodeError:
                print(k, v)
                # pprint.pprint(dict(st_audit))


if __name__ == '__main__':
    test()
