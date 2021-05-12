# -*- coding: utf-8 -*-

import pywikibot
import datetime
import gc
from babel.dates import format_date, format_datetime, format_time, get_timezone
from camel1czutils import *

# configuration
start_date = datetime.datetime(2020, 3, 1)
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19/Česko_aktuálně'
#target_article = 'Wikipedista:Camel1cz_bot/Pískoviště'

# data sources + tracking last updated
data_sources['filename'] = botname + '_C19ceskoaktualne.lastupdated'
data_sources['sources'] = \
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
            'url': 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/ockovani.csv',
            'updated': datetime.datetime(1970, 1, 1)
        }
    ]

# global vars
data = {}
lastdate_updated = datetime.datetime(1970, 1, 1)

def main():
    global lastdate_updated, data
    pywikibot.handle_args()
    site = pywikibot.Site()

    # get current page data
    page = pywikibot.Page(site, target_article)
    template = page.get()

    # read last updated from last update
    loadDataUpdated()

    # Get basic data
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv'
    expected_header = ['datum', 'kumulativni_pocet_nakazenych', 'kumulativni_pocet_vylecenych', 'kumulativni_pocet_umrti', 'kumulativni_pocet_testu']


    def callback_nvut_csv(row):
        global data

        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            return
        # data
        data['testovani'] = mk_int(row[4])
        data['nakazeni']  = mk_int(row[1])
        data['umrti']  = mk_int(row[3])
        data['zotaveni']  = mk_int(row[2])
        data['aktivnipripady']  = data['nakazeni'] - data['umrti'] - data['zotaveni']
        data['typ'] = '{{{1}}}'
        data['datum'] = format_date(row_date, "d. MMMM Y", locale='cs_CZ')

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=',', callback=callback_nvut_csv)

    # Get ockovani
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/ockovani.csv'
    expected_header = ['datum', 'vakcina', 'kraj_nuts_kod', 'kraj_nazev', 'vekova_skupina', 'prvnich_davek', 'druhych_davek', 'celkem_davek']
    data['plneockovani'] = 0
    data['castecneockovani'] = 0
    data['vakcin'] = 0

    def callback_om_csv(row):
        global lastdate_updated, data

        # empty data
        if not row:
            return
        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            return
        # lastdate
        if row_date > lastdate_updated:
            lastdate_updated = row_date
        # data
        data['castecneockovani'] += mk_int(row[5])
        data['plneockovani'] += mk_int(row[6])
        data['vakcin'] += mk_int(row[7])

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=',', callback=callback_om_csv)

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
        data['hospitalizovani'] = mk_int(row[3])

    processCVSfromURL(url=url, expected_header=expected_header, delimiter=',', callback=callback_hosp_csv)

    # finalize data
    data['aktualizovano'] = format_datetime(data_sources['updateddate'], "d. MMMM Y H:mm:ss", tzinfo=get_timezone('Europe/Prague'), locale='cs_CZ')
    # osoby plne ockovane jsou pouze ty s 2 dávkami - obě aktuálně používané vakcíny mají 2 dávky - bereme přímo hodnotu počtu vykázaných 2. dávek
    # počtet částečně očkovaných je počet vyočkovaných prvních dávek ponížený o počet druhých dávek
    data['castecneockovani'] -= data['plneockovani']
    # počet (nějak) očkovaných je součet plně a částečně očkovaných
    data['ockovani'] = data['castecneockovani'] + data['plneockovani']
    # počet vakcín je přímo udáván v datové sadě

    # output data
    output = '''<onlyinclude>{{{{Data pandemie covidu-19/Česko aktuálně/core
 |testovaní = {testovani}
 |nakažení = {nakazeni}
 |úmrtí = {umrti}
 |zotavení = {zotaveni}
 |aktivní případy = {aktivnipripady}
 |hospitalizovaní = {hospitalizovani}
 |plněočkovaní    = {plneockovani}
 |částečněočkovaní  = {castecneockovani}
 |vakcín      = {vakcin}
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
        comment = 'Aktualizace dat + statistika za ' + lastdate_updated.strftime('%-d.%-m.%Y') + ' (by ' + botname + ')'
        page.put(output, summary=comment,
            minor=False, botflag=True, apply_cosmetic_changes=False)
        # store info about Date-Modified of data sources
        saveDataUpdated()
    else:
        print('wikipedia is up2date')
    return 1

if __name__ == '__main__':
    exit(main())
