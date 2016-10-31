import time, json, ConfigParser
from datetime import datetime as dt
from flask import Flask, request, session, redirect, render_template
from fitbit.api import FitbitOauth2Client
import fitbit
import requests

app = Flask(__name__)
app.secret_key = 'super secret key'

def oauth2client():
    return FitbitOauth2Client(config.get('fitbit', 'CLIENT_ID'), config.get('fitbit', 'CLIENT_SECRET'))

def authorize_token_url():
    url, _ = oauth2client().authorize_token_url(redirect_uri = config.get('fitbit', 'CALL_BACK_URL'), scope=['heartrate', 'profile'])
    return url

def fetch_access_token(code):
    response = oauth2client().fetch_access_token(code, config.get('fitbit', 'CALL_BACK_URL'))
    return response

def get_heartrate(access_token, refresh_token):
    fitbit_client = fitbit.Fitbit(config.get('fitbit', 'CLIENT_ID'), config.get('fitbit', 'CLIENT_SECRET'),
                                  access_token = access_token,
                                  refresh_token = refresh_token)

    TODAY = dt.now()
    DATE = TODAY.strftime('%Y-%m-%d')
    response = fitbit_client.intraday_time_series('activities/heart', base_date=DATE, detail_level='1min')
    metrics = map(lambda x:{'time': int(time.mktime(dt.strptime(DATE + ' ' + x['time'], '%Y-%m-%d %H:%M:%S').timetuple())),
                  'value': int(x['value']),
                  'name': 'heartrate'},
                  response['activities-heart-intraday']['dataset'])

    post_mackerel(metrics)

    # return metrics
    return response['activities-heart-intraday']['dataset'][-1]

def post_mackerel(metrics):
    headers = {'Content-Type': 'application/json','X-Api-Key': config.get('mackerel', 'API_KEY')}
    request = requests.post('https://mackerel.io/api/v0/services/' + config.get('mackerel', 'SERVICE_NAME') + '/tsdb',
                            data = json.dumps(metrics),
                            headers = headers)

@app.route('/')
def root():
    url = authorize_token_url()
    return redirect(url)

@app.route('/heartrate')
def heartrate():
    if session.get('access_token') and session.get('refresh_token'):
        response = get_heartrate(session.get('access_token'), session.get('refresh_token'))
        return render_template('heartrate.html', data=json.dumps(response))
    else:
        return redirect('/')

@app.route('/auth/fitbit_oauth2/callback')
def callback():
    code = request.args.get('code', '')
    response = fetch_access_token(code)

    session['refresh_token'] = response['refresh_token']
    session['access_token'] = response['access_token']

    return redirect('/heartrate')

if __name__ == '__main__':
    config = ConfigParser.SafeConfigParser()
    config.read('./config.ini')
    app.run(port = config.get('general', 'FLASK_PORT'))
