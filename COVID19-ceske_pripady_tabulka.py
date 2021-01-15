# -*- coding: utf-8 -*-
import requests

import mwparserfromhell as parser
import pywikibot
import re
import csv
import codecs
import pytz
import datetime
import dateutil.parser
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
import json

# configuration
start_date = datetime.datetime(2020, 3, 1)
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19/České_případy_tabulka'
#target_article = 'Wikipedista:Camel1cz/Pískoviště'
table_header = '''|-
! rowspan="2" |Datum
! colspan="2" |Nakažení
! colspan="2" |Zotavení
! colspan="2" |Zemřelí
! colspan="2" |Aktivní případy
! colspan="2" |PCR testy
! colspan="2" |Antigenní testy
! colspan="2" |Hospitalizovaní
! colspan="2" |Očkovaní
! rowspan="2" |{{Popisek|PES|Vývoj indexu rizika v čase – přehled pro celou ČR}}<ref name=”pes”>{{Citace elektronické monografie | titul = Protiepidemický systém ČR | url = https://onemocneni-aktualne.mzcr.cz/pes | vydavatel = Ministerstvo zdravotnictví České republiky | datum vydání = 2020-11-17 | datum přístupu = 2020-11-17}}</ref>
|-
!Nárůst!!Celkem
!Nárůst!!Celkem
!Nárůst!!Celkem
!Nárůst!!Celkem
!Nárůst!!Celkem
!Nárůst!!Celkem
!Nárůst!!Celkem
!Nárůst!!Celkem'''

def getCSVfromURL(url, expected_header, delimiter=','):
    res = requests.get(url)
    if res.status_code != 200:
        print('Getting data failed. URL=' + url)
        return
    # get text
    text=res.text
    # strip magic header byte
    if text[0] == '\ufeff':
        text=res.text[1:]
#    input_file = csv.DictReader(text.splitlines(), delimiter=',')
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

def percentDiff(a, b):
    if a == 0:
        return ''
    if a == b:
        return ' (=)'

    diff=100*(b - a)/a
    if abs(diff) < 1:
        return ' (%+0.2f%%)' % (diff)
    if abs(diff) < 10:
        return ' (%+0.1f%%)' % (diff)
    return ' (%+d%%)' % (diff)

