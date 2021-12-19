FROM python:3
ADD requirements.txt /
RUN pip install -r requirements.txt
RUN mkdir /lab_api
COPY main.py wsgi.py delay_checker.py manage_vds.py starter.sh /lab_api
EXPOSE 5000
WORKDIR /lab_api
CMD ./starter.sh