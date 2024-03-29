import requests
import datetime
import csv
import json
from email.utils import parsedate_to_datetime
from contextlib import closing

# data sources + tracking last updated
data_sources = {
    'sources': [
      {
        'url': 'global',
        'updated': datetime.datetime(1970, 1, 1)
      }
    ],
    'updated': False,
    'updateddate': datetime.datetime(1970, 1, 1),
    'filename': '.lastupdated',
    # use wiki template for number format?
    'expand_templates': False
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

def getUpdated(url):
    for i, source in enumerate(data_sources['sources']):
        if source['url'] == url:
            return data_sources['sources'][i]['updated']
    return datetime.datetime(1970, 1, 1)

def setUpdated(url, dtm):
    for i, source in enumerate(data_sources['sources']):
        if source['url'] == url:
            data_sources['sources'][i]['updated'] = dtm
            return

def getCSVfromURL(url, expected_header, delimiter=','):
    data = []
    res = requests.get(url)
    if res.status_code != 200:
        print('Getting data failed. URL=' + url)
        return data

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
                    if source['updated'] > data_sources['updateddate']:
                        data_sources['updateddate'] = source['updated']
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

def processCVSfromURL(url, expected_header, callback, delimiter=','):
    data = []
    headerChecked = False
    with closing(requests.get(url, stream=True)) as r:
        # loop the lines
        for line in r.iter_lines():
            line = line.decode("utf-8")
            # work with header at first
            if not headerChecked:
                # check status code
                if r.status_code != 200:
                    print('Getting data failed. URL=' + url)
                    return data
                # check updated
                if 'Last-Modified' in r.headers:
                    found = False
                    last_modified_str=r.headers['Last-Modified']
                    last_modified_obj=parsedate_to_datetime(last_modified_str).replace(tzinfo=None)
                    for i, source in enumerate(data_sources['sources']):
                        if source['url'] == url:
                            found = True
                            if source['updated'] < last_modified_obj:
                                data_sources['sources'][i]['updated'] = last_modified_obj
                                data_sources['updated'] = True
                                if source['updated'] > data_sources['updateddate']:
                                    data_sources['updateddate'] = source['updated']
                            break
                    if not found:
                        print('Warning: url Last-Modified is ignored: %s' % (url))
                else:
                    print('No Last-Modified in request: %s' % (url))

                # skip magic word
                if line[0] == '\ufeff':
                    line=line[1:]

                # get csv from line
                row = next(csv.reader([line], delimiter=delimiter, quotechar='"'))

                # validate header
                for i, name in enumerate(expected_header, start=0):
                    if row[i] != name:
                        print(url + ': Unexpected format of CSV (expected "' + name + '" got "' + row[i] + '"')
                        return data
                headerChecked = True
                continue

            # get csv from line
            row = next(csv.reader([line], delimiter=delimiter, quotechar='"'))
            try:
              if len(row) > 0:
                data = callback(row)
            except Exception as e:
              print(e)
              print('On data:')
              print(row)
              raise
    return data

def mk_int(s):
    s = s.strip()
    return int(float(s)) if s else 0

def template_nts(val):
    t_sep = '&nbsp;'
    d_sep = ','
    sign = ''
    signFix = 1
    if val < 0:
      sign = '&minus;'
      signFix = -1
    val = abs(val)
    if data_sources['expand_templates']:
        return sign + format(val, ",d").replace(",", t_sep)
    return ('{{Nts|%d}}') % (signFix * val)

def percentDiff(a, b):
    if a == 0:
        return ''
    if a == b:
        return ' (=)'

    diff=100*(b - a)/a
    sign = '+'
    signFix = 1
    if diff < 0:
      sign = '&minus;'
      signFix = -1
      diff = abs(diff)
    if diff < 1:
        return (' (%s%0.2f%%)' % (sign, diff)).replace('.', ',')
    if diff < 10:
        return (' (%s%0.1f%%)' % (sign, diff)).replace('.', ',')
    return (' (%s%d%%)' % (sign, diff)).replace('.', ',')

def num2text(n):
    if n > 1000000000:
        return ('%0.2f&nbsp;miliard' % (n / 1000000000)).replace('.', ',')
    if n > 1000000:
        return ('%0.2f&nbsp;milionů' % (n / 1000000)).replace('.', ',')
    if n > 1000:
        return ('%0.2f&nbsp;tisíc' % (n / 1000)).replace('.', ',')
    return n
