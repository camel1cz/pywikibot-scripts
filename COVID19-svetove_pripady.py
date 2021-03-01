# -*- coding: utf-8 -*-
import pywikibot
from camel1czutils import *

# configuration
start_date = datetime.datetime(2020, 3, 1)
botname = 'COVID19dataczbot'
data_prefix = '<!--BEGIN COVID19dataczbot area-->'
data_suffix = '<!--END COVID19dataczbot area-->'
target_article = 'Šablona:Data_pandemie_covidu-19'
#target_article = 'Wikipedista:Camel1cz_bot/Pískoviště'

source_name = 'sse_covid_19_daily_report'
data_sources['filename'] = botname + '_C19svetove_pripady.lastupdated'
data_sources['sources'].append({
  'url': source_name,
  'updated': datetime.datetime(1970, 1, 1)
});

# sort data function
def get_nakazeni(elem):
    return elem['nakazeni']

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
    output=''
    data=[]

    for row in pData:
        # get date
        row_date = None
        # ignore ships
        if row[3] == 'MS Zaandam' or row[3] == 'Diamond Princess':
          continue
        try:
          # 2021-02-09 05:23:30
          # '%Y-%m-%d %H:%M:%S'
          row_date = datetime.datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S')
        except:
          pass;
        # lastdate
        if row_date > lastdate_updated:
          lastdate_updated = row_date
        dFound = False
        for i, source in enumerate(data):
          if source['zeme'] == row[3].rstrip('*'):
            data[i]['nakazeni'] += int(row[7])
            data[i]['umrti'] += int(row[8])
            data[i]['vyleceno'] += int(row[9])
            dFound = True

        if not dFound:
          data.append({'zeme': row[3].rstrip('*'), 'nakazeni': int(row[7]), 'umrti': int(row[8]), 'vyleceno': int(row[9])})

    # sort data
    data.sort(key=get_nakazeni, reverse=True)
    # fix data, there are no recovered reported by US
    # US not reporting recovered and active
    # Ref https://www.esri.com/arcgis-blog/products/product/public-safety/coronavirus-covid-19-data-available-by-county-from-johns-hopkins-university/
    for i, source in enumerate(data):
      if data[i]['vyleceno'] == 0:
        data[i]['vyleceno'] = None

    output = ''
    for row in data:
      output += ('|-\n! style="text-align:left;" | {{Vlajka a název|%s}}\n| ') % (row['zeme'])
      if row['nakazeni'] is None:
        output += '{{N/A}}'
      else:
        output += ('{{Nts|%d}}') % (row['nakazeni'])
      output += ' || '
      if row['umrti'] is None:
        output += '{{N/A}}'
      else:
        output += ('{{Nts|%d}}') % (row['umrti'])
      output += ' || '
      if row['vyleceno'] is None:
        output += '{{N/A}}'
      else:
        output += ('{{Nts|%d}}') % (row['vyleceno'])
      output += "\n"

    # need update?
    if lastdate_updated > data_sources['sources'][0]['updated']:
      data_sources['updated'] = True
      data_sources['sources'][0]['updated'] = lastdate_updated

    # store it into wiki template
    leadingText = template.split(data_prefix)[0] + data_prefix + '\n'
    trailingText = data_suffix + template.split(data_suffix)[1]

    if data_sources['updated']:
        comment = 'Aktualizace dat' + ' (by ' + botname + ')'
#        comment = 'Aktualizace dat + statistika za ' + lastdate_updated.strftime('%-d.%-m.%Y') + ' (by ' + botname + ')'
        page.put(leadingText + output + trailingText, summary=comment,
            minor=False, botflag=False, apply_cosmetic_changes=False)
        # store info about updated timestamp of data sources
        saveDataUpdated()
    else:
        print('wikipedia is up2date')
    return 1

if __name__ == '__main__':
    exit(main())

