# -*- coding: utf-8 -*-

import pywikibot
import requests
import re
import csv
import pytz
import datetime
from email.utils import parsedate_to_datetime
import json
import os
from babel.dates import format_date, format_datetime, format_time, get_timezone

# configuration
start_date = datetime.datetime(2020, 3, 1)
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19/Česko_aktuálně'
#target_article = 'Wikipedista:Camel1cz_bot/Pískoviště'

# data sources + tracking last updated
data_sources = {
    'sources': [
        {
            'url': 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv',
            'updated': datetime.datetime(1970, 1, 1)
        },
        {
            'url': 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/testy-pcr-antigenni.csv',
            'updated': datetime.datetime(1970, 1, 1)
        },
        {
            'url': 'https://share.uzis.cz/s/ZEAZtS4dWQXKWF4/download',
            'updated': datetime.datetime(1970, 1, 1)
        },
        {
            'url': 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/hospitalizace.csv',
            'updated': datetime.datetime(1970, 1, 1)
        },
        {
            'url': 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/ockovani.csv',
            'updated': datetime.datetime(1970, 1, 1)
        }
    ],
    'updated': False,
    'updateddate': False,
    'filename': botname + '_C19ceskoaktualne.lastupdated'
}

def saveDataUpdated():
    try:
        f=open(data_sources['filename'], "w")
        f.write(json.dumps(data_sources['sources'], default=str))
        f.close()
    except Exception as e:
        print('Storing of state data failed')
        print(e)
        pass

def loadDataUpdated():
    # read last updated data
    try:
        f=open(data_sources['filename'], "r")
        data = json.loads(f.read())
        f.close()
        for sRec in data:
            for i, cRec in enumerate(data_sources['sources']):
                if sRec['url'] == cRec['url']:
                    data_sources['sources'][i]['updated'] = datetime.datetime.strptime(sRec['updated'], '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print('Error loading state data')
        print(e)
        saveDataUpdated()

def getCSVfromURL(url, expected_header, delimiter=','):
    res = requests.get(url)
    if res.status_code != 200:
        print('Getting data failed. URL=' + url)
        return

    # check updated
    if 'Last-Modified' in res.headers:
        found = False
        last_modified_str=res.headers['Last-Modified']
        last_modified_obj=parsedate_to_datetime(last_modified_str).replace(tzinfo=None)
        for i, source in enumerate(data_sources['sources']):
            if source['url'] == url:
                found = True
                if source['updated'] < last_modified_obj:
                    data_sources['sources'][i]['updated'] = data_sources['updateddate'] = last_modified_obj
                    data_sources['updated'] = True
                break
        if not found:
            print('Warning: url Last-Modified is ignored: %s' % (url))
    else:
        print('No Last-Modified in request: %s' % (url))

    # get text
    text=res.text
    # strip magic header byte
    if text[0] == '\ufeff':
        text=res.text[1:]
    input_file = csv.reader(text.splitlines(), delimiter=delimiter)
    header=True
    data = []
    for row in input_file:
        if header:
            # validate header
            for i, name in enumerate(expected_header, start=0):
                if row[i] != name:
                    print(url + ': Unexpected format of CSV (expected "' + name + '" got "' + row[i] + '"')
                    return data
            header = False
            continue
        data.append(row)
    return data

def main():
    pywikibot.handle_args()
    site = pywikibot.Site()

    # get current page data
    page = pywikibot.Page(site, target_article)
    template = page.get()

    # read last updated from last update
    loadDataUpdated()

    data = []
    lastdate_obj = datetime.datetime(1970, 1, 1)

    # Get basic data
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv'
    expected_header = ['datum', 'kumulativni_pocet_nakazenych', 'kumulativni_pocet_vylecenych', 'kumulativni_pocet_umrti', 'kumulativni_pocet_testu']
    pData = getCSVfromURL(url, expected_header)[-1]
    row_date = datetime.datetime.strptime(pData[0], '%Y-%m-%d')

    data = {}
    data['testovani'] = int(pData[4])
    data['nakazeni']  = int(pData[1])
    data['umrti']  = int(pData[3])
    data['zotaveni']  = int(pData[2])
    data['aktivnipripady']  = data['nakazeni'] - data['umrti'] - data['zotaveni']
    data['typ'] = '{{{1}}}'
    data['datum'] = format_date(row_date, "d. MMMM Y", locale='cs_CZ')

    # Get ockovani
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/ockovani.csv'
    expected_header = ['datum', 'vakcina', 'kraj_nuts_kod', 'kraj_nazev', 'vekova_skupina', 'prvnich_davek', 'druhych_davek', 'celkem_davek']
    pData = getCSVfromURL(url, expected_header, ',')
    data['ockovani'] = 0
    for row in pData:
        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            continue;
        data['ockovani'] += int(row[7])

    # Get hospitalizovane
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/hospitalizace.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/hospitalizace.csv'
    expected_header = ['datum', 'pacient_prvni_zaznam', 'kum_pacient_prvni_zaznam', 'pocet_hosp']
    pData = getCSVfromURL(url, expected_header, ',')[-1]
    data['hospitalizovani'] = pData[3]


    # finalize data
    data['aktualizovano'] = format_datetime(data_sources['updateddate'], "d. MMMM Y H:mm:ss", tzinfo=get_timezone('Europe/Prague'), locale='cs_CZ')

    # output data
    output = '''<onlyinclude>{{{{Data pandemie covidu-19/Česko aktuálně/core
 |testovaní = {testovani}
 |nakažení = {nakazeni}
 |úmrtí = {umrti}
 |zotavení = {zotaveni}
 |aktivní případy = {aktivnipripady}
 |hospitalizovaní = {hospitalizovani}
 |očkovaní    = {ockovani}
 |datum       = {datum}
 |aktualizováno = {aktualizovano}
 |typ         = {typ}
}}}}</onlyinclude>
<!-- *** Data pochází výhradně z oficiálních zdrojů MZ ČR.
-->
{{{{documentation}}}}
[[Kategorie:Šablony:Pandemie covidu-19]]
'''.format(**data)

    # store it into wiki template
    if data_sources['updated']:
        comment = 'Aktualizace dat + statistika za ' + lastdate_obj.strftime('%-d.%-m.%Y') + ' (by ' + botname + ')'
        page.put(output, summary=comment,
            minor=False, botflag=False, apply_cosmetic_changes=False)
        # store info about Date-Modified of data sources
        saveDataUpdated()
    else:
        print('wikipedia is up2date')
    return 1

if __name__ == '__main__':
    exit(main())