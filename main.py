import configparser
from collections import OrderedDict
from gevent.threadpool import ThreadPool
from flask import Flask, request
from datetime import datetime
from gevent.pool import Pool
from gevent import monkey
import manage_vds as vds
import sqlite3
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
    return "service_started"


@app.route('/manage', methods=['POST'])
def create_servers():
    print(request.args)
    api_token = request.headers.get('X-Token', None)
    servers_amount = int(request.args.get('amount', 0))
    if servers_amount:
        # Получаем настройки по умолчанию на основании доступных значений из api VDS
        # (либо из кэша, если получали недавно)
        def_settings = cache.get('serv_def_settings', None)
        if def_settings is None:
            print('not from cache')
            settings = vds.get_default_settings(token=api_token,
                                                address=api_plans_url)
            if settings:
                cache['serv_def_settings'] = settings
            else:
                cache['serv_def_settings'] = default_settings
            def_settings = cache['serv_def_settings']
        else:
            if (datetime.now() - def_settings.get('timestamp')).seconds < 30:
                def_settings = cache['serv_def_settings']
            else:
                settings = vds.get_default_settings(token=api_token,
                                                    address=api_plans_url)
                if settings:
                    cache['serv_def_settings'] = settings
                else:
                    cache['serv_def_settings'] = default_settings
                def_settings = cache['serv_def_settings']
                print('not from cache(timeout)')

        a = datetime.now()

        # Добавляем в gevent pool запросы на создание указанного количества серверов (servers_amount)
        jobs = [pool.spawn(vds.create_server,
                           token=api_token,
                           address=api_scalets_url,
                           make_from=def_settings['template'],
                           plan=def_settings['plan'],
                           location=def_settings['location']) for _ in range(servers_amount)]
        pool.join(raise_error=False)
        result = [j.value for j in jobs]
        print(result)

        print(datetime.now() - a)

        # в зависимости от результатов выполнения записываем их в соответствующие переменные
        delayed = [r[1] for r in result if r[0] == 'try_later']
        successed = [r[1] for r in result if r[0] == 'success']
        failed = [r[1] for r in result if r[0] in ('failed', 'remote_address_unavailable')]
        if len([r[1] for r in result if r[0] == 'remote_address_unavailable']) == len(result):
            fail_message = fail_message_template | dict(error='VDS_API_unavailable')
            return fail_message, 403

        # если в результате запросов есть хотя бы один со статусом failed,
        # то удаляем созданные в рамках этой сессии серверы и возвращаем ответ с неудачей :(
        if len(failed) > 0 and len(successed) > 0:
            rm_pool = ThreadPool(10)
            print('rm')
            for vm in successed:
                vm['api_token'] = api_token
                cn = internal_db_conn()
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

            return fail_message_template, 403

        # если есть серверы, запрос по которым вернулся в статусе try_later (код 429),
        # то записываем их в БД в таблицу отложенных заданий
        if delayed:
            cn = internal_db_conn()
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

        return success_message
    else:
        fail_message = fail_message_template | dict(error='empty_param: amount')
        return fail_message


@app.route('/manage', methods=['DELETE'])
def delete_servers():
    api_token = request.headers.get('X-Token', None)
    servers_info = vds.get_servers_state_list(token=api_token,
                                              address=api_scalets_url)

    if servers_info[1]:
        print(servers_info[1])
        servers_id = [a['ctid'] for a in servers_info[1]]
        print(servers_id)

        a = datetime.now()

        jobs = [pool.spawn(vds.remove_server, api_token, api_scalets_url, s) for s in servers_id]
        pool.join(raise_error=False)
        result = [j.value for j in jobs]

        delayed = [r[1] for r in result if r[0] == 'try_later']
        successed = [r[1] for r in result if r[0] == 'success']

        print(datetime.now() - a)

        result = OrderedDict()
        if delayed:
            result['delayed'] = delayed
        result['successed'] = successed
        success_message = success_message_template | dict(result=result)
        return success_message
    else:
        success_message = success_message_template | dict(message='nothing_delete')
        return success_message


@app.route('/manage', methods=['GET'])
def get_servers():
    api_token = request.headers.get('X-Token', None)

    if request.args:
        if request.args.get('name', None):
            pass
    else:
        servers_info = vds.get_servers_state_list(token=api_token,
                                                  address=api_scalets_url)
        if servers_info[0] == 'success':
            # success_message = copy.deepcopy(success_message_template)
            # success_message['data'] = servers_info[1]
            success_message = success_message_template | dict(data=servers_info[1])

            return success_message, 200
        elif servers_info[0] == 'remote_address_unavailable':
            fail_message = fail_message_template | dict(error='vds_address_unavailable')
            return fail_message, 500
        elif servers_info[0] == 'failed':
            fail_message = fail_message_template | dict(error='something_went_wrong')
            return fail_message, 500


def internal_db_conn():
    conn = sqlite3.connect('api_db')
    conn.row_factory = dict_factory
    return conn


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


api_logger = setup_logger(name='api_full',
                          log_file='full.log',
                          level=logging.DEBUG)

CONCURRENCY = 10  # количество параллельных потоков
pool = Pool(CONCURRENCY)
cache = {}

config = configparser.ConfigParser()
config.read('conf.conf')
api_url = config['MAIN']['api_address']
service_name = config['MAIN']['service_name']

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

cn = internal_db_conn()
cur = cn.cursor()
sql_delay_table = """ CREATE TABLE IF NOT EXISTS delayed_create (
                                recreate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name text,
                                make_from text NOT NULL,
                                plan text,
                                location text,
                                password text,
                                api_token text)"""
cur.execute(sql_delay_table)
sql_failed_remove_table = """CREATE TABLE IF NOT EXISTS need_remove (
                                ctid INTEGER PRIMARY KEY,
                                name text,
                                status text,
                                api_token text)"""
cur.execute(sql_failed_remove_table)
cn.commit()

if __name__ == '__main__':
    app.config["JSON_SORT_KEYS"] = False
    app.run(debug=True, threaded=True)
