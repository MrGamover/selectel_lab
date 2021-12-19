from time import sleep
import unittest
import requests

from main import app


class TestCase(unittest.TestCase):
    def setUp(self):
        self.api_token = '7bb2b18b2863063c5fbd8f44020c26c46d594c092f3e0d1e456c990423732a4c'
        self.s_api_url = 'https://api.vscale.io/v1/scalets'
        self.manage_api_url = 'http://127.0.0.1:5003/manage'
        self.tester = app.test_client(self)

    def tearDown(self):
        pass

    def test_1_get_srv_list(self):
        response = self.tester.get(self.manage_api_url,
                                headers={'X-Token':self.api_token})

        assert isinstance(response.json, dict)
        assert response.status_code == 200
        data = response.json.get('message', None)
        assert isinstance(data, list)

    def test_2_delete_while_empty(self):
        self.tester.delete(self.manage_api_url,
                           headers={'X-Token': self.api_token})
        sleep(2)
        response = self.tester.delete(self.manage_api_url,
                                      headers={'X-Token': self.api_token})
        assert response.status_code == 200
        assert response.json.get('message', None) == 'nothing_delete'

    def test_3_get_srv_while_empty(self):
        response = self.tester.get(self.manage_api_url,
                                   headers={'X-Token': self.api_token})
        assert response.status_code == 200
        print(response.json)
        assert response.json.get('message', None) == []

    def test_4_get_srv_ident_result(self):
        response = self.tester.get(self.manage_api_url,
                                   headers={'X-Token': self.api_token})
        response_s = requests.get(self.s_api_url,
                                   headers={'X-Token': self.api_token})

        assert response.status_code == 200
        assert response_s.status_code == 200
        assert response.json.get('message', None) == response_s.json()

if __name__ == '__main__':
    unittest.main()