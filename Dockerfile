FROM python:2.7-alpine

COPY k2_compose /k2-compose/
COPY setup.py /k2-compose/
WORKDIR /k2-compose
RUN ping -c 3 www.baidu.com
RUN pip install docker-compose==1.14.0 -i http://pypi.douban.com/simple
RUN python setup.py install

ENTRYPOINT ["ping", "localhost"]
