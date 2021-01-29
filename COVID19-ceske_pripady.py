# -*- coding: utf-8 -*-
import pywikibot
from camel1czutils import *

# configuration
start_date = datetime.datetime(2020, 3, 1)
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19/České_případy'
#target_article = 'Wikipedista:Camel1cz_bot/Pískoviště'

data_sources['filename'] = botname + '_C19pripady.lastupdated'
data_sources['sources'].append({
    'url': 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv',
    'updated': datetime.datetime(1970, 1, 1)
});

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

    # Get basic data
    # get data from https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv
    url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv'
    expected_header = ['datum', 'kumulativni_pocet_nakazenych', 'kumulativni_pocet_vylecenych', 'kumulativni_pocet_umrti', 'kumulativni_pocet_testu']
    pData = getCSVfromURL(url, expected_header)
    output=''
    lastdate_updated = datetime.datetime(1970, 1, 1)

    for row in pData:
        # get date
        row_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
        # skip date before start_date
        if row_date < start_date:
            continue
        # lastdate
        if row_date > lastdate_updated:
            lastdate_updated = row_date
        output+=(row[0]+';'+row[3]+';'+row[2]+';'+row[1]+'\n')

    # store it into wiki template
    leadingText = template.split(data_prefix)[0] + data_prefix + '\n'
    trailingText = data_suffix + template.split(data_suffix)[1]

    if data_sources['updated']:
        comment = 'Aktualizace dat'
        comment = 'Aktualizace dat + statistika za ' + lastdate_updated.strftime('%-d.%-m.%Y') + ' (by ' + botname + ')'
        page.put(leadingText + output + trailingText, summary=comment,
            minor=False, botflag=False, apply_cosmetic_changes=False)
        # store info about Date-Modified of data sources
        saveDataUpdated()
    else:
        print('wikipedia is up2date')
    return 1

if __name__ == '__main__':
    exit(main())

