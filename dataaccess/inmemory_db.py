import logging
from dataaccess.db_dao import DbDAO


class InMemoryDB(DbDAO):

    def __init__(self):
        logging.info("Using in-memory DB")
        self._db = {}

    def is_up(self) -> bool:
        return True

    def add_trace(self, requester: dict, from_api: bool, linkedin_data: dict, profile_image: bytes, openai_request: dict, openai_response: str) -> str:
        collection = 'traces'

        data = {
            'requester': requester,
            'from_api': from_api,
            'linkedin_data': linkedin_data,
            'profile_image': profile_image,
            'openai_request': openai_request,
            'openai_response': openai_response
        }

        self._db.setdefault(collection, []).append(data)

        return str(len(self._db[collection]))

    def add_error(self, requester: dict, linkedin_url: str, exception_name: str, exception_message: str):
        collection = 'traces'

        data = {
            'requester': requester,
            'linkedin_url': linkedin_url,
            'exception_name': exception_name,
            'exception_message': exception_message,
        }

        self._db.setdefault(collection, []).append(data)

    def get_linked_in_data_by_username(self, username: str) -> dict or None:
        logging.info(f"Loading '{username}' from DB")

        collection = 'traces'

        documents = list(filter(lambda doc: doc['from_api'] and doc['linkedin_data']['public_identifier'] == username,
                                self._db.get(collection, [])))

        if not any(documents):
            logging.info(f"'{username}' not found in DB")
            return None, None

        document = documents[0]
        return document['profile_image'], document['linkedin_data']

    def get_ai_request_response(self) -> list[dict]:
        collection = 'traces'

        return list(map(lambda doc: {'openai_request.prompt': doc['openai_request']['prompt'], 'openai_response': doc['openai_response']},
                        self._db.get(collection, [])))

    def get_number_of_openai_api_requests_last_hour(self, email: str) -> int:
        collection = 'traces'

        documents = list(filter(lambda doc: doc['requester']['email'] == email,
                                self._db.get(collection, [])))

        return len(documents)

    def get_number_of_nubela_api_requests_last_hour(self, email: str) -> int:
        collection = 'traces'

        documents = list(filter(lambda doc: doc['from_api'] and doc['requester']['email'] == email,
                                self._db.get(collection, [])))

        return len(documents)
