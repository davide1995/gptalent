import json
import requests

from expiringdict import ExpiringDict

from dataaccess.DB import DB
from exceptions.nubela_auth_exception import NubelaAuthException
from exceptions.nubela_max_user_requests_allowed_exception import NubelaMaxUserRequestsAllowedException
from exceptions.nubela_profile_not_enough_information_exception import NubelaProfileNotEnoughInformationException
from exceptions.nubela_profile_not_found_exception import NubelaProfileNotFoundException
from exceptions.openai_max_user_requests_allowed_exception import OpenAiMaxUserRequestsAllowedException
from services.helpers import proxycurl_helper, openai_helper


PROFILE_IMAGES_CACHE = ExpiringDict(max_len=1000, max_age_seconds=36000)


def analyse(requester_linkedin_data: dict, requester_parameters: dict, user_max_allowed_nubela: int, user_max_allowed_openai: int) -> dict:
    linkedin_url = requester_parameters['url']

    linkedin_username = get_username_from_url(linkedin_url)

    from_api = False
    profile_image = None
    if linkedin_username == 'example':
        with open('mocks/proxycurl/example.json', 'r') as file:
            candidate_linkedin_data = json.loads(file.read())
    else:
        profile_image, candidate_linkedin_data = DB.get_instance().get_linked_in_data_by_username(linkedin_username)

    try:
        if not candidate_linkedin_data:
            from_api = True
            candidate_linkedin_data = proxycurl_helper.load_linkedin_data(requester_linkedin_data['email'], linkedin_url, user_max_allowed_nubela)
            profile_image = requests.get(candidate_linkedin_data['profile_pic_url']).content

        proxycurl_helper.check_enough_information_in_profile(candidate_linkedin_data)

        gpt_request, gpt_response = openai_helper.generate_message(requester_linkedin_data, requester_parameters, candidate_linkedin_data, user_max_allowed_openai)

        PROFILE_IMAGES_CACHE[linkedin_username] = profile_image

        DB.get_instance().add_trace(requester_linkedin_data, from_api, candidate_linkedin_data, profile_image, gpt_request, gpt_response)

        return __build_success_response(gpt_response)
    except (NubelaAuthException, NubelaProfileNotFoundException, NubelaProfileNotEnoughInformationException,
            NubelaMaxUserRequestsAllowedException, OpenAiMaxUserRequestsAllowedException) as e:
        DB.get_instance().add_error(requester_linkedin_data, linkedin_url, type(e).__name__, e.message)
        return __build_fail_response(e)


def adjust(requester_email: str, user_message: str, user_max_allowed_openai: int) -> dict:
    try:
        _, gpt_response = openai_helper.update_conversation(requester_email, user_message, user_max_allowed_openai)
        return __build_success_response(gpt_response)
    except OpenAiMaxUserRequestsAllowedException as e:
        return __build_fail_response(e)


def get_profile_image_by_username(username: str) -> bytes:
    return PROFILE_IMAGES_CACHE.get(username)


def get_username_from_url(linkedin_url: str) -> str:
    return linkedin_url[linkedin_url.rfind('/') + 1:]


def adjust_for_linkedin_url(user_input: str) -> str:
    if not user_input.startswith('https://www.linkedin.com/in/'):
        return 'https://www.linkedin.com/in/' + user_input
    elif user_input.endswith('/'):
        return user_input[:-1]
    return user_input


def __build_success_response(gpt_response: str) -> dict:
    return {
        'success': True,
        'user_response': gpt_response,
        'profile_image': None
    }


def __build_fail_response(e) -> dict:
    return {
        'success': False,
        'user_response': e.message
    }