def main():
    pywikibot.handle_args()
    site = pywikibot.Site()

    # get current page data
    page = pywikibot.Page(site, target_article)
    template = page.get()

    # validate page - we have to see correct comments
    prefix_pos = template.find(data_prefix)
    if prefix_pos < 0 or prefix_pos + len(data_prefix) > template.find(data_suffix):
        print('Template validation failure')
        return

    data = []
    lastdate_obj = datetime.datetime(1970, 1, 1)

    # Get basic data
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv'
    expected_header = ['datum', 'kumulativni_pocet_nakazenych', 'kumulativni_pocet_vylecenych', 'kumulativni_pocet_umrti', 'kumulativni_pocet_testu']
    pData = getCSVfromURL(url, expected_header)
    for row in pData:
        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            continue
        data.append({'datum': row_date, 'nakazeni': int(row[1]), 'zotaveni': int(row[2]), 'zemreli': int(row[3]), 'pocet_PCR_testu': int(row[4])})

    # Get PES data
    # get data from https://share.uzis.cz/s/BRfppYFpNTddAy4/download?path=%2F&files=pes_CR_verze2.csv
    url = 'https://share.uzis.cz/s/BRfppYFpNTddAy4/download?path=%2F&files=pes_CR_verze2.csv'
    expected_header = ['datum_zobrazeni', 'datum', 'body']
    pData = getCSVfromURL(url, expected_header, ';')
    for row in pData:
        # get date
        row_date = datetime.datetime.strptime(row[1], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            continue
        # seek for the row_date in data
        pos=0
        while pos < len(data):
            if data[pos]['datum'] == row_date:
                data[pos]['pes'] = int(row[2])
                break
            pos+=1

    # Get ockovani
    # we have no datasets from government yet. Updated manually. weekly
    known_data = { '2021-01-06': 19918, '2021-01-13': 70680 }
    for i, row in enumerate(data):
        # seek for the known data
        processed=0
        if processed == len(known_data):
            break
        if row['datum'].strftime('%Y-%m-%d') in known_data:
            processed+=1
            data[i]['ockovani']=known_data[row['datum'].strftime('%Y-%m-%d')]

    # Get testovane
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/testy-pcr-antigenni.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/testy-pcr-antigenni.csv'
    expected_header = ['datum', 'pocet_PCR_testy', 'pocet_AG_testy']
    pData = getCSVfromURL(url, expected_header, ',')
    for row in pData:
        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            continue
        # seek for the row_date in data
        pos=0
        while pos < len(data):
            if data[pos]['datum'] == row_date:
#                if len(row[1]) > 0:
#                    data[pos]['pocet_PCR_testu'] = int(row[1])
                data[pos]['pocet_AG_testu'] = int(row[2])
                break
            pos+=1

    # Get hospitalizovane
    # Get from JSON data from https://onemocneni-aktualne.mzcr.cz/covid-19
    url = 'https://onemocneni-aktualne.mzcr.cz/covid-19'
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')
    res = soup.find(attrs={ 'id': 'js-hospitalization-table-data'})
    pData = json.loads(res.get('data-table'))

    # check format of json
    if pData['header'][0]['title'] != 'Datum' or pData['header'][1]['title'] != 'Aktuální počet hospitalizovaných osob':
        print(url + ' Error in table header')
        return

    for row in pData['body']:
        # get date
        row_date = datetime.datetime.strptime(row[0], '%d.%m.%Y')
        # seek for the row_date in data
        pos=0
        while pos < len(data):
            if data[pos]['datum'] == row_date:
                data[pos]['hospitalizovani'] = int(row[1])
                break
            pos+=1

    # output data
    output = '\n<noinclude>'
    noinclude_closed = False
    prev_data = {'nakazeni': 0, 'zotaveni': 0, 'zemreli': 0, 'aktivni': 0, 'pocet_PCR_testu': 0, 'pocet_AG_testu': 0, 'hospitalizovani': 0}
    for row in data:
        # lastdate
        if row['datum'] > lastdate_obj:
            lastdate_obj = row['datum']
        # header + noinclude
        if (int(row['datum'].strftime('%d'))) == 1 and row['datum'] > datetime.datetime(2020, 3, 1):
            output += '\n' +table_header
            if (datetime.datetime.now() - row['datum']).days < 35 and not noinclude_closed:
                output += '\n' + '</noinclude>'
                noinclude_closed = True

        # style of Saturday and Sunday
        style=''
        # Saturday
        if row['datum'].weekday() == 5:
            style=' style="background: #87CEFA" |'
        # Sunday
        if row['datum'].weekday() == 6:
            style=' style="background: #FFB6C1" |'

        output = output +\
            '\n|-' +\
            '\n!' + style + row['datum'].strftime(' %-d.&nbsp;%-m.&nbsp;%Y') +\
            '\n| {{Nts|%d}}%s' % (row['nakazeni'] - prev_data['nakazeni'], percentDiff(prev_data['nakazeni'], row['nakazeni'])) +\
            '\n| {{Nts|%d}}' % (row['nakazeni']) +\
            '\n| {{Nts|%d}}%s' % (row['zotaveni'] - prev_data['zotaveni'], percentDiff(prev_data['zotaveni'], row['zotaveni'])) +\
            '\n| {{Nts|%d}}' % (row['zotaveni']) +\
            '\n| {{Nts|%d}}%s' % (row['zemreli'] - prev_data['zemreli'], percentDiff(prev_data['zemreli'], row['zemreli'])) +\
            '\n| {{Nts|%d}}' % (row['zemreli'])
        p = row['nakazeni'] - row['zotaveni'] - row['zemreli']
        output = output +\
            '\n| {{Nts|%d}}%s' % (p - prev_data['aktivni'], percentDiff(prev_data['aktivni'], p)) +\
            '\n| {{Nts|%d}}' % (p) +\
            '\n| {{Nts|%d}}' % (row['pocet_PCR_testu']-prev_data['pocet_PCR_testu']) +\
            '\n| {{Nts|%d}}' % (row['pocet_PCR_testu'])
        if 'pocet_AG_testu' in row and (row['pocet_AG_testu'] > 0 or prev_data['pocet_AG_testu'] > 0):
            output = output +\
                '\n| {{Nts|%d}}' % (row['pocet_AG_testu']) +\
                '\n| {{Nts|%d}}' % (row['pocet_AG_testu']+prev_data['pocet_AG_testu'])
            prev_data['pocet_AG_testu'] += row['pocet_AG_testu']
        else:
            output = output +\
                '\n| {{N/A}}\n| {{N/A}}'
        output = output +\
            '\n| {{Nts|%d}}%s' % (row['hospitalizovani'] - prev_data['hospitalizovani'], percentDiff(row['hospitalizovani'], prev_data['hospitalizovani'])) +\
            '\n| {{Nts|%d}}' % (row['hospitalizovani'])
        if 'ockovani' in row:
            output = output +\
                '\n| {{N/A}}\n| {{Nts|%d}}' % (row['ockovani'])
        else:
            output = output +\
                '\n| {{N/A}}\n| {{N/A}}'
        if 'pes' in row:
            output = output +\
                '\n| %d' % (row['pes'])
        else:
            output = output +\
                '\n| {{N/A}}'

        prev_data['nakazeni'] = row['nakazeni']
        prev_data['zotaveni'] = row['zotaveni']
        prev_data['zemreli'] = row['zemreli']
        prev_data['aktivni'] = row['nakazeni'] - row['zotaveni'] - row['zemreli']
        prev_data['pocet_PCR_testu'] = row['pocet_PCR_testu']
        prev_data['hospitalizovani'] = row['hospitalizovani']

    # store it into wiki template
    leadingText = template.split(data_prefix)[0] + data_prefix + '\n'
    trailingText = data_suffix + template.split(data_suffix)[1]

    page.put(leadingText + output + trailingText, summary='Aktualizace dat + statistika za ' + lastdate_obj.strftime('%-d.%-m.%Y') + ' (by ' + botname + ')',
             minor=False, botflag=False, apply_cosmetic_changes=False)
    return

if __name__ == '__main__':
    main()
