from gevent.pool import Pool
from gevent import monkey
import manage_vds as vds
import configparser
import gevent

monkey.patch_all(ssl=False, httplib=True)
CONCURRENCY = 10  # количество параллельных потоков
pool = Pool(CONCURRENCY)


def check_delay_vm():
    """function for checking order of delayed requests for create server"""

    while True:
        cn = vds.internal_db_conn(db_path=internal_db_name)
        c = cn.cursor()
        with open('tst', 'w') as f:
            f.write('123')
        c.execute('select * from delayed_create')
        delayed_create = c.fetchall()
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
    """function for checking order of delayed requests for remove server"""

    while True:

        cn = vds.internal_db_conn(db_path=internal_db_name)
        c = cn.cursor()
        c.execute('select * from need_remove')
        need_remove = c.fetchall()
        jobs = [pool.spawn(vds.remove_server,
                           token=n['api_token'],
                           address=api_scalets_url,
                           server_id=n['ctid']) for n in need_remove]
        pool.join(raise_error=False)
        result = [j.value for j in jobs]

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
internal_db_name = config['MAIN']['db_name']

api_scalets_url = f'{api_url}/scalets'

# проверяем таблицы для очередей отложенного создания/удаления и создаём их при необходимости
vds.db_struct_create(db_path=internal_db_name)

gevent.joinall([
    gevent.spawn(check_delay_vm),
    gevent.spawn(check_remove),
])



