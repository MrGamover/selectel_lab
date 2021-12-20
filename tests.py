from time import sleep
import unittest
import requests

from main import app


class TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        api_token = '7bb2b18b2863063c5fbd8f44020c26c46d594c092f3e0d1e456c990423732a4c'
        manage_api_url = '/manage'
        tester = app.test_client()
        tester.post(f'{manage_api_url}?amount=1',
                    headers={'X-Token': api_token})
        sleep(5)

    def setUp(self):
        self.api_token = '7bb2b18b2863063c5fbd8f44020c26c46d594c092f3e0d1e456c990423732a4c'
        self.s_api_url = 'https://api.vscale.io/v1/scalets'
        self.manage_api_url = '/manage'
        self.tester = app.test_client()

    def tearDown(self):
        sleep(2)

    def test_1_get_srv_ident_result(self):
        """Проверяем идентичность списка всех серверов из публичного API со списком из API нашего сервиса"""
        response = self.tester.get(self.manage_api_url,
                                   headers={'X-Token': self.api_token})
        response_s = requests.get(self.s_api_url,
                                   headers={'X-Token': self.api_token})

        assert response.status_code == 200
        assert response_s.status_code == 200
        assert response.json.get('data', None) == response_s.json()

    def test_2_delete_while_empty(self):

        self.tester.delete(self.manage_api_url,
                           headers={'X-Token': self.api_token})
        sleep(10)
        response = self.tester.delete(self.manage_api_url,
                                      headers={'X-Token': self.api_token})
        print(response.json)
        assert response.status_code == 200
        assert response.json.get('message', None) == 'nothing_delete'

    def test_3_get_srv_after_deleting(self):
        response = self.tester.get(self.manage_api_url,
                                   headers={'X-Token': self.api_token})
        assert response.status_code == 200
        print(response.json)
        assert response.json.get('data', None) == []

    def test_4_created_vm_exist_in_public_api(self):
        response = self.tester.post(f'{self.manage_api_url}?amount=1',
                                   headers={'X-Token': self.api_token})
        serv_info = response.json
        created_id = serv_info.get('result', {}).get('successed',[None])[0].get('ctid', None)

        response_s = requests.get(f'{self.s_api_url}/{created_id}',
                                   headers={'X-Token': self.api_token})
        s_created_id = response_s.json().get('ctid', None)
        assert created_id == s_created_id

    def test_5_deleted_vm_in_deleted_state_in_public_api(self):
        response = self.tester.delete(self.manage_api_url,
                                      headers={'X-Token': self.api_token})
        deleted_info = response.json.get('result', {}).get('successed',[None])
        sleep(5)
        for d_id in deleted_info:
            deleted = requests.get(f'{self.s_api_url}/{d_id}',
                                   headers={'X-Token': self.api_token})
            state = deleted.json().get('status', None)
            assert state == 'deleted'


if __name__ == '__main__':
    unittest.main()