import configparser
from threading import Thread

import gevent

import manage_vds as vds
from time import sleep
from gevent.pool import Pool
from gevent import monkey, thread
import sqlite3

monkey.patch_all(ssl=False, httplib=True)
CONCURRENCY = 5  # количество параллельных потоков
pool = Pool(CONCURRENCY)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def internal_db_conn():
    conn = sqlite3.connect('api_db')
    conn.row_factory = dict_factory
    return conn


def check_delay_vm():

    while True:
        cn = internal_db_conn()
        c = cn.cursor()
        print(10)
        with open('tst', 'w') as f:
            f.write('123')
        c.execute('select * from delayed_create')
        delayed_create = c.fetchall()
        if delayed_create:
            print('find')
        jobs = [pool.spawn(vds.create_server,
                           name=d['name'],
                           token=d['api_token'],
                           address=api_scalets_url,
                           make_from=d['make_from'],
                           plan=d['plan'],
                           location=d['location'],
                           recreate_id=d['recreate_id']) for d in delayed_create]
        pool.join(raise_error=False)
        result = [j.value for j in jobs]
        for r in result:
            if r[0] == 'success':
                c.execute(f'delete from delayed_create where recreate_id = {r[1]["recreate_id"]}')
                cn.commit()
        cn.close()
        gevent.sleep(60)


def check_remove():
    while True:
        print(1)
        cn = internal_db_conn()
        c = cn.cursor()
        c.execute('select * from need_remove')
        need_remove = c.fetchall()
        jobs = [pool.spawn(vds.remove_server,
                           token=n['api_token'],
                           address=api_scalets_url,
                           server_id=n['ctid']) for n in need_remove]
        pool.join(raise_error=False)
        result = [j.value for j in jobs]
        print(result)

        for r in result:
            if r[0] == 'success':
                c.execute(f'delete from need_remove where ctid = {r[1]}')
                cn.commit()
        cn.close()
        gevent.sleep(1)


config = configparser.ConfigParser()
config.read('conf.conf')
api_url = config['MAIN']['api_address']
service_name = config['MAIN']['service_name']

api_scalets_url = f'{api_url}/scalets'


gevent.joinall([
    gevent.spawn(check_delay_vm),
    gevent.spawn(check_remove),
])



