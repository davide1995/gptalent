import json

from instance.config import OPENAI_API_KEY, OPENAI_MAX_USER_REQUESTS_HOUR
from services.helpers import openai_helper

openai_helper.api_key = OPENAI_API_KEY

requester_linkedin_data = {
    'profile': {
        'localizedLastName': 'John',
        'localizedFirstName': 'Watson'
    },
    'email': 'davide95.v@gmail.com'
}

requester_parameters = {
    'searched_position': 'Java Engineer',
    'requester_position': 'Account Specialist'
}

openai_helper.generate_email(
    requester_linkedin_data,
    requester_parameters,
    json.load(open('../mocks/proxycurl/example.json')),
    OPENAI_MAX_USER_REQUESTS_HOUR
)
