# -*- coding: utf-8 -*-

import pywikibot
import datetime
from babel.dates import format_date, format_datetime, format_time, get_timezone
from camel1czutils import *

# configuration
start_date = datetime.datetime(2020, 3, 1)
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19/Svět_aktuálně'
#target_article = 'Wikipedista:Camel1cz_bot/Pískoviště'

# data sources + tracking last updated
data_sources['filename'] = botname + '_C19svetaktualne.lastupdated'
data_sources['sources'] = \
    [
        {
            'url': 'https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv',
            'updated': datetime.datetime(1970, 1, 1)
        },
        {
            'url': 'https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/jhu/full_data.csv',
            'updated': datetime.datetime(1970, 1, 1)
        }
    ]

def main():
    pywikibot.handle_args()
    site = pywikibot.Site()

    # get current page data
    page = pywikibot.Page(site, target_article)
    template = page.get()

    # read last updated from last update
    loadDataUpdated()

    data = []
    lastdate_updated = datetime.datetime(1970, 1, 1)

    # Get basic data
    yest = (datetime.datetime.now() - datetime.timedelta(days=1))
    yest = yest.replace(hour=0, minute=0, second=0, microsecond=0)
    url = ('https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/%s.csv') % (yest.strftime("%m-%d-%Y"))
    expected_header = ['FIPS', 'Admin2', 'Province_State', 'Country_Region', 'Last_Update', 'Lat', 'Long_', 'Confirmed', 'Deaths', 'Recovered', 'Active', 'Combined_Key', 'Incident_Rate', 'Case_Fatality_Ratio']
    pData = getCSVfromURL(url, expected_header)
    if len(pData) <= 0:
      print("No data available")
      print("wikipedia is up2date")
      return

    lastdate_updated = datetime.datetime(1970, 1, 1)
    data = {
      'testovani': 0,
      'nakazeni': 0,
      'umrti': 0,
      'zotaveni': 0,
      'aktivnipripady': 0,
      'castecneockovani': 0,
      'plneockovani': 0,
      'vakcin': 0,
      'hospitalizovani': 0,
      'typ': '{{{1}}}',
      'datum': ''
    }

    for row in pData:
      # get date
      row_date = None
      try:
        # 2021-02-09 05:23:30
        # '%Y-%m-%d %H:%M:%S'
        row_date = datetime.datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S')
      except:
        pass
      # lastdate
      if row_date > lastdate_updated:
        lastdate_updated = row_date
      data['nakazeni'] += mk_int(row[7])
      data['umrti'] += mk_int(row[8])
      data['zotaveni'] += mk_int(row[9])

    # active cases
    data['aktivnipripady'] = data['nakazeni'] - data['umrti'] - data['zotaveni']

    # get vaccination data
    # https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv
    url = 'https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv'
    expected_header = ['location', 'iso_code', 'date', 'total_vaccinations' ,'people_vaccinated', 'people_fully_vaccinated', 'daily_vaccinations_raw', 'daily_vaccinations', 'total_vaccinations_per_hundred', 'people_vaccinated_per_hundred', 'people_fully_vaccinated_per_hundred', 'daily_vaccinations_per_million']
    pData = getCSVfromURL(url, expected_header)
    if len(pData) <= 0:
      print("Can't get data")
      print("skipping wikipedia update")
      return

    lastdate_updated2 = datetime.datetime(1970, 1, 1)
    last_location = None
    ppData = {
      'castecneockovani': 0,
      'plneockovani': 0,
      'vakcin': 0
    }
    for row in pData:
      # get date
      row_date = None
      try:
        # 2021-02-09
        # '%Y-%m-%d'
        row_date = datetime.datetime.strptime(row[2], '%Y-%m-%d')
      except:
        pass;

      if last_location == row[0]:
        ppData['castecneockovani'] = mk_int(row[4])
        ppData['plneockovani'] = mk_int(row[5])
        ppData['vakcin'] = mk_int(row[3])
      else:
        # change!
        last_location = row[0]
        data['castecneockovani'] += ppData['castecneockovani']
        data['plneockovani'] += ppData['plneockovani']
        data['vakcin'] += ppData['vakcin']
        # start new
        ppData['castecneockovani'] = mk_int(row[4])
        ppData['plneockovani'] = mk_int(row[5])
        ppData['vakcin'] = mk_int(row[3])

      # lastdate
      if row_date > lastdate_updated2:
        lastdate_updated2 = row_date

    # add last record
    data['castecneockovani'] = ppData['castecneockovani']
    data['plneockovani'] = ppData['plneockovani']
    data['vakcin'] = ppData['vakcin']

    # finalize data
    data['ockovani'] = data['plneockovani'] + data['castecneockovani']
    data['aktualizovano'] = format_datetime(datetime.datetime.now(), "d. MMMM Y H:mm:ss", tzinfo=get_timezone('Europe/Prague'), locale='cs_CZ')
    data['datum'] = format_date(lastdate_updated2, "d. MMMM Y", locale='cs_CZ')

    # output data
    output = '''<onlyinclude>{{{{Data pandemie covidu-19/Svět aktuálně/core
 |testovaní = {testovani}
 |nakažení = {nakazeni}
 |úmrtí = {umrti}
 |zotavení = {zotaveni}
 |aktivní případy = {aktivnipripady}
 |hospitalizovaní = {hospitalizovani}
 |plněočkovaní    = {plneockovani}
 |částečněočkovaní  = {castecneockovani}
 |očkovaní  = {ockovani}
 |vakcín      = {vakcin}
 |datum       = {datum}
 |aktualizováno = {aktualizovano}
 |typ         = {typ}
}}}}<ref name="JHU_ref">{{Citace elektronické monografie | url=https://gisanddata.maps.arcgis.com/apps/opsdashboard/index.html#/bda7594740fd40299423467b48e9ecf6 |titul=COVID-19 Dashboard by the Center for Systems Science and Engineering (CSSE) at Johns Hopkins University (JHU) |vydavatel=[[Johns Hopkins University]] |datum přístupu=2021-02-09}}</ref></onlyinclude>
<!-- *** Data pochází výhradně ze zdrojů Johns Hopkins University (JHU).
-->
{{{{documentation}}}}
[[Kategorie:Šablony:Pandemie covidu-19]]'''.format(**data)

    # need update?
    if lastdate_updated > data_sources['sources'][0]['updated']:
      data_sources['updated'] = True
      data_sources['sources'][0]['updated'] = lastdate_updated

    if lastdate_updated2 > data_sources['sources'][0]['updated']:
      data_sources['updated'] = True
      data_sources['sources'][0]['updated'] = lastdate_updated2

    # store it into wiki template
    if data_sources['updated']:
        comment = 'Aktualizace dat (by ' + botname + ')'
        page.put(output, summary=comment,
            minor=False, botflag=False, apply_cosmetic_changes=False)
        # store info about Date-Modified of data sources
        saveDataUpdated()
    else:
        print('wikipedia is up2date')
    return 1

if __name__ == '__main__':
    exit(main())
