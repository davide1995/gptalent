from flask import Flask, redirect, request, render_template, abort, jsonify, send_file, url_for, make_response
from authlib.integrations.requests_client import OAuth2Session
from io import BytesIO

import logging
import os
import imghdr

from dataaccess.DB import DB
from dataaccess.inmemory_db import InMemoryDB
from dataaccess.mongo_db import MongoDB
from services import auth_service, analyse_service, readiness_service, export_service
from services.helpers import proxycurl_helper, openai_helper

app = Flask(__name__, instance_relative_config=True)

for env in os.environ:
    app.config[env] = os.environ[env]
if os.path.exists('instance/config.py'):
    app.config.from_pyfile('config.py')

logging.getLogger().setLevel(app.config['LOGGING_LEVEL'])

client = OAuth2Session(
    app.config['LINKEDIN_CLIENT_ID'],
    app.config['LINKEDIN_CLIENT_SECRET'],
    token_endpoint_auth_method='client_secret_post'
)

proxycurl_helper.api_key = app.config['NEBULA_API_KEY']
openai_helper.api_key = app.config['OPENAI_API_KEY']

persistence_strategy = app.config['PERSISTENCE_STRATEGY']
if persistence_strategy == 'mongo':
    DB.get_instance().set_db_type(MongoDB(
        app.config['MONGO_CONNECTION'],
        app.config['MONGO_DB'],
        app.config['MONGO_USER'],
        app.config['MONGO_PASSWORD'])
    )
elif persistence_strategy == 'in-memory':
    DB.get_instance().set_db_type(InMemoryDB())
else:
    raise Exception("Invalid persistence name")


@app.route('/')
def index():
    user_info = auth_service.verify_token(__get_token_cookie())
    if user_info:
        return render_template('home.html', data=user_info)
    else:
        return render_template('login.html')


@app.route('/login')
def login():
    uri, state = client.create_authorization_url(
        'https://www.linkedin.com/oauth/v2/authorization',
        redirect_uri=app.config['REDIRECT_URI'],
        scope='r_emailaddress r_liteprofile'
    )
    return redirect(uri)


@app.route('/oidc_callback')
def oidc_callback():
    encoded_token = auth_service.authorize(client, request.url, app.config['REDIRECT_URI'])
    response = redirect('/')
    response.set_cookie('token', encoded_token.decode())
    return response


@app.route('/send', methods=['POST'])
def send():
    requester_linkedin_data = auth_service.verify_token(__get_token_cookie())
    if not requester_linkedin_data:
        abort(401)

    data = request.get_json()
    url_or_username = data['url-or-username']
    if not url_or_username:
        return {
            'success': False,
            'user_response': 'Empty input'
        }

    linkedin_url = analyse_service.adjust_for_linkedin_url(url_or_username)
    requester_parameters = {
        'url': linkedin_url.strip(),
        'searched_position': data['searched-position'].strip(),
        'searched_position_url': data['searched-position-url'].strip(),
        'requester_position': data['requester-position'].strip(),
        'number_of_paragraphs': data['number-of-paragraphs'].strip(),
        'location': data['location'],
        'tone': data['tone'],
        'benefits': data['benefits'].strip()
    }

    response = analyse_service.analyse(
        requester_linkedin_data,
        requester_parameters,
        int(app.config['PROXYCURL_MAX_USER_REQUESTS_HOUR']),
        int(app.config['OPENAI_MAX_USER_REQUESTS_HOUR'])
    )

    if response['success']:
        url_profile_image = url_for(
            'get_profile_image',
            username=analyse_service.get_username_from_url(linkedin_url),
            _external=True
        )
        response['profile_image'] = url_profile_image

    template = render_template('message.html', data=response)

    return jsonify(template)


@app.route('/profile_image/<username>')
def get_profile_image(username):
    image = analyse_service.get_profile_image_by_username(username)
    if image:
        image_data = BytesIO(image)
        mimetype = '' if imghdr.what(image_data) else 'image/svg+xml'
        return send_file(image_data, mimetype=mimetype)
    else:
        return 'User has not been loaded yet. Cannot fetch the profile image', 404


@app.route('/export-all-messages', methods=['GET'])
def export_all_messages():
    user_info = auth_service.verify_token(__get_token_cookie())
    authorized_users = app.config['AUTHORIZED_USERS'].split(':')
    if not user_info or user_info.get('email') not in authorized_users:
        abort(401)

    filename, content = export_service.export_all_messages()

    response = make_response(content)
    response.headers['Content-Disposition'] = 'attachment; filename=' + filename
    response.headers['Content-Type'] = 'text/csv'

    return response


@app.route('/readiness')
def readiness():
    state = readiness_service.check(app.config['OPENAI_THRESHOLD'], app.config['PROXYCURL_THRESHOLD'])
    success = all(['error' not in state[key] for key in state.keys()])
    if not success:
        abort(make_response(jsonify(message=state), 500))
    return state


def __get_token_cookie() -> bytes or None:
    token = request.cookies.get('token')
    return str.encode(token) if token is not None else None


if __name__ == '__main__':
    app.static_url_path = '/static'
    app.run('localhost', port=8080)
