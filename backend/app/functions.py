 #!/usr/bin/python3

#################################################################################################################################################
#                                                    CLASSES CONTAINING ALL THE APP FUNCTIONS                                                 #
#################################################################################################################################################

class DB:
    def __init__(self, Config):
        from math import floor
        from os import getcwd
        from os.path import join
        from json import loads, dumps, dump
        from datetime import timedelta, datetime, timezone
        from pymongo import MongoClient, errors, ReturnDocument
        from urllib import parse
        from urllib.request import urlopen
        from bson.objectid import ObjectId

        self.Config                         = Config
        self.getcwd                         = getcwd
        self.join                           = join
        self.floor                          = floor
        self.loads                          = loads
        self.dumps                          = dumps
        self.dump                           = dump
        self.datetime                       = datetime
        self.ObjectId                       = ObjectId

        self.server                         = Config.DB_SERVER
        self.port                           = Config.DB_PORT

        # These may be None/"" for local no-auth MongoDB
        self.username_raw                   = Config.DB_USERNAME
        self.password_raw                   = Config.DB_PASSWORD
        self.username                       = parse.quote_plus(Config.DB_USERNAME) if Config.DB_USERNAME else ""
        self.password                       = parse.quote_plus(Config.DB_PASSWORD) if Config.DB_PASSWORD else ""

        self.remoteMongo                    = MongoClient
        self.ReturnDocument                 = ReturnDocument
        self.PyMongoError                   = errors.PyMongoError
        self.BulkWriteError                 = errors.BulkWriteError
        self.tls                            = False  # MUST SET TO TRUE IN PRODUCTION

    def __del__(self):
        # Delete class instance to free resources
        pass

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _uri(self) -> str:
        """
        Build MongoDB URI.
        If username/password are missing, fall back to no-auth local connection:
            mongodb://127.0.0.1:27017
        Otherwise:
            mongodb://user:pass@host:port
        """
        host = self.server if self.server else "127.0.0.1"
        port = self.port if self.port else "27017"

        # No-auth local MongoDB (common for Compass local default)
        if not self.username_raw or not self.password_raw:
            return f"mongodb://{host}:{port}"

        return f"mongodb://{self.username}:{self.password}@{host}:{port}"

    def _db(self):
        """Return a connected MongoClient handle."""
        return self.remoteMongo(self._uri(), tls=self.tls)

    # -----------------------------
    # LAB 2 DATABASE UTIL FUNCTIONS
    # -----------------------------

    def addUpdate(self, data):
        """INSERT ONE DOCUMENT INTO ELET2415.climo"""
        try:
            # Ensure timestamp is an int if present (helps with unique index + range queries)
            if isinstance(data, dict) and "timestamp" in data:
                data["timestamp"] = int(data["timestamp"])

            remotedb = self._db()
            remotedb.ELET2415.climo.insert_one(data)

        except Exception as e:
            msg = str(e)
            # If you made timestamp unique, duplicates are expected sometimes
            if "duplicate" not in msg.lower():
                print("addUpdate error:", msg)
            return False
        else:
            return True

    def getAllInRange(self, start, end):
        """RETURNS A LIST OF DOCUMENTS BETWEEN START AND END TIMESTAMPS (inclusive)"""
        try:
            remotedb = self._db()
            result = list(
                remotedb.ELET2415.climo.find(
                    {"timestamp": {"$gte": int(start), "$lte": int(end)}},
                    {"_id": 0}
                ).sort("timestamp", 1)
            )
        except Exception as e:
            print("getAllInRange error:", str(e))
            return []
        else:
            return result

    def humidityMMAR(self, start, end):
        """RETURNS MIN, MAX, AVG AND RANGE FOR HUMIDITY BETWEEN START AND END"""
        try:
            remotedb = self._db()
            pipeline = [
                {"$match": {"timestamp": {"$gte": int(start), "$lte": int(end)}}},
                {"$group": {
                    "_id": None,
                    "min": {"$min": "$humidity"},
                    "max": {"$max": "$humidity"},
                    "avg": {"$avg": "$humidity"},
                }},
                {"$project": {
                    "_id": 0,
                    "min": 1,
                    "max": 1,
                    "avg": 1,
                    "range": {"$subtract": ["$max", "$min"]}
                }}
            ]
            result = list(remotedb.ELET2415.climo.aggregate(pipeline))
        except Exception as e:
            print("humidityMMAR error:", str(e))
            return []
        else:
            return result

    def temperatureMMAR(self, start, end):
        """RETURNS MIN, MAX, AVG AND RANGE FOR TEMPERATURE BETWEEN START AND END"""
        try:
            remotedb = self._db()
            pipeline = [
                {"$match": {"timestamp": {"$gte": int(start), "$lte": int(end)}}},
                {"$group": {
                    "_id": None,
                    "min": {"$min": "$temperature"},
                    "max": {"$max": "$temperature"},
                    "avg": {"$avg": "$temperature"},
                }},
                {"$project": {
                    "_id": 0,
                    "min": 1,
                    "max": 1,
                    "avg": 1,
                    "range": {"$subtract": ["$max", "$min"]}
                }}
            ]
            result = list(remotedb.ELET2415.climo.aggregate(pipeline))
        except Exception as e:
            print("temperatureMMAR error:", str(e))
            return []
        else:
            return result

    def frequencyDistro(self, variable, start, end):
        """
        RETURNS FREQUENCY DISTRIBUTION FOR A SPECIFIED VARIABLE BETWEEN START AND END

        variable should be one of: "temperature", "humidity", "heatindex", etc.
        """
        try:
            # Very simple allowlist (prevents weird field injection)
            allowed = {"temperature", "humidity", "heatindex", "timestamp", "id"}
            if variable not in allowed:
                return []

            remotedb = self._db()
            pipeline = [
                {"$match": {"timestamp": {"$gte": int(start), "$lte": int(end)}}},
                {"$group": {"_id": f"${variable}", "count": {"$sum": 1}}},
                {"$project": {"_id": 0, "value": "$_id", "count": 1}},
                {"$sort": {"value": 1}}
            ]
            result = list(remotedb.ELET2415.climo.aggregate(pipeline))
        except Exception as e:
            print("frequencyDistro error:", str(e))
            return []
        else:
            return result


def main():
    from config import Config
    from time import time
    one = DB(Config)

    start = time()
    end = time()
    print(f"completed in: {end - start} seconds")


if __name__ == '__main__':
    main()
