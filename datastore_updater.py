import sys
import ConfigParser
import json
import datetime


import requests

usage = '''

    datastore_update.py setup
        Creates a dataset in the remote CKAN instance, adds a DataStore
        resource to it and pushes a first dump of the earthquakes that happened
        during the last day. It will return the resource id that you must
        write in your configuration file if you want to regularly update the
        DataStore table with the `update` command.

    datastore_update.py update
        Requests the last hour eartquakes from the remote server and pushes the
        records to the DataStore. You need to include the resource_id returned
        by the previous command to your configuration file before running this
        one. You should run this command periodically every each hour, eg with
        cron job.

'''

PAST_DAY_DATA_URL = 'http://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson'
PAST_HOUR_DATA_URL = 'http://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson'


def exit(msg=usage):
    print msg
    sys.exit(1)


def _get_records(earthquake_data):
    records = []
    if len(earthquake_data['features']):
        for feature in earthquake_data['features']:
            record = feature['properties']
            record.update({
                'longitude': feature['geometry']['coordinates'][0],
                'latitude': feature['geometry']['coordinates'][1],
                'added': datetime.datetime.now().isoformat(),
            })
            records.append(record)
    return records


def setup(config):

    ckan_url = config.get('main', 'ckan_url').rstrip('/')
    api_key = config.get('main', 'api_key')

    # Create a dataset first

    data = {
        'name': 'ngds-earthquakes-data11',
        'title': 'NGDS Earthquakes Data',
        'notes': '''
            Earthquake data from http,
            updated regularly
        ''',
    }

    response = requests.post('{0}/api/action/package_create'.format(ckan_url),
                             data=json.dumps(data),
                             headers={'Content-type': 'application/json',
                                      'Authorization': api_key},)

    if response.status_code != 200:
        exit('Error creating dataset: {0}'.format(response.content))

    dataset_id = response.json()['result']['id']

    # Get a first dump of the Earthquake data for the past day

    past_day_earthquake_data = requests.get(PAST_DAY_DATA_URL).json()
    records = _get_records(past_day_earthquake_data)

    # Manually set the field types to ensure they are handled properly

    fields = [
        {'id': 'mag', 'type': 'float'},
        {'id': 'place', 'type': 'text'},
        {'id': 'time', 'type': 'bigint'},
        {'id': 'updated', 'type': 'bigint'},
        {'id': 'tz', 'type': 'integer'},
        {'id': 'url', 'type': 'text'},
        {'id': 'detail', 'type': 'text'},
        {'id': 'felt', 'type': 'integer'},
        {'id': 'cdi', 'type': 'float'},
        {'id': 'mmi', 'type': 'float'},
        {'id': 'alert', 'type': 'text'},
        {'id': 'status', 'type': 'text'},
        {'id': 'tsunami', 'type': 'integer'},
        {'id': 'sig', 'type': 'integer'},
        {'id': 'net', 'type': 'text'},
        {'id': 'code', 'type': 'text'},
        {'id': 'ids', 'type': 'text'},
        {'id': 'sources', 'type': 'text'},
        {'id': 'types', 'type': 'text'},
        {'id': 'nst', 'type': 'integer'},
        {'id': 'dmin', 'type': 'float'},
        {'id': 'rms', 'type': 'float'},
        {'id': 'gap', 'type': 'float'},
        {'id': 'magType', 'type': 'text'},
        {'id': 'type', 'type': 'text'},
    ]

    # Push the records to the DataStore table. This will create a resource
    # of type datastore
    data = {
        'resource': {
            'package_id': dataset_id,
            'name': 'Earthquake data',
            'format': 'csv',
        },
        'records': records,
        'fields': fields,
        'primary_key': ['code'],
    }

    response = requests.post('{0}/api/action/datastore_create'.format(ckan_url),
                             data=json.dumps(data),
                             headers={'Content-type': 'application/json',
                                      'Authorization': api_key},)

    if response.status_code != 200:
        exit('Error: {0}'.format(response.content))

    resource_id = response.json()['result']['resource_id']

    print '''
Dataset and DataStore resource successfully created with {0} records.
Please add the resource id to your ini file:

resource_id={1}
          '''.format(len(records), resource_id)


def update(config):

    ckan_url = config.get('main', 'ckan_url').rstrip('/')
    api_key = config.get('main', 'api_key')

    resource_id = config.get('main', 'resource_id')
    if not resource_id:
        exit('You need to add the resource id to your configuration file.\n' +
             'Did you run `datastore_update.py setup`first?')

    # Get the latest Earthquake data
    past_hour_earthquake_data = requests.get(PAST_HOUR_DATA_URL).json()
    records = _get_records(past_hour_earthquake_data)

    if len(records) == 0:
        # No new records
        return

    # Push the records to the DataStore table
    data = {
        'resource_id': resource_id,
        'method': 'upsert',
        'records': records,
    }

    response = requests.post('{0}/api/action/datastore_upsert'.format(ckan_url),
                             data=json.dumps(data),
                             headers={'Content-type': 'application/json',
                                      'Authorization': api_key},)

    if response.status_code != 200:
        exit('Error: {0}'.format(response.content))

    return


if __name__ == '__main__':

    if len(sys.argv) < 2:
        exit()

    action = sys.argv[1]

    if action not in ('setup', 'update',):
        exit()

    config = ConfigParser.SafeConfigParser()
    config.read('config.ini')
    for key in ('ckan_url', 'api_key',):
        if not config.get('main', key):
            exit('Please fill the {0} option in the config.ini file'
                 .format(key))

    if action == 'setup':
        setup(config)
    elif action == 'update':
        update(config)
