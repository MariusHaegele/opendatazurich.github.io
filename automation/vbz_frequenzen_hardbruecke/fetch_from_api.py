# -*- coding: utf-8 -*-

import os
import sys
import csv
import traceback
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

user = os.getenv('SSZ_USER')
pw = os.getenv('SSZ_PASS')

try:
    # get locations
    s = requests.Session()
    s.auth = (user, pw)
    r = s.get('https://vbz.diamondreports.ch:8012/api/location')
    r.raise_for_status()
    locations = r.json()

    field_names = ['In', 'Out', 'Timestamp', 'Name']
    writer = csv.DictWriter(sys.stdout, field_names, quoting=csv.QUOTE_NONNUMERIC)
    writer.writeheader()

    today = datetime.now().date()
    total_days = 3
    for loc in locations:
        for day in range(total_days):
            current_date = (today - timedelta(days=day))
            cr = s.get(
                f"https://vbz.diamondreports.ch:8012/api/location/counter/{loc['Name']}",
                params={
                    'aggregate': 5,
                    'date': current_date.strftime('%Y%m%d')
                }
            )
            cr.raise_for_status()
            counter = cr.json()
            if len(counter['Counters']) == 0:
                continue
    
            for obs in counter['Counters'][0]['Counts']:
                writer.writerow({
                    'In': obs['In'],
                    'Out': obs['Out'],
                    'Timestamp': obs['Timestamp'],
                    'Name': loc['Name']
                })
except Exception as e:
    print("Error: %s" % e, file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    sys.exit(1)
finally:
    sys.stdout.flush()
