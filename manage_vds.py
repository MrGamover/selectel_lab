from datetime import datetime
import requests


def get_servers_state_list(token: str, address: str):
    """Get virtual servers list from Selectel VDS API

            Parameters:
            token (str): token for access to Selectel VDS API
            address (str): Selectel VDS scalets API url

            Returns:
            result (str): result code after attempting get servers list through API
            data (list): list of dicts with some servers info (ctid, name, status), or empty list if failed
           """
    data = []
    try:
        response = requests.get(url=address,
                                headers={'X-Token': token})
    except requests.exceptions.ConnectionError:
        return 'remote_address_unavailable', data
    info_data = response.json()

    if response.status_code in range(200, 300):
        result = 'success'
        for info in info_data:
            data.append({k: info[k] for k in ('ctid', 'name', 'status') if k in info})

    elif response.status_code == 429:
        result = 'try_later'

    else:
        result = 'failed'
    return result, data


def create_server(token: str, address: str, make_from: str, name: str = datetime.now().strftime("%m%d%Y%H%M%S%f"),
                  plan: str = 'small', location: str = 'spb0', password='StRoNg_PaSs', recreate_id: str = None):

    start = datetime.now()
    server_parameters = dict(make_from=make_from,
                             rplan=plan,
                             location=location,
                             password=password,
                             name=name)
    data = []
    try:
        response = requests.post(url=address,
                                 headers={'X-Token': token},
                                 json=server_parameters)
    except requests.exceptions.ConnectionError:
        return 'remote_address_unavailable', data

    end = datetime.now()
    if response.status_code in range(200, 300):
        result = 'success'
        info_data = response.json()
        data = {k: info_data[k] for k in ('ctid', 'name', 'status') if k in info_data}
        # data['start'], data['end'] = start, end
        if recreate_id:
            data['recreate_id'] = recreate_id
    elif response.status_code == 429:
        result = 'try_later'
        data = dict(name=name,
                    make_from=make_from,
                    plan=plan,
                    location=location,
                    password=password)
    elif response.status_code == 403:
        result = 'failed'
        data = dict(name=name,
                    error_code=response.json().get('error', {}).get('code', None))
    else:
        result = 'failed'

    return result, data


def remove_server(token: str, address: str, server_id: int):
    """For deleting virtual server through Selectel VDS API

        Parameters:
        token (str): token for access to Selectel VDS API
        address (str): Selectel VDS API url
        server_id (int): virtual server id (ctid in Selectel VDS API)

        Returns:
        server_id (int): virtual server id (ctid in Selectel VDS API)
        result (str): result code after attempting remove server through API
       """
    if not address:
        return None, 'empty_address'

    address = f'{address}{server_id}' if address[-1] == '/' else f'{address}/{server_id}'
    try:
        response = requests.delete(url=address, headers={'X-Token': token})
    except requests.exceptions.ConnectionError:
        result = 'failed'
        return result, server_id
    if response.status_code in range(200, 300):
        result = 'success'
    elif response.status_code == 429:
        result = 'try_later'
    else:
        result = 'failed'
    return result, server_id


def get_default_settings(token: str, address: str):
    """Generate default settings for new servers from location info

    Parameters:
    token (str): token for access to Selectel VDS API
    address (str): Selectel locations VDS API url

    Returns:
    result (str): result code after attempting get servers list through API
    data (list): list of dicts with some servers info (ctid, name, status), or empty list if failed
   """
    data = {}
    try:
        response = requests.get(url=address, headers={'X-Token': token})
    except requests.exceptions.ConnectionError:
        return data

    if response.status_code in range(200, 300):
        info_data = response.json()
        def_loc = info_data[0].get('id', None)
        def_plan = info_data[0].get('rplans', [None, ])[0]
        def_templates = info_data[0].get('templates', [None, ])[0]
        data = dict(location=def_loc,
                    plan=def_plan,
                    template=def_templates,
                    timestamp=datetime.now())

    return data
