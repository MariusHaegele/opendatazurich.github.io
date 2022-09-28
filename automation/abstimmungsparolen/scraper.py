# -*- coding: utf-8 -*-

import requests
import pandas as pd
import sqlite3
import re
import dateparser
import sys
import os
import traceback


__location__ = os.path.realpath(
    os.path.join(
        os.getcwd(),
        os.path.dirname(__file__)
    )
)
session = requests.Session()


def get_json(url):
    r = session.get(url)
    r.raise_for_status()
    return r.json()


def get_vote_dates():
    abst_dates = pd.read_html('https://www.bk.admin.ch/ch/d/pore/va/vab_1_3_3_1.html')[0]
    abst_df = abst_dates.melt(id_vars=["Jahr"], value_vars=["1. Quartal", "2. Quartal", "3. Quartal", "4. Quartal"], var_name="Quartal")
    abst_df = abst_df.dropna()
    abst_df = abst_df.sort_values(by=['Jahr', 'Quartal']).reset_index(drop=True)
    return abst_df.to_dict('records')


def insert_or_update(parole, conn):
    try:
        print(f"Try to insert vote parole: {parole['titel']}, {parole['partei']}: {parole['parole']}")
        c = conn.cursor()
        c.execute(
            '''
            INSERT INTO data (
                datum,
                titel,
                abstimmungstext,
                partei,
                parole
            )
            VALUES
            (?,?,?,?,?)
            ''',
            [
                parole['datum'],
                parole['titel'],
                parole['abstimmungstext'],     
                parole['partei'],
                parole['parole'],
            ]
        )
    except sqlite3.IntegrityError:
        try:
            print("Already there, updating instead")
            print(parole)
            c.execute(
                '''
                UPDATE data SET parole = ? WHERE datum = ? AND titel = ? AND partei = ?
                ''',
                [
                    parole['parole'],
                    parole['datum'],
                    parole['titel'],   
                    parole['partei'],
                ]
            )
        except sqlite3.Error as e:
            print("Error: an error occured in sqlite3: ", e.args[0], file=sys.stderr)
            conn.rollback()
            raise
    finally:
        conn.commit()


try:
    DATABASE_NAME = os.path.join(__location__, 'data.sqlite')
    conn = sqlite3.connect(DATABASE_NAME)

    # get vote dates
    vote_dates = get_vote_dates()
    next_vote = next(a for a in vote_dates if not a['value'].startswith('N'))
    m = re.match(r"(?P<day>\d{2}).(?P<month>\d{2}).(?P<year>\d{4})", next_vote['value'])
    datum = f"{m['year']}-{m['month']}-{m['day']}"

    # get paroles of current votes
    geolevel = 3
    bfsnr = 261
    vorlage_url = f"https://app.statistik.zh.ch/wahlen_abstimmungen/data_prod/geschaefte/{geolevel}_{bfsnr}_{m['year']}{m['month']}{m['day']}/Vorlagen.json"
    
    r = session.get(vorlage_url)
    if r.status_code != requests.codes.ok:
        print(f"Error when requesting url {vorlage_url}: {r.status_code}", file=sys.stderr)
        sys.exit(0)
    result = r.json()
    
    
    
    # extract paroles
    paroles = []
    for vorlage in result['vorlagen']:
        for erlaut in vorlage['erlaeuterungen']:
            title = erlaut['vorlagenTitel']
            print(title)
            question = ''
            for kapitel in erlaut['kapitel']:
                prev_title = ''
                for comp in kapitel['komponenten']:
                    if comp['typ'] == 'parole' and prev_title.startswith('Abstimmungsparolen'):
                        m = re.match(r"(.+): (.*)", comp['parole']['text'])
                        parties = m[2].split(',')
                        for party in parties:
                            parole = {
                                'datum': datum,
                                'titel': title,
                                'abstimmungstext': question,
                                'partei': party.strip(),
                                'parole': m[1],
                            }
                            paroles.append(parole)
                        print(f" {prev_title}: {comp['parole']['text']}")
                    elif comp['typ'] == 'text' and prev_title == 'Abstimmungsfrage' and not question:
                        question = comp['text']['text']
                    elif comp['typ'] == 'title':
                        prev_title = comp['title']['text']
    
    # insert paroles in db
    for parole in paroles:
        insert_or_update(parole, conn)
    
    conn.commit()
except Exception as e:
    print("Error: %s" % e)
    print(traceback.format_exc())
    raise
finally:
    conn.close()
