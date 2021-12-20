###Инструкция по сборке:
`docker build -t %image_name% %path_with_dockerfile%` </br>
, где `%image_name%` - желаемое имя образа, </br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`%path_with_dockerfile%` - путь к папке с файлом Dockerfile
###Инструкция по запуску:
`docker run --name %container_name% -p %ex_port%:5000 -d %image_name%` </br>
, где `%container_name%` - желаемое имя контейнера, </br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`%ex_port%` - порт хост машины, на который будет проброшен порт сервиса (5000)
###Инструкция по использованию:
•	Для создания виртуальных машин необходимо выполнить POST запрос по адресу: 
`http://%server%:%port%/manage?amount=%vm_count%`
</br>, где `%server%` - имя или адрес сервера, на котором запущен контейнер, </br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`%port%` - порт, на который проброшен порт сервиса, </br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`%vm_count%` - количество машин, которые требуется создать
</br>В результате чего будет выполнена попытка создания указанного количества машин. </br>В случае, если в процессе попытки создание хотя бы одной машины завершится провалом, будут удалены все машины, созданные в рамках этой попытки. Причём, если в процессе удаления возникнут ошибки, сервис будет пытаться их удалить до тех пор, пока операция не завершится успешно
</br>Если публичный API при попытке создания вернёт ошибку 429, то запрос на создание добавится в очередь отложенных, и каждую минуту будет выполняться попытка повторного создания
</br>Пример:  
`curl --request POST 'http://127.0.0.1:5003/manage?amount=1' --header 'X-Token: 7bb2b18b2863063c5fbd8f44020c26c46d594c092f3e0d1e456c990423732a4c'`
</br>Успешный ответ: