from dataaccess.db_dao import DbDAO


class InMemoryDB(DbDAO):

    def __init__(self):
        self._db = {}

    def is_up(self) -> bool:
        return True

    def add_phish(self, requester: dict, from_api: bool, linkedin_data: dict, profile_image: bytes, openai_request: dict, mail: str):
        collection = 'phishes'

        data = {
            'requester': requester,
            'from_api': from_api,
            'linkedin_data': linkedin_data,
            'profile_image': profile_image,
            'openai_request': openai_request,
            'mail': mail
        }

        self._db.setdefault(collection, []).append(data)

    def add_error(self, requester: dict, linkedin_url: str, exception_name: str, exception_message: str):
        collection = 'errors'

        data = {
            'requester': requester,
            'linkedin_url': linkedin_url,
            'exception_name': exception_name,
            'exception_message': exception_message,
        }

        self._db.setdefault(collection, []).append(data)

    def get_linked_in_data_by_username(self, username: str) -> dict or None:
        print(f"Loading '{username}' from DB")

        collection = 'phishes'

        documents = list(filter(lambda doc: doc['from_api'] and doc['linkedin_data']['public_identifier'] == username,
                                self._db.get(collection, [])))

        if not any(documents):
            print(f"'{username}' not found in DB")
            return None, None

        document = documents[0]
        return document['profile_image'], document['linkedin_data']

    def get_ai_request_response(self) -> list[dict]:
        collection = 'phishes'

        return list(map(lambda doc: {'openai_request.prompt': doc['openai_request']['prompt'], 'mail': doc['mail']},
                        self._db.get(collection, [])))
