import json
import os

from joepegs.joepegs_api import JoePegsClient

COLLECTION_SIZE = 4500

j = JoePegsClient()

collection = {}

JSON_FILE = "/tmp/collection_mechavax.json"
CSV_FILE = "/tmp/collection_mechavax.csv"
if os.path.isfile(JSON_FILE):
    with open(JSON_FILE) as infile:
        data = json.load(infile)
    with open(CSV_FILE, "w") as outfile:
        outfile.write("jp id, token id\n")
        for k, v in data.items():
            outfile.write(",".join([str(k), str(v)]) + "\n")
else:
    try:
        for token_id in range(COLLECTION_SIZE):
            item = j.get_item("0xb68f42c2c805b81dad78d2f07244917431c7f322", token_id)
            if not item:
                print(f"No data for {token_id}")
                continue

            if "metadata" not in item or "tokenId" not in item:
                print(f"Missing metadata for {token_id}")
                continue

            try:
                jp_id = os.path.basename(item["metadata"]["tokenUri"]).split(".")[0]
                name = item["metadata"]["name"]
                collection[jp_id] = token_id
            except:
                print(f"Failed to parse ids {item}")
    finally:
        with open("/tmp/collection_mechavax.json", "w") as outfile:
            json.dump(collection, outfile, indent=4)
