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

# configuration
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19/České_případy'
#target_article = 'Wikipedista:Camel1cz_bot/Pískoviště'
last_updated_filename = botname + 'C19_pripady.lastupdated'

def get_single_year(year):
    return year.rpartition(', ')[2]


def main():
    pywikibot.handle_args()
    site = pywikibot.Site()
    last_modified=''

    # get current page data
    page = pywikibot.Page(site, target_article)
    template = page.get()

    # validate page - we have to see correct comments
    prefix_pos = template.find(data_prefix)
    if prefix_pos < 0 or prefix_pos + len(data_prefix) > template.find(data_suffix):
        print('Template validation failure')
        return

    # get data from MZ ČR
    csv_url = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv'
    res = requests.get(csv_url)
    if res.status_code != 200:
        print('Getting data failed. URL=' + csv_url)
        return

    # get timestamp of last modification
    last_modified_str=res.headers['Last-Modified']
    last_modified_obj=parsedate_to_datetime(last_modified_str).astimezone(pytz.timezone("Europe/Prague"))
    # check of there are new data
    try:
        f=open(last_updated_filename, "r")
        l=f.read()
        last_updated=dateutil.parser.isoparse(l)
        f.close()
        if last_updated>=last_modified_obj:
            print('wikipedia is up2date')
            return 1
    except Exception as e:
        pass

    # build data
    reader = csv.reader(res.text.splitlines(), delimiter=',')
    header=True
    ignoring=True
    data=''
    lastdate=''
    for row in reader:
        if header:
            # test header
            if row[0][1:] != 'datum' or row[1] != 'kumulativni_pocet_nakazenych' or row[2] != 'kumulativni_pocet_vylecenych' or row[3] != 'kumulativni_pocet_umrti' or row[4] != 'kumulativni_pocet_testu':
                print('CSV Header check failed')
                return
            header=False
            continue
        if row[0] == '2020-03-01':
            ignoring=False
        if ignoring:
            continue
        data+=(row[0]+';'+row[3]+';'+row[2]+';'+row[1]+'\n')
        lastdate=row[0]

    # store it into wiki template
    leadingText = template.split(data_prefix)[0] + data_prefix + '\n'
    trailingText = data_suffix + template.split(data_suffix)[1]
    lastdate_obj = datetime.datetime.strptime(lastdate, '%Y-%m-%d')

    page.put(leadingText + data + trailingText, summary='Aktualizace dat + statistika za ' + lastdate_obj.strftime('%-d.%-m.%Y') + ' (by ' + botname + ')',
             minor=False, botflag=False, apply_cosmetic_changes=False)

    # store last update data
    try:
        f=open(last_updated_filename, "w+")
        f.write(last_modified_obj.isoformat())
        f.close()
    except:
        print('Cannot write date of last modification')
        return

if __name__ == '__main__':
    exit(main())
