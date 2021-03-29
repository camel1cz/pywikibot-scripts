# -*- coding: utf-8 -*-

import pywikibot
from camel1czutils import *

import requests
import re
import csv
import pytz
import datetime
from email.utils import parsedate_to_datetime
import json
import os

# configuration
start_date = datetime.datetime(2020, 3, 1)
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19/České_případy_tabulka'
#target_article = 'Wikipedista:Camel1cz_bot/Pískoviště'

# data sources + tracking last updated
data_sources['filename'] = botname + '_C19tabulka.lastupdated'
data_sources['expand_templates'] = True
data_sources['sources'].extend(
    [
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
            'url': 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/ockovaci-mista.csv',
            'updated': datetime.datetime(1970, 1, 1)
        }
    ]
)

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

# global vars
data = []
lastdate_obj = datetime.datetime(1970, 1, 1)
lastdate_updated = datetime.datetime(1970, 1, 1)
pDataDate = None
ockovani = 0

def main():
    global data, lastdate_obj, lastdate_updated, pDataDate, ockovani

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

    # Get basic data
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv'
    expected_header = ['datum', 'kumulativni_pocet_nakazenych', 'kumulativni_pocet_vylecenych', 'kumulativni_pocet_umrti', 'kumulativni_pocet_testu']

    def callback_nvut_csv(row):
        global lastdate_updated, data

        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            return
        # lastdate
        if row_date > lastdate_updated:
            lastdate_updated = row_date
        data.append({'datum': row_date, 'nakazeni': mk_int(row[1]), 'zotaveni': mk_int(row[2]), 'zemreli': mk_int(row[3]), 'pocet_PCR_testu': mk_int(row[4])})

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=',', callback=callback_nvut_csv)

    # Get PES data
    # get data from https://share.uzis.cz/s/BRfppYFpNTddAy4/download?path=%2F&files=pes_CR_verze2.csv
    url = 'https://share.uzis.cz/s/BRfppYFpNTddAy4/download?path=%2F&files=pes_CR_verze2.csv'
    expected_header = ['datum_zobrazeni', 'datum', 'body']

    def callback_pes_csv(row):
        global lastdate_updated, data

        # get date
        row_date = datetime.datetime.strptime(row[1], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            return
        # seek for the row_date in data
        pos=0
        while pos < len(data):
            if data[pos]['datum'] == row_date:
                data[pos]['pes'] = mk_int(row[2])
                break
            pos+=1

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=';', callback=callback_pes_csv)

    # Get ockovani
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/ockovaci-mista.csv'
    expected_header = ['datum', 'vakcina', 'kraj_nuts_kod', 'kraj_nazev', 'zarizeni_kod', 'zarizeni_nazev', 'poradi_davky', 'vekova_skupina']

    def callback_ocko_csv(row):
        global lastdate_updated, data, pDataDate, ockovani

        # empty data
        if not row:
            return
        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            return
        # add
        if pDataDate == row_date:
            if mk_int(row[6]) == 1:
                ockovani += 1
            return
        if pDataDate is None:
            pDataDate = row_date
            if mk_int(row[6]) == 1:
                ockovani = 1
            else:
                ockovani = 0
            return

        # seek for the row_date in data
        pos = 0
        while pos < len(data) and data[pos]['datum'] <= pDataDate:
            if data[pos]['datum'] == pDataDate:
                data[pos]['ockovani'] = ockovani
                break
            pos+=1
        pDataDate = row_date
        if mk_int(row[6]) == 1:
            ockovani = 1
        else:
            ockovani = 0

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=',', callback=callback_ocko_csv)

    # save last value
    # seek for the pDataDate in data
    pos = 0
    while pDataDate is not None and pos < len(data) and data[pos]['datum'] <= pDataDate:
        if data[pos]['datum'] == pDataDate:
            data[pos]['ockovani'] = ockovani
            break
        pos+=1

    # Get testovane
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/testy-pcr-antigenni.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/testy-pcr-antigenni.csv'
    expected_header = ['datum', 'pocet_PCR_testy', 'pocet_AG_testy']

    def callback_test_csv(row):
        global lastdate_updated, data

        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            return
        # seek for the row_date in data
        pos=0
        while pos < len(data):
            if data[pos]['datum'] == row_date:
                data[pos]['pocet_AG_testu'] = mk_int(row[2])
                break
            pos+=1

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=',', callback=callback_test_csv)

    # Get hospitalizovane
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/hospitalizace.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/hospitalizace.csv'
    expected_header = ['datum', 'pacient_prvni_zaznam', 'kum_pacient_prvni_zaznam', 'pocet_hosp']

    def callback_hosp_csv(row):
        global lastdate_updated, data

        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            return
        # seek for the row_date in data
        pos=0
        while pos < len(data) and data[pos]['datum'] <= row_date:
            if data[pos]['datum'] == row_date:
                data[pos]['hospitalizovani'] = mk_int(row[3])
                break
            pos+=1

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=',', callback=callback_hosp_csv)

    # output data
    output = '\n<noinclude>'
    noinclude_closed = False
    prev_data = {'nakazeni': 0, 'zotaveni': 0, 'zemreli': 0, 'aktivni': 0, 'pocet_PCR_testu': 0, 'pocet_AG_testu': 0, 'hospitalizovani': 0, 'ockovani': 0}
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
            '\n| %s%s' % (template_nts(row['nakazeni'] - prev_data['nakazeni']), percentDiff(prev_data['nakazeni'], row['nakazeni'])) +\
            '\n| %s' % (template_nts(row['nakazeni'])) +\
            '\n| %s%s' % (template_nts(row['zotaveni'] - prev_data['zotaveni']), percentDiff(prev_data['zotaveni'], row['zotaveni'])) +\
            '\n| %s' % (template_nts(row['zotaveni'])) +\
            '\n| %s%s' % (template_nts(row['zemreli'] - prev_data['zemreli']), percentDiff(prev_data['zemreli'], row['zemreli'])) +\
            '\n| %s' % (template_nts(row['zemreli']))
        p = row['nakazeni'] - row['zotaveni'] - row['zemreli']
        output = output +\
            '\n| %s%s' % (template_nts(p - prev_data['aktivni']), percentDiff(prev_data['aktivni'], p)) +\
            '\n| %s' % (template_nts(p)) +\
            '\n| %s' % (template_nts(row['pocet_PCR_testu']-prev_data['pocet_PCR_testu'])) +\
            '\n| %s' % (template_nts(row['pocet_PCR_testu']))
        if 'pocet_AG_testu' in row and (row['pocet_AG_testu'] > 0 or prev_data['pocet_AG_testu'] > 0):
            output = output +\
                '\n| %s' % (template_nts(row['pocet_AG_testu'])) +\
                '\n| %s' % (template_nts(row['pocet_AG_testu']+prev_data['pocet_AG_testu']))
            prev_data['pocet_AG_testu'] += row['pocet_AG_testu']
        else:
            output = output +\
                '\n| {{N/A}}\n| {{N/A}}'
        output = output +\
            '\n| %s%s' % (template_nts(row['hospitalizovani'] - prev_data['hospitalizovani']), percentDiff(row['hospitalizovani'], prev_data['hospitalizovani'])) +\
            '\n| %s' % (template_nts(row['hospitalizovani']))
        # ockovani
        if 'ockovani' in row:
            if prev_data['ockovani'] + row['ockovani'] > 0:
                output = output +\
                    '\n| %s\n| %s' % (template_nts(row['ockovani']), template_nts(prev_data['ockovani'] + row['ockovani']))
                prev_data['ockovani'] = prev_data['ockovani'] + row['ockovani']
            else:
                output = output +\
                    '\n| {{N/A}}\n| {{N/A}}'
        else:
            output = output +\
                '\n| {{N/A}}\n| {{N/A}}'
        # PES
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
        comment = 'Aktualizace dat'
        comment = 'Aktualizace dat + statistika za ' + lastdate_obj.strftime('%-d.%-m.%Y') + ' (by ' + botname + ')'
        page.put(leadingText + output + trailingText, summary=comment,
            minor=False, botflag=True, apply_cosmetic_changes=False)
        # store info about Date-Modified of data sources
        saveDataUpdated()
    else:
        print('wikipedia is up2date')
    return 1

if __name__ == '__main__':
    exit(main())
