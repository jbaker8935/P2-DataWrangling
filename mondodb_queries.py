from pymongo import MongoClient
import pprint

aggregate_query_list = [
    ("Number of primitives",
     [{"$group": {"_id": "$primitive",
                  "total": {"$sum": 1}
                  }
       }
      ]),
    ("Number of unique users",
     [{"$group": {"_id": None,
                  "userset": {"$addToSet": "$attrib.user"}}},
      {"$unwind": "$userset"},
      {"$group": {"_id": None,
                  "count": {"$sum": 1}
                  }
       }
      ]),
     ("Users with most updates",
     [{"$group": {"_id": "$attrib.user",
                  "count": {"$sum": 1}}},
      {"$sort": {"count": -1}},
      {"$limit": 5}
      ]),
    ("Number of amenities",
     [{"$match": {"tag.amenity": {"$exists": 1}}},
         {"$group": {"_id": "$tag.amenity",
                  "total": {"$sum": 1}
                  }
       },
      {"$sort": {"total": -1}},
      {"$limit": 3}
      ]),
    ("How many ways allow horses",
     [{"$match": {"tag.horse": "yes", "primitive": "way"}},
      {"$group": {"_id": None,
      "total": {"$sum": 1}}}])
]

find_query_list = [
    ("Get Pos for Da Kine Diego's",
     ({"tag.name": "Da Kine Diego's Insane Burrito"},
      {"_id": 0, "attrib.pos.coordinates": 1})
     ),

    ("List Near Bus Stop for Da Kine Diego's",
     ({"tag.highway": "bus_stop",
       "attrib.pos": {"$near": {"$geometry": {"type": "Point", "coordinates": [-80.5902917, 28.17372]},
                                "$minDistance": 0,
                                "$maxDistance": 500}}}, {"_id": 0, "tag.name": 1})
     )
]


def get_db(db_name):
    client = MongoClient('localhost:27017')
    db = client[db_name]
    return db


if __name__ == '__main__':
    db = get_db('local')

    for (desc, query) in aggregate_query_list:
        print("Query: %s" % desc)
        pprint.pprint(query)
        result = db.brevardcty.aggregate(query)
        print("Result:")
        for doc in result['result']:
            pprint.pprint(doc)

    for (desc, (query, projection)) in find_query_list:
        print("Query: %s" % desc)
        pprint.pprint(query)
        result = db.brevardcty.find(query, projection)
        print("Result:")
        for doc in result:
            pprint.pprint(doc)
