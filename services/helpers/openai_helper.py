import json
import datetime
import openai
import requests
from openai.error import RateLimitError
from tenacity import *
from jinja2 import Template

from dataaccess.DB import DB
from exceptions.openai_max_user_requests_allowed_exception import OpenAiMaxUserRequestsAllowedException

api_key: str


@retry(retry=retry_if_exception_type(RateLimitError),
       wait=wait_exponential(multiplier=1, min=1, max=30),
       stop=stop_after_attempt(10))
def __try_to_generate_gpt_text(openai_request):

    return openai.ChatCompletion.create(**openai_request)


def generate_message(requester_linkedin_data: dict, requester_parameters: dict, candidate_linkedin_data: dict, user_max_allowed: int) -> tuple[dict, str]:
    _stop_if_user_access_not_allowed(user_max_allowed, requester_linkedin_data['email'])

    openai.api_key = api_key

    with open('templates/prompt.txt', 'r') as file:
        template_str = file.read()

    template = Template(template_str)

    data = {
        'sender': f"{requester_linkedin_data['profile']['localizedFirstName']} {requester_linkedin_data['profile']['localizedLastName']}",
        'requester_position': requester_parameters['requester_position'],
        'searched_position': requester_parameters['searched_position'],
        'number_of_paragraphs': requester_parameters['number_of_paragraphs'],
        'location': requester_parameters['location'],
        'tone': requester_parameters['tone'],
        'benefits': requester_parameters['benefits'],

        'name': candidate_linkedin_data['full_name'],
        'about': candidate_linkedin_data['summary'] or '',
        'occupation': candidate_linkedin_data['occupation'] or '',
        'headline': candidate_linkedin_data['headline'] or '',
        'experiences': candidate_linkedin_data['experiences'],
        'educations': candidate_linkedin_data['education'],

        'year': datetime.datetime.now().year
    }

    gpt_query = template.render(**data)

    openai_request = dict(
        model='gpt-3.5-turbo',
        messages=[
            {'role': 'system', 'content': 'You are a tech recruiter.'},
            {'role': 'user', 'content': gpt_query}
        ],
        temperature=1,
        max_tokens=1000,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    response = __try_to_generate_gpt_text(openai_request)
    return openai_request, response['choices'][0]['message']['content'].strip()


def get_usage() -> float or bool:
    # other undocumented endpoint: https://api.openai.com/dashboard/billing/usage
    api_endpoint = 'https://api.openai.com/dashboard/billing/credit_grants'
    header_dic = {'Authorization': 'Bearer ' + api_key}
    response = requests.get(api_endpoint, headers=header_dic)
    if response.status_code == 200:
        return json.loads(response.content)['total_used']
    return False


def _stop_if_user_access_not_allowed(user_max_allowed: int, mail_address: str):
    if user_max_allowed <= DB.get_instance().get_number_of_openai_api_requests_last_hour(mail_address):
        raise OpenAiMaxUserRequestsAllowedException