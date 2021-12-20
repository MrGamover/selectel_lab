import configparser
from collections import OrderedDict
from flask import Flask, request
from datetime import datetime
from gevent.pool import Pool
from gevent import monkey
import manage_vds as vds
import logging

monkey.patch_all(ssl=False, httplib=True)

app = Flask(__name__)


def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""
    _formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file, encoding='utf8')
    handler.setFormatter(_formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


@app.route("/")
def hello():
    return "service_started", 200


@app.route('/manage', methods=['POST'])
def create_servers():
    api_token = request.headers.get('X-Token', None)
    servers_amount = int(request.args.get('amount', 0))
    if servers_amount:
        # Получаем настройки по умолчанию на основании доступных значений из api VDS
        # (либо из кэша, если получали недавно)
        def_settings = cache.get('serv_def_settings', None)
        if def_settings is None:
            api_logger.info('default settings not from cache')
            settings = vds.get_default_settings(token=api_token,
                                                address=api_plans_url)
            if settings:
                cache['serv_def_settings'] = settings
            else:
                cache['serv_def_settings'] = default_settings
            def_settings = cache['serv_def_settings']
        else:
            if (datetime.now() - def_settings.get('timestamp')).seconds < 14400:
                def_settings = cache['serv_def_settings']
            else:
                settings = vds.get_default_settings(token=api_token,
                                                    address=api_plans_url)
                if settings:
                    cache['serv_def_settings'] = settings

                def_settings = cache['serv_def_settings']

        # Добавляем в gevent pool запросы на создание указанного количества серверов (servers_amount)
        jobs = [pool.spawn(vds.create_server,
                           token=api_token,
                           address=api_scalets_url,
                           make_from=def_settings['template'],
                           plan=def_settings['plan'],
                           location=def_settings['location']) for _ in range(servers_amount)]
        pool.join(raise_error=False)
        result = [j.value for j in jobs]

        # в зависимости от результатов выполнения записываем их в соответствующие переменные
        delayed = [r[1] for r in result if r[0] == 'try_later']
        successed = [r[1] for r in result if r[0] == 'success']
        failed = [r[1] for r in result if r[0] in ('failed', 'remote_address_unavailable')]
        if len([r[1] for r in result if r[0] == 'remote_address_unavailable']) == len(result):
            fail_message = fail_message_template | dict(error='VDS_API_unavailable')
            api_logger.error('all request failed: VDS_API_unavailable')
            return fail_message, 503

        # если в результате запросов есть хотя бы один со статусом failed,
        # то удаляем созданные в рамках этой сессии серверы и возвращаем ответ с неудачей :(
        if len(failed) > 0 and len(successed) > 0:
            for vm in successed:
                vm['api_token'] = api_token
                vm = {k: vm[k] for k in ('ctid', 'name', 'status', 'api_token')}
                cn = vds.internal_db_conn(db_path=internal_db_name)
                c = cn.cursor()
                columns = ', '.join(vm.keys())
                placeholders = ':' + ', :'.join(vm.keys())
                query = 'INSERT INTO need_remove (%s) VALUES (%s)' % (columns, placeholders)
                c.execute(query, vm)
                cn.commit()
                '''rm_pool.spawn(vds.remove_server,
                              token=api_token,
                              address=api_scalets_url,
                              server_id=vm['ctid'])'''
            api_logger.error('some request failed, remove created machine')
            return fail_message_template, 403

        # если есть серверы, запрос по которым вернулся в статусе try_later (код 429),
        # то записываем их в БД в таблицу отложенных заданий
        if delayed:
            cn = vds.internal_db_conn(db_path=internal_db_name)
            c = cn.cursor()
            for d in delayed:
                d['api_token'] = api_token
                columns = ', '.join(d.keys())
                placeholders = ':' + ', :'.join(d.keys())
                query = 'INSERT INTO delayed_create (%s) VALUES (%s)' % (columns, placeholders)
                c.execute(query, d)
                cn.commit()

        # результаты запросов на создание
        r_dict = OrderedDict(result=OrderedDict(successed=successed,
                                                delayed=delayed,
                                                failed=failed))

        success_message = success_message_template | r_dict

        return success_message, 200
    else:
        fail_message = fail_message_template | dict(error='empty_param: amount')
        api_logger.error('empty amount parameters')
        return fail_message, 400


@app.route('/manage', methods=['DELETE'])
def delete_servers():
    api_token = request.headers.get('X-Token', None)
    servers_info = vds.get_servers_state_list(token=api_token,
                                              address=api_scalets_url)
    if servers_info[0] == 'remote_address_unavailable':
        api_logger.error('getting servers list for remove failed: VDS_API_unavailable')
        fail_message = fail_message_template | dict(error='VDS_API_unavailable')
        return fail_message, 503

    # если серверы есть в списке, начинаем процесс удаления
    if servers_info[1]:
        servers_id = [a['ctid'] for a in servers_info[1]]
        jobs = [pool.spawn(vds.remove_server, api_token, api_scalets_url, s) for s in servers_id]
        pool.join(raise_error=False)
        result = [j.value for j in jobs]

        delayed = [r[1] for r in result if r[0] == 'try_later']
        successed = [r[1] for r in result if r[0] == 'success']

        result = OrderedDict()
        if delayed:
            result['delayed'] = delayed
        result['successed'] = successed
        success_message = success_message_template | dict(result=result)
        return success_message, 200
    else:
        # если серверов для удаления нет - сообщаем клиенту
        success_message = success_message_template | dict(message='nothing_delete')
        return success_message, 200


@app.route('/manage', methods=['GET'])
def get_servers():
    # получаем список серверов и возвращаем их клиенту, либо возвращаем сообщения об ошибке в случае неудачи
    api_token = request.headers.get('X-Token', None)

    servers_info = vds.get_servers_state_list(token=api_token,
                                              address=api_scalets_url)

    if servers_info[0] == 'success':
        success_message = success_message_template | dict(data=servers_info[1])

        return success_message, 200

    elif servers_info[0] == 'remote_address_unavailable':
        api_logger.error('getting servers list failed: VDS_API_unavailable')
        fail_message = fail_message_template | dict(error='VDS_API_unavailable')
        return fail_message, 503
    elif servers_info[0] == 'failed':
        api_logger.error('getting servers list failed: something went wrong')
        fail_message = fail_message_template | dict(error='something_went_wrong')
        return fail_message, 500


# задаём параметры логирования
api_logger = setup_logger(name='api_full_log',
                          log_file='full.log',
                          level=logging.DEBUG)

CONCURRENCY = 10  # количество параллельных потоков
pool = Pool(CONCURRENCY)
cache = {}  # переменная для хранения "кеша" настроек по умолчанию для новых серверов

config = configparser.ConfigParser()
config.read('conf.conf')
api_url = config['MAIN']['api_address']
service_name = config['MAIN']['service_name']
internal_db_name = config['MAIN']['db_name']

# настройки по умолчанию на случай, если не удастся получить их из публичного API
default_settings = dict(location=config['VDS_SETTINGS']['location'],
                        plan=config['VDS_SETTINGS']['plan'],
                        template=config['VDS_SETTINGS']['template'],
                        timestamp=datetime.now())

api_scalets_url = f'{api_url}/scalets'
api_plans_url = f'{api_url}/locations'

success_message_template = OrderedDict(service_name=service_name,
                                       success=1, )

fail_message_template = OrderedDict(service_name=service_name,
                                    success=0, )

# проверяем таблицы для очередей отложенного создания/удаления и создаём их при необходимости
vds.db_struct_create(db_path=internal_db_name)

if __name__ == '__main__':
    app.config["JSON_SORT_KEYS"] = False  # отключаем принудительную сортировку json
    app.run(debug=True, threaded=True)
