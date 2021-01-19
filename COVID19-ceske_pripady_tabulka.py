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
        }
    ],
    'updated': False,
    'filename': botname + '_C19tabulka.lastupdated'
}
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
                    data_sources['sources'][i]['updated'] = last_modified_obj
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

def percentDiff(a, b):
    if a == 0:
        return ''
    if a == b:
        return ' (=)'

    diff=100*(b - a)/a
    if abs(diff) < 1:
        return (' (%+0.2f%%)' % (diff)).replace('.', ',')
    if abs(diff) < 10:
        return (' (%+0.1f%%)' % (diff)).replace('.', ',')
    return (' (%+d%%)' % (diff)).replace('.', ',')

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

    # read last updated from last update
    loadDataUpdated()

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
    ockovani_known_data = { '2021-01-06': { 'hodnota': 19918}, '2021-01-13': { 'hodnota': 70680 } , '2021-01-17': { 'hodnota': 108239, 'reference': '''<ref>{{Citace elektronického periodika
 | titul = Politici hodnotí první týdny očkování: Česko zaspalo, premiér řeší mikromanagement
 | periodikum = ČT24
 | datum_vydání = 2021-01-19
 | url = https://ct24.ceskatelevize.cz/domaci/3256782-politici-hodnoti-prvni-tydny-ockovani-cesko-zaspalo-premier-resi-mikromanagement
 | datum_přístupu = 2021-01-19
}}</ref>''' }}
    # zdroj dat 2021-01-17: https://www.lidovky.cz/domov/cesko-ma-podle-babise-objednanych-20-milionu-vakcin-proti-covidu-zatim-jsme-obdrzeli-necelych-170-ti.A210117_215054_ln_domov_sed
    for i, row in enumerate(data):
        # seek for the known data
        processed=0
        if processed == len(ockovani_known_data):
            break
        if row['datum'].strftime('%Y-%m-%d') in ockovani_known_data:
            processed+=1
            data[i]['ockovani']=ockovani_known_data[row['datum'].strftime('%Y-%m-%d')]['hodnota']

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
            reference = '';
            if 'reference' in ockovani_known_data[row['datum'].strftime('%Y-%m-%d')]:
                reference = ockovani_known_data[row['datum'].strftime('%Y-%m-%d')]['reference']
            output = output +\
                '\n| {{N/A}}\n| {{Nts|%d%s}}' % (row['ockovani'], reference)
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

    if data_sources['updated']:
        comment = 'Oprava desetiného oddelovače a přidání reference na počet očkovaných.'
        page.put(leadingText + output + trailingText, summary=comment,
            minor=False, botflag=False, apply_cosmetic_changes=False)
        # store info about Date-Modified of data sources
        saveDataUpdated()
    else:
        print('wikipedia is up2date')
    return 1

if __name__ == '__main__':
    exit(main())
